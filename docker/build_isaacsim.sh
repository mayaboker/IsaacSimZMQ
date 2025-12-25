#!/bin/bash
# Build Isaac Sim + ZMQ Extension Docker image
#
# Prerequisites:
# 1. Docker with NVIDIA Container Toolkit
# 2. NGC authentication (for Isaac Sim base image):
#    docker login nvcr.io
#    Username: $oauthtoken
#    Password: <your NGC API key from https://ngc.nvidia.com/setup>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

IMAGE_NAME="${1:-isaacsim-zmq}"
IMAGE_TAG="${2:-5.0}"

echo "=========================================="
echo "Building Isaac Sim + ZMQ Extension"
echo "=========================================="
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "Project: ${PROJECT_DIR}"
echo ""

# Check if logged into NGC
if ! docker manifest inspect nvcr.io/nvidia/isaac-sim:4.5.0 > /dev/null 2>&1; then
    echo "ERROR: Cannot access NGC. Please login first:"
    echo "  docker login nvcr.io"
    echo "  Username: \$oauthtoken"
    echo "  Password: <NGC API Key>"
    exit 1
fi

# Build the extension first
echo "Building extension..."
cd "$PROJECT_DIR"
if [ -f "./build.sh" ]; then
    ./build.sh
fi

# Build Docker image
echo ""
echo "Building Docker image..."
docker build \
    -f docker/Dockerfile.isaacsim \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    .

echo ""
echo "=========================================="
echo "Build complete!"
echo "=========================================="
echo ""
echo "Run with GUI:"
echo "  xhost +local:docker"
echo "  docker run --rm -it --gpus all \\"
echo "      -e DISPLAY=\$DISPLAY \\"
echo "      -v /tmp/.X11-unix:/tmp/.X11-unix \\"
echo "      ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "Run headless with custom USD:"
echo "  docker run --rm -it --gpus all \\"
echo "      -p 5561:5561 \\"
echo "      -v /path/to/usd:/data \\"
echo "      ${IMAGE_NAME}:${IMAGE_TAG} \\"
echo "      python tools/run_generic_headless.py"
echo ""

