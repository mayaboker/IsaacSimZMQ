#!/bin/bash
# Run container built from Dockerfile.minimal (see build_minimal.sh).
# For OpenCV windows, allow local X11 (same idea as run_server.sh).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

xhost +local: 2>/dev/null || true

exec docker run --rm -it --network host \
  -e DISPLAY="${DISPLAY:-}" \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v "${SCRIPT_DIR}/src:/app:ro" \
  isaac-zmq-server-minimal \
  "$@"
