#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
docker build -f Dockerfile.minimal -t isaac-zmq-server-minimal .
