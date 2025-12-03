"""
Debug script to list all nodes in the SDGPipeline graph.
Run this in Isaac Sim's Script Editor after clicking "Start Streaming".
Output is written to /tmp/graph_debug.txt
"""
import omni.graph.core as og

output_file = "/tmp/graph_debug.txt"
lines = []

graph = og.get_graph_by_path("/Render/PostProcess/SDGPipeline")
if graph:
    lines.append("=== Nodes in SDGPipeline ===")
    for node in graph.get_nodes():
        path = node.get_prim_path()
        lines.append(path)
        # Check if it's the ZMQ node and print its input values
        if "zmq" in path.lower():
            try:
                buf_color = node.get_attribute("inputs:bufferSizeColor")
                buf_depth = node.get_attribute("inputs:bufferSizeDepth")
                if buf_color:
                    lines.append(f"  -> bufferSizeColor: {buf_color.get()}")
                if buf_depth:
                    lines.append(f"  -> bufferSizeDepth: {buf_depth.get()}")
            except Exception as e:
                lines.append(f"  -> Error reading attributes: {e}")
else:
    lines.append("Graph /Render/PostProcess/SDGPipeline not found!")

# Also check for render product nodes
lines.append("\n=== Looking for LdrColorSD nodes ===")
all_graphs = og.get_all_graphs()
for g in all_graphs:
    for node in g.get_nodes():
        path = node.get_prim_path()
        if "LdrColor" in path or "DistanceToCamera" in path:
            lines.append(f"Found: {path}")

# Write to file
with open(output_file, "w") as f:
    f.write("\n".join(lines))

print(f"Output written to {output_file}")
