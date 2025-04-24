"""
Flow graph visualization components for SolanaGuard dashboard.
Provides functions to display transaction flow networks.
"""
import streamlit as st
import plotly.graph_objects as go
import networkx as nx
from typing import Dict, Any, List, Optional, Tuple

def display_transaction_flow(graph_data: Dict[str, List], source_address: Optional[str] = None, height: int = 600):
    """
    Display a transaction flow graph visualization.
    
    Args:
        graph_data: Dictionary with nodes and edges
        source_address: Optional source address to highlight
        height: Height of the visualization in pixels
    """
    # Create NetworkX graph
    G = nx.DiGraph()
    
    # Add nodes
    for node in graph_data.get("nodes", []):
        node_id = node.get("id")
        if node_id:
            G.add_node(node_id, **{k: v for k, v in node.items() if k != "id"})
    
    # Add edges
    for edge in graph_data.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if source and target:
            G.add_edge(source, target, **{k: v for k, v in edge.items() if k not in ["source", "target"]})
    
    # Define node colors based on type
    color_map = {
        "exchange": "#4575b4",
        "mixer": "#d73027",
        "bridge": "#91bfdb",
        "contract": "#fc8d59",
        "user": "#91cf60",
        "source": "#2c7bb6",
        "entity": "#fc8d59",
        "address": "#91cf60",
        "unknown": "#bdbdbd"
    }
    
    # Set node colors
    node_colors = []
    for node in G.nodes():
        node_type = G.nodes[node].get("type", "unknown").lower()
        
        # Highlight source address
        if source_address and node == source_address:
            color = "#2c7bb6"  # Blue for source
        else:
            color = color_map.get(node_type, color_map["unknown"])
        
        node_colors.append(color)
    
    # Set node sizes based on importance
    node_sizes = []
    for node in G.nodes():
        size = 10  # Default size
        
        # Larger size for source address
        if source_address and node == source_address:
            size = 20
        # Size based on risk score or other metrics
        elif "risk_score" in G.nodes[node]:
            size = 10 + G.nodes[node]["risk_score"] / 10
        
        node_sizes.append(size)
    
    # Set edge colors based on type or risk
    edge_colors = []
    edge_widths = []
    for u, v, data in G.edges(data=True):
        if "risk_score" in data:
            # Color based on risk score
            risk = data["risk_score"]
            if risk >= 80:
                color = "#d73027"  # Red
            elif risk >= 60:
                color = "#fc8d59"  # Orange
            elif risk >= 40:
                color = "#ffffbf"  # Yellow
            elif risk >= 20:
                color = "#91cf60"  # Light green
            else:
                color = "#1a9850"  # Green
            
            # Width based on risk score
            width = 1 + risk / 20
        else:
            # Default color and width
            color = "#bdbdbd"  # Gray
            width = 1
        
        edge_colors.append(color)
        edge_widths.append(width)
    
    # Create layout
    if len(G.nodes()) > 0:
        try:
            pos = nx.spring_layout(G, seed=42, k=0.3)
        except:
            pos = {node: (i, i) for i, node in enumerate(G.nodes())}
        
        # Add edges
        edge_traces = []
        for i, (u, v, data) in enumerate(G.edges(data=True)):
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            
            # Get edge attributes for hover text
            hover_text = f"From: {u[:8]}...{u[-4:] if len(u) > 12 else ''}<br>" + \
                         f"To: {v[:8]}...{v[-4:] if len(v) > 12 else ''}"
            
            if "weight" in data:
                hover_text += f"<br>Weight: {data['weight']}"
            if "volume" in data:
                hover_text += f"<br>Volume: {data['volume']}"
            if "tokens" in data:
                tokens = data["tokens"]
                if isinstance(tokens, list) and len(tokens) > 0:
                    hover_text += f"<br>Tokens: {', '.join(tokens[:3])}"
                elif isinstance(tokens, set) and len(tokens) > 0:
                    hover_text += f"<br>Tokens: {', '.join(list(tokens)[:3])}"
            
            edge_traces.append(
                go.Scatter(
                    x=[x0, x1, None],
                    y=[y0, y1, None],
                    line=dict(width=edge_widths[i], color=edge_colors[i]),
                    hoverinfo="text",
                    text=hover_text,
                    mode="lines"
                )
            )
        
        # Add nodes
        node_texts = []
        for node in G.nodes():
            node_text = f"Address: {node[:8]}...{node[-4:] if len(node) > 12 else ''}"
            
            # Add label if available
            if "label" in G.nodes[node]:
                node_text += f"<br>Label: {G.nodes[node]['label']}"
            
            # Add type if available
            if "type" in G.nodes[node]:
                node_text += f"<br>Type: {G.nodes[node]['type']}"
            
            # Add risk score if available
            if "risk_score" in G.nodes[node]:
                node_text += f"<br>Risk: {G.nodes[node]['risk_score']}"
            
            node_texts.append(node_text)
        
        node_trace = go.Scatter(
            x=[pos[node][0] for node in G.nodes()],
            y=[pos[node][1] for node in G.nodes()],
            mode="markers",
            marker=dict(
                size=node_sizes,
                color=node_colors,
                line=dict(width=1, color="#333")
            ),
            text=node_texts,
            hoverinfo="text"
        )
        
        # Create figure
        fig = go.Figure(data=edge_traces + [node_trace])
        
        # Update layout
        fig.update_layout(
            title="Transaction Flow Graph",
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            annotations=[dict(
                text="",
                showarrow=False,
                xref="paper", yref="paper"
            )],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=height,
            plot_bgcolor='rgba(255,255,255,0.8)'
        )
        
        # Display figure
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No graph data to display")

def display_money_laundering_graph(routes_df, source_address=None, height=600):
    """
    Display a money laundering flow graph from route data.
    
    Args:
        routes_df: DataFrame with money laundering routes
        source_address: Optional source address to highlight
        height: Height of the visualization in pixels
    """
    if routes_df.empty:
        st.info("No money laundering routes to display")
        return
    
    # Create NetworkX graph
    G = nx.DiGraph()
    
    # Process each route
    for _, route in routes_df.iterrows():
        source = route.get("source_address")
        target = route.get("target_address")
        
        if not source or not target:
            continue
        
        # Add nodes if they don't exist
        if source not in G:
            G.add_node(source, type="source" if source == source_address else "address")
        
        if target not in G:
            G.add_node(target, type=route.get("flow_type", "unknown"), risk_score=route.get("risk_score", 0))
        
        # Add edge
        G.add_edge(
            source,
            target,
            weight=1,
            risk_score=route.get("risk_score", 0),
            amount_usd=route.get("amount_usd", 0),
            flow_type=route.get("flow_type", "unknown")
        )
    
    # Convert to graph data format
    nodes = []
    for node, attrs in G.nodes(data=True):
        node_data = {"id": node}
        node_data.update(attrs)
        nodes.append(node_data)
    
    edges = []
    for source, target, attrs in G.edges(data=True):
        edge_data = {
            "source": source,
            "target": target
        }
        edge_data.update(attrs)
        edges.append(edge_data)
    
    graph_data = {
        "nodes": nodes,
        "edges": edges
    }
    
    # Display the graph
    display_transaction_flow(graph_data, source_address, height)
