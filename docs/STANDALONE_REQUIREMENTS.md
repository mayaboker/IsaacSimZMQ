# Standalone Target Machine Requirements

This page describes the software required on a target machine when deploying a
standalone package produced by `docker/pack_standalone.sh`.

It applies to running:

- Isaac Sim with the `isaacsim.zmq.bridge` extensions
- ZMQ camera streaming and optional pose control

## 1. Operating System

- Ubuntu 22.04 (recommended, same as build machine)
- `bash` shell available

## 2. GPU and Driver

- NVIDIA GPU supported by Isaac Sim 5.0.0
- Compatible NVIDIA driver installed and working (`nvidia-smi` succeeds)

See official Isaac Sim hardware requirements:
[Isaac Sim Requirements](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html)

## 3. Isaac Sim Installation

- Isaac Sim 5.0.0 installed on target machine
- Launcher present at: `<ISAAC_SIM_PATH>/isaac-sim.sh`

Examples:

- `/home/<user>/isaacsim5.0`
- `/home/<user>/.local/share/ov/pkg/isaac-sim-5.0.0`

## 4. Python Runtime

- Python 3 available on PATH (`python3`)
- Standard system tools: `tar`, `cp`, `chmod`

## 5. Network and Ports

Open and route ports according to your deployment topology:

- Image stream output from Isaac Sim: default `5561` (`--port`)
- Pose input to Isaac Sim: default `5562` (`--pose-port`)
- Control topic default: `camera/pose` (`--pose-topic`)

If using custom values, update both producer and consumer sides consistently.

## 6. Optional GUI Dependencies

For GUI workflows (Isaac GUI and OpenCV/Qt viewers):

- X11/desktop environment available
- Display permissions configured (`xhost` as needed for containers)
- Qt/XCB runtime libraries available in viewer environment

For headless workflows, GUI dependencies can be omitted.

## 7. Stream Mode Compatibility

Choose a single stream mode and match receiver scripts accordingly:

- Full stream (default): `ISAAC_ZMQ_SERIALIZATION=msgpack` and no `ISAAC_ZMQ_SIMPLE_STREAM`
  - Isaac socket pattern: PUSH -> receiver must be PULL
  - Typical receiver: `isaac-zmq-server/src/msgpack_camera_viewer.py`
- Simple stream: `ISAAC_ZMQ_SERIALIZATION=msgpack` + `ISAAC_ZMQ_SIMPLE_STREAM=1`
  - Isaac socket pattern: PUB -> receiver must be SUB
  - Typical receiver: `isaac-zmq-server/src/simple_msgpack_camera_gui.py`

## 8. Deployment Checklist

Before first run on target machine:

1. Confirm `nvidia-smi` works.
2. Confirm `<ISAAC_SIM_PATH>/isaac-sim.sh` exists.
3. Extract standalone tarball.
4. Run `./install.sh <ISAAC_SIM_PATH>` from extracted package.
5. Launch with `./run.sh [<ISAAC_SIM_PATH>] ...` (generated inside package).
6. Start matching receiver script for selected stream mode.

## 9. Notes for This Repository

- Source repo launcher (development workflow):
  - `python3 tools/run_zmq_msgpack.py ...`
- Generated standalone launcher (packaged workflow):
  - `isaacsim-zmq/run.sh` after extracting packaged tarball

The generated `run.sh` is not a file in the source repository; it is created by
`docker/pack_standalone.sh` inside the packaged output.
