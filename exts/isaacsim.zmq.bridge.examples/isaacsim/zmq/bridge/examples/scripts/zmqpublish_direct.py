"""
MsgPack ZMQ Publisher Script for Isaac Sim (Direct Mode).

This script assumes the USD stage is already loaded (e.g., via Isaac Sim's -f flag or GUI).
It waits for the stage to be ready and then publishes camera frames via ZMQ using MsgPack.

Usage:
    # From Isaac Sim Script Editor or via --exec:
    # Use this when the USD is already loaded by the launcher or GUI
"""

import asyncio
import omni.kit.app
import omni.timeline
import omni.usd
from pxr import Usd

from isaacsim.zmq.bridge.examples.core.ZMQMsgpackAnnotator import ZMQMsgpackAnnotator

# --- Configure these values ---
CAMERA_PATH = "/World/turtlebot3_burger/base_link/car_camera"      # USD path to your camera prim
RESOLUTION = (1280, 720)             # Render-product resolution
ZMQ_IP = "*"
ZMQ_PORT = 5561
TOPIC = "camera/image"
# --------------------------------

annotator = None
app = omni.kit.app.get_app()
timeline = omni.timeline.get_timeline_interface()
subscription = None

async def publish_frame(_):
    if annotator is not None:
        await annotator.publish()

def on_update(event):
    if not timeline.is_playing() or annotator is None:
        return
    asyncio.ensure_future(publish_frame(event.payload["dt"]))

def check_and_start():
    """Check if stage and camera are ready, then initialize the annotator."""
    global annotator, subscription

    if annotator is not None:
        return  # Already initialized

    usd_context = omni.usd.get_context()
    stage = usd_context.get_stage()

    if stage is None:
        print(f"[zmqpublish-direct] Waiting for stage to be loaded...")
        return  # Stage not ready yet

    # Check if the camera prim exists
    camera_prim = stage.GetPrimAtPath(CAMERA_PATH)
    if not camera_prim.IsValid():
        print(f"[zmqpublish-direct] Stage loaded but camera {CAMERA_PATH} not found yet. Current stage root: {stage.GetRootLayer().identifier if stage.GetRootLayer() else 'None'}")
        return  # Camera not found yet

    # Stage and camera are ready, initialize annotator
    print(f"[zmqpublish-direct] Stage loaded, initializing MsgPack annotator for camera: {CAMERA_PATH}")
    annotator = ZMQMsgpackAnnotator(
        camera_path=CAMERA_PATH,
        resolution=RESOLUTION,
        ip=ZMQ_IP,
        port=ZMQ_PORT,
        topic=TOPIC,
    )

    subscription = app.get_update_event_stream().create_subscription_to_pop(on_update)
    print("MsgPack annotator started.")

def on_stage_event(event):
    """Handle stage events to detect when stage is loaded."""
    if event.type == int(omni.usd.StageEventType.OPENED):
        print(f"[zmqpublish-direct] Stage opened")
        check_and_start()

# Subscribe to stage events
usd_context = omni.usd.get_context()
stage_stream = usd_context.get_stage_event_stream()
stage_subscription = stage_stream.create_subscription_to_pop(on_stage_event)

# Also check immediately in case stage is already loaded
check_and_start()

# Keep checking periodically until annotator is initialized
def periodic_check(event):
    if annotator is None:
        check_and_start()

# Subscribe to update events for periodic checking
check_subscription = app.get_update_event_stream().create_subscription_to_pop(periodic_check)
