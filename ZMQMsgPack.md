# ZMQ MsgPack Quickstart

This note covers three common ways to stream camera frames from Isaac Sim to a
MsgPack ZMQ subscriber using the new `ZMQMsgpackAnnotator`:

1. Launch Isaac Sim normally and paste a small helper into the Script Editor.
2. Start Isaac Sim from the command line with a utility script.
3. Drive the same flow in headless mode.

The examples below assume you already built the project (`./build.sh`) and that
a subscriber is running on the **server side** to verify frames. You can use
`simple_msgpack_camera_gui.py` from the `isaac-zmq-server/src/` directory.

---

## 1. Use the Script Editor inside Isaac Sim

1. Open the stage that contains your camera (e.g. `/home/user/omniverse/is40/zmq-turtle-rate-camera.usd`).
2. Open **Window → Script Editor**.
3. Paste the snippet below, adjust the camera path, resolution, topic, etc., and
   press **Run**.

```python
import asyncio
import omni.kit.app
import omni.timeline

from isaacsim.zmq.bridge.examples.core.ZMQMsgpackAnnotator import ZMQMsgpackAnnotator

CAMERA_PATH = "/World/turtlebot3_burger/base_link/car_camera"
RESOLUTION = (1280, 720)
ANNOTATOR_TOPIC = "camera/image"
ZMQ_IP = "0.0.0.0"          # bind on all interfaces
ZMQ_PORT = 5561

annotator = ZMQMsgpackAnnotator(
    camera_path=CAMERA_PATH,
    resolution=RESOLUTION,
    ip=ZMQ_IP,
    port=ZMQ_PORT,
    topic=ANNOTATOR_TOPIC,
)

app = omni.kit.app.get_app()
timeline = omni.timeline.get_timeline_interface()
subscription = None

async def publish_frame(_dt):
    await annotator.publish()

def on_update(event):
    if timeline.is_playing():
        asyncio.ensure_future(publish_frame(event.payload["dt"]))

def start():
    global subscription
    if subscription is None:
        subscription = app.get_update_event_stream().create_subscription_to_pop(on_update)
        print("MsgPack annotator started")

def stop():
    global subscription
    if subscription is not None:
        subscription = None
        annotator.destroy()
        print("MsgPack annotator stopped")

start()
```

4. Press **Play** on the timeline. Frames are now emitted on `tcp://0.0.0.0:5561`
   with topic `camera/image`.
5. Run the viewer (from the repo root) to confirm:

```bash
python isaac-zmq-server/src/simple_msgpack_camera_gui.py \
    --ip 127.0.0.1 --port 5561 --topic camera/image \
    --width 1280 --height 720
```

(Press `ESC` to close the window.)

When you are done, call `stop()` in the Script Editor or simply restart Isaac
Sim.

---

## 2. Launch Isaac Sim with a helper script

A convenience launcher is provided at `tools/run_zmq_msgpack.py`. It wraps the
usual Isaac Sim startup flags, loads a USD stage, and executes a helper Python
script from the repo.

```
python tools/run_zmq_msgpack.py \
    --usd /home/user/omniverse/is40/zmq-turtle-rate-camera.usd
```

By default, it uses `exts/isaacsim.zmq.bridge.examples/isaacsim/zmq/bridge/examples/scripts/zmqpublish.py`.
You can override with `--script` to use a different script (e.g., `zmqpublish_direct.py` for when the USD is already loaded).

Useful options:

- `--launcher` — override the default Isaac Sim launcher path.
- `--headless` — automatically switch to headless mode if it exists.
- `--extra ...` — forward additional arguments to the launcher (e.g. GPU options).

Once the window appears, the USD stage is loaded and the script executes,
instantiating the MsgPack annotator automatically. Use the same viewer command as
above to monitor frames.

---

## 3. Headless mode

The same launcher can start Isaac Sim without a GUI. Add `--headless` to switch
to headless mode:

```
python tools/run_zmq_msgpack.py \
    --headless \
    --usd /home/user/omniverse/is40/zmq-turtle-rate-camera.usd
```

In headless mode the MsgPack annotator runs exactly as in the GUI case, so you
can keep the same ZMQ subscriber. If you need to tweak simulation parameters or
log information, edit the script in `exts/isaacsim.zmq.bridge.examples/isaacsim/zmq/bridge/examples/scripts/`.

---

## Subscribers and Debugging

Two simple clients are included under `isaac-zmq-server/src/`:

- `simple_msgpack_camera_gui.py` — DearPyGui viewer (no OpenCV dependencies).
- `msgpack_camera_sub.py` — OpenCV-based script (requires an X/Qt environment).

Example GUI viewer usage:

```
python isaac-zmq-server/src/simple_msgpack_camera_gui.py \
    --ip 127.0.0.1 --port 5561 --topic camera/image \
    --width 1280 --height 720
```

If you prefer the OpenCV script, run it on a machine with a GUI stack (or use a
headless OpenCV build and save frames to disk).

---

## Camera Pose Control

The `zmqpublish.py` script automatically includes a **pose subscriber** that listens
for camera pose commands via ZMQ/MsgPack. This allows external applications (e.g.,
Gazebo plugins) to control the camera position and orientation in Isaac Sim.

### How It Works

When you run `zmqpublish.py`, it automatically starts a `ZMQPoseSubscriber` that:
- Subscribes to pose messages on a configurable port (default: `5562`)
- Receives pose data as `[x, y, z, roll, pitch, yaw]` or `{"x": ..., "y": ..., ...}`
- Applies the pose to the camera prim in real-time

### Configuration

Edit the pose subscriber settings in `zmqpublish.py`:

```python
# Pose subscriber configuration
POSE_SERVER_IP = "localhost"         # IP of the pose publisher
POSE_PORT = 5562                     # Port for pose messages (use 5556 for Gazebo)
POSE_TOPIC = "camera/pose"          # Topic for pose messages
```

**Note**: If using with a Gazebo plugin that publishes on port `5556`, change
`POSE_PORT = 5556` in the script.

### Using with Gazebo Plugin

The pose subscriber is compatible with Gazebo's `PublishPoseZMQPlugin` which
publishes pose messages in the format `[x, y, z, roll, pitch, yaw]`.

1. Ensure the Gazebo plugin is configured to publish on topic `camera/pose`
2. Update `POSE_PORT` in `zmqpublish.py` to match the Gazebo plugin's port (default: `5556`)
3. Set `POSE_SERVER_IP` to the IP address of the machine running Gazebo
4. The camera will automatically move when Gazebo publishes pose updates

### Testing with pose_publisher.py

A test script is provided to manually publish pose commands:

```bash
# Publish a single pose command
python isaac-zmq-server/src/pose_publisher.py \
    --x 1.0 --y 2.0 --z 3.0 \
    --roll 0.0 --pitch 0.5 --yaw 1.0 \
    --port 5562 \
    --once

# Publish continuously at 10 Hz
python isaac-zmq-server/src/pose_publisher.py \
    --x 1.0 --y 2.0 --z 3.0 \
    --roll 0.0 --pitch 0.5 --yaw 1.0 \
    --port 5562 \
    --rate 10.0
```

### Message Format

The pose subscriber accepts two message formats:

**Array format** (Gazebo-compatible):
```python
[x, y, z, roll, pitch, yaw]  # All values as floats
```

**Dictionary format**:
```python
{
    "x": 1.0,      # meters
    "y": 2.0,      # meters
    "z": 3.0,      # meters
    "roll": 0.0,   # radians (rotation around X)
    "pitch": 0.5,  # radians (rotation around Y)
    "yaw": 1.0     # radians (rotation around Z)
}
```

Both formats are automatically detected and parsed.

### Using in Script Editor

To add pose control when using the Script Editor (Section 1), add this to your script:

```python
from isaacsim.zmq.bridge.examples.core.ZMQPoseSubscriber import ZMQPoseSubscriber

# After creating the annotator, add:
pose_subscriber = ZMQPoseSubscriber(
    prim_path=CAMERA_PATH,
    server_ip="localhost",
    port=5562,
    topic="camera/pose",
)
pose_subscriber.start()
```

---

## Summary

- Use the Script Editor for quick experiments (Section 1).
- Use `tools/run_zmq_msgpack.py` to launch Isaac Sim with the MsgPack publisher
  and your USD stage (Section 2).
- Add `--headless` to run without a GUI (Section 3).
- Subscribe with either of the provided scripts to verify the stream.

The `ZMQMsgpackAnnotator` class is reusable—import it in your own missions or
extensions whenever you need a Gazebo-style MsgPack feed from Isaac Sim.

The `ZMQPoseSubscriber` enables bidirectional control, allowing external applications
to command camera poses in Isaac Sim, making it ideal for closed-loop systems and
hardware-in-the-loop testing.
