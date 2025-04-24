"""
Visualization utilities for blockchain data analysis.
"""
import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
from typing import Dict, List, Any, Union, Optional

from .graph_utils import TransactionFlowGraph

def visualize_transaction_flow(
    flow_graph: TransactionFlowGraph,
    highlight_nodes: List[str] = None,
    output_file: str = None,
    max_nodes: int = 100
) -> Optional[str]:
    """
    Create a visualization of transaction flows.
    
    Args:
        flow_graph: Transaction flow graph
        highlight_nodes: Nodes to highlight (e.g., mixer addresses)
        output_file: Path to save the visualization
        max_nodes: Maximum number of nodes to visualize
        
    Returns:
        Path to saved visualization or None if visualization failed
    """
    if not flow_graph or len(flow_graph.get_nodes()) == 0:
        return None
        
    # Convert to networkx graph
    G = flow_graph.graph
    
    # Limit graph size if needed
    if len(G) > max_nodes:
        # Get the most important nodes
        centrality = nx.degree_centrality(G)
        important_nodes = sorted(centrality, key=centrality.get, reverse=True)[:max_nodes]
        
        # Create a subgraph with just the important nodes
        G = G.subgraph(important_nodes).copy()
    
    # Set up node colors
    node_colors = []
    if highlight_nodes:
        for node in G.nodes():
            if node in highlight_nodes:
                node_colors.append('red')
            elif G.nodes[node].get('is_mixer', False):
                node_colors.append('orange')
            else:
                node_colors.append('skyblue')
    else:
        # Color based on is_mixer attribute
        for node in G.nodes():
            if G.nodes[node].get('is_mixer', False):
                node_colors.append('red')
            else:
                node_colors.append('skyblue')
    
    # Set up node sizes based on degree
    node_sizes = []
    for node in G.nodes():
        degree = G.degree(node)
        node_sizes.append(100 + (degree * 20))
    
    # Create figure
    plt.figure(figsize=(12, 10))
    
    # Use spring layout for node positioning
    pos = nx.spring_layout(G)
    
    # Draw the graph
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, alpha=0.8, node_size=node_sizes)
    nx.draw_networkx_edges(G, pos, alpha=0.2, arrows=True)
    
    # Add labels for highlighted nodes
    labels = {}
    for node in G.nodes():
        if highlight_nodes and node in highlight_nodes:
            # For highlighted nodes, show the first 10 characters
            labels[node] = node[:10] + "..."
        elif G.nodes[node].get('is_mixer', False):
            # For mixer nodes, show the first 10 characters
            labels[node] = node[:10] + "..."
    
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)
    
    plt.title("Transaction Flow Graph")
    plt.axis('off')
    plt.tight_layout()
    
    # Save to file if specified
    if output_file:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
    
    return output_file

def plot_entropy_distribution(data, bins=30, output_file=None):
    """
    Plot the distribution of values and their entropy.
    
    Args:
        data: Array-like data to plot
        bins: Number of histogram bins
        output_file: Path to save the plot
    
    Returns:
        Path to saved plot or None
    """
    from .entropy_analysis import calculate_transaction_entropy
    
    # Convert to numpy array
    data_array = np.asarray(data)
    
    # Calculate entropy
    entropy = calculate_transaction_entropy(data_array)
    
    plt.figure(figsize=(10, 6))
    
    # Plot histogram
    sns.histplot(data_array, bins=bins, kde=True)
    
    plt.title(f"Value Distribution (Entropy: {entropy:.4f})")
    plt.xlabel("Value")
    plt.ylabel("Frequency")
    plt.grid(alpha=0.3)
    
    # Add entropy annotation
    plt.annotate(f"Entropy: {entropy:.4f}", xy=(0.7, 0.9), xycoords='axes fraction',
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8))
    
    plt.tight_layout()
    
    # Save to file if specified
    if output_file:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        return output_file
    
    return None
