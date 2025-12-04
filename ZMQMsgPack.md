# ZMQ MsgPack Quickstart

This document covers how to stream camera frames from Isaac Sim using different
serialization formats and ZMQ patterns.

---

## Streaming Modes Overview

The ZMQ bridge supports three streaming modes, controlled by environment variables:

| Isaac Sim Config | Streaming Format | Socket Pattern | Server Tester |
|------------------|------------------|----------------|---------------|
| `ISAAC_ZMQ_SERIALIZATION` unset or `protobuf` | Complex Protobuf structure | PUSH → PULL | `example.py` |
| `ISAAC_ZMQ_SERIALIZATION=msgpack` | Complex MsgPack structure | PUSH → PULL | `example.py` |
| `ISAAC_ZMQ_SERIALIZATION=msgpack` + `ISAAC_ZMQ_SIMPLE_STREAM=1` | Topic + Raw BGR Image | PUB → SUB | `simple_msgpack_camera_gui.py` |

### Environment Variables

| Variable | Values | Description |
|----------|--------|-------------|
| `ISAAC_ZMQ_SERIALIZATION` | `msgpack` / `protobuf` (default) | Serialization format |
| `ISAAC_ZMQ_SIMPLE_STREAM` | `1` / `true` | Enable PUB/SUB mode for simple viewers |
| `ISAAC_ZMQ_TOPIC` | string (default: `camera/image`) | Topic name for simple stream mode |

### Data Formats

**Complex structure (modes 1 & 2):**
Contains full telemetry: `bbox2d`, `camera`, `clock`, `color_image`, `depth_image`

**Simple stream (mode 3):**
Multipart ZMQ message: `(topic, msgpack-packed BGR frame bytes)`
Matches Gazebo `camera2zmq.cpp` pattern for compatibility with existing viewers.

### Socket Patterns

**Modes 1 & 2 (PUSH/PULL):**
- Isaac Sim **connects** (PUSH socket) to server
- Server **binds** (PULL socket) on port

**Mode 3 - Simple Stream (PUB/SUB):**
- Isaac Sim **binds** (PUB socket) on port
- Viewer **connects** (SUB socket) to Isaac Sim

### Quick Start Examples

**Mode 1 - Protobuf (default):**
```bash
# No env vars needed, just start Isaac Sim
# Server:
python example.py
```

**Mode 2 - MsgPack with full structure:**
```bash
export ISAAC_ZMQ_SERIALIZATION=msgpack
# Start Isaac Sim
# Server:
python example.py
```

**Mode 3 - Simple stream for camera viewers:**
```bash
export ISAAC_ZMQ_SERIALIZATION=msgpack
export ISAAC_ZMQ_SIMPLE_STREAM=1
# Start Isaac Sim, load scene, start streaming
# Viewer:
python simple_msgpack_camera_gui.py --ip 127.0.0.1 --port 5561 --topic camera/image --width 720 --height 720
```

---

## ZMQMsgpackAnnotator (Script Editor Method)

This section covers using the `ZMQMsgpackAnnotator` class directly for custom
streaming scenarios:

1. Launch Isaac Sim normally and paste a small helper into the Script Editor.
2. Start Isaac Sim from the command line with a utility script.
3. Drive the same flow in headless mode.

The examples below assume you already built the project (`./build.sh`) and that
a subscriber is running on the **server side** to verify frames:

- **Complex stream** (PUSH/PULL): Use `example.py` from `isaac-zmq-server/src/`
- **Simple stream** (PUB/SUB): Use `simple_msgpack_camera_gui.py` from `isaac-zmq-server/src/`

---

## 1. Use the Script Editor inside Isaac Sim

1. Open your USD stage that contains a camera.
2. Open **Window → Script Editor**.
3. Paste the snippet below, adjust the camera path for your scene, and press **Run**.

> **Note:** This uses `ZMQMsgpackAnnotator` which streams via PUB/SUB (simple stream mode).
> Use `simple_msgpack_camera_gui.py` as the subscriber.

```python
import asyncio
import omni.kit.app
import omni.timeline

from isaacsim.zmq.bridge.examples.core.ZMQMsgpackAnnotator import ZMQMsgpackAnnotator

# Adjust camera path for your scene
CAMERA_PATH = "/World/Camera"
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
5. Run the viewer (in server container) to confirm:

```bash
python simple_msgpack_camera_gui.py \
    --ip <ISAAC_SIM_HOST_IP> --port 5561 --topic camera/image \
    --width 1280 --height 720
```

(Press `ESC` to close the window.)

When you are done, call `stop()` in the Script Editor or simply restart Isaac
Sim.

---

## 2. Using the Built-in Franka Example (Recommended)

The easiest way to test ZMQ streaming is with the built-in Franka robot example:

**Setup:**
```bash
# Set environment variables for your desired streaming mode
export ISAAC_ZMQ_SERIALIZATION=msgpack
export ISAAC_ZMQ_SIMPLE_STREAM=1  # Optional: for simple PUB/SUB mode

# Start Isaac Sim
```

**In Isaac Sim:**
1. Go to **Create → Isaac ZMQ Examples → Franka RMPFlow**
2. Click **"Reset World"**
3. Click **"Start Streaming"**

**Run the viewer:**
```bash
python isaac-zmq-server/src/simple_msgpack_camera_gui.py \
    --ip 127.0.0.1 --port 5561 --topic camera/image \
    --width 720 --height 720
```

---

## 3. Launch Isaac Sim with a helper script

A convenience launcher is provided at `tools/run_zmq_msgpack.py` for custom USD
stages or the Franka example. It enables the ZMQ bridge extension and auto-starts streaming.

**Available modes:**

| Mode | Command | Description |
|------|---------|-------------|
| GUI + custom USD | `--gui --usd X --camera Y` | Opens Isaac Sim with GUI, loads USD, starts streaming |
| Headless + custom USD | `--headless --usd X --camera Y` | No GUI, loads USD, starts streaming |
| Headless + Franka | `--franka` | No GUI, loads Franka example, starts streaming |
| Basic launch | (no flags) | Just opens Isaac Sim with extension enabled |

**Available options:**

| Option | Description |
|--------|-------------|
| `--gui` | Run with GUI and auto-start streaming (requires `--usd` and `--camera`) |
| `--headless` | Run without GUI (requires `--usd` and `--camera`) |
| `--franka` | Run the Franka example (headless) |
| `--usd PATH` | USD stage to load |
| `--camera PATH` | Camera prim path (e.g., `/World/Camera`) |
| `--width N` | Camera resolution width (default: 720) |
| `--height N` | Camera resolution height (default: 720) |
| `--port N` | ZMQ port (default: 5561) |
| `--topic NAME` | MsgPack topic (default: `camera/image`) |
| `--launcher PATH` | Override Isaac Sim launcher path |
| `--extra ...` | Additional arguments for the launcher |

---

## 4. Examples

**GUI mode with custom USD:**
```bash
export ISAAC_ZMQ_SERIALIZATION=msgpack
export ISAAC_ZMQ_SIMPLE_STREAM=1

python tools/run_zmq_msgpack.py --gui \
    --usd /path/to/scene.usd \
    --camera /World/Camera \
    --width 1280 --height 720
```

**Headless mode with custom USD:**
```bash
export ISAAC_ZMQ_SERIALIZATION=msgpack
export ISAAC_ZMQ_SIMPLE_STREAM=1

python tools/run_zmq_msgpack.py --headless \
    --usd /path/to/scene.usd \
    --camera /World/Camera
```

**Franka example (headless):**
```bash
export ISAAC_ZMQ_SERIALIZATION=msgpack
export ISAAC_ZMQ_SIMPLE_STREAM=1

python tools/run_zmq_msgpack.py --franka
```

**Viewer (in server container):**
```bash
python simple_msgpack_camera_gui.py \
    --ip <ISAAC_SIM_HOST_IP> --port 5561 --topic camera/image \
    --width 1280 --height 720
```

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
