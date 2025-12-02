xhost +local:
docker run --gpus all --network host \
       -e DISPLAY=$DISPLAY \
       -e NVIDIA_DRIVER_CAPABILITIES=all \
       -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
       -e XAUTHORITY=$XAUTHORITY \
       -v $XAUTHORITY:$XAUTHORITY \
       -v ./src:/isaac-zmq-server/src \
       --privileged \
       -it --rm \
        isaac-zmq-server bash
