#!/usr/bin/env python3
import argparse
import msgpack
import numpy as np
import cv2
import zmq

def main():
    parser = argparse.ArgumentParser(description="MsgPack ZMQ Camera Subscriber")
    parser.add_argument("--ip", default="localhost", help="Publisher IP (default: localhost)")
    parser.add_argument("--port", type=int, default=5561, help="Publisher port (default: 5561)")
    parser.add_argument("--topic", default="camera/image", help="MsgPack topic (default: camera/image)")
    parser.add_argument("--width", type=int, required=True, help="Image width in pixels")
    parser.add_argument("--height", type=int, required=True, help="Image height in pixels")
    args = parser.parse_args()

    ctx = zmq.Context()
    sock = ctx.socket(zmq.SUB)
    endpoint = f"tcp://{args.ip}:{args.port}"
    print(f"[subscriber] Connecting to {endpoint} on topic '{args.topic}'")
    sock.connect(endpoint)
    sock.setsockopt(zmq.SUBSCRIBE, args.topic.encode("utf-8"))

    window = "MsgPack Camera"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    try:
        while True:
            topic, payload = sock.recv_multipart()
            frame_bytes = msgpack.unpackb(payload, raw=False)

            # Convert to grayscale+BGR array; publisher sent grayscale repeated into 3 channels
            img = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(args.height, args.width, 3)

            cv2.imshow(window, img)
            if cv2.waitKey(1) == 27:  # ESC to exit
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        sock.close()
        ctx.term()

if __name__ == "__main__":
    main()
