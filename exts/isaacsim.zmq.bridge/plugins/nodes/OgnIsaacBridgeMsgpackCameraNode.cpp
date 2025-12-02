// SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: MIT

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include <cuda/include/cuda_runtime_api.h>
#include <msgpack.hpp>
#include <zmq.hpp>

#include <carb/logging/Log.h>

#include <OgnIsaacBridgeMsgpackCameraNodeDatabase.h>

using omni::graph::core::BaseDataType;
using omni::graph::core::Type;

namespace isaacsim {
namespace zmq {
namespace bridge {

namespace zmq_lib = ::zmq;

class OgnIsaacBridgeMsgpackCameraNode
{
public:
    OgnIsaacBridgeMsgpackCameraNode()
        : m_zmqContext(std::make_unique<zmq_lib::context_t>(1))
    {
    }

    ~OgnIsaacBridgeMsgpackCameraNode()
    {
        if (m_zmqSocket)
        {
            m_zmqSocket->close();
        }
        if (!m_cudaStreamNotCreated)
        {
            cudaStreamDestroy(m_cudaStream);
        }
    }

    bool initializeSocket(const std::string& address)
    {
        std::lock_guard<std::mutex> lock(m_mutex);

        if (m_address == address && m_zmqSocket)
        {
            return true;
        }

        try
        {
            m_zmqSocket = std::make_unique<zmq_lib::socket_t>(*m_zmqContext, zmq_lib::socket_type::pub);

            int linger = 0;
            m_zmqSocket->setsockopt(ZMQ_LINGER, &linger, sizeof(linger));

            int hwm = 1;
            m_zmqSocket->setsockopt(ZMQ_SNDHWM, &hwm, sizeof(hwm));

            m_zmqSocket->connect(address);
            CARB_LOG_INFO("[MsgpackCameraNode] Connected to %s", address.c_str());
            m_address = address;
            return true;
        }
        catch (const std::exception& e)
        {
            CARB_LOG_ERROR("[MsgpackCameraNode] Failed to connect to %s: %s", address.c_str(), e.what());
            m_zmqSocket.reset();
            m_address.clear();
            return false;
        }
    }

    static bool compute(OgnIsaacBridgeMsgpackCameraNodeDatabase& db)
    {
        auto& state = db.internalState<OgnIsaacBridgeMsgpackCameraNode>();

        const uint32_t width = db.inputs.width();
        const uint32_t height = db.inputs.height();
        const uint32_t channels = std::max<uint32_t>(1, db.inputs.channels());
        const size_t bufferSize = db.inputs.bufferSizeColor();
        const uint64_t rawPtr = db.inputs.dataPtrColor();

        if (width == 0 || height == 0 || bufferSize == 0 || rawPtr == 0)
        {
            return true;
        }

        const auto ipConst = db.inputs.ip();
        const std::string address = "tcp://" + std::string(ipConst.data(), ipConst.size()) + ":" + std::to_string(db.inputs.port());
        if (!state.initializeSocket(address))
        {
            return true;
        }

        // Allocate host buffer and copy from device if needed
        std::vector<uint8_t> hostBuffer(bufferSize);
        const void* srcPtr = reinterpret_cast<const void*>(rawPtr);
        void* dstPtr = hostBuffer.data();

        if (state.m_cudaStreamNotCreated)
        {
            if (cudaSuccess != cudaStreamCreate(&state.m_cudaStream))
            {
                CARB_LOG_ERROR("[MsgpackCameraNode] Failed to create CUDA stream");
                return true;
            }
            state.m_cudaStreamNotCreated = false;
        }

        cudaError_t err = cudaMemcpyAsync(dstPtr, srcPtr, bufferSize, cudaMemcpyDeviceToHost, state.m_cudaStream);
        if (err == cudaErrorInvalidValue || err == cudaErrorInvalidDevicePointer)
        {
            cudaGetLastError();
            std::memcpy(dstPtr, srcPtr, bufferSize);
        }
        else if (err != cudaSuccess)
        {
            CARB_LOG_ERROR("[MsgpackCameraNode] cudaMemcpyAsync failed: %s", cudaGetErrorString(err));
            return true;
        }
        else
        {
            err = cudaStreamSynchronize(state.m_cudaStream);
            if (err != cudaSuccess)
            {
                CARB_LOG_ERROR("[MsgpackCameraNode] cudaStreamSynchronize failed: %s", cudaGetErrorString(err));
                return true;
            }
        }

        const size_t expected = static_cast<size_t>(width) * height * channels;
        if (bufferSize < expected)
        {
            CARB_LOG_WARN("[MsgpackCameraNode] Provided buffer smaller than expected (%zu < %zu)", bufferSize, expected);
        }

        // Convert to BGR (3-channel)
        std::vector<uint8_t> bgr(static_cast<size_t>(width) * height * 3, 0);

        if (channels == 4)
        {
            const uint8_t* src = hostBuffer.data();
            for (size_t i = 0; i < static_cast<size_t>(width) * height; ++i)
            {
                const uint8_t r = src[i * 4 + 0];
                const uint8_t g = src[i * 4 + 1];
                const uint8_t b = src[i * 4 + 2];
                bgr[i * 3 + 0] = b;
                bgr[i * 3 + 1] = g;
                bgr[i * 3 + 2] = r;
            }
        }
        else if (channels == 3)
        {
            std::memcpy(bgr.data(), hostBuffer.data(), std::min(bgr.size(), hostBuffer.size()));
        }
        else if (channels == 1)
        {
            const uint8_t* src = hostBuffer.data();
            for (size_t i = 0; i < static_cast<size_t>(width) * height; ++i)
            {
                const uint8_t v = src[i];
                bgr[i * 3 + 0] = v;
                bgr[i * 3 + 1] = v;
                bgr[i * 3 + 2] = v;
            }
        }
        else
        {
            CARB_LOG_WARN("[MsgpackCameraNode] Unsupported channel count %u", channels);
            return true;
        }

        // Convert to grayscale and back to BGR (to match Gazebo example)
        std::vector<uint8_t> gray(static_cast<size_t>(width) * height);
        for (size_t i = 0; i < static_cast<size_t>(width) * height; ++i)
        {
            const uint8_t b = bgr[i * 3 + 0];
            const uint8_t g = bgr[i * 3 + 1];
            const uint8_t r = bgr[i * 3 + 2];
            gray[i] = static_cast<uint8_t>(0.299f * r + 0.587f * g + 0.114f * b);
        }

        std::vector<uint8_t> finalBgr(static_cast<size_t>(width) * height * 3);
        for (size_t i = 0; i < static_cast<size_t>(width) * height; ++i)
        {
            const uint8_t v = gray[i];
            finalBgr[i * 3 + 0] = v;
            finalBgr[i * 3 + 1] = v;
            finalBgr[i * 3 + 2] = v;
        }

        msgpack::sbuffer sbuf;
        msgpack::pack(sbuf, finalBgr);

        const auto topicConst = db.inputs.topic();
        const std::string topic(topicConst.data(), topicConst.size());
        zmq_lib::message_t topicMsg(topic.size());
        std::memcpy(topicMsg.data(), topic.data(), topic.size());

        zmq_lib::message_t dataMsg(sbuf.size());
        std::memcpy(dataMsg.data(), sbuf.data(), sbuf.size());

        try
        {
            state.m_zmqSocket->send(topicMsg, zmq_lib::send_flags::sndmore);
            auto result = state.m_zmqSocket->send(dataMsg, zmq_lib::send_flags::dontwait);
            if (!result.has_value())
            {
                CARB_LOG_WARN("[MsgpackCameraNode] Failed to send frame (no receiver)");
            }
        }
        catch (const std::exception& e)
        {
            CARB_LOG_ERROR("[MsgpackCameraNode] ZMQ send failed: %s", e.what());
        }

        return true;
    }

private:
    std::unique_ptr<zmq_lib::context_t> m_zmqContext;
    std::unique_ptr<zmq_lib::socket_t> m_zmqSocket;
    std::string m_address;
    std::mutex m_mutex;
    cudaStream_t m_cudaStream{};
    bool m_cudaStreamNotCreated{ true };
};

REGISTER_OGN_NODE()

} // namespace bridge
} // namespace zmq
} // namespace isaacsim
