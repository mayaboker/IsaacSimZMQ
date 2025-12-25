#!/bin/bash
# Create a standalone tarball of Isaac Sim + ZMQ Extension
# 
# This copies the essential files for deployment WITHOUT Docker.
# Target machine requirements:
# - Ubuntu 22.04 (same as build machine)
# - NVIDIA GPU with compatible drivers
# - Isaac Sim dependencies (or copy the full Isaac Sim installation)
#
# Usage:
#   ./pack_standalone.sh /path/to/isaacsim5.0 output.tar.gz

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

ISAAC_SIM_PATH="${1:-/home/user/isaacsim5.0}"
OUTPUT_FILE="${2:-isaacsim-zmq-standalone.tar.gz}"
TEMP_DIR=$(mktemp -d)

echo "=========================================="
echo "Packing Isaac Sim + ZMQ Extension"
echo "=========================================="
echo "Isaac Sim: ${ISAAC_SIM_PATH}"
echo "Output: ${OUTPUT_FILE}"
echo "Temp: ${TEMP_DIR}"
echo ""

# Verify Isaac Sim path
if [ ! -f "${ISAAC_SIM_PATH}/isaac-sim.sh" ]; then
    echo "ERROR: Isaac Sim not found at ${ISAAC_SIM_PATH}"
    echo "Please provide the path to your Isaac Sim installation"
    exit 1
fi

# Build extension first
echo "Building extension..."
cd "$PROJECT_DIR"
./build.sh

# Create package structure
PACK_DIR="${TEMP_DIR}/isaacsim-zmq"
mkdir -p "${PACK_DIR}"

echo "Copying extension files..."

# Copy extensions
cp -r "${PROJECT_DIR}/exts/isaacsim.zmq.bridge" "${PACK_DIR}/"
cp -r "${PROJECT_DIR}/exts/isaacsim.zmq.bridge.examples" "${PACK_DIR}/"

# Copy tools
cp -r "${PROJECT_DIR}/tools" "${PACK_DIR}/"

# Copy assets
cp -r "${PROJECT_DIR}/assets" "${PACK_DIR}/"

# Copy documentation
cp -r "${PROJECT_DIR}/docs" "${PACK_DIR}/"
cp "${PROJECT_DIR}/README.md" "${PACK_DIR}/"
cp "${PROJECT_DIR}/ZMQMsgPack.md" "${PACK_DIR}/"

# Create install script
cat > "${PACK_DIR}/install.sh" << 'EOF'
#!/bin/bash
# Install IsaacSimZMQ extension into Isaac Sim
#
# Usage:
#   ./install.sh /path/to/isaacsim5.0

set -e

ISAAC_SIM_PATH="${1:-/home/$USER/.local/share/ov/pkg/isaac-sim-5.0.0}"

if [ ! -f "${ISAAC_SIM_PATH}/isaac-sim.sh" ]; then
    echo "ERROR: Isaac Sim not found at ${ISAAC_SIM_PATH}"
    echo "Usage: ./install.sh /path/to/isaacsim"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTS_DIR="${ISAAC_SIM_PATH}/exts"

echo "Installing IsaacSimZMQ extensions to ${EXTS_DIR}..."

# Copy extensions
cp -r "${SCRIPT_DIR}/isaacsim.zmq.bridge" "${EXTS_DIR}/"
cp -r "${SCRIPT_DIR}/isaacsim.zmq.bridge.examples" "${EXTS_DIR}/"

echo ""
echo "Installation complete!"
echo ""
echo "To use, launch Isaac Sim and enable extensions:"
echo "  1. Window → Extensions"
echo "  2. Search for 'zmq'"
echo "  3. Enable both extensions"
echo ""
echo "Or use the launcher script:"
echo "  export ISAAC_ZMQ_SERIALIZATION=msgpack"
echo "  export ISAAC_ZMQ_SIMPLE_STREAM=1"
echo "  python3 ${SCRIPT_DIR}/tools/run_zmq_msgpack.py --gui --usd /path/to/scene.usd --camera /World/Camera"
EOF
chmod +x "${PACK_DIR}/install.sh"

# Create run script
cat > "${PACK_DIR}/run.sh" << 'EOF'
#!/bin/bash
# Quick-run script for IsaacSimZMQ
#
# Usage:
#   ./run.sh /path/to/isaacsim --gui --usd /path/to/scene.usd --camera /World/Camera

ISAAC_SIM_PATH="${1:-/home/$USER/.local/share/ov/pkg/isaac-sim-5.0.0}"
shift

export ISAAC_ZMQ_SERIALIZATION=msgpack
export ISAAC_ZMQ_SIMPLE_STREAM=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"

python3 "${SCRIPT_DIR}/tools/run_zmq_msgpack.py" "$@"
EOF
chmod +x "${PACK_DIR}/run.sh"

# Create tarball
echo ""
echo "Creating tarball..."
cd "${TEMP_DIR}"
tar -czf "${PROJECT_DIR}/${OUTPUT_FILE}" isaacsim-zmq

# Cleanup
rm -rf "${TEMP_DIR}"

echo ""
echo "=========================================="
echo "Package created: ${OUTPUT_FILE}"
echo "=========================================="
echo ""
echo "To deploy on target machine:"
echo "  1. Copy ${OUTPUT_FILE} to target"
echo "  2. tar -xzf ${OUTPUT_FILE}"
echo "  3. cd isaacsim-zmq"
echo "  4. ./install.sh /path/to/isaacsim"
echo ""

