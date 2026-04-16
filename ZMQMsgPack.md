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
# Viewer / receiver:
python isaac-zmq-server/src/msgpack_camera_viewer.py --ip 0.0.0.0 --port 5561 --width 720 --height 720
#
# Or use the full example server:
python isaac-zmq-server/src/example.py
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
| `--pose-port N` | ZMQ port Isaac Sim listens on for pose commands (default: `5562`) |
| `--pose-topic NAME` | Topic for incoming pose commands (default: `camera/pose`) |
| `--pose-ip HOST` | IP address of the external pose publisher Isaac Sim should connect to |
| `--launcher PATH` | Override Isaac Sim launcher path |
| `--extra ...` | Additional arguments for the launcher |

### Port Mapping for `run_zmq_msgpack.py`

The helper script configures two independent channels:

- `--port`: the **image stream output** port from Isaac Sim
- `--pose-port`: the **pose command input** port that Isaac Sim listens to

For example:

```bash
python3 /home/user/IsaacSimZMQ/tools/run_zmq_msgpack.py \
    --gui \
    --usd /home/user/ov/is40-zmq.usd \
    --camera /World/Camera \
    --width 720 --height 720 \
    --pose-port 5556 \
    --pose-ip 10.0.0.16
```

means:

- Isaac Sim publishes images on port `5561` because `--port` was not provided, so the default is used
- Isaac Sim subscribes to pose commands on port `5556`
- Isaac Sim expects the pose publisher to be running on host `10.0.0.16`

The equivalent fully explicit command is:

```bash
python3 /home/user/IsaacSimZMQ/tools/run_zmq_msgpack.py \
    --gui \
    --usd /home/user/ov/is40-zmq.usd \
    --camera /World/Camera \
    --width 720 --height 720 \
    --port 5561 \
    --pose-port 5556 \
    --pose-ip 10.0.0.16
```

---

## 4. Examples

**GUI mode with custom USD (full MsgPack stream, PUSH/PULL):**
```bash
export ISAAC_ZMQ_SERIALIZATION=msgpack

python tools/run_zmq_msgpack.py --gui \
    --usd /path/to/scene.usd \
    --camera /World/Camera \
    --width 1280 --height 720
```

**Headless mode with custom USD (full MsgPack stream, PUSH/PULL):**
```bash
export ISAAC_ZMQ_SERIALIZATION=msgpack

python tools/run_zmq_msgpack.py --headless \
    --usd /path/to/scene.usd \
    --camera /World/Camera
```

**Franka example (headless, full MsgPack stream):**
```bash
export ISAAC_ZMQ_SERIALIZATION=msgpack

python tools/run_zmq_msgpack.py --franka
```

**Viewer for full MsgPack stream (in server container):**
```bash
python isaac-zmq-server/src/msgpack_camera_viewer.py \
    --ip 0.0.0.0 --port 5561 \
    --width 1280 --height 720
```

**Simple stream example (PUB/SUB):**
```bash
export ISAAC_ZMQ_SERIALIZATION=msgpack
export ISAAC_ZMQ_SIMPLE_STREAM=1

python tools/run_zmq_msgpack.py --gui \
    --usd /path/to/scene.usd \
    --camera /World/Camera \
    --width 1280 --height 720
```

**Viewer for simple stream (PUB/SUB):**
```bash
python simple_msgpack_camera_gui.py \
    --ip <ISAAC_SIM_HOST_IP> --port 5561 --topic camera/image \
    --width 1280 --height 720
```

---

## Subscribers and Debugging

Several clients are included under `isaac-zmq-server/src/`:

| Client | Socket | Format | Description |
|--------|--------|--------|-------------|
| `example.py` | PULL | Protobuf or Complex MsgPack | Full-featured GUI with robot control |
| `msgpack_camera_viewer.py` | PULL | Complex MsgPack | Lightweight OpenCV viewer for `run_zmq_msgpack.py --gui/--headless` |
| `simple_msgpack_camera_gui.py` | SUB | Simple MsgPack (Topic + BGR) | Lightweight DearPyGui viewer |
| `msgpack_camera_sub.py` | SUB | Simple MsgPack | OpenCV-based viewer |

**For complex stream (PUSH/PULL):**
```bash
python isaac-zmq-server/src/msgpack_camera_viewer.py \
    --ip 0.0.0.0 --port 5561 \
    --width 1280 --height 720
```

Alternative full-featured receiver:

```bash
python isaac-zmq-server/src/example.py
```

`msgpack_camera_viewer.py` is appropriate when Isaac Sim is started with:

- `ISAAC_ZMQ_SERIALIZATION=msgpack`
- `ISAAC_ZMQ_SIMPLE_STREAM` unset

It binds a `PULL` socket, so it is the matching receiver for the default `run_zmq_msgpack.py --gui` flow.

**For simple stream (PUB/SUB):**
```bash
python isaac-zmq-server/src/simple_msgpack_camera_gui.py \
    --ip <ISAAC_SIM_HOST_IP> --port 5561 --topic camera/image \
    --width 1280 --height 720
```
Requires `ISAAC_ZMQ_SIMPLE_STREAM=1` on the Isaac Sim side.

---

## Camera Pose Control

The helper launch flow (`tools/run_zmq_msgpack.py --gui ...`) automatically configures
a **pose subscriber** inside Isaac Sim. This allows external applications (for example,
Gazebo plugins or test scripts) to control the camera position and orientation via ZMQ/MsgPack.

### How It Works

When you run `tools/run_zmq_msgpack.py` with `--gui` or `--headless` and provide a
USD stage plus camera path, the executed Isaac-side script starts a `ZMQPoseSubscriber` that:
- Subscribes to pose messages on a configurable port (default: `5562`)
- Receives pose data as `[x, y, z, roll, pitch, yaw]` or `{"x": ..., "y": ..., ...}`
- Applies the pose to the camera prim in real-time

### Configuration

These settings are controlled from the launcher command line:

```bash
python tools/run_zmq_msgpack.py --gui \
    --usd /path/to/scene.usd \
    --camera /World/Camera \
    --pose-port 5556 \
    --pose-ip 10.0.0.16 \
    --pose-topic camera/pose
```

This means:

- Isaac Sim listens for pose commands on port `5556`
- Isaac Sim connects to the pose publisher at `10.0.0.16`
- Isaac Sim subscribes to topic `camera/pose`

### Using with Gazebo Plugin

The pose subscriber is compatible with Gazebo's `PublishPoseZMQPlugin` which
publishes pose messages in the format `[x, y, z, roll, pitch, yaw]`.

1. Ensure the Gazebo plugin is configured to publish on topic `camera/pose`
2. Set `--pose-port` to match the Gazebo plugin's port (often `5556`)
3. Set `--pose-ip` to the IP address of the machine running Gazebo
4. The camera will automatically move when Gazebo publishes pose updates

### Testing with pose_publisher.py

A test script is provided to manually publish pose commands:

```bash
# Publish a single pose command
python isaac-zmq-server/src/pose_publisher.py \
    --x 1.0 --y 2.0 --z 3.0 \
    --roll 0.0 --pitch 0.5 --yaw 1.0 \
    --port 5556 \
    --once

# Publish continuously at 10 Hz
python isaac-zmq-server/src/pose_publisher.py \
    --x 1.0 --y 2.0 --z 3.0 \
    --roll 0.0 --pitch 0.5 --yaw 1.0 \
    --port 5556 \
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
  and your USD stage (Section 3).
- Add `--headless` to run without a GUI (Section 3).
- For the default `run_zmq_msgpack.py --gui/--headless` flow, use `msgpack_camera_viewer.py`.
- Use `simple_msgpack_camera_gui.py` only when `ISAAC_ZMQ_SIMPLE_STREAM=1` is enabled.
- Treat `--port` and `--pose-port` as separate channels: image output vs pose input.

The `ZMQMsgpackAnnotator` class is reusable—import it in your own missions or
extensions whenever you need a Gazebo-style MsgPack feed from Isaac Sim.

The `ZMQPoseSubscriber` enables bidirectional control, allowing external applications
to command camera poses in Isaac Sim, making it ideal for closed-loop systems and
hardware-in-the-loop testing.
