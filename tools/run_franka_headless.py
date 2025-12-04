#!/usr/bin/env python3
"""
Run the Franka ZMQ example in headless mode.

Usage:
    # Set environment variables first:
    export ISAAC_ZMQ_SERIALIZATION=msgpack
    export ISAAC_ZMQ_SIMPLE_STREAM=1

    # Run headless:
    /home/user/isaacsim5.0/isaac-sim.sh --no-window --enable isaacsim.zmq.bridge.examples --exec tools/run_franka_headless.py
"""

import asyncio
import carb
import omni.kit.app
import omni.usd


def main():
    from isaacsim.zmq.bridge.examples.example_missions import FrankaVisionMission

    print("[run_franka_headless] Starting Franka ZMQ example...")

    async def setup_and_run():
        # Load the mission USD stage
        print("[run_franka_headless] Loading mission USD...")
        source_usd = FrankaVisionMission.mission_usd_path()
        print(f"[run_franka_headless] USD path: {source_usd}")
        
        # Load the stage (no argument - method gets path internally)
        FrankaVisionMission.load_mission()

        # Wait for stage to load
        for _ in range(10):
            await omni.kit.app.get_app().next_update_async()

        # Create the mission instance
        print("[run_franka_headless] Creating mission instance...")
        mission = FrankaVisionMission(server_ip="localhost")

        # Reset world (this initializes everything and starts streaming)
        print("[run_franka_headless] Resetting world and starting mission...")
        mission.reset_world_async()

        # Wait for reset to complete
        for _ in range(30):
            await omni.kit.app.get_app().next_update_async()

        print("[run_franka_headless] Franka example running!")
        print("[run_franka_headless] Connect viewer with:")
        print("  python simple_msgpack_camera_gui.py --ip <HOST_IP> --port 5561 --topic camera/image --width 720 --height 720")
        print()
        print("[run_franka_headless] Press Ctrl+C to stop.")

        # Keep running
        while True:
            await omni.kit.app.get_app().next_update_async()

    # Run the async setup
    asyncio.ensure_future(setup_and_run())


# Entry point when run via --exec
main()
