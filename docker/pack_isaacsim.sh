#!/bin/bash
# Pack a full Isaac Sim installation for transfer.
#
# Usage:
#   ./docker/pack_isaacsim.sh /path/to/isaacsim5.0 [output.tar.gz]
#
# Examples:
#   ./docker/pack_isaacsim.sh /home/user/isaacsim5.0
#   ./docker/pack_isaacsim.sh /home/user/isaacsim5.0 isaacsim-5.0-full.tar.gz

set -euo pipefail

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
    echo "Usage: $0 /path/to/isaacsim5.0 [output.tar.gz]"
    exit 1
fi

ISAAC_SIM_PATH="${1%/}"
if [ ! -d "$ISAAC_SIM_PATH" ]; then
    echo "ERROR: Directory not found: $ISAAC_SIM_PATH"
    exit 1
fi

if [ ! -f "${ISAAC_SIM_PATH}/isaac-sim.sh" ]; then
    echo "ERROR: ${ISAAC_SIM_PATH} does not look like an Isaac Sim install (isaac-sim.sh missing)."
    exit 1
fi

ISAAC_DIR_NAME="$(basename "$ISAAC_SIM_PATH")"
DEFAULT_OUTPUT="${ISAAC_DIR_NAME}-full.tar.gz"
OUTPUT_FILE="${2:-$DEFAULT_OUTPUT}"

echo "=========================================="
echo "Packing full Isaac Sim installation"
echo "=========================================="
echo "Source: ${ISAAC_SIM_PATH}"
echo "Output: ${OUTPUT_FILE}"
echo ""
echo "Calculating source size..."
du -sh "$ISAAC_SIM_PATH" || true
echo ""

PARENT_DIR="$(dirname "$ISAAC_SIM_PATH")"
ABS_OUTPUT="$(realpath -m "$OUTPUT_FILE")"

echo "Creating tarball (this can take a while)..."
tar -C "$PARENT_DIR" -czf "$ABS_OUTPUT" "$ISAAC_DIR_NAME"

echo ""
echo "Done."
echo "Archive created at: ${ABS_OUTPUT}"
du -sh "$ABS_OUTPUT" || true
echo ""
echo "Transfer this archive to your standalone machine, then extract:"
echo "  tar -xzf $(basename "$ABS_OUTPUT")"
echo ""
echo "After extraction, verify launcher exists:"
echo "  ls ${ISAAC_DIR_NAME}/isaac-sim.sh"
