# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

"""
ZMQ Pose Subscriber for receiving camera pose commands via ZMQ/MsgPack.

This subscriber listens for pose messages on a specified topic and applies
the pose (x, y, z, roll, pitch, yaw) to a USD prim (typically a camera).
"""

import asyncio
import msgpack
import zmq.asyncio
import numpy as np
from pxr import Usd, UsdGeom, Gf

import carb


class ZMQPoseSubscriber:
    """Subscribes to ZMQ pose messages and applies them to a USD prim."""

    def __init__(self, prim_path: str, server_ip: str = "localhost",
                 port: int = 5562, topic: str = "camera/pose"):
        """
        Initialize the pose subscriber.

        Args:
            prim_path: USD path to the prim to control (e.g., camera path)
            server_ip: IP address of the ZMQ publisher
            port: Port number for the ZMQ SUB socket
            topic: Topic name to subscribe to (default: "camera/pose")
        """
        self._prim_path = prim_path
        self._topic = topic.encode("utf-8")
        self._server_ip = server_ip
        self._port = port

        # ZMQ SUB socket
        self._ctx = zmq.asyncio.Context.instance()
        self._sock = self._ctx.socket(zmq.SUB)
        self._sock.setsockopt(zmq.SUBSCRIBE, self._topic)
        self._sock.connect(f"tcp://{server_ip}:{port}")
        self._sock.set_hwm(1)  # Only buffer 1 message

        print(f"ZMQPoseSubscriber: Connected to tcp://{server_ip}:{port}, subscribed to topic '{topic}'")

        # Get USD context
        import omni.usd
        self._usd_context = omni.usd.get_context()
        self._stage = None

        # Task for receiving messages
        self._task = None
        self._running = False

    def _euler_to_quaternion(self, roll: float, pitch: float, yaw: float) -> Gf.Quatd:
        """
        Convert Euler angles (roll, pitch, yaw) to a quaternion.

        Uses ZYX (intrinsic) rotation order, which is common in robotics.

        Args:
            roll: Rotation around X axis (radians)
            pitch: Rotation around Y axis (radians)
            yaw: Rotation around Z axis (radians)

        Returns:
            Gf.Quatd: Quaternion representation
        """
        # Convert to quaternion using ZYX order (yaw-pitch-roll)
        cy = np.cos(yaw * 0.5)
        sy = np.sin(yaw * 0.5)
        cp = np.cos(pitch * 0.5)
        sp = np.sin(pitch * 0.5)
        cr = np.cos(roll * 0.5)
        sr = np.sin(roll * 0.5)

        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy

        return Gf.Quatd(w, x, y, z)

    def _apply_pose(self, x: float, y: float, z: float,
                    roll: float, pitch: float, yaw: float):
        """
        Apply pose to the USD prim.

        Args:
            x, y, z: Position in meters
            roll, pitch, yaw: Orientation in radians
        """
        # Get or refresh stage
        self._stage = self._usd_context.get_stage()
        if self._stage is None:
            carb.log_warn("ZMQPoseSubscriber: Stage not available")
            return

        # Get the prim
        prim = self._stage.GetPrimAtPath(self._prim_path)
        if not prim.IsValid():
            carb.log_warn(f"ZMQPoseSubscriber: Prim not found: {self._prim_path}")
            return

        # Get Xformable interface
        xformable = UsdGeom.Xformable(prim)
        if not xformable:
            carb.log_warn(f"ZMQPoseSubscriber: Prim is not xformable: {self._prim_path}")
            return

        # Convert Euler angles to quaternion
        quat = self._euler_to_quaternion(roll, pitch, yaw)

        # Find or create translate and orient ops
        translate_op = None
        orient_op = None

        # Check existing ops
        ops = xformable.GetOrderedXformOps()
        for op in ops:
            if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
                translate_op = op
            elif op.GetOpType() == UsdGeom.XformOp.TypeOrient:
                orient_op = op

        # Create ops if they don't exist
        if translate_op is None:
            translate_op = xformable.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble)
        if orient_op is None:
            orient_op = xformable.AddOrientOp(UsdGeom.XformOp.PrecisionDouble)

        # Set values
        translate_op.Set(Gf.Vec3d(x, y, z))
        orient_op.Set(quat)

        carb.log_info(f"ZMQPoseSubscriber: Applied pose to {self._prim_path}: "
                     f"pos=({x:.3f}, {y:.3f}, {z:.3f}), "
                     f"rpy=({roll:.3f}, {pitch:.3f}, {yaw:.3f})")

    async def _receive_loop(self):
        """Main loop for receiving and processing pose messages."""
        while self._running:
            try:
                # Receive multipart message: [topic, payload]
                parts = await self._sock.recv_multipart()
                if len(parts) < 2:
                    continue

                topic_bytes, payload = parts[0], parts[1]

                # Verify topic matches
                if topic_bytes != self._topic:
                    continue

                # Unpack MsgPack message
                try:
                    data = msgpack.unpackb(payload, raw=False)
                except Exception as e:
                    carb.log_error(f"ZMQPoseSubscriber: Failed to unpack message: {e}")
                    continue

                # Extract pose data
                # Support two formats:
                # 1. Array format (Gazebo): [x, y, z, roll, pitch, yaw]
                # 2. Dictionary format: {"x": float, "y": float, "z": float, "roll": float, "pitch": float, "yaw": float}
                if isinstance(data, (list, tuple)) and len(data) >= 6:
                    # Array format: [x, y, z, roll, pitch, yaw]
                    x, y, z, roll, pitch, yaw = float(data[0]), float(data[1]), float(data[2]), \
                                                 float(data[3]), float(data[4]), float(data[5])
                elif isinstance(data, dict):
                    # Dictionary format
                    x = float(data.get("x", 0.0))
                    y = float(data.get("y", 0.0))
                    z = float(data.get("z", 0.0))
                    roll = float(data.get("roll", 0.0))
                    pitch = float(data.get("pitch", 0.0))
                    yaw = float(data.get("yaw", 0.0))
                else:
                    carb.log_error(f"ZMQPoseSubscriber: Unexpected message format: {type(data)}")
                    continue

                # Apply pose
                self._apply_pose(x, y, z, roll, pitch, yaw)

            except asyncio.CancelledError:
                break
            except Exception as e:
                carb.log_error(f"ZMQPoseSubscriber: Error in receive loop: {e}")
                await asyncio.sleep(0.1)  # Brief pause before retrying

    def start(self):
        """Start the pose subscriber task. Should be called from an async context."""
        if self._running:
            return

        self._running = True

        # Schedule the receive loop to run in the current event loop
        # This will work if called from an async context, or will schedule it
        # to run when an event loop becomes available
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, create task directly
            self._task = loop.create_task(self._receive_loop())
            print(f"ZMQPoseSubscriber: Started receiving pose messages for {self._prim_path}")
        except RuntimeError:
            # No running event loop, schedule it to start when one is available
            # This will be handled by calling start_async() from an async context
            print(f"ZMQPoseSubscriber: Will start when event loop is available")

    async def start_async(self):
        """Start the pose subscriber task from an async context."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._receive_loop())
        print(f"ZMQPoseSubscriber: Started receiving pose messages for {self._prim_path}")

    def stop(self):
        """Stop the pose subscriber task."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                asyncio.get_event_loop().run_until_complete(self._task)
            except asyncio.CancelledError:
                pass
        print(f"ZMQPoseSubscriber: Stopped")

    def destroy(self):
        """Clean up resources."""
        self.stop()
        try:
            self._sock.close()
        except Exception:
            pass
