# Example container to mock as Server for Isaac Sim ZMQ Bridge


This example container provides a starting point for building your own server to communicate with Isaac Sim using ZMQ and Protobuf.
You can use it to run and test your CV models, or any other task that will form a closed loop with Isaac Sim.

The server also provides a GUI to visualize the data sensor messages being recived, using the [DearPyGui](https://github.com/hoffstadt/DearPyGui) library, which is a simple and easy to use and extend.

---

## Instructions

### Standalone / lightweight Docker (no CUDA image)

If you cannot use the default `Dockerfile` (CUDA + PyTorch + DearPyGui), use one of these:

1. **Minimal image (recommended):** small Debian-based image, only ZMQ/msgpack/OpenCV/protobuf — enough for `msgpack_camera_viewer.py` and protobuf workflows.

   ```bash
   cd isaac-zmq-server
   ./build_minimal.sh
   ./run_minimal.sh
   # then e.g.:
   python /app/msgpack_camera_viewer.py --ip 0.0.0.0 --port 5561 --topic camera/image --width 720 --height 720
   ```

2. **No local image build:** pulls `python:3.11-slim-bookworm` and installs deps at container start (needs network the first time).

   ```bash
   cd isaac-zmq-server
   ./run_viewer_pull_only.sh --ip 0.0.0.0 --port 5561 --topic camera/image --width 720 --height 720
   ```

The full `Dockerfile` remains for DearPyGui / GPU-heavy examples (`example.py` with torch).

#### Server (Python inside a contatiner)

1. Build the docker image and run it
```bash
cd isaac-zmq-server
./build_server.sh
./run_server.sh
```
2. Inside the container, run the server
```bash
python example.py
```
3. Optional - For the Franka RMPFlow (Multi Camera), start two servers


```bash
# Inside the container
python example.py # server 1 for main camera
# in a second container
python example.py --subscribe_only 1 --port 5591 # server 2 for gripper camera
```
