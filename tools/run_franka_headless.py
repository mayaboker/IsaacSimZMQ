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
from omni.isaac.core import World

# Import after Isaac Sim is initialized
def main():
    from isaacsim.zmq.bridge.examples.example_missions import FrankaVisionMission
    
    print("[run_franka_headless] Starting Franka ZMQ example...")
    
    # Create world
    world = World(stage_units_in_meters=1.0)
    
    # Create and setup the mission
    mission = FrankaVisionMission(server_ip="localhost")

    # Setup the scene
    async def setup_and_run():
        print("[run_franka_headless] Setting up scene...")
        mission.setup_scene()

        # Wait for scene to load
        await omni.kit.app.get_app().next_update_async()
        await omni.kit.app.get_app().next_update_async()

        # Reset world
        print("[run_franka_headless] Resetting world...")
        await world.reset_async()

        # Start mission (this starts streaming)
        print("[run_franka_headless] Starting mission and streaming...")
        mission.start_mission()

        print("[run_franka_headless] Franka example running!")
        print("[run_franka_headless] Connect viewer with:")
        print("  python isaac-zmq-server/src/simple_msgpack_camera_gui.py --ip 127.0.0.1 --port 5561 --topic camera/image --width 720 --height 720")
        print()
        print("[run_franka_headless] Press Ctrl+C to stop.")

        # Keep running - the physics step callback handles streaming
        while True:
            await asyncio.sleep(1.0)
            # Step physics
            world.step(render=True)

    # Run the async setup
    asyncio.ensure_future(setup_and_run())


# Entry point when run via --exec
main()
