# Isaac Sim ZMQ Bridge — Quick Refresher

## 1. Build the Extension

```bash
cd /home/user/git/IsaacSimZMQ
./build.sh
```
Bundles the Python dependencies (protobuf, msgpack, pyzmq) for the extension.

---

## 2. Launch Isaac Sim with the Bridge

### Workstation UI
1. Start Isaac Sim.
2. Window → Extensions: add `/home/user/git/IsaacSimZMQ/exts` and enable `ISAAC SIM ZMQ BRIDGE EXAMPLES`.
3. Load an example (Menu → Create → Isaac ZMQ Examples → Franka …).
4. _Optional_: enable MsgPack before launching Isaac Sim:
   ```bash
   export ISAAC_ZMQ_SERIALIZATION=msgpack
   ```
   PowerShell: `$Env:ISAAC_ZMQ_SERIALIZATION = "msgpack"`

### Headless mode
```bash
export ISAAC_ZMQ_SERIALIZATION=msgpack   # optional
env ISAACSIM_PYTHON=/path/to/isaac-sim/python.sh
$ISAACSIM_PYTHON exts/isaacsim.zmq.bridge.examples/isaacsim/zmq/bridge/examples/example_headless.py --ext-folder ./exts
```

---

## 3. Start a ZMQ Server

### Python GUI server (auto-detects Protobuf/MsgPack)
```bash
cd isaac-zmq-server
./build_server.sh
./run_server.sh
# inside container
python example.py
```
- Default ports: camera 5561, controls 5557/5559/5560.
- For multi-camera: `python example.py --subscribe_only 1 --port 5591`.

### Python MsgPack-only headless demo
```bash
python isaac-zmq-server/src/example_msgpack.py --port 5561
```

### C++ MsgPack server (viewer + optional control publishers)
```bash
cd isaac-zmq-server/src/cpp
mkdir build && cd build
cmake ..
make -j$(nproc)  # adjust -j for your CPU
./msgpack_server 5561 5557 5559 5560 1 1
```
- Syntax: `./msgpack_server <camera_port> <ctrl_cam_port> <settings_port> <franka_port> <publish_control> <enable_gui>`
- To disable publishers, set port ≤ 0 or pass `0` as `publish_control`.
- Docker GUI: `xhost +local:` then `docker run -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix:ro …`

---

## 4. Start Streaming in Isaac Sim
1. Reset World.
2. Click **Start Streaming**.
3. Watch the Isaac Sim console for `Using serialization: msgpack` (if enabled) and the server logs for received frames.

---

## 5. Port Alignment
Keep ports synchronized between Isaac Sim and your server:
- Camera stream: 5561 (main), 5591 (gripper).
- Control: 5557 (camera control), 5559 (settings), 5560 (Franka).
Adjust both sides if you change them.

---

Happy streaming!

