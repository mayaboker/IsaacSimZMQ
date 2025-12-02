# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import asyncio
import msgpack
import numpy as np
import zmq.asyncio

import omni.replicator.core as rep
from omni.replicator.core.scripts.utils import viewport_manager


class ZMQMsgpackAnnotator:
    """Captures frames from a camera render product and publishes them over ZMQ using MsgPack."""

    def __init__(self, camera_path: str, resolution=(1280, 720),
                 ip="localhost", port=5561, topic="camera/image"):
        self._camera_path = camera_path
        self._width, self._height = resolution
        self._topic = topic.encode("utf-8")

        # ZMQ PUB socket
        self._ctx = zmq.asyncio.Context.instance()
        self._sock = self._ctx.socket(zmq.PUB)
        self._sock.bind(f"tcp://*:{port}")
        print(f"ZMQMsgpackAnnotator: binding on port {port}")

        # Create / fetch render product for the camera
        name = f"{camera_path.split('/')[-1]}_rp_msgpack"
        rp = viewport_manager.get_render_product(camera_path, resolution, False, name)
        self._render_product_path = rp.hydra_texture.get_render_product_path()

        # Annotator to pull RGB frames on CPU
        self._annotator = rep.AnnotatorRegistry.get_annotator("rgb", device="cpu")
        self._annotator.attach(self._render_product_path)

    async def publish(self):
        """Grab the latest frame, convert to Gazebo-style grayscale BGR, pack, and publish."""
        frame = self._annotator.get_data()
        if frame is None:
            print(f"No frame found")
            return

        arr = np.array(frame, copy=False)
        if arr.shape[-1] == 4:  # RGBA
            rgb = arr[..., :3]
        else:
            rgb = arr

        # Convert to grayscale then back to BGR (matches Gazebo example)
        gray = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]).astype(np.uint8)
        bgr = np.repeat(gray[..., None], 3, axis=2)

        payload = msgpack.packb(bgr.tobytes(), use_bin_type=True)
        await self._sock.send_multipart([self._topic, payload])

    def destroy(self):
        try:
            self._annotator.detach(self._render_product_path)
        except Exception:
            pass
        self._sock.close()
