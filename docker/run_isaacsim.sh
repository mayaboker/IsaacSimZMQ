#!/bin/bash
# Run Isaac Sim + ZMQ Extension Docker container
#
# Usage:
#   ./run_isaacsim.sh                     # GUI mode, Franka example
#   ./run_isaacsim.sh --headless          # Headless mode, Franka example
#   ./run_isaacsim.sh --usd /data/x.usd --camera /World/Camera  # Custom USD

set -e

IMAGE_NAME="${ISAACSIM_ZMQ_IMAGE:-isaacsim-zmq:5.0}"
HOST_IP="${HOST_IP:-$(hostname -I | awk '{print $1}')}"

# Default ports
STREAM_PORT="${STREAM_PORT:-5561}"
POSE_PORT="${POSE_PORT:-5562}"

# Check for headless mode
HEADLESS=false
for arg in "$@"; do
    if [ "$arg" == "--headless" ]; then
        HEADLESS=true
        break
    fi
done

# Build docker run command
DOCKER_CMD="docker run --rm -it --gpus all"

# Add port mappings
DOCKER_CMD+=" -p ${STREAM_PORT}:${STREAM_PORT}"
DOCKER_CMD+=" -p ${POSE_PORT}:${POSE_PORT}"

# Add environment variables
DOCKER_CMD+=" -e ISAAC_ZMQ_SERIALIZATION=msgpack"
DOCKER_CMD+=" -e ISAAC_ZMQ_SIMPLE_STREAM=1"
DOCKER_CMD+=" -e NVIDIA_DRIVER_CAPABILITIES=all"

# Add X11 forwarding for GUI mode
if [ "$HEADLESS" = false ]; then
    xhost +local:docker 2>/dev/null || true
    DOCKER_CMD+=" -e DISPLAY=$DISPLAY"
    DOCKER_CMD+=" -v /tmp/.X11-unix:/tmp/.X11-unix"
fi

# Add USD data volume if provided
if [ -n "$USD_DIR" ]; then
    DOCKER_CMD+=" -v ${USD_DIR}:/data"
fi

# Add the image
DOCKER_CMD+=" ${IMAGE_NAME}"

# Add arguments
DOCKER_CMD+=" $@"

echo "=========================================="
echo "Running Isaac Sim + ZMQ Extension"
echo "=========================================="
echo "Image: ${IMAGE_NAME}"
echo "Stream port: ${STREAM_PORT}"
echo "Pose port: ${POSE_PORT}"
echo "Host IP: ${HOST_IP}"
echo ""
echo "Command: ${DOCKER_CMD}"
echo ""

# Run
eval $DOCKER_CMD

