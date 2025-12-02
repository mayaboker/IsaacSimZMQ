# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import time
import traceback

import numpy as np
import zmq

try:
    import msgpack  # type: ignore
except Exception:
    msgpack = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Isaac Sim ZMQ MsgPack Server Example (headless)")
    parser.add_argument("--port", type=int, default=5561, help="Port to subscribe data on")
    args = parser.parse_args()

    if not msgpack:
        print("This example requires the 'msgpack' package. Please rebuild or install it.")
        return

    ctx = zmq.Context()
    sock = ctx.socket(zmq.PULL)
    sock.set_hwm(1)
    sock.setsockopt(zmq.RCVTIMEO, 2000)
    sock.bind(f"tcp://*:{args.port}")

    print(f"[example_msgpack] Listening for MsgPack messages on port {args.port}")

    last_report = time.monotonic()
    printed_first = False
    received = 0
    try:
        while True:
            try:
                msg = sock.recv()
            except zmq.Again:
                continue

            try:
                obj = msgpack.unpackb(msg, raw=False)
            except Exception:
                # Ignore non-MsgPack frames
                continue

            received += 1

            if not printed_first:
                print("[example_msgpack] Received first MsgPack frame")
                printed_first = True

            clk = obj.get("clock", {})
            sim_time = float(clk.get("sim_time", 0.0))
            view = obj.get("camera", {}).get("view_matrix_ros", [])
            bbox_n = len(obj.get("bbox2d", {}).get("data", []))
            color_sz = len(obj.get("color_image", b""))
            depth_sz = len(obj.get("depth_image", b""))

            if time.monotonic() - last_report > 1.0:
                last_report = time.monotonic()
                print(
                    f"[example_msgpack] recv={received} sim_time={sim_time:.3f} bbox={bbox_n} "
                    f"color={color_sz}B depth={depth_sz}B view_len={len(view)}"
                )

            # Example: read color image shape if square RGBA
            side = int(np.sqrt(color_sz / 4.0)) if color_sz % 4 == 0 else 0
            if side and side * side * 4 == color_sz:
                # Do something lightweight to verify
                _ = np.frombuffer(obj["color_image"], dtype=np.uint8).reshape(side, side, 4)

    except KeyboardInterrupt:
        pass
    except Exception:
        print(traceback.format_exc())
    finally:
        sock.close()
        ctx.term()


if __name__ == "__main__":
    main()
