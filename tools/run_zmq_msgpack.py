#!/usr/bin/env python3
"""Launch Isaac Sim with a specified USD stage and MsgPack publisher script."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Get the repo root (this script is in tools/)
REPO_ROOT = Path(__file__).parent.parent

# Update these defaults for Isaac Sim 5.0.0
DEFAULT_LAUNCHER = Path("/opt/nvidia/isaac-sim/isaac-sim.sh")
DEFAULT_USD = Path("/home/user/omniverse/is40/zmq-turtle-rate-camera.usd")
# Default to the script in the repo
DEFAULT_SCRIPT = REPO_ROOT / "exts" / "isaacsim.zmq.bridge.examples" / "isaacsim" / "zmq" / "bridge" / "examples" / "scripts" / "zmqpublish.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Isaac Sim with the MsgPack publisher stage/script",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--launcher", type=Path, default=DEFAULT_LAUNCHER,
                        help="Path to isaac-sim.sh (or headless variant)")
    parser.add_argument("--usd", type=Path, default=DEFAULT_USD,
                        help="USD stage to load")
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT,
                        help="Python script to execute with -p")
    parser.add_argument("--headless", action="store_true",
                        help="Run the headless launcher if available")
    parser.add_argument("--extra", nargs=argparse.REMAINDER,
                        help="Additional arguments forwarded to the launcher")
    return parser.parse_args()


def resolve_launcher(base: Path, headless: bool) -> Path:
    launcher = base.expanduser().resolve()
    if headless:
        # Try to swap to isaac-sim-headless.sh beside the provided launcher
        if "headless" not in launcher.name:
            candidate = launcher.with_name("isaac-sim-headless.sh")
            if candidate.exists():
                launcher = candidate
            else:
                print(f"[run_zmq_msgpack] Warning: headless flag requested but {candidate} not found."
                      " Using provided launcher instead.")
    if not launcher.exists():
        raise FileNotFoundError(f"Launcher not found: {launcher}")
    return launcher


def main() -> int:
    args = parse_args()

    try:
        launcher = resolve_launcher(args.launcher, args.headless)
    except FileNotFoundError as exc:
        print(exc)
        return 1

    usd = args.usd.expanduser().resolve()
    script = args.script.expanduser().resolve()

    if not usd.exists():
        print(f"[run_zmq_msgpack] USD stage not found: {usd}")
        return 1
    if not script.exists():
        print(f"[run_zmq_msgpack] Script not found: {script}")
        return 1

    cmd = [str(launcher), "--exec", str(script), "--enable", "isaacsim.zmq.bridge.examples"]
    if args.extra:
        cmd.extend(args.extra)

    env = os.environ.copy()
    env["ISAAC_ZMQ_STAGE"] = str(usd)

    print("[run_zmq_msgpack] Executing:\n  " + " ".join(cmd))
    print(f"[run_zmq_msgpack] ISAAC_ZMQ_STAGE={env['ISAAC_ZMQ_STAGE']}")
    try:
        return subprocess.call(cmd, env=env)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
