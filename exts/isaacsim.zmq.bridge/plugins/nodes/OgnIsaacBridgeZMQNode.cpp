// SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: MIT

#include <cstring>
#include <iostream>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include <cuda/include/cuda_runtime_api.h>
#include <zmq.hpp>

// Check for msgpack availability at compile time
#if defined(__has_include)
#  if __has_include(<msgpack.hpp>)
#    include <msgpack.hpp>
#    define ISAACSIM_HAVE_MSGPACK 1
#  else
#    define ISAACSIM_HAVE_MSGPACK 0
#  endif
#else
#  define ISAACSIM_HAVE_MSGPACK 0
#endif

#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/vec3d.h>

#include <carb/logging/Log.h>

#include <OgnIsaacBridgeZMQNodeDatabase.h>
#include "client_stream_message.pb.h"


using omni::graph::core::Type;
using omni::graph::core::BaseDataType;

#define CUDA_CHECK(call)                                                   \
do {                                                                       \
    cudaError_t err = call;                                                \
    if (err != cudaSuccess) {                                              \
        fprintf(stderr, "CUDA error at %s %d: %s\n", __FILE__, __LINE__,   \
                cudaGetErrorString(err));                                  \
        /* Instead of exiting, log the error and continue */               \
        return true;                                                       \
    }                                                                      \
} while (0)

namespace zmq_lib = zmq; // assign namespace to zmq library to avoid conflicts with our library

namespace isaacsim {
namespace zmq {
namespace bridge {

struct InputDataBBox2d {
    uint32_t semanticId;
    int xMin;
    int yMin;
    int xMax;
    int yMax;
    float occlusionRatio;
};

class OgnIsaacBridgeZMQNode {
    std::unique_ptr<zmq_lib::context_t> m_zmqContext;
    std::unique_ptr<zmq_lib::socket_t> m_zmqSocket;
    uint32_t m_port;
    std::string m_ip;
    std::mutex m_mutex;
    cudaStream_t m_cudaStream;
    bool m_cudaStreamNotCreated{ true };
    uint32_t m_zmqFailCount{ 0 };
    bool m_useSimpleStream{ false };  // PUB/SUB with topic for simple viewers
    std::string m_topic{ "camera/image" };

public:
    OgnIsaacBridgeZMQNode()
        : m_zmqContext(std::make_unique<zmq_lib::context_t>(1)) {
        CARB_LOG_INFO("OgnIsaacBridgeZMQNode::constructor\n");
    }
    ~OgnIsaacBridgeZMQNode() {
        CARB_LOG_INFO("OgnIsaacBridgeZMQNode::destructor\n");
        if (m_zmqSocket) {
            m_zmqSocket->close();
        }
        if (m_zmqContext) {
            m_zmqContext->close();
        }

        // Clean up CUDA stream if it was created
        if (!m_cudaStreamNotCreated) {
            cudaError_t err = cudaStreamDestroy(m_cudaStream);
            if (err != cudaSuccess) {
                // Just log the error instead of using CUDA_CHECK
                CARB_LOG_ERROR("Error destroying CUDA stream in destructor: %s", cudaGetErrorString(err));
            }
        }
    }

    static bool compute(OgnIsaacBridgeZMQNodeDatabase& db);

    bool initializeSocket(uint32_t port, const std::string& ip, bool simpleStream) {
        std::lock_guard<std::mutex> lock(m_mutex);

        m_port = port;
        m_ip = ip;
        m_zmqFailCount = 0;
        m_useSimpleStream = simpleStream;

        // Get topic from env var
        const char* topic_env = std::getenv("ISAAC_ZMQ_TOPIC");
        if (topic_env) {
            m_topic = std::string(topic_env);
        }

        try {
            if (m_useSimpleStream) {
                // PUB socket for simple streaming (binds, clients subscribe)
                m_zmqSocket = std::make_unique<zmq_lib::socket_t>(*m_zmqContext, zmq_lib::socket_type::pub);
                
                int linger = 0;
                m_zmqSocket->setsockopt(ZMQ_LINGER, &linger, sizeof(linger));
                
                int hwm = 1;
                m_zmqSocket->setsockopt(ZMQ_SNDHWM, &hwm, sizeof(hwm));
                
                std::string address = "tcp://*:" + std::to_string(m_port);
                m_zmqSocket->bind(address);
                CARB_LOG_INFO("Simple stream: PUB socket bound to %s, topic: %s\n", address.c_str(), m_topic.c_str());
            } else {
                // PUSH socket for full streaming (connects to server)
                m_zmqSocket = std::make_unique<zmq_lib::socket_t>(*m_zmqContext, zmq_lib::socket_type::push);

                int linger = 0;
                m_zmqSocket->setsockopt(ZMQ_LINGER, &linger, sizeof(linger));

                int hwm = 1;
                m_zmqSocket->setsockopt(ZMQ_SNDHWM, &hwm, sizeof(hwm));

                std::string address = "tcp://" + m_ip + ":" + std::to_string(m_port);
                m_zmqSocket->connect(address);
                CARB_LOG_INFO("Full stream: PUSH socket connected to %s\n", address.c_str());
            }
            return true;
        } catch (const std::exception& e) {
            CARB_LOG_WARN("Failed to create socket: %s", e.what());
            m_zmqSocket.reset();
            return false;
        }
    }
};


bool OgnIsaacBridgeZMQNode::compute(OgnIsaacBridgeZMQNodeDatabase& db) {
    // Static variable to track the last time an error was logged
    // This persists between function calls to limit error message frequency
    static double lastErrorLogTime = 0.0;

    // Get the internal state for this node
    auto& state = db.internalState<OgnIsaacBridgeZMQNode>();

    // Get the port and IP address from the inputs
    uint32_t port = db.inputs.port();
    const omni::graph::core::ogn::const_string& ip = db.inputs.ip();
    std::string std_ip(ip.data(), ip.size());

    // Check for simple stream mode (PUB/SUB with topic for simple viewers)
    const char* simple_env = std::getenv("ISAAC_ZMQ_SIMPLE_STREAM");
    bool simpleStream = simple_env && (std::string(simple_env) == "1" || std::string(simple_env) == "true");

    // If the socket is not initialized, or the port or IP address has changed, initialize the socket
    if (!state.m_zmqSocket || port != state.m_port || std_ip != state.m_ip) {
        if (!state.initializeSocket(port, std_ip, simpleStream)) {
            return true;
        }
    }

    // Create Protobuf message
    ClientStreamMessage message;

    // Bounding boxes 2d
    const InputDataBBox2d* bbox_data = reinterpret_cast<const InputDataBBox2d*>(db.inputs.dataBBox2d().data());
    size_t num_boxes = db.inputs.dataBBox2d().size() / sizeof(InputDataBBox2d);
    auto& bbox_ids = db.inputs.idsBBox2d();
    auto& bbox_bbox_ids = db.inputs.bboxIdsBBox2d();
    auto& bbox_labels = db.inputs.labelsBBox2d();

    // Populate bbox2d data
    for (size_t i = 0; i < num_boxes; ++i) {
        const InputDataBBox2d& bbox = bbox_data[i];
        BBox2DType* bbox_proto = message.mutable_bbox2d()->add_data();
        bbox_proto->set_semanticid(bbox.semanticId);
        bbox_proto->set_xmin(bbox.xMin);
        bbox_proto->set_ymin(bbox.yMin);
        bbox_proto->set_xmax(bbox.xMax);
        bbox_proto->set_ymax(bbox.yMax);
        bbox_proto->set_occlusionratio(bbox.occlusionRatio);
    }

    // Populate bboxIds
    for (size_t i = 0; i < bbox_bbox_ids.size(); ++i) {
        message.mutable_bbox2d()->mutable_info()->add_bboxids(bbox_bbox_ids[i]);
    }

    // Populate idToLabels
    for (size_t i = 0; i < bbox_ids.size(); ++i) {
        int id = bbox_ids[i];
        std::string label = db.tokenToString(bbox_labels[i]);
        (*message.mutable_bbox2d()->mutable_info()->mutable_idtolabels())[std::to_string(id)] = label;
    }

    // Simulation & System time
    double sim_dt = db.inputs.deltaSimulationTime();
    double sys_dt = db.inputs.deltaSystemTime();
    double sim_time = db.inputs.simulationTime();
    double sys_time = db.inputs.systemTime();

    message.mutable_clock()->set_sim_dt(sim_dt);
    message.mutable_clock()->set_sys_dt(sys_dt);
    message.mutable_clock()->set_sim_time(sim_time);
    message.mutable_clock()->set_sys_time(sys_time);

    // Camera data
    const pxr::GfMatrix4d& view_matrix = db.inputs.cameraViewTransform();
    const pxr::GfVec3d& scale = db.inputs.cameraWorldScale();
    const pxr::GfMatrix3d& intrinsics_matrix = db.inputs.cameraIntrinsics();

    // Flatten and populate view_matrix_ros
    for (int row = 0; row < 4; ++row) {
        for (int col = 0; col < 4; ++col) {
            message.mutable_camera()->add_view_matrix_ros(view_matrix[row][col]);
        }
    }

    // Populate camera_scale
    message.mutable_camera()->add_camera_scale(scale[0]);
    message.mutable_camera()->add_camera_scale(scale[1]);
    message.mutable_camera()->add_camera_scale(scale[2]);

    // Flatten and populate intrinsics_matrix
    for (int row = 0; row < 3; ++row) {
        for (int col = 0; col < 3; ++col) {
            message.mutable_camera()->add_intrinsics_matrix(intrinsics_matrix[row][col]);
        }
    }

    // RGB & DEPTH

    // Copy from Device to Host
    size_t data_size_color = db.inputs.bufferSizeColor();
    uint64_t raw_ptr_color = db.inputs.dataPtrColor();
    auto data_ptr_color = std::make_unique<int8_t[]>(data_size_color);

    size_t data_size_depth = db.inputs.bufferSizeDepth();
    uint64_t raw_ptr_depth = db.inputs.dataPtrDepth();
    auto data_ptr_depth = std::make_unique<float[]>(data_size_depth / sizeof(float));

    // Create CUDA stream if not already created
    if (state.m_cudaStreamNotCreated) {
        CUDA_CHECK(cudaStreamCreate(&state.m_cudaStream));
        state.m_cudaStreamNotCreated = false;
    }

    // If the stream is not created, warn and return true
    if (state.m_cudaStreamNotCreated) {
        CARB_LOG_WARN("CUDA stream not created, will not stream images");
        return true;
    }

    // Use the stream for memory operations
    CUDA_CHECK(cudaMemcpyAsync(data_ptr_color.get(), reinterpret_cast<void*>(raw_ptr_color),
                            data_size_color, cudaMemcpyDeviceToHost, state.m_cudaStream));

    CUDA_CHECK(cudaMemcpyAsync(data_ptr_depth.get(), reinterpret_cast<void*>(raw_ptr_depth),
                        data_size_depth, cudaMemcpyDeviceToHost, state.m_cudaStream));

    CUDA_CHECK(cudaStreamSynchronize(state.m_cudaStream));

    // Add image data to Protobuf message (used for both paths initially)
    message.set_color_image(data_ptr_color.get(), data_size_color);
    message.set_depth_image(reinterpret_cast<const char*>(data_ptr_depth.get()), data_size_depth);

    // Detect runtime preference for serialization format
    const char* ser_env = std::getenv("ISAAC_ZMQ_SERIALIZATION");
    bool want_msgpack = false;
    if (ser_env) {
        std::string s(ser_env);
        for (auto& c : s) c = static_cast<char>(::tolower(c));
        want_msgpack = (s == "msgpack");
    }

    // Serialize message
    std::string serialized_message;

#if ISAACSIM_HAVE_MSGPACK
    if (want_msgpack) {
        static bool logged_once = false;
        if (!logged_once) {
            CARB_LOG_INFO("OgnIsaacBridgeZMQNode: Using MSGPACK serialization");
            CARB_LOG_INFO("  color buffer size: %zu, depth buffer size: %zu", data_size_color, data_size_depth);
            logged_once = true;
        }
        try {
            msgpack::sbuffer sbuf;
            msgpack::packer<msgpack::sbuffer> pk(&sbuf);

            // Pack a map with 5 keys: bbox2d, camera, clock, color_image, depth_image
            pk.pack_map(5);

            // bbox2d
            pk.pack(std::string("bbox2d"));
            pk.pack_map(2);
            // bbox2d.info
            pk.pack(std::string("info"));
            pk.pack_map(2);
            pk.pack(std::string("bboxIds"));
            {
                const auto& ids = message.bbox2d().info().bboxids();
                pk.pack_array(ids.size());
                for (int i = 0; i < ids.size(); ++i) pk.pack(ids.Get(i));
            }
            pk.pack(std::string("idToLabels"));
            {
                pk.pack_map(message.bbox2d().info().idtolabels_size());
                for (const auto& kv : message.bbox2d().info().idtolabels()) {
                    pk.pack(kv.first);
                    pk.pack(kv.second);
                }
            }
            // bbox2d.data
            pk.pack(std::string("data"));
            {
                const auto& arr = message.bbox2d().data();
                pk.pack_array(arr.size());
                for (int i = 0; i < arr.size(); ++i) {
                    const auto& b = arr.Get(i);
                    pk.pack_map(6);
                    pk.pack(std::string("semanticId")); pk.pack(b.semanticid());
                    pk.pack(std::string("xMin")); pk.pack(b.xmin());
                    pk.pack(std::string("yMin")); pk.pack(b.ymin());
                    pk.pack(std::string("xMax")); pk.pack(b.xmax());
                    pk.pack(std::string("yMax")); pk.pack(b.ymax());
                    pk.pack(std::string("occlusionRatio")); pk.pack(b.occlusionratio());
                }
            }

            // camera
            pk.pack(std::string("camera"));
            pk.pack_map(3);
            pk.pack(std::string("view_matrix_ros"));
            {
                const auto& v = message.camera().view_matrix_ros();
                pk.pack_array(v.size());
                for (int i = 0; i < v.size(); ++i) pk.pack(v.Get(i));
            }
            pk.pack(std::string("intrinsics_matrix"));
            {
                const auto& v = message.camera().intrinsics_matrix();
                pk.pack_array(v.size());
                for (int i = 0; i < v.size(); ++i) pk.pack(v.Get(i));
            }
            pk.pack(std::string("camera_scale"));
            {
                const auto& v = message.camera().camera_scale();
                pk.pack_array(v.size());
                for (int i = 0; i < v.size(); ++i) pk.pack(v.Get(i));
            }

            // clock
            pk.pack(std::string("clock"));
            pk.pack_map(4);
            pk.pack(std::string("sim_dt")); pk.pack(message.clock().sim_dt());
            pk.pack(std::string("sys_dt")); pk.pack(message.clock().sys_dt());
            pk.pack(std::string("sim_time")); pk.pack(message.clock().sim_time());
            pk.pack(std::string("sys_time")); pk.pack(message.clock().sys_time());

            // color_image
            pk.pack(std::string("color_image"));
            pk.pack_bin(static_cast<uint32_t>(data_size_color));
            pk.pack_bin_body(reinterpret_cast<const char*>(data_ptr_color.get()), static_cast<uint32_t>(data_size_color));

            // depth_image
            pk.pack(std::string("depth_image"));
            pk.pack_bin(static_cast<uint32_t>(data_size_depth));
            pk.pack_bin_body(reinterpret_cast<const char*>(data_ptr_depth.get()), static_cast<uint32_t>(data_size_depth));

            serialized_message.assign(sbuf.data(), sbuf.size());
        } catch (const std::exception& e) {
            CARB_LOG_WARN("MsgPack serialization failed, falling back to Protobuf: %s", e.what());
            message.SerializeToString(&serialized_message);
        }
    } else
#endif
    {
        if (want_msgpack) {
            CARB_LOG_WARN("ISAAC_ZMQ_SERIALIZATION=msgpack set, but msgpack.hpp not found at build time. Using Protobuf.");
        }
        message.SerializeToString(&serialized_message);
    }

    // ZMQ Data sending
    bool message_sent_ok = false;

    if (state.m_useSimpleStream) {
#if ISAACSIM_HAVE_MSGPACK
        // Simple stream mode: PUB/SUB with topic and simple msgpack frame
        // Send multipart: (TOPIC, msgpack-packed raw frame bytes)
        try {
            // Pack just the raw frame bytes (matching camera2zmq.cpp format)
            msgpack::sbuffer sbuf_simple;
            msgpack::packer<msgpack::sbuffer> pk_simple(&sbuf_simple);
            
            // Convert RGBA to BGR for OpenCV compatibility (like Gazebo example)
            std::vector<unsigned char> bgr_frame(data_size_color * 3 / 4);  // RGB without alpha
            const uint8_t* rgba = reinterpret_cast<const uint8_t*>(data_ptr_color.get());
            for (size_t i = 0, j = 0; i < data_size_color; i += 4, j += 3) {
                bgr_frame[j + 0] = rgba[i + 2];  // B
                bgr_frame[j + 1] = rgba[i + 1];  // G
                bgr_frame[j + 2] = rgba[i + 0];  // R
            }
            
            pk_simple.pack(bgr_frame);

            // Send topic
            zmq_lib::message_t topic_msg(state.m_topic.size());
            memcpy(topic_msg.data(), state.m_topic.c_str(), state.m_topic.size());
            state.m_zmqSocket->send(topic_msg, zmq_lib::send_flags::sndmore | zmq_lib::send_flags::dontwait);

            // Send data
            zmq_lib::message_t data_msg(sbuf_simple.size());
            memcpy(data_msg.data(), sbuf_simple.data(), sbuf_simple.size());
            auto result = state.m_zmqSocket->send(data_msg, zmq_lib::send_flags::dontwait);
            message_sent_ok = result.has_value();
        } catch (const std::exception& e) {
            CARB_LOG_WARN("Simple stream send failed: %s", e.what());
        }
#else
        CARB_LOG_WARN("Simple stream requires msgpack support. Rebuild with msgpack.hpp available.");
#endif
    } else {
        // Full stream mode: send complex protobuf/msgpack structure
        zmq_lib::message_t zmq_message(serialized_message.size());
        memcpy(zmq_message.data(), serialized_message.data(), serialized_message.size());
        auto result = state.m_zmqSocket->send(zmq_message, zmq_lib::send_flags::dontwait);
        message_sent_ok = result.has_value();
    }

    if (!message_sent_ok) {
        state.m_zmqFailCount++;
        double currentTime = db.inputs.systemTime();
        // Log the error state every 5 seconds,
        // and only if errors are accumulating.
        if (state.m_zmqFailCount > 20 && currentTime - lastErrorLogTime >= 5.0) {
            CARB_LOG_ERROR("Failed to send message (no server/subscriber available)");
            lastErrorLogTime = currentTime;
        }
    } else {
        state.m_zmqFailCount = 0;
    }

    return true;
}

// This macro provides the information necessary to OmniGraph that lets it automatically register and deregister
// your node type definition.
REGISTER_OGN_NODE()

} // bridge
} // zmq
} // isaacsim
