#!/usr/bin/env python3
"""
Simple ZMQ pose publisher for testing camera pose control.

Publishes pose messages (x, y, z, roll, pitch, yaw) on topic "camera/pose"
that can be received by the ZMQPoseSubscriber in Isaac Sim.

Usage:
    python pose_publisher.py [--ip localhost] [--port 5562] [--topic camera/pose]
"""

import argparse
import time
import msgpack
import zmq

def main():
    parser = argparse.ArgumentParser(description="Publish camera pose commands via ZMQ/MsgPack")
    parser.add_argument("--ip", default="localhost", help="IP address to bind (default: localhost)")
    parser.add_argument("--port", type=int, default=5562, help="Port number (default: 5562)")
    parser.add_argument("--topic", default="camera/pose", help="Topic name (default: camera/pose)")
    parser.add_argument("--x", type=float, default=0.0, help="X position (default: 0.0)")
    parser.add_argument("--y", type=float, default=0.0, help="Y position (default: 0.0)")
    parser.add_argument("--z", type=float, default=1.0, help="Z position (default: 1.0)")
    parser.add_argument("--roll", type=float, default=0.0, help="Roll angle in radians (default: 0.0)")
    parser.add_argument("--pitch", type=float, default=0.0, help="Pitch angle in radians (default: 0.0)")
    parser.add_argument("--yaw", type=float, default=0.0, help="Yaw angle in radians (default: 0.0)")
    parser.add_argument("--rate", type=float, default=10.0, help="Publishing rate in Hz (default: 10.0)")
    parser.add_argument("--once", action="store_true", help="Publish once and exit")

    args = parser.parse_args()

    # Create ZMQ PUB socket
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(f"tcp://*:{args.port}")

    # Wait a bit for subscribers to connect
    print(f"Pose publisher: Binding on port {args.port}, topic '{args.topic}'")
    print("Waiting for subscribers to connect...")
    time.sleep(1.0)

    topic_bytes = args.topic.encode("utf-8")
    period = 1.0 / args.rate

    try:
        if args.once:
            # Publish once
            pose_data = {
                "x": args.x,
                "y": args.y,
                "z": args.z,
                "roll": args.roll,
                "pitch": args.pitch,
                "yaw": args.yaw,
            }
            payload = msgpack.packb(pose_data, use_bin_type=True)
            socket.send_multipart([topic_bytes, payload])
            print(f"Published pose: x={args.x}, y={args.y}, z={args.z}, "
                  f"roll={args.roll:.3f}, pitch={args.pitch:.3f}, yaw={args.yaw:.3f}")
        else:
            # Publish continuously
            print(f"Publishing pose at {args.rate} Hz. Press Ctrl+C to stop.")
            print(f"Pose: x={args.x}, y={args.y}, z={args.z}, "
                  f"roll={args.roll:.3f}, pitch={args.pitch:.3f}, yaw={args.yaw:.3f}")

            while True:
                pose_data = {
                    "x": args.x,
                    "y": args.y,
                    "z": args.z,
                    "roll": args.roll,
                    "pitch": args.pitch,
                    "yaw": args.yaw,
                }
                payload = msgpack.packb(pose_data, use_bin_type=True)
                socket.send_multipart([topic_bytes, payload])
                time.sleep(period)

    except KeyboardInterrupt:
        print("\nStopping pose publisher...")
    finally:
        socket.close()
        context.term()

if __name__ == "__main__":
    main()
