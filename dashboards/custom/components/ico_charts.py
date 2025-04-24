"""
ICO chart components for SolanaGuard dashboard.
Provides functions to visualize token launch and ICO-related metrics.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

def display_token_price_chart(price_data: Dict[str, Any], timeframe: str = "30d"):
    """
    Display a token price chart with OHLC data.
    
    Args:
        price_data: Dictionary containing OHLC price data
        timeframe: Timeframe to display (e.g., "7d", "30d", "90d")
    """
    if not price_data or "data" not in price_data:
        st.warning("No price data available")
        return
    
    price_history = price_data.get("data", [])
    
    if not price_history:
        st.warning("Empty price history")
        return
    
    # Convert to DataFrame
    df_price = pd.DataFrame(price_history)
    
    if "time" not in df_price.columns or "close" not in df_price.columns:
        st.warning("Invalid price data format")
        return
    
    # Convert time to datetime
    df_price["time"] = pd.to_datetime(df_price["time"], unit="s")
    
    # Create candlestick chart
    fig = go.Figure(data=[go.Candlestick(
        x=df_price["time"],
        open=df_price["open"],
        high=df_price["high"],
        low=df_price["low"],
        close=df_price["close"],
        increasing_line_color='#26a69a', 
        decreasing_line_color='#ef5350'
    )])
    
    fig.update_layout(
        title=f"Token Price ({timeframe})",
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        xaxis_rangeslider_visible=False,
        height=400,
        margin=dict(l=10, r=10, t=50, b=10)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Volume chart
    if "volume" in df_price.columns:
        fig_volume = px.bar(
            df_price,
            x="time",
            y="volume",
            title="Trading Volume",
            labels={"time": "Date", "volume": "Volume"},
            color_discrete_sequence=["#4575b4"]
        )
        
        fig_volume.update_layout(
            height=250,
            margin=dict(l=10, r=10, t=50, b=10),
            xaxis_title="",
            yaxis_title="Volume"
        )
        
        st.plotly_chart(fig_volume, use_container_width=True)

def display_token_allocation(allocation_data: List[Dict[str, Any]]):
    """
    Display a token allocation chart.
    
    Args:
        allocation_data: List of allocation dictionaries with category and percentage
    """
    if not allocation_data:
        st.warning("No token allocation data available")
        return
    
    # Convert to DataFrame
    df_allocation = pd.DataFrame(allocation_data)
    
    if "category" not in df_allocation.columns or "percentage" not in df_allocation.columns:
        st.warning("Invalid allocation data format")
        return
    
    # Create pie chart
    fig = px.pie(
        df_allocation,
        values="percentage",
        names="category",
        title="Token Allocation",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    
    fig.update_layout(
        height=400,
        margin=dict(l=10, r=10, t=50, b=10)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def display_ico_timeline(timeline_events: List[Dict[str, Any]]):
    """
    Display a timeline of ICO events.
    
    Args:
        timeline_events: List of timeline event dictionaries with date and description
    """
    if not timeline_events:
        st.warning("No timeline data available")
        return
    
    # Convert to DataFrame
    df_timeline = pd.DataFrame(timeline_events)
    
    if "date" not in df_timeline.columns or "event" not in df_timeline.columns:
        st.warning("Invalid timeline data format")
        return
    
    # Ensure date is datetime
    df_timeline["date"] = pd.to_datetime(df_timeline["date"])
    df_timeline = df_timeline.sort_values("date")
    
    # Create figure
    fig = go.Figure()
    
    # Add events
    for i, event in enumerate(df_timeline.itertuples()):
        fig.add_trace(go.Scatter(
            x=[event.date],
            y=[0],
            mode="markers+text",
            marker=dict(size=15, color="#4575b4", symbol="circle"),
            text=[event.event],
            textposition="top center",
            name=event.event,
            hoverinfo="text",
            hovertext=f"{event.date.strftime('%Y-%m-%d')}: {event.event}"
        ))
    
    # Add line connecting events
    fig.add_trace(go.Scatter(
        x=df_timeline["date"],
        y=[0] * len(df_timeline),
        mode="lines",
        line=dict(color="#bdbdbd", width=2),
        hoverinfo="skip",
        showlegend=False
    ))
    
    # Update layout
    fig.update_layout(
        title="ICO Timeline",
        showlegend=False,
        xaxis=dict(title=""),
        yaxis=dict(
            title="",
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            range=[-1, 1]
        ),
        height=250,
        margin=dict(l=10, r=10, t=50, b=10)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def display_holder_distribution(holders_data: Dict[str, Any]):
    """
    Display token holder distribution charts.
    
    Args:
        holders_data: Dictionary with token holder data
    """
    if not holders_data or "data" not in holders_data:
        st.warning("No holder data available")
        return
    
    holders = holders_data.get("data", [])
    
    if not holders:
        st.warning("Empty holder data")
        return
    
    # Convert to DataFrame
    df_holders = pd.DataFrame(holders)
    
    if "address" not in df_holders.columns or "percentage" not in df_holders.columns:
        st.warning("Invalid holder data format")
        return
    
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
    
    fig.update_layout(
        height=400,
        margin=dict(l=10, r=10, t=50, b=10)
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
