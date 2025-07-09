import pickle
import os
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import time

#PKL_FILE_PATH = 'tests/cfgs/unit-tests/blinky-o1-ffxe-cfg.pkl' 
#FUNCTIONS_FILE_PATH = 'blinky_functions.txt'      

PKL_FILE_PATH = 'tests/cfgs/unit-tests/spi-o1-ffxe-cfg.pkl' 
FUNCTIONS_FILE_PATH = 'spi00_functions.txt'             

function_map = {}
function_entry_points = {}

with open(FUNCTIONS_FILE_PATH, 'r') as f:
    for line in f:
        parts = line.strip().split(',')
        if len(parts) == 2:
            address_str = parts[0].replace('L', '') 
            address = int(address_str, 16)
            name = parts[1]
            function_entry_points[address] = name

recovered_cfg_data = pickle.load(open(PKL_FILE_PATH, 'rb'))

nodes_data = recovered_cfg_data['nodes']
edges_data = recovered_cfg_data['edges']

#Full CFG Processing and Visualization
start_total_time = time.perf_counter()

G_full = nx.DiGraph()

all_node_ids = set()
for address, size in nodes_data:
    all_node_ids.add(address)
for source, destination in edges_data:
    all_node_ids.add(source)
    all_node_ids.add(destination)

sorted_all_node_ids = sorted(list(all_node_ids))

current_function_name = "unknown_function"
for address in sorted_all_node_ids:
    if address in function_entry_points:
        current_function_name = function_entry_points[address]
    function_map[address] = current_function_name

node_sizes_map = {addr: size for addr, size in nodes_data}

for address in sorted_all_node_ids:
    size = node_sizes_map.get(address, 0)
    G_full.add_node(address, size=size, function=function_map.get(address, "unknown_function"))
    
for source, destination in edges_data:
    G_full.add_edge(source, destination)

# Generate Colors for Functions (Full CFG)
unique_functions_full = set(nx.get_node_attributes(G_full, 'function').values())

colors = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
    '#8c564b', '#e377c2', '#bcbd22', '#17becf', '#7f7f7f', 
    '#A6CEE3', '#1F78B4', '#B2DF8A', '#33A02C', '#FB9A99', 
    '#E31A1C', '#FDBF6F', '#FF7F00', '#CAB2D6', '#6A3D9A'  
]

if len(unique_functions_full) > len(colors):
    cmap_full = plt.cm.get_cmap('tab20', len(unique_functions_full))
    function_colors_full = {func: mcolors.rgb2hex(cmap_full(i)[:3]) for i, func in enumerate(sorted(list(unique_functions_full)))}
else:
    function_colors_full = {func: colors[i % len(colors)] for i, func in enumerate(sorted(list(unique_functions_full)))}

function_colors_full['unknown_function'] = '#000000' 

# Calculate Function Statistics
function_stats_full = {}
for node_id in G_full.nodes():
    func_name = G_full.nodes[node_id].get('function', 'unknown_function')
    node_size = G_full.nodes[node_id].get('size', 0)

    if func_name not in function_stats_full:
        function_stats_full[func_name] = {'nodes': 0, 'size': 0}
    function_stats_full[func_name]['nodes'] += 1
    function_stats_full[func_name]['size'] += node_size

# Assign colors to nodes 
node_colors_full = []
for node_id in G_full.nodes():
    node_func_name = G_full.nodes[node_id].get('function', 'unknown_function')
    color = function_colors_full.get(node_func_name, '#FF00FF') # Magenta fallback if not found
    node_colors_full.append(color)

try:
    pos_full = nx.nx_pydot.graphviz_layout(G_full, prog='dot')
except (ImportError, Exception): 
    pos_full = nx.spring_layout(G_full, k=0.5, iterations=50)

end_total_time = time.perf_counter()
total_time_full_cfg = max(0, end_total_time - start_total_time)
print(f"\nProcessing Time for Full CFG: {total_time_full_cfg:.4f} seconds")
print(f"Full CFG Nodes: {G_full.number_of_nodes()}, Edges: {G_full.number_of_edges()}")

#Visualize the Full graph
plt.figure(figsize=(20, 16))
nx.draw_networkx_nodes(G_full, pos_full, node_size=700, node_color=node_colors_full, alpha=0.9, linewidths=0.5, edgecolors='black')
nx.draw_networkx_edges(G_full, pos_full, edgelist=G_full.edges(),
                       width=1, alpha=0.7, edge_color='gray',
                       arrows=True, arrowsize=10, arrowstyle='->')

labels_full = {node: f"0x{node:x}" for node in G_full.nodes()}
nx.draw_networkx_labels(G_full, pos_full, labels_full, font_size=7, font_color='black')

if len(unique_functions_full) <= 25:
    legend_handles_full = []
    for func_name in sorted(list(unique_functions_full)):
        stats_info = function_stats_full.get(func_name, {'nodes': 0, 'size': 0})
        legend_label = f"{func_name} (Blocks: {stats_info['nodes']}, Size: {stats_info['size']}B)"
        
        handle = plt.Line2D([0], [0], marker='o', color='w', label=legend_label,
                            markerfacecolor=function_colors_full.get(func_name, '#AAAAAA'), markersize=10,
                            markeredgecolor='black', markeredgewidth=0.5)
        legend_handles_full.append(handle)
    plt.legend(handles=legend_handles_full, title="Functions (Full CFG)", bbox_to_anchor=(1.02, 1), loc='upper left', borderaxespad=0., fontsize=8)

plt.title(f"Full Control Flow Graph for {os.path.basename(PKL_FILE_PATH)} (Colored by Function)")
plt.axis('off')
plt.tight_layout()
plt.show()

# Unknown Functions 
start_unknown_neighbors_time = time.perf_counter()

G_unknown_neighbors = nx.DiGraph()

nodes_to_include = set()
unknown_function_nodes = []

for node_id in G_full.nodes():
    if G_full.nodes[node_id].get('function') == 'unknown_function':
        nodes_to_include.add(node_id)
        unknown_function_nodes.append(node_id)

# add direct neighbors
for u_node in unknown_function_nodes:
    for pred in G_full.predecessors(u_node):
        nodes_to_include.add(pred)
    for succ in G_full.successors(u_node):
        nodes_to_include.add(succ)

for node_id in nodes_to_include:
    G_unknown_neighbors.add_node(node_id, **G_full.nodes[node_id])

for u, v in G_full.edges():
    if u in G_unknown_neighbors.nodes() and v in G_unknown_neighbors.nodes():
        G_unknown_neighbors.add_edge(u, v)

# Generate Colors 
node_colors_unknown_neighbors = []
for node_id in G_unknown_neighbors.nodes():
    func_name = G_full.nodes[node_id].get('function', 'unknown_function')
    color = function_colors_full.get(func_name, '#FFFF00') # Yellow fallback if not found in full map
    node_colors_unknown_neighbors.append(color)

try:
    pos_unknown_neighbors = nx.nx_pydot.graphviz_layout(G_unknown_neighbors, prog='dot')
except (ImportError, Exception):
    pos_unknown_neighbors = nx.spring_layout(G_unknown_neighbors, k=0.5, iterations=50)

end_unknown_neighbors_time = time.perf_counter()
total_time_unknown_neighbors_cfg = max(0, end_unknown_neighbors_time - start_unknown_neighbors_time)
print(f"Processing Time for Unknown & Neighbors CFG: {total_time_unknown_neighbors_cfg:.4f} seconds")
print(f"Unknown & Neighbors CFG Nodes: {G_unknown_neighbors.number_of_nodes()}, Edges: {G_unknown_neighbors.number_of_edges()}")

# Visualize the Unknown Functions 
plt.figure(figsize=(20, 16))
nx.draw_networkx_nodes(G_unknown_neighbors, pos_unknown_neighbors, node_size=700, node_color=node_colors_unknown_neighbors, alpha=0.9, linewidths=0.5, edgecolors='black')
nx.draw_networkx_edges(G_unknown_neighbors, pos_unknown_neighbors, edgelist=G_unknown_neighbors.edges(),
                       width=1, alpha=0.7, edge_color='gray',
                       arrows=True, arrowsize=10, arrowstyle='->')

labels_unknown_neighbors = {node: f"0x{node:x}" for node in G_unknown_neighbors.nodes()}
nx.draw_networkx_labels(G_unknown_neighbors, pos_unknown_neighbors, labels_unknown_neighbors, font_size=7, font_color='black')

# Legend for Unknown and Neighboring Functions 
legend_handles_unknown_neighbors = []

# Get all unique function names 
functions_in_unknown_neighbors_graph = set(nx.get_node_attributes(G_unknown_neighbors, 'function').values())

# Sort and add to legend handles
for func_name in sorted(list(functions_in_unknown_neighbors_graph)):
    stats_info = function_stats_full.get(func_name, {'nodes': 0, 'size': 0}) # Use full stats for metadata
    
    if func_name == 'unknown_function':
        legend_label = f"unknown_function (Blocks: {stats_info['nodes']}, Size: {stats_info['size']}B)"
    else:
        legend_label = f"{func_name} (Neighbor - Blocks: {stats_info['nodes']}, Size: {stats_info['size']}B)"
    
    handle = plt.Line2D([0], [0], marker='o', color='w', label=legend_label,
                        markerfacecolor=function_colors_full.get(func_name, '#AAAAAA'), 
                        markersize=10, markeredgecolor='black', markeredgewidth=0.5)
    legend_handles_unknown_neighbors.append(handle)

if legend_handles_unknown_neighbors:
    plt.legend(handles=legend_handles_unknown_neighbors, title="Unknowns & Neighbors", bbox_to_anchor=(1.02, 1), loc='upper left', borderaxespad=0., fontsize=8)


plt.title(f"Unknown Functions & Immediate Neighbors for {os.path.basename(PKL_FILE_PATH)}")
plt.axis('off')
plt.tight_layout()
plt.show()

print(f"\n--- Overall Comparison ---")
print(f"Full CFG Nodes: {G_full.number_of_nodes()}, Edges: {G_full.number_of_edges()}, Time: {total_time_full_cfg:.4f}s")
print(f"Unknown & Neighbors CFG Nodes: {G_unknown_neighbors.number_of_nodes()}, Edges: {G_unknown_neighbors.number_of_edges()}, Time: {total_time_unknown_neighbors_cfg:.4f}s")

print(f"\nReduction from Full CFG to Unknown & Neighbors CFG:")
print(f"  Nodes Reduced By: {G_full.number_of_nodes() - G_unknown_neighbors.number_of_nodes()} ({((G_full.number_of_nodes() - G_unknown_neighbors.number_of_nodes()) / G_full.number_of_nodes()) * 100:.2f}%)")
print(f"  Edges Reduced By: {G_full.number_of_edges() - G_unknown_neighbors.number_of_edges()} ({((G_full.number_of_edges() - G_unknown_neighbors.number_of_edges()) / G_full.number_of_edges()) * 100:.2f}%)")
print(f"  Processing Time Difference: {(total_time_full_cfg - total_time_unknown_neighbors_cfg):.4f}s")
print(f"  Processing Time Reduction: {((total_time_full_cfg - total_time_unknown_neighbors_cfg) / total_time_full_cfg) * 100:.2f}%")
