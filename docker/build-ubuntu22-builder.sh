docker build -f Dockerfile.ubuntu22-builder \
  --build-arg UID=$(id -u) \
  --build-arg GID=$(id -g) \
  --build-arg USER_NAME=$(id -un) \
  -t isaacsimzmq-builder:22.04 .
