# Isaac Sim ZMQ Bridge — Architecture Guide

This document explains how the IsaacSimZMQ extension system works.

---

## 🧩 What is an Extension?

An **extension** is a plugin that Isaac Sim loads at runtime. It can contain:
- **C++ code** (compiled into `.so` files) - for performance-critical operations
- **Python code** - for UI, scripting, glue logic
- **OmniGraph nodes** - visual programming nodes

---

## 📁 Extension Structure

```
exts/isaacsim.zmq.bridge/              ← Extension folder name = extension ID
├── config/
│   └── extension.toml                 ← MANIFEST: name, version, dependencies
├── plugins/
│   ├── nodes/
│   │   ├── OgnIsaacBridgeZMQNode.ogn  ← Node SCHEMA (inputs/outputs definition)
│   │   └── OgnIsaacBridgeZMQNode.cpp  ← Node IMPLEMENTATION (C++ code)
│   └── isaacsim.zmq.bridge/
│       └── IsaacBridgePlugin.cpp      ← Plugin registration
├── bin/
│   └── libisaacsim.zmq.bridge.plugin.so  ← COMPILED C++ (built by build.sh)
├── isaacsim/zmq/bridge/
│   └── __init__.py                    ← Python module (if any)
└── ogn/                               ← Auto-generated OGN bindings
```

---

## 🔧 How Extension Loading Works

```
1. Isaac Sim starts
         ↓
2. Reads extension.toml files from exts/ folders
         ↓
3. Loads dependencies (e.g., "isaacsim.zmq.bridge" depends on nothing,
   "isaacsim.zmq.bridge.examples" depends on "isaacsim.zmq.bridge")
         ↓
4. For C++ extensions: loads .so files from bin/
         ↓
5. For Python: adds paths from [[python.module]] to sys.path
         ↓
6. Registers OmniGraph nodes (from .ogn files)
         ↓
7. Extension is ready to use!
```

---

## 📋 The `extension.toml` File (Manifest)

```toml
[package]
version = "1.1.0"
title = "isaacsim zmq bridge"
description = "ZMQ streaming for Isaac Sim"

[dependencies]
"omni.graph" = {}           # Requires OmniGraph
"omni.isaac.sensor" = {}    # Requires Isaac sensors

[[python.module]]
path = "pip_prebundle"      # Add this folder to Python path

[[python.module]]
name = "isaacsim.zmq.bridge"  # Python module name

[[native.plugin]]
path = "bin/*.plugin.so"    # Load C++ plugins from here
```

---

## 🎯 OmniGraph Nodes (The Key Concept)

OmniGraph is Isaac Sim's **visual programming system**. Nodes are connected in a graph to process data each frame.

### Node Definition (`.ogn` file)

```json
{
    "IsaacBridgeZMQNode": {
        "version": 1,
        "description": "Streams camera data via ZMQ",
        "language": "C++",
        
        "inputs": {
            "execIn": { "type": "execution" },
            "bufferPtr": { "type": "uint64" },
            "width": { "type": "uint" },
            "height": { "type": "uint" },
            "port": { "type": "int", "default": 5561 }
        },
        "outputs": {
            "execOut": { "type": "execution" }
        }
    }
}
```

### Node Implementation (`.cpp` file)

```cpp
class OgnIsaacBridgeZMQNode {
public:
    static bool compute(OgnIsaacBridgeZMQNodeDatabase& db) {
        // Called EVERY FRAME when node is triggered
        
        // 1. Get inputs
        uint64_t bufferPtr = db.inputs.bufferPtr();
        int width = db.inputs.width();
        
        // 2. Process (pack image, send via ZMQ)
        void* data = reinterpret_cast<void*>(bufferPtr);
        zmq_socket.send(data, width * height * 3);
        
        // 3. Trigger output
        db.outputs.execOut() = kExecutionAttributeStateEnabled;
        return true;
    }
};
```

---

## 🔗 How Python Connects to C++ Nodes

The `ZMQAnnotator` (Python) builds an OmniGraph that connects:

```
┌──────────────────────────────────────────────────────────────────┐
│                    OmniGraph Pipeline                            │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │ RenderProduct│ → │ OnRenderEnd │ → │ OgnIsaacBridgeZMQNode│  │
│  │  (Camera)    │    │  (Trigger)  │    │     (C++ Node)      │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│        ↓                                         ↑               │
│  Captures frame                          Receives buffer pointer │
│  every render                            Sends via ZMQ           │
└──────────────────────────────────────────────────────────────────┘
```

**Python code in `annotators.py`:**

```python
def build_graph(self, name, camera):
    # Create nodes
    render_product = og.Controller.create_node(
        f"/Render/PostProcess/SDGPipeline/{name}_rp",
        "omni.graph.nodes.RenderProduct"
    )
    
    zmq_node = og.Controller.create_node(
        f"/Render/PostProcess/SDGPipeline/zmq{self.port}",
        "isaacsim.zmq.bridge.IsaacBridgeZMQNode"  # ← References C++ node
    )
    
    # Connect nodes
    render_product.get_attribute("outputs:buffer").connect(
        zmq_node.get_attribute("inputs:bufferPtr")
    )
```

---

## 🔄 Frame-by-Frame Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ Each Frame (60 FPS):                                            │
│                                                                  │
│ 1. Isaac Sim renders camera view                                │
│         ↓                                                        │
│ 2. RenderProduct captures frame to GPU buffer                   │
│         ↓                                                        │
│ 3. OnRenderComplete triggers execution                          │
│         ↓                                                        │
│ 4. OgnIsaacBridgeZMQNode.compute() called                       │
│    - Gets buffer pointer                                         │
│    - Copies to CPU (if needed)                                   │
│    - Packs with msgpack                                          │
│    - Sends via ZMQ PUB socket                                    │
│         ↓                                                        │
│ 5. Server receives and displays                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Making Changes

| Change | Where |
|--------|-------|
| **Add new input to streaming** | 1. Add to `.ogn` schema<br>2. Handle in `.cpp` compute()<br>3. Rebuild with `./build.sh` |
| **Change serialization format** | Modify `.cpp` file, rebuild |
| **Change how cameras connect** | Modify `annotators.py` (Python) |
| **Add UI buttons** | Modify `extension.py` (Python) |
| **Change port/topic defaults** | Modify `.ogn` defaults or Python args |

---

## 📦 Build Process

```bash
./build.sh           # Compiles C++ → .so files in _build/
                     # Also copies to exts/*/bin/
```

After building, changes to:
- **C++**: Require `./build.sh` + restart Isaac Sim
- **Python**: Just restart Isaac Sim (or reload extension)
- **.ogn schema**: Require `./build.sh` + restart Isaac Sim

---

## 🏗️ Project Structure Overview

```
IsaacSimZMQ/
├── exts/                              # Isaac Sim Extensions
│   ├── isaacsim.zmq.bridge/           # Core C++ extension (streaming nodes)
│   └── isaacsim.zmq.bridge.examples/  # Python examples & UI
├── tools/                             # Launcher scripts (run FROM HOST)
├── isaac-zmq-server/                  # Server side (runs in Docker)
├── docs/                              # Documentation
└── assets/                            # USD files for examples
```

---

## 📦 Extension 1: `isaacsim.zmq.bridge` (C++ Core)

**Purpose:** High-performance streaming nodes (OmniGraph nodes written in C++)

| File | What it does |
|------|--------------|
| `plugins/nodes/OgnIsaacBridgeZMQNode.cpp` | **Main streaming node** - captures camera data, serializes (protobuf/msgpack), sends via ZMQ |
| `plugins/nodes/OgnIsaacBridgeZMQNode.ogn` | Node definition (inputs/outputs schema) |
| `plugins/nodes/OgnIsaacBridgeMsgpackCameraNode.cpp` | Simple msgpack camera node (PUB socket) |
| `config/extension.toml` | Extension metadata & dependencies |

**When to modify:**
- Change streaming format/protocol
- Add new data to stream (e.g., more sensor data)
- Optimize performance

---

## 📦 Extension 2: `isaacsim.zmq.bridge.examples` (Python)

**Purpose:** UI, examples, and Python helpers

### Core Components (`isaacsim/zmq/bridge/examples/core/`)

| File | What it does |
|------|--------------|
| `annotators.py` | **ZMQAnnotator** - Sets up OmniGraph to capture camera → connect to C++ node |
| `ZMQMsgpackAnnotator.py` | Pure Python msgpack streaming (alternative to C++) |
| `ZMQPoseSubscriber.py` | **Receives pose commands** from server, moves camera/prim |

### Mission System (`isaacsim/zmq/bridge/examples/`)

| File | What it does |
|------|--------------|
| `mission.py` | Base class for "missions" (load USD, setup streaming, handle control) |
| `example_missions.py` | **Franka example** - robot control, multi-camera setup |
| `extension.py` | UI menu items ("Create → Isaac ZMQ Examples → ...") |

### Scripts (`isaacsim/zmq/bridge/examples/scripts/`)

| File | What it does |
|------|--------------|
| `zmqpublish.py` | Script for custom USD streaming |

**When to modify:**
- Add new UI menu items → `extension.py`
- Change Franka behavior → `example_missions.py`
- Change how cameras connect to streaming → `annotators.py`
- Change pose handling → `ZMQPoseSubscriber.py`

---

## 🚀 Launcher Scripts (`tools/`)

**Purpose:** Convenience scripts to launch Isaac Sim with correct settings

| File | What it does |
|------|--------------|
| `run_zmq_msgpack.py` | **Main launcher** - parses args, sets env vars, launches Isaac Sim |
| `run_generic_gui.py` | Executed BY Isaac Sim (via `--exec`) - loads USD, starts streaming (GUI mode) |
| `run_generic_headless.py` | Same but headless |
| `run_franka_headless.py` | Launches Franka example headlessly |

**Flow:**

```
You run:     python3 tools/run_zmq_msgpack.py --gui --usd ... --camera ...
                            ↓
Sets env vars:  ISAAC_ZMQ_STAGE, ISAAC_ZMQ_CAMERA, etc.
                            ↓
Launches:       isaac-sim.sh --exec tools/run_generic_gui.py
                            ↓
run_generic_gui.py reads env vars, loads USD, creates ZMQAnnotator
```

---

## 🔄 Data Flow (Simple Stream Mode)

```
┌─────────────────────────────────────────────────────────────────┐
│                         ISAAC SIM                                │
│                                                                  │
│  Camera Prim ──► ZMQAnnotator ──► C++ OgnIsaacBridgeZMQNode     │
│       │              (Python)         (captures frame,           │
│       │                                packs msgpack,            │
│       │                                PUB socket)               │
│       │                                    │                     │
│       │         ZMQPoseSubscriber ◄────────┼──── SUB socket      │
│       │              (Python)              │     (receives pose) │
│       ▼                 │                  │                     │
│  [Camera moves] ◄───────┘                  │                     │
└────────────────────────────────────────────┼─────────────────────┘
                                             │ ZMQ (tcp://...:5561)
                                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SERVER (Docker)                             │
│                                                                  │
│  simple_msgpack_camera_gui.py ◄─── SUB socket (receives images) │
│                                                                  │
│  pose_publisher.py ──────────────► PUB socket (sends pose)       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Common Modifications

| Want to... | Modify... |
|------------|-----------|
| Change image resolution | `--width`, `--height` args |
| Stream different data | `OgnIsaacBridgeZMQNode.cpp` |
| Add new control commands | `ZMQPoseSubscriber.py` + server's `pose_publisher.py` |
| Change ZMQ ports | `--port`, `--pose-port` args |
| Add new USD example | Create new mission in `example_missions.py` |
| Modify Franka behavior | `example_missions.py` → `FrankaVisionMission` |

