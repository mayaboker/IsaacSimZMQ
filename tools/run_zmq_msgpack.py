#!/usr/bin/env python3
"""
Launch Isaac Sim with MsgPack streaming.

This script provides a convenient way to launch Isaac Sim with the ZMQ MsgPack
streaming extension enabled. It can optionally load a USD stage and run a
custom publisher script.

For simple testing, use the built-in Franka example instead:
    1. Start Isaac Sim normally
    2. Enable the isaacsim.zmq.bridge.examples extension
    3. Use Window > Examples > ZMQ Bridge > Franka

Usage:
    # Basic launch (just enables the extension)
    python tools/run_zmq_msgpack.py

    # Launch with a specific USD stage
    python tools/run_zmq_msgpack.py --usd /path/to/your/stage.usd

    # Launch with custom camera path
    python tools/run_zmq_msgpack.py --usd /path/to/stage.usd --camera /World/Camera

    # Headless mode
    python tools/run_zmq_msgpack.py --headless --usd /path/to/stage.usd
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Get the repo root (this script is in tools/)
REPO_ROOT = Path(__file__).parent.parent

# Default paths for Isaac Sim 5.0.0
DEFAULT_LAUNCHER = Path("/home/user/isaacsim5.0/isaac-sim.sh")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Isaac Sim with ZMQ MsgPack streaming",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--launcher", type=Path, default=DEFAULT_LAUNCHER,
                        help="Path to isaac-sim.sh (or headless variant)")
    parser.add_argument("--usd", type=Path, default=None,
                        help="USD stage to load (optional)")
    parser.add_argument("--camera", type=str, default=None,
                        help="Camera prim path (e.g., /World/Camera)")
    parser.add_argument("--width", type=int, default=720,
                        help="Camera resolution width")
    parser.add_argument("--height", type=int, default=720,
                        help="Camera resolution height")
    parser.add_argument("--port", type=int, default=5561,
                        help="ZMQ port for streaming")
    parser.add_argument("--topic", type=str, default="camera/image",
                        help="MsgPack topic name")
    parser.add_argument("--headless", action="store_true",
                        help="Run without GUI (--no-window)")
    parser.add_argument("--franka", action="store_true",
                        help="Run the Franka example automatically (headless)")
    parser.add_argument("--extra", nargs=argparse.REMAINDER,
                        help="Additional arguments forwarded to the launcher")
    return parser.parse_args()


def resolve_launcher(base: Path) -> Path:
    launcher = base.expanduser().resolve()
    if not launcher.exists():
        raise FileNotFoundError(f"Launcher not found: {launcher}")
    return launcher


def main() -> int:
    args = parse_args()

    try:
        launcher = resolve_launcher(args.launcher)
    except FileNotFoundError as exc:
        print(exc)
        return 1

    # Build command
    cmd = [str(launcher), "--enable", "isaacsim.zmq.bridge.examples"]

    # Isaac Sim 5.0.0 uses --no-window for headless mode
    if args.headless or args.franka:
        cmd.append("--no-window")

    # Run Franka example script
    if args.franka:
        franka_script = REPO_ROOT / "tools" / "run_franka_headless.py"
        if not franka_script.exists():
            print(f"[run_zmq_msgpack] Franka script not found: {franka_script}")
            return 1
        cmd.extend(["--exec", str(franka_script)])

    if args.extra:
        cmd.extend(args.extra)

    # Set environment variables for the streaming configuration
    env = os.environ.copy()

    if args.usd:
        usd = args.usd.expanduser().resolve()
        if not usd.exists():
            print(f"[run_zmq_msgpack] USD stage not found: {usd}")
            return 1
        env["ISAAC_ZMQ_STAGE"] = str(usd)
        print(f"[run_zmq_msgpack] USD stage: {usd}")

    if args.camera:
        env["ISAAC_ZMQ_CAMERA"] = args.camera
        print(f"[run_zmq_msgpack] Camera path: {args.camera}")

    env["ISAAC_ZMQ_WIDTH"] = str(args.width)
    env["ISAAC_ZMQ_HEIGHT"] = str(args.height)
    env["ISAAC_ZMQ_PORT"] = str(args.port)
    env["ISAAC_ZMQ_TOPIC"] = args.topic

    print("[run_zmq_msgpack] Executing:\n  " + " ".join(cmd))
    print(f"[run_zmq_msgpack] Resolution: {args.width}x{args.height}")
    print(f"[run_zmq_msgpack] Port: {args.port}, Topic: {args.topic}")
    print()
    print("[run_zmq_msgpack] TIP: For quick testing, use the built-in Franka example:")
    print("  Create > Isaac ZMQ Examples > Franka RMPFlow")
    print()

    try:
        return subprocess.call(cmd, env=env)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
