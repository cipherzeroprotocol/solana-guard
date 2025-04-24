"""
Utility functions for visualizing blockchain data.
Provides methods to create visualizations for analysis results.
"""
import json
import logging
import os
import pandas as pd
import numpy as np
import networkx as nx
from typing import Dict, List, Optional, Any, Union
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

from config import DATA_DIR

logger = logging.getLogger(__name__)

# Create visualization output directory
VIZ_DIR = os.path.join(DATA_DIR, "visualizations")
os.makedirs(VIZ_DIR, exist_ok=True)

# Define color schemes
COLOR_SCHEMES = {
    "risk": {
        "very_low": "#1a9850",  # Green
        "low": "#91cf60",       # Light green
        "medium": "#ffffbf",    # Yellow
        "high": "#fc8d59",      # Orange
        "very_high": "#d73027"  # Red
    },
    "flow": {
        "source": "#2c7bb6",    # Blue
        "intermediate": "#ffffbf", # Yellow
        "destination": "#d7191c"   # Red
    },
    "entity": {
        "exchange": "#4575b4",  # Blue
        "mixer": "#d73027",     # Red
        "bridge": "#91bfdb",    # Light blue
        "contract": "#fc8d59",  # Orange
        "user": "#91cf60",      # Light green
        "unknown": "#bdbdbd"    # Gray
    }
}

def visualize_risk_score(risk_data: Dict, output_file: Optional[str] = None) -> str:
    """
    Create a visualization of risk score and factors.
    
    Args:
        risk_data: Risk score data
        output_file: Output file path (if None, auto-generate)
        
    Returns:
        Path to the generated visualization file
    """
    logger.info("Creating risk score visualization")
    
    # Set up the figure
    fig, axes = plt.subplots(2, 1, figsize=(10, 12), gridspec_kw={'height_ratios': [1, 2]})
    
    # Extract data
    risk_score = risk_data.get("risk_score", 0)
    risk_level = risk_data.get("risk_level", "unknown")
    category_scores = risk_data.get("category_scores", {})
    risk_factors = risk_data.get("risk_factors", [])
    
    # Plot 1: Risk gauge
    ax1 = axes[0]
    
    # Create gauge
    def degree_to_rad(degree):
        return degree * np.pi / 180
    
    # Gauge settings
    gauge_min = 0
    gauge_max = 100
    gauge_range = gauge_max - gauge_min
    
    # Determine color
    if risk_level in COLOR_SCHEMES["risk"]:
        color = COLOR_SCHEMES["risk"][risk_level]
    else:
        color = COLOR_SCHEMES["risk"]["medium"]
    
    # Draw gauge
    angle_range = 180
    ratio = (risk_score - gauge_min) / gauge_range
    angle = angle_range * ratio
    
    # Draw background
    bg_angle = degree_to_rad(180)
    bg_radius = 0.8
    ax1.add_patch(plt.Rectangle((-bg_radius, 0), 2 * bg_radius, bg_radius, color='#f0f0f0', alpha=0.5))
    
    # Draw gauge background
    for i, level in enumerate(["very_low", "low", "medium", "high", "very_high"]):
        start_angle = degree_to_rad(180 - i * 36)
        end_angle = degree_to_rad(180 - (i + 1) * 36)
        ax1.add_patch(plt.Wedge((0, 0), bg_radius, 180 - (i + 1) * 36, 180 - i * 36, 
                               width=bg_radius * 0.3, color=COLOR_SCHEMES["risk"][level], alpha=0.7))
    
    # Draw needle
    needle_angle = degree_to_rad(180 - angle)
    ax1.plot([0, bg_radius * 0.7 * np.cos(needle_angle)], [0, bg_radius * 0.7 * np.sin(needle_angle)], 
             color='black', linewidth=3)
    ax1.add_patch(plt.Circle((0, 0), 0.05, color='black'))
    
    # Add score text
    ax1.text(0, -0.2, f"Risk Score: {risk_score:.1f}", ha='center', va='center', fontsize=14, 
             fontweight='bold', color=color)
    ax1.text(0, -0.35, f"Risk Level: {risk_level.replace('_', ' ').title()}", ha='center', va='center', 
             fontsize=12, color=color)
    
    # Labels
    ax1.text(-bg_radius, -0.6 * bg_radius, "Very Low", ha='center', va='center')
    ax1.text(-bg_radius/2, -0.6 * bg_radius, "Low", ha='center', va='center')
    ax1.text(0, -0.6 * bg_radius, "Medium", ha='center', va='center')
    ax1.text(bg_radius/2, -0.6 * bg_radius, "High", ha='center', va='center')
    ax1.text(bg_radius, -0.6 * bg_radius, "Very High", ha='center', va='center')
    
    # Set limits and remove axes
    ax1.set_xlim(-1, 1)
    ax1.set_ylim(-0.7, 1)
    ax1.axis('off')
    ax1.set_title("Risk Assessment", fontsize=16, pad=20)
    
    # Plot 2: Risk factors
    ax2 = axes[1]
    
    # Sort risk factors by score
    sorted_factors = sorted(risk_factors, key=lambda x: x.get("score", 0), reverse=True)
    
    # Prepare data for plotting
    factor_names = [f"{factor.get('name', 'unknown')} ({factor.get('score', 0)})" for factor in sorted_factors[:10]]
    factor_scores = [factor.get("score", 0) for factor in sorted_factors[:10]]
    factor_categories = [factor.get("category", "unknown") for factor in sorted_factors[:10]]
    
    # Determine colors based on severity
    factor_colors = []
    for factor in sorted_factors[:10]:
        severity = factor.get("severity", "medium")
        if severity in COLOR_SCHEMES["risk"]:
            factor_colors.append(COLOR_SCHEMES["risk"][severity])
        else:
            factor_colors.append(COLOR_SCHEMES["risk"]["medium"])
    
    # Create horizontal bar chart
    y_pos = np.arange(len(factor_names))
    ax2.barh(y_pos, factor_scores, color=factor_colors)
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(factor_names)
    ax2.invert_yaxis()  # Labels read top-to-bottom
    ax2.set_xlabel('Risk Score')
    ax2.set_title('Top Risk Factors', fontsize=14)
    
    # Add category labels
    for i, category in enumerate(factor_categories):
        ax2.text(1, i, f"Category: {category.replace('_', ' ').title()}", 
                 va='center', ha='left', transform=ax2.get_yticklabels()[i].get_transform())
    
    # Add descriptions as annotations
    for i, factor in enumerate(sorted_factors[:10]):
        description = factor.get("description", "")
        if description:
            ax2.annotate(description, xy=(factor_scores[i], i), xytext=(factor_scores[i] + 5, i),
                         va='center', ha='left', fontsize=8)
    
    # Set layout
    plt.tight_layout()
    
    # Save to file
    if output_file is None:
        entity_type = "address"
        entity_id = risk_data.get("address", risk_data.get("token_mint", "unknown"))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(VIZ_DIR, f"risk_{entity_type}_{entity_id}_{timestamp}.png")
    
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    logger.info(f"Saved risk visualization to {output_file}")
    return output_file

def visualize_transaction_flow(
    graph_data: Dict,
    source_address: Optional[str] = None,
    highlight_paths: Optional[List[List[str]]] = None,
    output_file: Optional[str] = None
) -> str:
    """
    Create a visualization of transaction flows.
    
    Args:
        graph_data: Graph data with nodes and edges
        source_address: Source address to highlight
        highlight_paths: List of paths to highlight
        output_file: Output file path (if None, auto-generate)
        
    Returns:
        Path to the generated visualization file
    """
    logger.info("Creating transaction flow visualization")
    
    # Create networkx graph
    G = nx.DiGraph()
    
    # Add nodes
    nodes = graph_data.get("nodes", [])
    
    for node in nodes:
        node_id = node.get("id")
        if not node_id:
            continue
            
        # Extract node attributes
        attrs = {}
        for k, v in node.items():
            if k != "id":
                attrs[k] = v
        
        G.add_node(node_id, **attrs)
    
    # Add edges
    edges = graph_data.get("edges", [])
    
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        
        if not source or not target:
            continue
            
        # Extract edge attributes
        attrs = {}
        for k, v in edge.items():
            if k not in ["source", "target"]:
                attrs[k] = v
        
        G.add_edge(source, target, **attrs)
    
    # Plot setup
    plt.figure(figsize=(12, 10))
    
    # Determine node positions using layout algorithm
    pos = nx.spring_layout(G, seed=42, k=0.3)
    
    # Determine node colors
    node_colors = []
    node_sizes = []
    
    for node in G.nodes():
        # Default values
        color = COLOR_SCHEMES["entity"]["unknown"]
        size = 300
        
        # Determine color by node type
        node_type = G.nodes[node].get("type", "unknown")
        if node_type in COLOR_SCHEMES["entity"]:
            color = COLOR_SCHEMES["entity"][node_type]
        
        # Highlight source address
        if source_address and node == source_address:
            color = COLOR_SCHEMES["flow"]["source"]
            size = size * 2  # Fixed: replaced a2 with size
        
        # Determine size by importance
        importance = G.nodes[node].get("importance", 0)
        risk_score = G.nodes[node].get("risk_score", 0)
        
        size = 300 + importance * 200 + risk_score * 3
        
        node_colors.append(color)
        node_sizes.append(size)
    
    # Determine edge colors and widths
    edge_colors = []
    edge_widths = []
    
    for u, v, data in G.edges(data=True):
        # Default values
        color = 'gray'
        width = 1
        
        # Determine color by edge type
        edge_type = data.get("type", "unknown")
        if edge_type in COLOR_SCHEMES["entity"]:
            color = COLOR_SCHEMES["entity"][edge_type]
        
        # Determine width by weight or volume
        weight = data.get("weight", 1)
        volume = data.get("volume", 0)
        
        width = 1 + weight * 0.5 + min(5, volume / 1000)
        
        edge_colors.append(color)
        edge_widths.append(width)
    
    # Draw the graph
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes, alpha=0.8)
    nx.draw_networkx_edges(G, pos, edge_color=edge_colors, width=edge_widths, alpha=0.6, 
                          arrowsize=15, connectionstyle='arc3,rad=0.1')
    
    # Draw labels
    label_dict = {}
    for node in G.nodes():
        # Use label if available, otherwise use shortened address
        label = G.nodes[node].get("label", "")
        if not label:
            # Shortened address (first 4, last 4)
            if len(node) > 8:
                label = f"{node[:4]}...{node[-4:]}"
            else:
                label = node
        
        label_dict[node] = label
    
    nx.draw_networkx_labels(G, pos, labels=label_dict, font_size=10, font_weight='bold')
    
    # Highlight paths if provided
    if highlight_paths:
        for i, path in enumerate(highlight_paths):
            # Skip paths that are too short
            if len(path) < 2:
                continue
                
            # Draw edges for the path
            edges = [(path[i], path[i+1]) for i in range(len(path)-1)]
            
            nx.draw_networkx_edges(G, pos, edgelist=edges, edge_color='red', width=3, alpha=0.8,
                                  arrowsize=20, connectionstyle='arc3,rad=0.1')
    
    # Add legend
    legend_elements = []
    for entity_type, color in COLOR_SCHEMES["entity"].items():
        legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=color,
                                         markersize=10, label=entity_type.replace('_', ' ').title()))
    
    if source_address:
        legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', 
                                         markerfacecolor=COLOR_SCHEMES["flow"]["source"],
                                         markersize=15, label='Source Address'))
    
    if highlight_paths:
        legend_elements.append(plt.Line2D([0], [0], color='red', lw=3, label='Highlighted Path'))
    
    plt.legend(handles=legend_elements, loc='upper right')
    
    # Set title and remove axes
    plt.title("Transaction Flow Visualization", fontsize=16)
    plt.axis('off')
    
    # Save to file
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(VIZ_DIR, f"transaction_flow_{timestamp}.png")
    
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    logger.info(f"Saved transaction flow visualization to {output_file}")
    return output_file

def visualize_token_activity(token_data: Dict, output_file: Optional[str] = None) -> str:
    """
    Create a visualization of token activity.
    
    Args:
        token_data: Token activity data
        output_file: Output file path (if None, auto-generate)
        
    Returns:
        Path to the generated visualization file
    """
    logger.info("Creating token activity visualization")
    
    # Extract price history if available
    price_history = token_data.get("price_history", [])
    
    if not price_history:
        logger.warning("No price history data available")
        price_history = []
    
    # Extract volume data if available
    volume_data = token_data.get("volume_data", [])
    
    if not volume_data:
        logger.warning("No volume data available")
        volume_data = []
    
    # Extract holder data if available
    holder_data = token_data.get("holder_data", [])
    
    if not holder_data:
        logger.warning("No holder data available")
        holder_data = []
    
    # Set up the figure
    fig, axes = plt.subplots(3, 1, figsize=(12, 14), sharex=True if price_history and volume_data else False)
    
    # Plot 1: Price history
    ax1 = axes[0]
    
    if price_history and len(price_history) > 1:
        # Convert data to DataFrame
        if not isinstance(price_history, pd.DataFrame):
            price_df = pd.DataFrame(price_history)
        else:
            price_df = price_history
        
        # Ensure datetime conversion
        if "time" in price_df.columns and not pd.api.types.is_datetime64_any_dtype(price_df["time"]):
            price_df["time"] = pd.to_datetime(price_df["time"], unit='s')
        
        # Plot price
        if "time" in price_df.columns and "close" in price_df.columns:
            ax1.plot(price_df["time"], price_df["close"], color=COLOR_SCHEMES["entity"]["contract"], linewidth=2)
            
            # Add min/max markers
            min_price = price_df["close"].min()
            max_price = price_df["close"].max()
            
            min_idx = price_df["close"].idxmin()
            max_idx = price_df["close"].idxmax()
            
            min_time = price_df.loc[min_idx, "time"]
            max_time = price_df.loc[max_idx, "time"]
            
            ax1.scatter(min_time, min_price, color='blue', s=100, zorder=5)
            ax1.scatter(max_time, max_price, color='red', s=100, zorder=5)
            
            ax1.annotate(f"Min: ${min_price:.4f}", (min_time, min_price), 
                       xytext=(10, -20), textcoords='offset points')
            ax1.annotate(f"Max: ${max_price:.4f}", (max_time, max_price), 
                       xytext=(10, 20), textcoords='offset points')
            
            # Format x-axis
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=45)
            
            # Calculate price change
            first_price = price_df["close"].iloc[0]
            last_price = price_df["close"].iloc[-1]
            price_change_pct = ((last_price - first_price) / first_price) * 100 if first_price > 0 else 0
            
            # Add price change annotation
            ax1.text(0.02, 0.95, f"Price Change: {price_change_pct:.2f}%", 
                   transform=ax1.transAxes, fontsize=12,
                   color='green' if price_change_pct >= 0 else 'red')
    else:
        ax1.text(0.5, 0.5, "No price history data available", ha='center', va='center', fontsize=12)
    
    ax1.set_title("Token Price History", fontsize=14)
    ax1.set_ylabel("Price ($)")
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Volume data
    ax2 = axes[1]
    
    if volume_data and len(volume_data) > 1:
        # Convert data to DataFrame
        if not isinstance(volume_data, pd.DataFrame):
            volume_df = pd.DataFrame(volume_data)
        else:
            volume_df = volume_data
        
        # Ensure datetime conversion
        if "time" in volume_df.columns and not pd.api.types.is_datetime64_any_dtype(volume_df["time"]):
            volume_df["time"] = pd.to_datetime(volume_df["time"], unit='s')
        
        # Plot volume
        if "time" in volume_df.columns and "volume" in volume_df.columns:
            ax2.bar(volume_df["time"], volume_df["volume"], color=COLOR_SCHEMES["entity"]["exchange"], alpha=0.7)
            
            # Format x-axis
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=45)
            
            # Calculate average volume
            avg_volume = volume_df["volume"].mean()
            
            # Add average volume line
            ax2.axhline(avg_volume, color='red', linestyle='--', linewidth=2)
            ax2.text(0.02, 0.95, f"Avg Volume: ${avg_volume:.2f}", 
                   transform=ax2.transAxes, fontsize=12)
    else:
        ax2.text(0.5, 0.5, "No volume data available", ha='center', va='center', fontsize=12)
    
    ax2.set_title("Trading Volume", fontsize=14)
    ax2.set_ylabel("Volume ($)")
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Holder distribution
    ax3 = axes[2]
    
    if holder_data and len(holder_data) > 1:
        # Extract top holders
        top_holders = holder_data[:10] if len(holder_data) > 10 else holder_data
        
        # Prepare data for plotting
        addresses = []
        percentages = []
        colors = []
        
        for holder in top_holders:
            address = holder.get("address", "unknown")
            if len(address) > 10:
                address = f"{address[:6]}...{address[-4:]}"
            
            addresses.append(address)
            percentages.append(holder.get("percentage", 0))
            
            # Determine color based on percentage
            pct = holder.get("percentage", 0)
            if pct > 50:
                colors.append(COLOR_SCHEMES["risk"]["very_high"])
            elif pct > 25:
                colors.append(COLOR_SCHEMES["risk"]["high"])
            elif pct > 10:
                colors.append(COLOR_SCHEMES["risk"]["medium"])
            else:
                colors.append(COLOR_SCHEMES["risk"]["low"])
        
        # Plot horizontal bar chart
        y_pos = np.arange(len(addresses))
        ax3.barh(y_pos, percentages, color=colors)
        ax3.set_yticks(y_pos)
        ax3.set_yticklabels(addresses)
        ax3.invert_yaxis()  # Labels read top-to-bottom
        
        # Add percentage labels
        for i, pct in enumerate(percentages):
            ax3.text(pct + 1, i, f"{pct:.2f}%", va='center')
        
        # Calculate concentration metrics
        top_holder_pct = percentages[0] if percentages else 0
        top5_holder_pct = sum(percentages[:5]) if len(percentages) >= 5 else sum(percentages)
        top10_holder_pct = sum(percentages[:10]) if len(percentages) >= 10 else sum(percentages)
        
        # Add concentration metrics
        ax3.text(0.5, -0.15, 
               f"Top Holder: {top_holder_pct:.2f}% | Top 5: {top5_holder_pct:.2f}% | Top 10: {top10_holder_pct:.2f}%",
               transform=ax3.transAxes, ha='center', fontsize=12)
    else:
        ax3.text(0.5, 0.5, "No holder data available", ha='center', va='center', fontsize=12)
    
    ax3.set_title("Top Token Holders", fontsize=14)
    ax3.set_xlabel("Percentage of Supply (%)")
    ax3.grid(True, alpha=0.3)
    
    # Add token info header
    token_name = token_data.get("token_name", "Unknown Token")
    token_symbol = token_data.get("token_symbol", "???")
    token_mint = token_data.get("token_mint", "")
    
    plt.figtext(0.5, 0.95, f"{token_name} ({token_symbol})", ha='center', fontsize=16, fontweight='bold')
    if token_mint:
        plt.figtext(0.5, 0.93, f"Mint: {token_mint}", ha='center', fontsize=10)
    
    # Add risk data if available
    risk_score = token_data.get("risk_score", None)
    risk_level = token_data.get("risk_level", None)
    
    if risk_score is not None and risk_level is not None:
        # Determine color
        if risk_level in COLOR_SCHEMES["risk"]:
            risk_color = COLOR_SCHEMES["risk"][risk_level]
        else:
            risk_color = COLOR_SCHEMES["risk"]["medium"]
            
        plt.figtext(0.5, 0.91, f"Risk Score: {risk_score:.1f} ({risk_level.replace('_', ' ').title()})", 
                  ha='center', fontsize=12, color=risk_color, fontweight='bold')
    
    # Set layout
    plt.tight_layout()
    plt.subplots_adjust(top=0.9)
    
    # Save to file
    if output_file is None:
        token_id = token_data.get("token_mint", "unknown")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(VIZ_DIR, f"token_activity_{token_id}_{timestamp}.png")
    
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    logger.info(f"Saved token activity visualization to {output_file}")
    return output_file

def visualize_money_laundering_routes(
    routes_data: List[Dict],
    output_file: Optional[str] = None
) -> str:
    """
    Create a visualization of money laundering routes.
    
    Args:
        routes_data: Money laundering routes data
        output_file: Output file path (if None, auto-generate)
        
    Returns:
        Path to the generated visualization file
    """
    logger.info("Creating money laundering routes visualization")
    
    if not routes_data:
        logger.warning("No money laundering routes data provided")
        return None
    
    # Set up the figure
    fig, ax = plt.figure(figsize=(12, 10), dpi=100)
    
    # Create directed graph
    G = nx.DiGraph()
    
    # Add nodes and edges from routes
    for route in routes_data:
        source = route.get("source_address")
        target = route.get("target_address")
        
        if not source or not target:
            continue
            
        # Add source node
        if source not in G:
            G.add_node(source, type="source", risk_score=0)
        
        # Add target node
        target_type = route.get("flow_type", "unknown")
        target_risk = route.get("risk_score", 0)
        
        if target not in G:
            G.add_node(target, type=target_type, risk_score=target_risk)
        
        # Add intermediate nodes
        intermediate_addresses = route.get("intermediate_addresses", [])
        
        # Create the full path
        path = [source] + intermediate_addresses + [target]
        
        # Add nodes and edges along the path
        for i in range(len(path) - 1):
            current = path[i]
            next_node = path[i + 1]
            
            if next_node not in G:
                G.add_node(next_node, type="intermediate", risk_score=0)
            
            # Add edge with route information
            G.add_edge(current, next_node, 
                     route_type=target_type,
                     risk_score=target_risk,
                     amount=route.get("total_volume_usd", 0))
    
    # Set up node positions with spring layout
    pos = nx.spring_layout(G, seed=42, k=0.3)
    
    # Prepare node colors and sizes
    node_colors = []
    node_sizes = []
    
    for node in G.nodes():
        node_type = G.nodes[node].get("type", "unknown")
        risk_score = G.nodes[node].get("risk_score", 0)
        
        # Determine color
        if node_type == "source":
            color = COLOR_SCHEMES["flow"]["source"]
        elif node_type == "intermediate":
            color = COLOR_SCHEMES["flow"]["intermediate"]
        else:
            # Use entity color if available, otherwise use destination color
            if node_type in COLOR_SCHEMES["entity"]:
                color = COLOR_SCHEMES["entity"][node_type]
            else:
                color = COLOR_SCHEMES["flow"]["destination"]
        
        # Determine size based on risk and type
        size = 300
        if node_type == "source":
            size = 500
        else:
            size = 300 + risk_score * 3
        
        node_colors.append(color)
        node_sizes.append(size)
    
    # Prepare edge colors and widths
    edge_colors = []
    edge_widths = []
    
    for u, v, data in G.edges(data=True):
        route_type = data.get("route_type", "unknown")
        risk_score = data.get("risk_score", 0)
        amount = data.get("amount", 0)
        
        # Determine color based on risk score
        if risk_score >= 75:
            color = COLOR_SCHEMES["risk"]["very_high"]
        elif risk_score >= 50:
            color = COLOR_SCHEMES["risk"]["high"]
        elif risk_score >= 25:
            color = COLOR_SCHEMES["risk"]["medium"]
        else:
            color = COLOR_SCHEMES["risk"]["low"]
        
        # Determine width based on amount
        width = 1 + min(5, amount / 10000)
        
        edge_colors.append(color)
        edge_widths.append(width)
    
    # Draw the graph
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes, alpha=0.8)
    nx.draw_networkx_edges(G, pos, edge_color=edge_colors, width=edge_widths, alpha=0.6,
                          arrowsize=15, connectionstyle='arc3,rad=0.1')
    
    # Draw labels
    label_dict = {}
    for node in G.nodes():
        # Shortened address (first 4, last 4)
        if len(node) > 8:
            label = f"{node[:4]}...{node[-4:]}"
        else:
            label = node
        
        label_dict[node] = label
    
    nx.draw_networkx_labels(G, pos, labels=label_dict, font_size=10, font_weight='bold')
    
    # Add legend
    legend_elements = [
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=COLOR_SCHEMES["flow"]["source"],
                  markersize=15, label='Source Address'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=COLOR_SCHEMES["flow"]["intermediate"],
                  markersize=10, label='Intermediate Address'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=COLOR_SCHEMES["flow"]["destination"],
                  markersize=10, label='Destination Address')
    ]
    
    # Add entity types to legend
    for entity_type, color in COLOR_SCHEMES["entity"].items():
        if any(G.nodes[node].get("type") == entity_type for node in G.nodes()):
            legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=color,
                                           markersize=10, label=entity_type.replace('_', ' ').title()))
    
    # Add risk levels to legend
    for risk_level, color in COLOR_SCHEMES["risk"].items():
        if any(data.get("risk_score", 0) >= 25 * (list(COLOR_SCHEMES["risk"].keys()).index(risk_level))
              for _, _, data in G.edges(data=True)):
            legend_elements.append(plt.Line2D([0], [0], color=color, lw=2,
                                           label=f"{risk_level.replace('_', ' ').title()} Risk"))
    
    plt.legend(handles=legend_elements, loc='upper right')
    
    # Set title and remove axes
    plt.title("Money Laundering Routes Visualization", fontsize=16)
    plt.axis('off')
    
    # Save to file
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(VIZ_DIR, f"money_laundering_routes_{timestamp}.png")
    
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    logger.info(f"Saved money laundering routes visualization to {output_file}")
    return output_file