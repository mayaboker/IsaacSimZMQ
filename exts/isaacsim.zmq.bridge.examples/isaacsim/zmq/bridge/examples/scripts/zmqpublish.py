"""
MsgPack ZMQ Publisher Script for Isaac Sim.

This script loads a USD stage and publishes camera frames via ZMQ using MsgPack serialization.
The USD path can be provided via the ISAAC_ZMQ_STAGE environment variable.

Usage:
    # From Isaac Sim Script Editor or via --exec:
    # The script will read ISAAC_ZMQ_STAGE env var to determine which USD to load

    # Or set defaults at the top of this file and run directly
"""

import asyncio
import os
import omni.kit.app
import omni.timeline
import omni.usd
from pxr import Usd

from isaacsim.zmq.bridge.examples.core.ZMQMsgpackAnnotator import ZMQMsgpackAnnotator
from isaacsim.zmq.bridge.examples.core.ZMQPoseSubscriber import ZMQPoseSubscriber

# --- Configure these values ---
CAMERA_PATH = "/World/turtlebot3_burger/base_link/car_camera"      # USD path to your camera prim
RESOLUTION = (1280, 720)             # Render-product resolution
ZMQ_IP = "*"
ZMQ_PORT = 5561
TOPIC = "camera/image"
# Pose subscriber configuration
POSE_SERVER_IP = "localhost"         # IP of the pose publisher (change to Gazebo machine IP if different)
POSE_PORT = 5556                     # Port for pose messages (Gazebo plugin uses 5556)
POSE_TOPIC = "camera/pose"          # Topic for pose messages
# --------------------------------

annotator = None
pose_subscriber = None
app = omni.kit.app.get_app()
timeline = omni.timeline.get_timeline_interface()
subscription = None

# Ensure the ZMQ bridge extension is enabled
ext_manager = app.get_extension_manager()
ext_manager.set_extension_enabled("isaacsim.zmq.bridge.examples", True)

# Open the USD stage (fall back to default if the env var is missing)
USD_PATH = os.getenv("ISAAC_ZMQ_STAGE", "/home/user/omniverse/is40/zmq-turtle-rate-camera.usd")
usd_context = omni.usd.get_context()
stage_url = usd_context.get_stage_url()
if stage_url != USD_PATH:
    print(f"[zmqpublish] Opening USD: {USD_PATH}")
    usd_context.open_stage(USD_PATH)

async def publish_frame(_):
    if annotator is not None:
        await annotator.publish()

    # Start pose subscriber on first frame (when event loop is running)
    # start_async() is idempotent - it checks if already running
    global pose_subscriber
    if pose_subscriber is not None:
        await pose_subscriber.start_async()

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
        return  # Stage not ready yet

    # Check if the camera prim exists
    camera_prim = stage.GetPrimAtPath(CAMERA_PATH)
    if not camera_prim.IsValid():
        return  # Camera not found yet

    # Stage and camera are ready, initialize annotator
    print(f"[zmqpublish] Stage loaded, initializing MsgPack annotator for camera: {CAMERA_PATH}")
    annotator = ZMQMsgpackAnnotator(
        camera_path=CAMERA_PATH,
        resolution=RESOLUTION,
        ip=ZMQ_IP,
        port=ZMQ_PORT,
        topic=TOPIC,
    )

    subscription = app.get_update_event_stream().create_subscription_to_pop(on_update)
    print("MsgPack annotator started.")

    # Initialize pose subscriber (will start when event loop is running)
    global pose_subscriber
    if pose_subscriber is None:
        pose_subscriber = ZMQPoseSubscriber(
            prim_path=CAMERA_PATH,
            server_ip=POSE_SERVER_IP,
            port=POSE_PORT,
            topic=POSE_TOPIC,
        )
        # Don't call start() here - it will be started in publish_frame() when event loop is available
        print(f"Pose subscriber initialized for {POSE_SERVER_IP}:{POSE_PORT}, topic '{POSE_TOPIC}'")

def on_stage_event(event):
    """Handle stage events to detect when stage is loaded."""
    if event.type == int(omni.usd.StageEventType.OPENED):
        print(f"[zmqpublish] Stage opened")
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
