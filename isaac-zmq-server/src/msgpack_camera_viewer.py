#!/usr/bin/env python3
"""
Simple MsgPack camera viewer using PULL socket.
Compatible with Isaac Sim's OgnIsaacBridgeZMQNode (which uses PUSH socket).

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
    parser = argparse.ArgumentParser(description="MsgPack Camera Viewer (PULL socket)")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="IP address to bind to")
    parser.add_argument("--port", type=int, default=5561, help="Port to bind to")
    parser.add_argument("--width", type=int, default=720, help="Image width")
    parser.add_argument("--height", type=int, default=720, help="Image height")
    args = parser.parse_args()

    # Create ZMQ context and PULL socket
    ctx = zmq.Context()
    sock = ctx.socket(zmq.PULL)

    # Bind to receive from PUSH socket
    addr = f"tcp://{args.ip}:{args.port}"
    sock.bind(addr)
    print(f"[viewer] Bound PULL socket to {addr}")
    print(f"[viewer] Waiting for frames (expected size: {args.width}x{args.height})...")

    expected_size = args.width * args.height * 4  # RGBA

    cv2.namedWindow("MsgPack Camera Viewer", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("MsgPack Camera Viewer", args.width, args.height)

    frame_count = 0
    while True:
        try:
            # Receive message (blocking)
            message = sock.recv()

            # Check first byte to detect format
            first_byte = message[0] if message else 0
            is_msgpack = (0x80 <= first_byte <= 0x8f) or first_byte in (0xde, 0xdf)

            if not is_msgpack:
                if frame_count == 0:
                    print("[viewer] Received protobuf data - this viewer only supports msgpack!")
                    print("[viewer] Set ISAAC_ZMQ_SERIALIZATION=msgpack in Isaac Sim")
                continue

            # Unpack msgpack
            obj = msgpack.unpackb(message, raw=False)

            # Extract image data
            img_data = obj.get("color_image", b"")

            if len(img_data) == 0:
                if frame_count == 0:
                    print("[viewer] Received empty image data")
                continue

            if len(img_data) != expected_size:
                if frame_count == 0:
                    print(f"[viewer] Image size mismatch: got {len(img_data)}, expected {expected_size}")
                continue

            # Convert to numpy array (RGBA format from Isaac Sim)
            img = np.frombuffer(img_data, dtype=np.uint8).reshape(args.height, args.width, 4)

            # Convert RGBA to BGR for OpenCV
            img_bgr = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)

            # Display
            cv2.imshow("MsgPack Camera Viewer", img_bgr)

            frame_count += 1
            if frame_count == 1:
                print(f"[viewer] Receiving frames! First frame size: {len(img_data)} bytes")

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
