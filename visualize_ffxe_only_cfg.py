# visualize_ffxe_only_cfg.py
# This script visualizes the raw Control Flow Graph (CFG) recovered by FFXE
# from its .pkl output, without any additional semantic information from Ghidra.

import pickle
import networkx as nx
import matplotlib.pyplot as plt
import os
import argparse
import time

# --- Configuration ---
# Updated default path to an existing FFXE generated .pkl file from their test suite
# Corrected filename: removed '.bin' from 'blinky-o1.bin-ffxe-cfg.pkl'
DEFAULT_PKL_PATH = 'tests/cfgs/unit-tests/blinky-o1-ffxe-cfg.pkl' # <--- CORRECTED PATH HERE
OUTPUT_IMAGE_DIR = 'cfg_visualizations'

def main():
    parser = argparse.ArgumentParser(
        description="Visualize FFXE-only CFG from a .pkl file."
    )
    parser.add_argument(
        'pkl_file',
        nargs='?', # Makes the argument optional
        default=DEFAULT_PKL_PATH,
        help=f"Path to the FFXE .pkl CFG file (default: {DEFAULT_PKL_PATH})"
    )
    
    args = parser.parse_args()

    # Ensure output directory exists
    if not os.path.exists(OUTPUT_IMAGE_DIR):
        os.makedirs(OUTPUT_IMAGE_DIR)
        print(f"Created output directory: {OUTPUT_IMAGE_DIR}")

    pkl_filepath = args.pkl_file

    if not os.path.exists(pkl_filepath):
        print(f"Error: PKL file not found at {pkl_filepath}")
        print("Please ensure the specified .pkl file exists in the FFXE project's tests/cfgs/unit-tests directory.")
        print(f"Available files for blinky: blinky-o0-ffxe-cfg.pkl, blinky-o1-ffxe-cfg.pkl, blinky-o2-ffxe-cfg.pkl, blinky-o3-ffxe-cfg.pkl")
        return

    print(f"Loading CFG data from: {pkl_filepath}")
    
    start_time = time.time()

    try:
        with open(pkl_filepath, 'rb') as f:
            cfg_data = pickle.load(f)
    except Exception as e:
        print(f"Error loading pickle file: {e}")
        print("Ensure the .pkl file is not corrupted and was generated correctly.")
        return

    # FFXE's original PKL might have a slightly different structure than ours.
    # We will try to extract 'nodes' and 'edges' assuming it's a dictionary
    # or handle if it's directly a CFG object (which is less likely for pickled output).
    # Based on our previous inspection and the `visualize_cfg.py`'s handling,
    # it's likely still a dictionary with 'nodes' and 'edges' as sets of tuples.
    nodes = cfg_data.get('nodes', set())
    edges = cfg_data.get('edges', set())

    # --- Important Note for Original FFXE CFG Structure ---
    # The original FFXE `CFG` object stores basic blocks as `BBlock` objects
    # and edges as `(u, v, type)` tuples. When *pickled*, it seems to be converting
    # these to simple (address, size) for nodes and (source_addr, target_addr) for edges.
    # Our `run_fxe_with_hints.py` was adapted for this. Let's confirm for the existing PKL.

    # If the nodes are not simple (address, size) tuples, we need to convert them
    # This block attempts to normalize the node data if it's not already in the
    # (address, size) tuple format, which might be the case for older pickled CFGs
    # or if the internal BBlock objects were pickled directly.
    normalized_nodes = set()
    for node_item in nodes:
        if isinstance(node_item, tuple) and len(node_item) == 2:
            normalized_nodes.add(node_item)
        # Add more isinstance checks here if you find other structures in their PKLs
        # e.g., if it's a BBlock object itself, you'd do:
        # elif hasattr(node_item, 'address') and hasattr(node_item, 'size'):
        #     normalized_nodes.add((node_item.address, node_item.size))
        else:
            # Fallback if the format is unexpected. Just use the item as an address.
            # This might cause issues if it's not an int, but it's a safeguard.
            try:
                # Assuming the node_item itself is the address if not a tuple
                if isinstance(node_item, int):
                    normalized_nodes.add((node_item, 0)) # Assume size 0 if unknown
                else:
                    print(f"Warning: Unexpected node format: {node_item} (type: {type(node_item)}). Skipping or handling as address only.")
            except (ValueError, TypeError):
                print(f"Warning: Could not convert node {node_item} to an integer address. Skipping.")
                pass 
    nodes = normalized_nodes # Use the normalized set

    # Similar normalization for edges if they are (u, v, type) and we only need (u, v)
    normalized_edges = set()
    for edge_item in edges:
        if isinstance(edge_item, tuple) and len(edge_item) == 2:
            normalized_edges.add(edge_item)
        elif isinstance(edge_item, tuple) and len(edge_item) == 3: # Assuming (u, v, type)
            normalized_edges.add((edge_item[0], edge_item[1]))
        else:
            print(f"Warning: Unexpected edge format: {edge_item}. Skipping.")
            pass
    edges = normalized_edges


    if not nodes or not edges:
        print("Warning: Loaded CFG data is empty or malformed after normalization. Check original PKL structure.")
        print(f"Normalized Nodes found: {len(nodes)}, Normalized Edges found: {len(edges)}")
        return

    # Create a directed graph
    G = nx.DiGraph()

    # Add nodes. Nodes are (address, size) tuples, but we only need address for graph nodes
    for addr, size in nodes:
        G.add_node(addr, size=size) # Store size as a node attribute if needed later

    # Add edges. Edges are (source_addr, target_addr) tuples
    for u, v in edges:
        G.add_edge(u, v)

    end_time = time.time()
    data_load_time = end_time - start_time
    print(f"Data loaded and graph constructed in {data_load_time:.4f} seconds.")

    print(f"Nodes in FFXE-only CFG: {G.number_of_nodes()}")
    print(f"Edges in FFXE-only CFG: {G.number_of_edges()}")

    # --- Visualization ---
    print("Generating FFXE-only CFG visualization...")
    plt.figure(figsize=(18, 12)) # Adjust figure size as needed for better readability

    # Set node labels to hexadecimal addresses
    labels = {node: f"0x{node:x}" for node in G.nodes()}

    # Use a spring layout for initial visualization.
    # For very large graphs, this can be slow.
    # You can experiment with 'k' and 'iterations' for better layout
    pos = nx.spring_layout(G, k=0.15, iterations=50) 

    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=50, node_color='skyblue', alpha=0.8)

    # Draw edges
    nx.draw_networkx_edges(G, pos, edge_color='gray', arrows=True, arrowsize=10, alpha=0.6)

    # Draw labels
    # Use a smaller font size for labels for better readability in dense graphs
    nx.draw_networkx_labels(G, pos, labels, font_size=8, font_color='black')

    plt.title(f"FFXE-Only Recovered Control Flow Graph (Raw Original Output: {os.path.basename(pkl_filepath)})", fontsize=16)
    plt.axis('off') # Hide axes

    # Save the plot
    output_image_path = os.path.join(OUTPUT_IMAGE_DIR, f'ffxe_original_raw_cfg_{os.path.basename(pkl_filepath).replace(".pkl", ".png")}') # Dynamic filename
    plt.savefig(output_image_path, bbox_inches='tight')
    plt.close() # Close the plot to free up memory

    print(f"FFXE-only CFG visualization saved to: {output_image_path}")

if __name__ == "__main__":
    main()
