"""
Timeline visualization components for SolanaGuard dashboard.
Provides functions to display transaction and event timelines.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

def display_transaction_timeline(tx_history: pd.DataFrame):
    """
    Display a timeline of transactions.
    
    Args:
        tx_history: DataFrame containing transaction history
    """
    if tx_history.empty:
        st.info("No transaction history to display")
        return
    
    # Ensure required columns exist
    if "block_time" not in tx_history.columns:
        st.warning("Transaction data missing 'block_time' column")
        return
    
    # Convert block_time to datetime
    if pd.api.types.is_numeric_dtype(tx_history["block_time"]):
        # Convert from Unix timestamp
        tx_history["datetime"] = pd.to_datetime(tx_history["block_time"], unit="s")
    else:
        # Try to parse as datetime string
        try:
            tx_history["datetime"] = pd.to_datetime(tx_history["block_time"])
        except:
            st.warning("Could not convert block_time to datetime")
            return
    
    # Sort by datetime
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
    
    fig.update_layout(
        height=300,
        margin=dict(l=10, r=10, t=50, b=10),
        xaxis_title="Date",
        yaxis_title="Transaction Count"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Check for status column to count success/failure
    if "success" in tx_history.columns:
        success_count = tx_history["success"].value_counts()
        
        # Create pie chart for success/failure
        labels = ["Success", "Failed"]
        values = [
            success_count.get(True, 0),
            success_count.get(False, 0)
        ]
        
        fig_success = px.pie(
            names=labels,
            values=values,
            title="Transaction Success Rate",
            color_discrete_sequence=["#1a9850", "#d73027"]
        )
        
        fig_success.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=50, b=10)
        )
        
        st.plotly_chart(fig_success, use_container_width=True)

def display_token_transfer_timeline(token_transfers: pd.DataFrame):
    """
    Display a timeline of token transfers.
    
    Args:
        token_transfers: DataFrame containing token transfer data
    """
    if token_transfers.empty:
        st.info("No token transfers to display")
        return
    
    # Ensure required columns exist
    required_cols = ["block_time", "mint", "direction", "amount_change"]
    missing_cols = [col for col in required_cols if col not in token_transfers.columns]
    
    if missing_cols:
        st.warning(f"Token transfer data missing columns: {', '.join(missing_cols)}")
        return
    
    # Convert block_time to datetime
    if pd.api.types.is_numeric_dtype(token_transfers["block_time"]):
        # Convert from Unix timestamp
        token_transfers["datetime"] = pd.to_datetime(token_transfers["block_time"], unit="s")
    else:
        # Try to parse as datetime string
        try:
            token_transfers["datetime"] = pd.to_datetime(token_transfers["block_time"])
        except:
            st.warning("Could not convert block_time to datetime")
            return
    
    # Sort by datetime
    token_transfers = token_transfers.sort_values("datetime")
    
    # Token distribution by mint
    token_counts = token_transfers["mint"].value_counts().reset_index()
    token_counts.columns = ["mint", "count"]
    
    # Direction distribution
    direction_counts = token_transfers["direction"].value_counts().reset_index()
    direction_counts.columns = ["direction", "count"]
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Plot token distribution
        fig_tokens = px.pie(
            token_counts.head(10),
            values="count",
            names="mint",
            title="Token Distribution",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        
        fig_tokens.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=50, b=10)
        )
        
        st.plotly_chart(fig_tokens, use_container_width=True)
    
    with col2:
        # Plot direction distribution
        fig_direction = px.pie(
            direction_counts,
            values="count",
            names="direction",
            title="Transfer Direction",
            hole=0.4,
            color_discrete_sequence=["#91cf60", "#fc8d59"]
        )
        
        fig_direction.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=50, b=10)
        )
        
        st.plotly_chart(fig_direction, use_container_width=True)
    
    # Daily transfer volume
    if "amount_change" in token_transfers.columns:
        # Group by date
        daily_volume = token_transfers.groupby(token_transfers["datetime"].dt.date)["amount_change"].sum().reset_index()
        daily_volume.columns = ["date", "volume"]
        
        # Plot daily volume
        fig_volume = px.line(
            daily_volume,
            x="date",
            y="volume",
            title="Daily Transfer Volume",
            labels={"date": "Date", "volume": "Volume"},
            color_discrete_sequence=["#4575b4"]
        )
        
        fig_volume.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=50, b=10),
            xaxis_title="Date",
            yaxis_title="Volume"
        )
        
        st.plotly_chart(fig_volume, use_container_width=True)

def display_laundering_event_timeline(ml_routes: pd.DataFrame):
    """
    Display a timeline of money laundering events.
    
    Args:
        ml_routes: DataFrame containing money laundering route data
    """
    if ml_routes.empty:
        st.info("No money laundering events to display")
        return
    
    # Ensure required columns exist
    if "block_time" not in ml_routes.columns:
        st.warning("Money laundering data missing 'block_time' column")
        return
    
    # Convert block_time to datetime if needed
    if pd.api.types.is_numeric_dtype(ml_routes["block_time"]):
        ml_routes["datetime"] = pd.to_datetime(ml_routes["block_time"], unit="s")
    else:
        try:
            ml_routes["datetime"] = pd.to_datetime(ml_routes["block_time"])
        except:
            st.warning("Could not convert block_time to datetime")
            return
    
    # Sort by datetime
    ml_routes = ml_routes.sort_values("datetime")
    
    # Create figure for timeline
    fig = go.Figure()
    
    # Add events to timeline
    for i, event in enumerate(ml_routes.itertuples()):
        event_text = f"{getattr(event, 'flow_type', 'Unknown')}"
        
        # Add risk score if available
        if hasattr(event, 'risk_score'):
            if event.risk_score >= 80:
                color = "#d73027"  # Red for high risk
            elif event.risk_score >= 60:
                color = "#fc8d59"  # Orange for medium-high risk
            elif event.risk_score >= 40:
                color = "#ffffbf"  # Yellow for medium risk
            else:
                color = "#91cf60"  # Green for low risk
            
            event_text += f" (Risk: {event.risk_score})"
        else:
            color = "#4575b4"  # Default blue
        
        # Add amount if available
        hover_text = event_text
        if hasattr(event, 'amount_usd') and event.amount_usd is not None:
            hover_text += f"<br>Amount: ${event.amount_usd:.2f}"
        
        # Add source/target if available
        if hasattr(event, 'source_address') and hasattr(event, 'target_address'):
            hover_text += f"<br>From: {event.source_address[:6]}...{event.source_address[-4:]}"
            hover_text += f"<br>To: {event.target_address[:6]}...{event.target_address[-4:]}"
        
        # Add event to timeline
        fig.add_trace(go.Scatter(
            x=[event.datetime],
            y=[0],
            mode="markers+text",
            marker=dict(size=15, color=color, symbol="circle"),
            text=[event_text],
            textposition="top center",
            hoverinfo="text",
            hovertext=hover_text
        ))
    
    # Create line connecting events
    fig.add_trace(go.Scatter(
        x=ml_routes["datetime"],
        y=[0] * len(ml_routes),
        mode="lines",
        line=dict(color="#bdbdbd", width=2),
        hoverinfo="skip",
        showlegend=False
    ))
    
    # Update layout
    fig.update_layout(
        title="Money Laundering Events Timeline",
        showlegend=False,
        xaxis=dict(title="Date and Time"),
        yaxis=dict(
            title="",
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            range=[-1, 1]
        ),
        height=300,
        margin=dict(l=10, r=10, t=50, b=10)
    )
    
    st.plotly_chart(fig, use_container_width=True)
