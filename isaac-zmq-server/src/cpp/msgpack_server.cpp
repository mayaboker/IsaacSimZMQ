// SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA
// SPDX-License-Identifier: MIT

#include <chrono>
#include <cstdint>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

#include <zmq.hpp>
#include <msgpack.hpp>

#include <opencv2/opencv.hpp>

struct ClockMsg {
    double sim_dt{0.0};
    double sys_dt{0.0};
    double sim_time{0.0};
    double sys_time{0.0};
};

int main(int argc, char** argv) {
    int port = 5561;          // camera stream in
    int ctrl_cam_port = 5557; // camera control out (set <=0 to disable)
    int settings_port = 5559; // settings out (set <=0 to disable)
    int franka_port = 5560;   // franka out (set <=0 to disable)
    bool publish_control = true;
    bool enable_gui = true;
    if (argc > 1) port = std::atoi(argv[1]);
    if (argc > 2) ctrl_cam_port = std::atoi(argv[2]);
    if (argc > 3) settings_port = std::atoi(argv[3]);
    if (argc > 4) franka_port = std::atoi(argv[4]);
    if (argc > 5) publish_control = (std::atoi(argv[5]) != 0);
    if (argc > 6) enable_gui = (std::atoi(argv[6]) != 0);


    try {
        zmq::context_t ctx{1};
        zmq::socket_t sock{ctx, zmq::socket_type::pull};
        sock.set(zmq::sockopt::rcvhwm, 1);
        sock.bind("tcp://*:" + std::to_string(port));
        // Outgoing control sockets (optional)
        std::unique_ptr<zmq::socket_t> cam_cmd_sock;
        std::unique_ptr<zmq::socket_t> settings_sock;
        std::unique_ptr<zmq::socket_t> franka_sock;
        if (publish_control) {
            try {
                if (ctrl_cam_port > 0) {
                    cam_cmd_sock = std::make_unique<zmq::socket_t>(ctx, zmq::socket_type::push);
                    cam_cmd_sock->bind("tcp://*:" + std::to_string(ctrl_cam_port));
                }
                if (settings_port > 0) {
                    settings_sock = std::make_unique<zmq::socket_t>(ctx, zmq::socket_type::push);
                    settings_sock->bind("tcp://*:" + std::to_string(settings_port));
                }
                if (franka_port > 0) {
                    franka_sock = std::make_unique<zmq::socket_t>(ctx, zmq::socket_type::push);
                    franka_sock->bind("tcp://*:" + std::to_string(franka_port));
                }
            } catch (const std::exception& e) {
                std::cerr << "[msgpack_server.cpp] Failed to bind control ports: " << e.what() << std::endl;
                publish_control = false;
            }
        }

        std::cout << "[msgpack_server.cpp] Listening on tcp://*:" << port << std::endl;

        auto last_report = std::chrono::steady_clock::now();
        std::uint64_t received = 0;

        while (true) {
            zmq::message_t msg;
            if (!sock.recv(msg, zmq::recv_flags::none)) {
                continue;
            }

            ++received;

            try {
                // Unpack as a generic map<string, object>
                msgpack::object_handle oh = msgpack::unpack(static_cast<const char*>(msg.data()), msg.size());
                msgpack::object obj = oh.get();

                // Expect a map
                if (obj.type != msgpack::type::MAP) {
                    continue;
                }

                ClockMsg clk;
                std::size_t bbox_n = 0;
                std::size_t color_sz = 0;
                std::size_t depth_sz = 0;
                std::size_t view_len = 0;

                std::vector<unsigned char> color_buf;
                auto to_double = [](const msgpack::object& cv, double& out) -> bool {
                    switch (cv.type) {
                        case msgpack::type::FLOAT32:
                            out = static_cast<double>(cv.via.f64); // f64 used for both
                            return true;
                        case msgpack::type::FLOAT64:
                            out = cv.via.f64;
                            return true;
                        case msgpack::type::POSITIVE_INTEGER:
                            out = static_cast<double>(cv.via.u64);
                            return true;
                        case msgpack::type::NEGATIVE_INTEGER:
                            out = static_cast<double>(cv.via.i64);
                            return true;
                        default:
                            return false;
                    }
                };

                for (uint32_t i = 0; i < obj.via.map.size; ++i) {
                    const auto& k = obj.via.map.ptr[i].key;
                    const auto& v = obj.via.map.ptr[i].val;

                    if (k.type == msgpack::type::STR) {
                        const std::string key = {k.via.str.ptr, k.via.str.size};
                        if (key == "clock" && v.type == msgpack::type::MAP) {
                            for (uint32_t j = 0; j < v.via.map.size; ++j) {
                                const auto& ck = v.via.map.ptr[j].key;
                                const auto& cv = v.via.map.ptr[j].val;
                                if (ck.type != msgpack::type::STR) continue;
                                const std::string cks = {ck.via.str.ptr, ck.via.str.size};
                                double tmp;
                                if (cks == "sim_dt" && to_double(cv, tmp)) clk.sim_dt = tmp;
                                else if (cks == "sys_dt" && to_double(cv, tmp)) clk.sys_dt = tmp;
                                else if (cks == "sim_time" && to_double(cv, tmp)) clk.sim_time = tmp;
                                else if (cks == "sys_time" && to_double(cv, tmp)) clk.sys_time = tmp;
                            }
                        } else if (key == "bbox2d" && v.type == msgpack::type::MAP) {
                            for (uint32_t j = 0; j < v.via.map.size; ++j) {
                                const auto& bk = v.via.map.ptr[j].key;
                                const auto& bv = v.via.map.ptr[j].val;
                                if (bk.type != msgpack::type::STR) continue;
                                const std::string bks = {bk.via.str.ptr, bk.via.str.size};
                                if (bks == "data" && bv.type == msgpack::type::ARRAY) {
                                    bbox_n = bv.via.array.size;
                                }
                            }
                        } else if (key == "color_image" && v.type == msgpack::type::BIN) {
                            color_sz = v.via.bin.size;
                            color_buf.assign(reinterpret_cast<const unsigned char*>(v.via.bin.ptr),
                                             reinterpret_cast<const unsigned char*>(v.via.bin.ptr) + v.via.bin.size);
                        } else if (key == "depth_image" && v.type == msgpack::type::BIN) {
                            depth_sz = v.via.bin.size;
                        } else if (key == "camera" && v.type == msgpack::type::MAP) {
                            for (uint32_t j = 0; j < v.via.map.size; ++j) {
                                const auto& ck = v.via.map.ptr[j].key;
                                const auto& cv = v.via.map.ptr[j].val;
                                if (ck.type != msgpack::type::STR) continue;
                                const std::string cks = {ck.via.str.ptr, ck.via.str.size};
                                if (cks == "view_matrix_ros" && cv.type == msgpack::type::ARRAY) {
                                    view_len = cv.via.array.size;
                                }
                            }
                        }
                    }
                }

                auto now = std::chrono::steady_clock::now();
                if (std::chrono::duration_cast<std::chrono::seconds>(now - last_report).count() >= 1) {
                    last_report = now;
                    std::cout << "[msgpack_server.cpp] recv=" << received
                              << " sim_time=" << clk.sim_time
                              << " bbox=" << bbox_n
                              << " color=" << color_sz << "B depth=" << depth_sz << "B"
                              << " view_len=" << view_len
                              << std::endl;
                }

                // Quick viewer: attempt to display color buffer if square RGBA
                if (enable_gui && !color_buf.empty() && (color_buf.size() % 4 == 0)) {
                    double side_d = std::sqrt(static_cast<double>(color_buf.size()) / 4.0);
                    int side = static_cast<int>(std::round(side_d));
                    if (side > 0 && static_cast<size_t>(side * side * 4) == color_buf.size()) {
                        cv::Mat rgba(side, side, CV_8UC4, color_buf.data());
                        cv::Mat bgr;
                        cv::cvtColor(rgba, bgr, cv::COLOR_RGBA2BGR);
                        cv::imshow("IsaacSim MsgPack Stream", bgr);
                        // Non-blocking wait; press ESC to exit viewer
                        int key = cv::waitKey(1);
                        (void)key;
                    }
                }

                // Publish simple control commands as MsgPack (if enabled)
                if (publish_control && cam_cmd_sock) {
                    msgpack::sbuffer sb;
                    msgpack::packer<msgpack::sbuffer> pk(&sb);
                    pk.pack_map(1);
                    pk.pack(std::string("camera_control_command"));
                    pk.pack_map(2);
                    pk.pack(std::string("joints_vel"));
                    pk.pack_map(3);
                    // In order to move the camera, insert x,y,z velocities
                    pk.pack(std::string("x")); pk.pack(0.0);
                    pk.pack(std::string("y")); pk.pack(0.0);
                    pk.pack(std::string("z")); pk.pack(0.0);
                    pk.pack(std::string("focal_length")); pk.pack(20.0);
                    cam_cmd_sock->send(zmq::message_t(sb.data(), sb.size()), zmq::send_flags::dontwait);
                }
                if (publish_control && settings_sock) {
                    msgpack::sbuffer sb;
                    msgpack::packer<msgpack::sbuffer> pk(&sb);
                    pk.pack_map(1);
                    pk.pack(std::string("settings_command"));
                    pk.pack_map(1);
                    pk.pack(std::string("adaptive_rate")); pk.pack(true);
                    settings_sock->send(zmq::message_t(sb.data(), sb.size()), zmq::send_flags::dontwait);
                }
                if (publish_control && franka_sock) {
                    msgpack::sbuffer sb;
                    msgpack::packer<msgpack::sbuffer> pk(&sb);
                    pk.pack_map(1);
                    pk.pack(std::string("franka_command"));
                    pk.pack_map(2);
                    pk.pack(std::string("effector_pos"));
                    pk.pack_map(3);
                    pk.pack(std::string("x")); pk.pack(0.4);
                    pk.pack(std::string("y")); pk.pack(0.0);
                    pk.pack(std::string("z")); pk.pack(0.3);
                    pk.pack(std::string("show_marker")); pk.pack(true);
                    franka_sock->send(zmq::message_t(sb.data(), sb.size()), zmq::send_flags::dontwait);
                }

            } catch (const std::exception& e) {
                std::cerr << "[msgpack_server.cpp] unpack error: " << e.what() << std::endl;
            }
        }

    } catch (const std::exception& e) {
        std::cerr << "[msgpack_server.cpp] error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
