"""
SolanaGuard Dashboard Application

This Streamlit app provides an interactive interface to SolanaGuard's analytical capabilities,
allowing users to analyze addresses, tokens, and transactions on the Solana blockchain.
"""
import os
import sys
import json
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
from datetime import datetime, timedelta
from PIL import Image

from analysis.utils.risk_scoring import calculate_address_risk, calculate_token_risk

# Add project root to path
sys.path.append('../..')

# Import SolanaGuard modules
from analysis.utils.address_utils import classify_address, detect_money_laundering_patterns
from analysis.utils.graph_utils import analyze_exfiltration_routes, build_money_laundering_graph, build_token_insider_graph
from collectors.helius_collector import HeliusCollector
from collectors.range_collector import RangeCollector
from collectors.rugcheck_collector import RugCheckCollector
from collectors.vybe_collector import VybeCollector


# Set page configuration
st.set_page_config(
    page_title="SolanaGuard Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create directories if they don't exist
DATA_DIR = "../../data"
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
VIZ_DIR = os.path.join(DATA_DIR, "visualizations")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(VIZ_DIR, exist_ok=True)

# Initialize collectors
@st.cache_resource
def initialize_collectors():
    return {
        "helius": HeliusCollector(),
        "range": RangeCollector(),
        "rugcheck": RugCheckCollector(),
        "vybe": VybeCollector()
    }

collectors = initialize_collectors()

# Function to validate Solana address
def is_valid_solana_address(address):
    # Basic validation - Solana addresses are typically Base58 encoded
    # and around 32-44 characters long
    if not address:
        return False
    
    if len(address) < 32 or len(address) > 44:
        return False
    
    # Check for allowed characters in Base58
    allowed_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
    return all(c in allowed_chars for c in address)

# Function to validate token mint address
def is_valid_token_mint(mint):
    # For simplicity, we'll use the same validation as for Solana addresses
    return is_valid_solana_address(mint)

# Function to display risk score visualization
def display_risk_score(risk_score, entity_type="address"):
    # Extract data
    score = risk_score.get("risk_score", 0)
    level = risk_score.get("risk_level", "unknown")
    factors = risk_score.get("risk_factors", [])
    
    # Create columns for layout
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Create gauge chart for risk score
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': f"Risk Score: {level.replace('_', ' ').title()}"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "darkgray"},
                'steps': [
                    {'range': [0, 20], 'color': "#1a9850"},
                    {'range': [20, 40], 'color': "#91cf60"},
                    {'range': [40, 60], 'color': "#ffffbf"},
                    {'range': [60, 80], 'color': "#fc8d59"},
                    {'range': [80, 100], 'color': "#d73027"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': score
                }
            }
        ))
        
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True)
        
    with col2:
        # Display risk factors
        st.write("### Risk Factors")
        
        if not factors:
            st.info("No risk factors identified.")
        else:
            # Create DataFrame for risk factors
            df_factors = pd.DataFrame(factors)
            
            # Sort by score descending
            df_factors = df_factors.sort_values("score", ascending=False)
            
            # Create horizontal bar chart
            fig = px.bar(
                df_factors.head(10),
                x="score",
                y="name",
                color="score",
                color_continuous_scale=["#1a9850", "#91cf60", "#ffffbf", "#fc8d59", "#d73027"],
                labels={"score": "Risk Score", "name": "Factor"},
                title="Top Risk Factors",
                orientation='h'
            )
            
            fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)
            
            # Display risk factor details
            for i, factor in enumerate(df_factors.head(5).to_dict("records")):
                with st.expander(f"{factor['name']} (Score: {factor['score']})"):
                    st.write(f"**Category**: {factor.get('category', 'Unknown')}")
                    st.write(f"**Severity**: {factor.get('severity', 'Unknown')}")
                    st.write(f"**Description**: {factor.get('description', '')}")

# Function to display transaction flow graph
def display_transaction_flow(graph_data, source_address=None):
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
        "unknown": "#bdbdbd"
    }
    
    # Set node colors
    node_colors = []
    for node in G.nodes():
        node_type = G.nodes[node].get("type", "unknown")
        
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
        else:
            # Default color
            color = "#bdbdbd"  # Gray
        
        edge_colors.append(color)
    
    # Create Plotly figure for network graph
    pos = nx.spring_layout(G, seed=42)
    
    # Add edges
    edge_traces = []
    for i, (u, v, data) in enumerate(G.edges(data=True)):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        weight = data.get("weight", 1)
        edge_traces.append(
            go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                line=dict(width=weight, color=edge_colors[i]),
                hoverinfo="none",
                mode="lines"
            )
        )
    
    # Add nodes
    node_trace = go.Scatter(
        x=[pos[node][0] for node in G.nodes()],
        y=[pos[node][1] for node in G.nodes()],
        mode="markers",
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(width=1, color="#333")
        ),
        text=[node for node in G.nodes()],
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
        height=600
    )
    
    # Display figure
    st.plotly_chart(fig, use_container_width=True)

# Address Analysis Page
def page_address_analysis():
    st.title("🔍 Address Analysis")
    
    st.write("""
    Analyze a Solana wallet address to assess risk, detect suspicious patterns, and identify potential
    money laundering activities. Enter a wallet address below to begin.
    """)
    
    # Address input
    address = st.text_input("Enter Solana wallet address", placeholder="e.g., VinesRG7K3ubzKLbxXz197c1RHV3cACkvGr9Zca7BSw")
    
    if address:
        if not is_valid_solana_address(address):
            st.error("Invalid Solana address format. Please check the address and try again.")
            return
        
        # Create analysis tabs
        tab_overview, tab_transfers, tab_risk, tab_laundering = st.tabs([
            "Overview", "Token Transfers", "Risk Analysis", "Money Laundering"
        ])
        
        with st.spinner("Analyzing address..."):
            # Fetch basic data
            try:
                tx_history = collectors["helius"].fetch_transaction_history(address, limit=100)
                token_transfers = collectors["helius"].analyze_token_transfers(address, limit=100)
                
                with tab_overview:
                    st.subheader("Address Overview")
                    
                    # Fetch balance data
                    sol_balance = collectors["helius"].get_balance(address) / 10**9  # Convert lamports to SOL
                    token_accounts = []
                    
                    try:
                        token_accounts_data = collectors["helius"].get_token_accounts_by_owner(address)
                        if token_accounts_data and "value" in token_accounts_data:
                            token_accounts = token_accounts_data["value"]
                    except:
                        pass
                    
                    # Display basic information
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("SOL Balance", f"{sol_balance:.4f} SOL")
                    
                    with col2:
                        st.metric("Token Accounts", len(token_accounts))
                    
                    with col3:
                        st.metric("Transactions", len(tx_history))
                    
                    # Classification
                    if not tx_history.empty:
                        # Get risk score from Range API
                        risk_info = {}
                        try:
                            risk_info = collectors["range"].get_address_risk_score(address)
                        except:
                            pass
                        
                        # Classify address
                        classification = classify_address(address, tx_history, token_transfers, risk_info)
                        
                        st.subheader("Address Classification")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.info(f"**Type**: {classification.get('type', 'Unknown').replace('_', ' ').title()}")
                            st.progress(classification.get('confidence', 0))
                            st.caption(f"Confidence: {classification.get('confidence', 0):.2f}")
                        
                        with col2:
                            st.info(f"**Activity Level**: {classification.get('activity_level', 'Unknown').replace('_', ' ').title()}")
                            st.info(f"**Risk Level**: {classification.get('risk_level', 'Unknown').replace('_', ' ').title()}")
                    
                    # Transaction history
                    st.subheader("Transaction History")
                    
                    if tx_history.empty:
                        st.info("No transaction history found.")
                    else:
                        # Prepare data for plotting
                        if "block_time" in tx_history.columns:
                            tx_history["datetime"] = pd.to_datetime(tx_history["block_time"], unit="s")
                            tx_history = tx_history.sort_values("datetime")
                            
                            # Create daily transaction count
                            daily_tx = tx_history.groupby(tx_history["datetime"].dt.date).size().reset_index()
                            daily_tx.columns = ["date", "count"]
                            
                            # Plot daily transaction count
                            fig = px.bar(
                                daily_tx,
                                x="date",
                                y="count",
                                title="Daily Transaction Count",
                                labels={"date": "Date", "count": "Transactions"},
                                color_discrete_sequence=["#4575b4"]
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # Display recent transactions
                        st.write("#### Recent Transactions")
                        
                        if "signature" in tx_history.columns and "block_time" in tx_history.columns:
                            recent_tx = tx_history.sort_values("block_time", ascending=False).head(10)
                            
                            for _, tx in recent_tx.iterrows():
                                with st.expander(f"Transaction: {tx['signature'][:15]}..."):
                                    st.write(f"**Time**: {pd.to_datetime(tx['block_time'], unit='s')}")
                                    st.write(f"**Status**: {'Success' if tx.get('success', False) else 'Failed'}")
                                    
                                    if "log_messages" in tx and tx["log_messages"]:
                                        with st.expander("Log Messages"):
                                            for i, log in enumerate(tx["log_messages"]):
                                                st.text(log)
                
                with tab_transfers:
                    st.subheader("Token Transfers")
                    
                    if token_transfers.empty:
                        st.info("No token transfers found.")
                    else:
                        # Prepare data for display
                        if "mint" in token_transfers.columns and "direction" in token_transfers.columns:
                            # Token distribution by mint
                            token_counts = token_transfers["mint"].value_counts().reset_index()
                            token_counts.columns = ["mint", "count"]
                            
                            # Direction distribution
                            direction_counts = token_transfers["direction"].value_counts().reset_index()
                            direction_counts.columns = ["direction", "count"]
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                # Plot token distribution
                                fig = px.pie(
                                    token_counts.head(10),
                                    values="count",
                                    names="mint",
                                    title="Token Distribution",
                                    hole=0.4
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            
                            with col2:
                                # Plot direction distribution
                                fig = px.pie(
                                    direction_counts,
                                    values="count",
                                    names="direction",
                                    title="Transfer Direction",
                                    hole=0.4,
                                    color_discrete_sequence=["#91cf60", "#fc8d59"]
                                )
                                st.plotly_chart(fig, use_container_width=True)
                        
                        # Display recent transfers
                        st.write("#### Recent Token Transfers")
                        
                        if "block_time" in token_transfers.columns:
                            recent_transfers = token_transfers.sort_values("block_time", ascending=False).head(10)
                            
                            for _, transfer in recent_transfers.iterrows():
                                with st.expander(f"{transfer.get('direction', 'Transfer')} of {transfer.get('amount_change', '?')} {transfer.get('mint', '?')}"):
                                    st.write(f"**Time**: {pd.to_datetime(transfer['block_time'], unit='s')}")
                                    st.write(f"**Token Account**: {transfer.get('token_account', 'Unknown')}")
                                    st.write(f"**Amount**: {transfer.get('amount_change', 0)}")
                                    st.write(f"**Direction**: {transfer.get('direction', 'Unknown')}")
                
                with tab_risk:
                    st.subheader("Risk Analysis")
                    
                    # Fetch risk data
                    risk_info = {}
                    try:
                        risk_info = collectors["range"].get_address_risk_score(address)
                    except Exception as e:
                        st.warning(f"Could not fetch external risk score: {e}")
                    
                    # Calculate comprehensive risk score
                    risk_score = calculate_address_risk(
                        address,
                        tx_history,
                        token_transfers,
                        risk_info
                    )
                    
                    # Display risk score visualization
                    display_risk_score(risk_score)
                    
                    # Check for dusting attacks
                    st.write("### Attack Detection")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("#### Dusting Attacks")
                        dusting_attacks = collectors["helius"].detect_dusting_attacks(address)
                        
                        if dusting_attacks.empty:
                            st.success("No dusting attacks detected.")
                        else:
                            st.error(f"⚠️ Detected {len(dusting_attacks)} potential dusting attacks.")
                            
                            with st.expander("View Dusting Attack Details"):
                                st.dataframe(dusting_attacks)
                    
                    with col2:
                        st.write("#### Address Poisoning")
                        address_poisoning = collectors["helius"].detect_address_poisoning(address)
                        
                        if address_poisoning.empty:
                            st.success("No address poisoning detected.")
                        else:
                            st.error(f"⚠️ Detected {len(address_poisoning)} potential address poisoning attempts.")
                            
                            with st.expander("View Address Poisoning Details"):
                                st.dataframe(address_poisoning)
                
                with tab_laundering:
                    st.subheader("Money Laundering Detection")
                    
                    # Detect money laundering patterns
                    try:
                        ml_routes = collectors["range"].analyze_money_laundering_routes(address)
                        
                        if ml_routes.empty:
                            st.success("No money laundering routes detected.")
                        else:
                            st.error(f"⚠️ Detected {len(ml_routes)} potential money laundering routes.")
                            
                            # Build money laundering graph
                            ml_graph = build_money_laundering_graph(ml_routes)
                            graph_data = ml_graph.export_to_json()
                            
                            # Visualize the graph
                            display_transaction_flow(graph_data, address)
                            
                            # Display routes details
                            st.write("#### Money Laundering Routes")
                            
                            for i, route in enumerate(ml_routes.head(5).to_dict("records")):
                                with st.expander(f"Route {i+1}: {route.get('flow_type', 'Unknown').replace('_', ' ').title()}"):
                                    st.write(f"**From**: {route.get('source_address', 'Unknown')}")
                                    st.write(f"**To**: {route.get('target_address', 'Unknown')}")
                                    st.write(f"**Risk Score**: {route.get('risk_score', 0)}")
                                    st.write(f"**Amount**: ${route.get('amount_usd', 0):.2f}")
                                    
                                    # Display more details if available
                                    if "counterparty_labels" in route and route["counterparty_labels"]:
                                        st.write(f"**Counterparty Labels**: {', '.join(route['counterparty_labels'])}")
                                    
                                    if "counterparty_entity" in route and route["counterparty_entity"]:
                                        st.write(f"**Counterparty Entity**: {route['counterparty_entity']}")
                            
                            # Analyze exfiltration routes
                            exfiltration_routes = analyze_exfiltration_routes(ml_graph, address)
                            
                            if exfiltration_routes:
                                st.write("#### Potential Exfiltration Routes")
                                
                                for i, route in enumerate(exfiltration_routes[:3]):
                                    with st.expander(f"Exfiltration Route {i+1}: {route.get('target_type', 'Unknown').replace('_', ' ').title()}"):
                                        st.write(f"**Target**: {route.get('target_address', 'Unknown')}")
                                        st.write(f"**Risk Score**: {route.get('risk_score', 0)}")
                                        st.write(f"**Path Length**: {route.get('path_length', 0)} nodes")
                                        
                                        # Show the path
                                        path = [route['source_address']] + route['intermediate_addresses'] + [route['target_address']]
                                        st.write(f"**Path**: {' → '.join([p[:6] + '...' for p in path])}")
                            else:
                                st.info("No exfiltration routes identified.")
                    except Exception as e:
                        st.warning(f"Error analyzing money laundering routes: {e}")
                        
                        # Try to detect patterns locally
                        ml_patterns = detect_money_laundering_patterns(
                            address,
                            tx_history,
                            token_transfers,
                            {},
                            pd.DataFrame()
                        )
                        
                        if ml_patterns["is_suspicious"]:
                            st.error(f"⚠️ Detected suspicious money laundering patterns.")
                            
                            for pattern in ml_patterns["patterns"]:
                                st.warning(f"**{pattern['type']}**: {pattern['description']} (confidence: {pattern['confidence']:.2f})")
                        else:
                            st.success("No suspicious money laundering patterns detected locally.")
                
            except Exception as e:
                st.error(f"Error analyzing address: {e}")

# Token Analysis Page
def page_token_analysis():
    st.title("🪙 Token Analysis")
    
    st.write("""
    Analyze a Solana token to assess risk, detect insider trading patterns, and identify potential
    rug pull indicators. Enter a token mint address below to begin.
    """)
    
    # Token input
    token_mint = st.text_input("Enter token mint address", placeholder="e.g., EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
    
    if token_mint:
        if not is_valid_token_mint(token_mint):
            st.error("Invalid token mint address format. Please check the address and try again.")
            return
        
        # Create analysis tabs
        tab_overview, tab_holders, tab_insiders, tab_risk = st.tabs([
            "Overview", "Holders", "Insider Analysis", "Risk Assessment"
        ])
        
        with st.spinner("Analyzing token..."):
            # Fetch basic token data
            try:
                token_details = collectors["vybe"].get_token_details(token_mint)
                
                with tab_overview:
                    st.subheader("Token Overview")
                    
                    # Display basic information
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Token Name", token_details.get("name", "Unknown"))
                    
                    with col2:
                        st.metric("Token Symbol", token_details.get("symbol", "???"))
                    
                    with col3:
                        st.metric("Price", f"${token_details.get('price', 0):.6f}")
                    
                    # More token metrics
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Market Cap", f"${token_details.get('market_cap', 0):.2f}")
                    
                    with col2:
                        st.metric("24h Volume", f"${token_details.get('volume_24h', 0):.2f}")
                    
                    with col3:
                        st.metric("Holders Count", token_details.get("holders_count", 0))
                    
                    # Token price history
                    st.subheader("Price History")
                    
                    try:
                        price_data = collectors["vybe"].get_token_price_ohlcv(
                            token_mint,
                            resolution="1d",
                            time_start=int((datetime.now() - timedelta(days=30)).timestamp()),
                            time_end=int(datetime.now().timestamp())
                        )
                        
                        price_history = price_data.get("data", [])
                        
                        if price_history:
                            # Convert to DataFrame
                            df_price = pd.DataFrame(price_history)
                            
                            if "time" in df_price.columns and "close" in df_price.columns:
                                # Convert time to datetime
                                df_price["time"] = pd.to_datetime(df_price["time"], unit="s")
                                
                                # Create candlestick chart
                                fig = go.Figure(data=[go.Candlestick(
                                    x=df_price["time"],
                                    open=df_price["open"],
                                    high=df_price["high"],
                                    low=df_price["low"],
                                    close=df_price["close"]
                                )])
                                
                                fig.update_layout(
                                    title="Token Price (30 Days)",
                                    xaxis_title="Date",
                                    yaxis_title="Price (USD)"
                                )
                                
                                st.plotly_chart(fig, use_container_width=True)
                                
                                # Volume chart
                                if "volume" in df_price.columns:
                                    fig = px.bar(
                                        df_price,
                                        x="time",
                                        y="volume",
                                        title="Trading Volume (30 Days)",
                                        labels={"time": "Date", "volume": "Volume"},
                                        color_discrete_sequence=["#4575b4"]
                                    )
                                    
                                    st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("Insufficient price data to display chart.")
                        else:
                            st.info("No price history available for this token.")
                    except Exception as e:
                        st.warning(f"Could not fetch price history: {e}")
                
                with tab_holders:
                    st.subheader("Token Holders")
                    
                    try:
                        holders_data = collectors["vybe"].get_token_top_holders(token_mint)
                        holders = holders_data.get("data", [])
                        
                        if holders:
                            # Create DataFrame
                            df_holders = pd.DataFrame(holders)
                            
                            # Display top holders distribution
                            st.write("#### Top Holders Distribution")
                            
                            if "percentage" in df_holders.columns:
                                # Sort by percentage
                                df_holders = df_holders.sort_values("percentage", ascending=False)
                                
                                # Take top 10 holders
                                top_10 = df_holders.head(10)
                                
                                # Create bar chart
                                fig = px.bar(
                                    top_10,
                                    x="address",
                                    y="percentage",
                                    title="Top 10 Holders",
                                    labels={"address": "Wallet", "percentage": "Percentage (%)"},
                                    color="percentage",
                                    color_continuous_scale=["#1a9850", "#91cf60", "#ffffbf", "#fc8d59", "#d73027"]
                                )
                                
                                # Update x-axis labels to shortened addresses
                                fig.update_xaxes(
                                    ticktext=[addr[:6] + "..." + addr[-4:] for addr in top_10["address"]],
                                    tickvals=top_10["address"]
                                )
                                
                                st.plotly_chart(fig, use_container_width=True)
                                
                                # Calculate concentration metrics
                                top_holder_pct = df_holders.iloc[0]["percentage"] if len(df_holders) > 0 else 0
                                top5_pct = df_holders.head(5)["percentage"].sum() if len(df_holders) >= 5 else df_holders["percentage"].sum()
                                top10_pct = df_holders.head(10)["percentage"].sum() if len(df_holders) >= 10 else df_holders["percentage"].sum()
                                
                                # Display concentration metrics
                                col1, col2, col3 = st.columns(3)
                                
                                with col1:
                                    st.metric("Top Holder", f"{top_holder_pct:.2f}%")
                                
                                with col2:
                                    st.metric("Top 5 Holders", f"{top5_pct:.2f}%")
                                
                                with col3:
                                    st.metric("Top 10 Holders", f"{top10_pct:.2f}%")
                                
                                # Display top holders table
                                st.write("#### Top Holders Details")
                                
                                # Format address for display
                                df_display = df_holders.copy()
                                df_display["short_address"] = df_display["address"].apply(lambda x: x[:10] + "..." + x[-4:])
                                
                                st.dataframe(
                                    df_display[["short_address", "percentage", "balance"]].rename(
                                        columns={"short_address": "Address", "percentage": "Percentage (%)", "balance": "Balance"}
                                    ).head(20)
                                )
                            else:
                                st.info("Holder percentage data not available.")
                        else:
                            st.info("No holder data available for this token.")
                    except Exception as e:
                        st.warning(f"Could not fetch token holders: {e}")
                
                with tab_insiders:
                    st.subheader("Insider Analysis")
                    
                    try:
                        # Get token report to check for creator
                        token_report = collectors["rugcheck"].get_token_report(token_mint)
                        
                        creator_address = token_report.get("creator")
                        
                        if creator_address:
                            st.write(f"#### Token Creator")
                            st.info(f"Creator Address: `{creator_address}`")
                            
                            # Get creator's other tokens
                            creator_tokens = token_report.get("creatorTokens", [])
                            
                            if creator_tokens:
                                st.write(f"Creator has launched {len(creator_tokens)} tokens.")
                                
                                # Create DataFrame
                                df_creator_tokens = pd.DataFrame(creator_tokens)
                                
                                if not df_creator_tokens.empty and "createdAt" in df_creator_tokens.columns:
                                    # Convert createdAt to datetime
                                    df_creator_tokens["createdAt"] = pd.to_datetime(df_creator_tokens["createdAt"])
                                    
                                    # Sort by creation date
                                    df_creator_tokens = df_creator_tokens.sort_values("createdAt", ascending=False)
                                    
                                    # Display creator tokens table
                                    st.write("#### Other Tokens by Same Creator")
                                    
                                    # Format mint for display
                                    df_creator_tokens["short_mint"] = df_creator_tokens["mint"].apply(lambda x: x[:10] + "..." + x[-4:])
                                    
                                    st.dataframe(
                                        df_creator_tokens[["short_mint", "createdAt", "marketCap"]].rename(
                                            columns={"short_mint": "Mint", "createdAt": "Created At", "marketCap": "Market Cap"}
                                        )
                                    )
                            
                        # Get insider graph
                        insider_graph_data = collectors["rugcheck"].get_token_insider_graph(token_mint)
                        
                        if insider_graph_data:
                            st.write("#### Insider Network")
                            
                            # Build insider graph
                            insider_graph = build_token_insider_graph(insider_graph_data)
                            graph_data = insider_graph.export_to_json()
                            
                            # Visualize the graph
                            display_transaction_flow(graph_data)
                            
                            # Detect suspicious patterns
                            suspicious_patterns = insider_graph.detect_suspicious_patterns()
                            
                            if suspicious_patterns:
                                st.write("#### Suspicious Patterns")
                                
                                for pattern in suspicious_patterns:
                                    with st.expander(f"{pattern['type']}: {pattern['description']}"):
                                        st.write(f"**Risk Score**: {pattern['risk_score']}")
                                        
                                        if "examples" in pattern:
                                            st.write("**Examples**:")
                                            for example in pattern["examples"]:
                                                st.write(f"- {example}")
                            else:
                                st.success("No suspicious patterns detected in the insider network.")
                        else:
                            st.info("No insider graph data available for this token.")
                    except Exception as e:
                        st.warning(f"Could not fetch insider data: {e}")
                
                with tab_risk:
                    st.subheader("Risk Assessment")
                    
                    try:
                        # Get token report summary
                        token_summary = collectors["rugcheck"].get_token_report_summary(token_mint)
                        
                        if token_summary:
                            # Calculate risk score
                            token_holders = []
                            token_transfers = pd.DataFrame()
                            token_insider_data = {}
                            
                            try:
                                holders_data = collectors["vybe"].get_token_top_holders(token_mint)
                                token_holders = holders_data.get("data", [])
                            except:
                                pass
                            
                            risk_score = calculate_token_risk(
                                token_mint,
                                token_details,
                                token_holders,
                                token_transfers,
                                token_insider_data,
                                pd.DataFrame([token_summary])
                            )
                            
                            # Display risk score visualization
                            display_risk_score(risk_score, entity_type="token")
                            
                            # Rug pull assessment
                            st.write("### Rug Pull Assessment")
                            
                            # RugCheck normalized score
                            normalized_score = token_summary.get("score_normalised", 0)
                            
                            # Check contract risk factors
                            has_mint_authority = False
                            has_freeze_authority = False
                            
                            for risk in token_summary.get("risks", []):
                                if risk.get("name") == "mint_authority":
                                    has_mint_authority = True
                                elif risk.get("name") == "freeze_authority":
                                    has_freeze_authority = True
                            
                            # Check liquidity lock
                            liquidity_locked_pct = 0
                            
                            if token_report and "markets" in token_report:
                                for market in token_report.get("markets", []):
                                    if "lp" in market and "lpLockedPct" in market["lp"]:
                                        liquidity_locked_pct = max(liquidity_locked_pct, market["lp"]["lpLockedPct"])
                            
                            # Calculate rug pull likelihood
                            rug_factors = []
                            rug_score = 0
                            
                            if has_mint_authority:
                                rug_factors.append("Mint authority is active")
                                rug_score += 30
                            
                            if has_freeze_authority:
                                rug_factors.append("Freeze authority is active")
                                rug_score += 20
                            
                            if liquidity_locked_pct < 50:
                                rug_factors.append(f"Low liquidity lock percentage ({liquidity_locked_pct:.2f}%)")
                                rug_score += 40
                            elif liquidity_locked_pct < 80:
                                rug_factors.append(f"Medium liquidity lock percentage ({liquidity_locked_pct:.2f}%)")
                                rug_score += 20
                            
                            # Determine rug pull likelihood
                            if rug_score >= 80:
                                rug_likelihood = "Very High"
                                rug_color = "#d73027"
                            elif rug_score >= 60:
                                rug_likelihood = "High"
                                rug_color = "#fc8d59"
                            elif rug_score >= 40:
                                rug_likelihood = "Medium"
                                rug_color = "#ffffbf"
                            elif rug_score >= 20:
                                rug_likelihood = "Low"
                                rug_color = "#91cf60"
                            else:
                                rug_likelihood = "Very Low"
                                rug_color = "#1a9850"
                            
                            # Display rug pull assessment
                            st.markdown(f"#### Rug Pull Likelihood: <span style='color:{rug_color}'>{rug_likelihood}</span>", unsafe_allow_html=True)
                            
                            # Display gauge chart for rug pull score
                            fig = go.Figure(go.Indicator(
                                mode="gauge+number",
                                value=rug_score,
                                domain={'x': [0, 1], 'y': [0, 1]},
                                title={'text': "Rug Pull Score"},
                                gauge={
                                    'axis': {'range': [0, 100]},
                                    'bar': {'color': rug_color},
                                    'steps': [
                                        {'range': [0, 20], 'color': "#1a9850"},
                                        {'range': [20, 40], 'color': "#91cf60"},
                                        {'range': [40, 60], 'color': "#ffffbf"},
                                        {'range': [60, 80], 'color': "#fc8d59"},
                                        {'range': [80, 100], 'color': "#d73027"}
                                    ],
                                    'threshold': {
                                        'line': {'color': "red", 'width': 4},
                                        'thickness': 0.75,
                                        'value': rug_score
                                    }
                                }
                            ))
                            
                            fig.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=20))
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Display rug pull factors
                            if rug_factors:
                                st.write("#### Rug Pull Risk Factors")
                                for factor in rug_factors:
                                    st.warning(factor)
                            else:
                                st.success("No significant rug pull risk factors detected.")
                        else:
                            st.info("No risk data available for this token.")
                    except Exception as e:
                        st.warning(f"Could not fetch risk data: {e}")
                
            except Exception as e:
                st.error(f"Error analyzing token: {e}")

# Dashboard Home Page
def page_home():
    st.title("🛡️ SolanaGuard Dashboard")
    
    st.write("""
    Welcome to SolanaGuard, a comprehensive analysis platform for detecting suspicious activities,
    money laundering, and high-risk entities on the Solana blockchain.
    
    ## Features
    
    - **Address Analysis**: Analyze wallet addresses for risk factors and suspicious behavior
    - **Token Analysis**: Evaluate tokens for rug pull potential and insider trading patterns
    - **Money Laundering Detection**: Identify potential money laundering routes and patterns
    - **Risk Scoring**: Calculate comprehensive risk scores for addresses and tokens
    
    ## Getting Started
    
    Select one of the analysis options from the sidebar to begin exploring the Solana blockchain.
    """)
    
    # Display quick search
    st.subheader("Quick Search")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### Address Analysis")
        address = st.text_input("Enter a Solana wallet address", key="home_address")
        if address:
            if is_valid_solana_address(address):
                st.success(f"Valid address format: {address[:10]}...{address[-6:]}")
                if st.button("Analyze Address"):
                    st.session_state.page = "address_analysis"
                    st.session_state.search_address = address
                    st.experimental_rerun()
            else:
                st.error("Invalid Solana address format")
    
    with col2:
        st.write("### Token Analysis")
        token = st.text_input("Enter a token mint address", key="home_token")
        if token:
            if is_valid_token_mint(token):
                st.success(f"Valid token mint format: {token[:10]}...{token[-6:]}")
                if st.button("Analyze Token"):
                    st.session_state.page = "token_analysis"
                    st.session_state.search_token = token
                    st.experimental_rerun()
            else:
                st.error("Invalid token mint format")
    
    # Display recent suspicious activities
    st.subheader("Recent Suspicious Activities")
    
    # This would be populated with real data in a full implementation
    # For now, just show placeholders
    with st.container():
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info("#### Potential Mixer Detected")
            st.write("A new potential mixing service has been identified.")
            st.button("View Details", key="mixer_details", disabled=True)
        
        with col2:
            st.warning("#### Suspicious Token")
            st.write("Token with high rug pull likelihood detected.")
            st.button("View Details", key="token_details", disabled=True)
        
        with col3:
            st.error("#### Laundering Activity")
            st.write("Unusual cross-chain activity detected.")
            st.button("View Details", key="laundering_details", disabled=True)

def main():
    # Initialize session state
    if "page" not in st.session_state:
        st.session_state.page = "home"
    
    # Create sidebar
    st.sidebar.title("SolanaGuard")
    
    # Navigation
    st.sidebar.subheader("Navigation")
    
    if st.sidebar.button("🏠 Home"):
        st.session_state.page = "home"
        st.experimental_rerun()
    
    if st.sidebar.button("🔍 Address Analysis"):
        st.session_state.page = "address_analysis"
        st.experimental_rerun()
    
    if st.sidebar.button("🪙 Token Analysis"):
        st.session_state.page = "token_analysis"
        st.experimental_rerun()
    
    # Display current page
    if st.session_state.page == "home":
        page_home()
    elif st.session_state.page == "address_analysis":
        page_address_analysis()
    elif st.session_state.page == "token_analysis":
        page_token_analysis()

if __name__ == "__main__":
    main()