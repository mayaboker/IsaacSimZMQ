#!/usr/bin/env python3
import argparse
import msgpack
import numpy as np
import zmq
import dearpygui.dearpygui as dpg

class MsgPackViewer:
    def __init__(self, ip: str, port: int, topic: str, width: int, height: int):
        self.endpoint = f"tcp://{ip}:{port}"
        self.topic = topic.encode("utf-8")
        self.width = width
        self.height = height

        self.ctx = zmq.Context()
        self.sock = None
        self.poller = zmq.Poller()

        dpg.create_context()
        with dpg.texture_registry(show=False):
            self.tex_id = dpg.add_raw_texture(
                self.width,
                self.height,
                np.zeros((self.height, self.width, 4), dtype=np.float32),
                format=dpg.mvFormat_Float_rgba,
                tag="camera_texture"
            )

        with dpg.window(label="MsgPack Camera", width=self.width, height=self.height + 60):
            dpg.add_image("camera_texture")
            dpg.add_button(label="Restart", callback=self.restart)

        dpg.create_viewport(title="MsgPack Camera Viewer", width=self.width, height=self.height + 60)
        dpg.setup_dearpygui()
        dpg.show_viewport()

        self.connect()

    def connect(self):
        if self.sock is not None:
            self.poller.unregister(self.sock)
            self.sock.close()
        self.sock = self.ctx.socket(zmq.SUB)
        self.sock.connect(self.endpoint)
        self.sock.setsockopt(zmq.SUBSCRIBE, self.topic)
        self.poller.register(self.sock, zmq.POLLIN)
        print(f"[viewer] Subscribed to {self.endpoint} on topic '{self.topic.decode()}'")

    def restart(self, *_):
        print("[viewer] Restarting subscriber...")
        self.connect()

    def update_frame(self):
        socks = dict(self.poller.poll(timeout=1))
        if self.sock in socks:
            try:
                topic, payload = self.sock.recv_multipart(flags=zmq.NOBLOCK)
                frame_bytes = msgpack.unpackb(payload, raw=False)
                img = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(self.height, self.width, 3)

                rgba = np.zeros((self.height, self.width, 4), dtype=np.float32)
                rgba[..., :3] = img.astype(np.float32) / 255.0
                rgba[..., 3] = 1.0
                dpg.set_value("camera_texture", rgba)
            except zmq.Again:
                pass

    def render(self):
        try:
            while dpg.is_dearpygui_running():
                self.update_frame()
                dpg.render_dearpygui_frame()
        finally:
            dpg.destroy_context()
            self.sock.close()
            self.ctx.term()

def main():
    parser = argparse.ArgumentParser(description="MsgPack ZMQ Camera Viewer (Dear PyGui)")
    parser.add_argument("--ip", default="127.0.0.1", help="Publisher IP")
    parser.add_argument("--port", type=int, default=5561, help="Publisher port")
    parser.add_argument("--topic", default="camera/image", help="MsgPack topic")
    parser.add_argument("--width", type=int, required=True, help="Image width")
    parser.add_argument("--height", type=int, required=True, help="Image height")
    args = parser.parse_args()

    viewer = MsgPackViewer(args.ip, args.port, args.topic, args.width, args.height)
    viewer.render()

if __name__ == "__main__":
    main()
