#!/bin/bash
# No local image build: uses public python:3.11-slim-bookworm and pip-installs deps each run.
# First run downloads packages; use a named volume if you want pip caching between runs.
#
# Usage:
#   ./run_viewer_pull_only.sh --ip 0.0.0.0 --port 5561 --topic camera/image --width 720 --height 720
#
# Requires: Docker, network for first-time pip pulls.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

xhost +local: 2>/dev/null || true

IMAGE="${ISAAC_ZMQ_SERVER_BASE_IMAGE:-python:3.11-slim-bookworm}"

exec docker run --rm -it --network host \
  -e DISPLAY="${DISPLAY:-}" \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v "${SCRIPT_DIR}/src:/app:ro" \
  "${IMAGE}" \
  bash -c 'set -e
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libxcb1 libxkbcommon0 \
      >/dev/null
    rm -rf /var/lib/apt/lists/*
    pip install --no-cache-dir -q pyzmq==26.4.0 msgpack==1.0.8 opencv-python==4.10.0.84 protobuf==5.26.0
    exec python /app/msgpack_camera_viewer.py "$@"
  ' bash "$@"
