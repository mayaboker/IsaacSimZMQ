#!/usr/bin/env python3
"""
Generic GUI camera streaming script.

Reads configuration from environment variables set by run_zmq_msgpack.py:
- ISAAC_ZMQ_STAGE: Path to USD stage
- ISAAC_ZMQ_CAMERA: Camera prim path (e.g., /World/Camera)
- ISAAC_ZMQ_WIDTH: Resolution width (default: 720)
- ISAAC_ZMQ_HEIGHT: Resolution height (default: 720)
- ISAAC_ZMQ_PORT: ZMQ port (default: 5561)

Usage:
    export ISAAC_ZMQ_SERIALIZATION=msgpack
    export ISAAC_ZMQ_SIMPLE_STREAM=1

    python tools/run_zmq_msgpack.py --gui \\
        --usd /path/to/scene.usd \\
        --camera /World/Camera
"""

import asyncio
import os
import carb
import omni.kit.app
import omni.usd
import omni.timeline
from omni.isaac.core.utils import stage as stage_utils


def main():
    print("[run_generic_gui] Starting generic camera streaming (GUI mode)...")
    
    # Read configuration from environment
    usd_path = os.getenv("ISAAC_ZMQ_STAGE")
    camera_path = os.getenv("ISAAC_ZMQ_CAMERA")
    width = int(os.getenv("ISAAC_ZMQ_WIDTH", "720"))
    height = int(os.getenv("ISAAC_ZMQ_HEIGHT", "720"))
    port = int(os.getenv("ISAAC_ZMQ_PORT", "5561"))
    topic = os.getenv("ISAAC_ZMQ_TOPIC", "camera/image")
    pose_port = int(os.getenv("ISAAC_ZMQ_POSE_PORT", "5562"))
    pose_topic = os.getenv("ISAAC_ZMQ_POSE_TOPIC", "camera/pose")
    pose_ip = os.getenv("ISAAC_ZMQ_POSE_IP", "localhost")

    if not usd_path:
        print("[run_generic_gui] ERROR: ISAAC_ZMQ_STAGE not set. Use --usd option.")
        return

    if not camera_path:
        print("[run_generic_gui] ERROR: ISAAC_ZMQ_CAMERA not set. Use --camera option.")
        return

    print(f"[run_generic_gui] USD: {usd_path}")
    print(f"[run_generic_gui] Camera: {camera_path}")
    print(f"[run_generic_gui] Resolution: {width}x{height}")
    print(f"[run_generic_gui] Port: {port}, Topic: {topic}")

    async def setup_streaming():
        # Load the USD stage
        print("[run_generic_gui] Loading USD stage...")
        await stage_utils.open_stage_async(usd_path)

        # Wait for stage to load
        for _ in range(10):
            await omni.kit.app.get_app().next_update_async()

        # Verify camera exists
        stage = omni.usd.get_context().get_stage()
        if not stage:
            print("[run_generic_gui] ERROR: Failed to load stage")
            return

        camera_prim = stage.GetPrimAtPath(camera_path)
        if not camera_prim.IsValid():
            print(f"[run_generic_gui] ERROR: Camera not found at {camera_path}")
            print("[run_generic_gui] Available camera-like prims:")
            for prim in stage.Traverse():
                if "camera" in prim.GetPath().pathString.lower():
                    print(f"  {prim.GetPath()}")
            return

        print(f"[run_generic_gui] Camera found: {camera_path}")

        # Import and create annotator
        from isaacsim.zmq.bridge.examples.core.annotators import ZMQAnnotator
        from isaacsim.zmq.bridge.examples.core.ZMQPoseSubscriber import ZMQPoseSubscriber
        
        print("[run_generic_gui] Creating ZMQ annotator...")
        annotator = ZMQAnnotator(
            camera=camera_path,
            resolution=(width, height),
            use_ogn_nodes=True,
            server_ip="localhost",
            port=port,
        )
        
        # Create pose subscriber for camera control
        print(f"[run_generic_gui] Creating pose subscriber on {pose_ip}:{pose_port}, topic '{pose_topic}'...")
        pose_subscriber = ZMQPoseSubscriber(
            prim_path=camera_path,
            server_ip=pose_ip,
            port=pose_port,
            topic=pose_topic,
        )
        
        # Start timeline
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        
        # Start pose subscriber
        await pose_subscriber.start_async()
        
        print("[run_generic_gui] ✓ Streaming started!")
        print(f"[run_generic_gui] Connect viewer with:")
        print(f"  python simple_msgpack_camera_gui.py --ip <HOST_IP> --port {port} --topic {topic} --width {width} --height {height}")
        print()
        print(f"[run_generic_gui] Pose subscriber listening on {pose_ip}:{pose_port}, topic '{pose_topic}'")
        print("[run_generic_gui] Use the GUI normally. Close Isaac Sim to stop.")

    # Run the async setup
    asyncio.ensure_future(setup_streaming())


# Entry point when run via --exec
main()
