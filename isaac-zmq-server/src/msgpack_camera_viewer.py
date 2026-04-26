#!/usr/bin/env python3
"""
Simple MsgPack camera viewer using SUB socket.
Compatible with the Isaac Sim msgpack pipeline that publishes multipart data:
    [topic, msgpack-encoded image bytes]

Usage:
    python msgpack_camera_viewer.py --ip 127.0.0.1 --port 5561 --width 720 --height 720
"""

import argparse
import numpy as np
import zmq
import cv2

try:
    import msgpack
except ImportError:
    print("ERROR: msgpack not installed. Run: pip install msgpack")
    exit(1)


def main():
    parser = argparse.ArgumentParser(description="MsgPack Camera Viewer (SUB socket)")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="Publisher IP address to connect to")
    parser.add_argument("--port", type=int, default=5561, help="Publisher port to connect to")
    parser.add_argument("--topic", type=str, default="", help="Topic filter (empty subscribes to all topics)")
    parser.add_argument("--width", type=int, default=720, help="Image width")
    parser.add_argument("--height", type=int, default=720, help="Image height")
    args = parser.parse_args()

    # Create ZMQ context and SUB socket
    ctx = zmq.Context()
    sock = ctx.socket(zmq.SUB)
    sock.setsockopt(zmq.SUBSCRIBE, args.topic.encode("utf-8"))

    # Connect to publisher
    addr = f"tcp://{args.ip}:{args.port}"
    sock.connect(addr)
    topic_label = args.topic if args.topic else "<all>"
    print(f"[viewer] Connected SUB socket to {addr}")
    print(f"[viewer] Subscribed topic: {topic_label}")
    print(f"[viewer] Waiting for frames (expected size: {args.width}x{args.height}x3 BGR)...")

    expected_size = args.width * args.height * 3  # BGR bytes

    cv2.namedWindow("MsgPack Camera Viewer", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("MsgPack Camera Viewer", args.width, args.height)

    frame_count = 0
    while True:
        try:
            # Receive multipart message: [topic, msgpack_payload]
            topic_msg, payload_msg = sock.recv_multipart()
            topic = topic_msg.decode("utf-8", errors="replace")

            # Unpack msgpack payload (contains raw BGR bytes)
            img_data = msgpack.unpackb(payload_msg, raw=False)

            if len(img_data) == 0:
                if frame_count == 0:
                    print("[viewer] Received empty image data")
                continue

            if len(img_data) != expected_size:
                if frame_count == 0:
                    print(f"[viewer] Image size mismatch: got {len(img_data)}, expected {expected_size}")
                continue

            # Convert to numpy array (BGR format from publisher)
            img_bgr = np.frombuffer(img_data, dtype=np.uint8).reshape(args.height, args.width, 3)

            # Display
            cv2.imshow("MsgPack Camera Viewer", img_bgr)

            frame_count += 1
            if frame_count == 1:
                print(f"[viewer] Receiving frames on topic '{topic}'! First frame size: {len(img_data)} bytes")

            # Check for quit key
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # q or ESC
                break

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[viewer] Error: {e}")
            continue

    print(f"[viewer] Received {frame_count} frames total")
    cv2.destroyAllWindows()
    sock.close()
    ctx.term()


if __name__ == "__main__":
    main()
