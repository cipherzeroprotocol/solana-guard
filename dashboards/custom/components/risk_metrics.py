"""
Risk metrics visualization components for SolanaGuard dashboard.
Provides functions to display risk scores and metrics.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional, Any, Union

def display_risk_score(risk_score: Dict[str, Any], entity_type: str = "address"):
    """
    Display a risk score visualization with gauge chart and risk factors.
    
    Args:
        risk_score: Dictionary containing risk score and factors
        entity_type: Type of entity being analyzed ("address" or "token")
    """
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
            st.info(f"No risk factors identified for this {entity_type}.")
        else:
            # Create DataFrame for risk factors
            df_factors = pd.DataFrame(factors)
            
            # Sort by score descending
            if "score" in df_factors.columns:
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
            else:
                # Simplified display when score is not available
                for i, factor in enumerate(factors):
                    if isinstance(factor, dict):
                        st.write(f"- **{factor.get('name', f'Factor {i+1}')}**: {factor.get('description', 'No description')}")
                    else:
                        st.write(f"- {factor}")

def display_risk_comparison(entities: List[Dict[str, Any]], entity_type: str = "address"):
    """
    Display a comparison of risk scores for multiple entities.
    
    Args:
        entities: List of dictionaries with entity data including risk scores
        entity_type: Type of entities being compared
    """
    if not entities:
        st.warning(f"No {entity_type} data to compare")
        return
    
    # Extract risk scores and labels
    scores = []
    labels = []
    colors = []
    
    for entity in entities:
        score = entity.get("risk_score", 0)
        name = entity.get("name", entity.get("address", entity.get("id", f"Unknown {entity_type}")))
        
        if len(name) > 12:
            name = name[:8] + "..." + name[-4:]
            
        scores.append(score)
        labels.append(name)
        
        # Determine color based on risk score
        if score >= 80:
            colors.append("#d73027")  # Red
        elif score >= 60:
            colors.append("#fc8d59")  # Orange
        elif score >= 40:
            colors.append("#ffffbf")  # Yellow
        elif score >= 20:
            colors.append("#91cf60")  # Light green
        else:
            colors.append("#1a9850")  # Green
    
    # Create bar chart
    fig = px.bar(
        x=labels,
        y=scores,
        color=scores,
        color_continuous_scale=["#1a9850", "#91cf60", "#ffffbf", "#fc8d59", "#d73027"],
        labels={"x": entity_type.capitalize(), "y": "Risk Score"},
        title=f"{entity_type.capitalize()} Risk Comparison"
    )
    
    fig.update_layout(height=400, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True)

def display_risk_factors_breakdown(risk_score: Dict[str, Any]):
    """
    Display a detailed breakdown of risk factors.
    
    Args:
        risk_score: Dictionary containing risk score and factors
    """
    factors = risk_score.get("risk_factors", [])
    
    if not factors:
        st.info("No risk factors available for breakdown")
        return
    
    # Group factors by category
    categories = {}
    for factor in factors:
        if isinstance(factor, dict):
            category = factor.get("category", "Other")
            if category not in categories:
                categories[category] = []
            categories[category].append(factor)
    
    # Calculate category scores
    category_scores = {}
    for category, factors_list in categories.items():
        if factors_list:
            scores = [f.get("score", 0) for f in factors_list]
            category_scores[category] = sum(scores) / len(scores)
    
    if category_scores:
        # Create radar chart for category breakdown
        categories_list = list(category_scores.keys())
        scores_list = list(category_scores.values())
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=scores_list + [scores_list[0]],
            theta=categories_list + [categories_list[0]],
            fill='toself',
            line=dict(color='rgba(214, 39, 40, 0.8)'),
            name='Risk Categories'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100]
                )
            ),
            showlegend=False,
            title="Risk Category Breakdown",
            height=400,
            margin=dict(l=10, r=10, t=50, b=10)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Display factors by category
    for category, factors_list in categories.items():
        with st.expander(f"{category} Factors"):
            for factor in sorted(factors_list, key=lambda x: x.get("score", 0), reverse=True):
                st.write(f"**{factor.get('name')}** (Score: {factor.get('score', 0)})")
                st.write(f"{factor.get('description', '')}")
                st.write("---")

def display_risk_threshold_alerts(risk_score: Dict[str, Any], thresholds: Dict[str, int]):
    """
    Display alerts based on risk score thresholds.
    
    Args:
        risk_score: Dictionary containing risk score and factors
        thresholds: Dictionary with threshold levels and their values
    """
    score = risk_score.get("risk_score", 0)
    
    # Default thresholds if not provided
    if not thresholds:
        thresholds = {
            "critical": 80,
            "high": 60,
            "medium": 40,
            "low": 20
        }
    
    if score >= thresholds.get("critical", 80):
        st.error("⚠️ **CRITICAL RISK ALERT**: This entity has a critical risk score that requires immediate attention.")
    elif score >= thresholds.get("high", 60):
        st.warning("⚠️ **HIGH RISK ALERT**: This entity has a high risk score that should be investigated.")
    elif score >= thresholds.get("medium", 40):
        st.info("ℹ️ **MEDIUM RISK NOTICE**: This entity has a moderate risk score worth monitoring.")
    elif score >= thresholds.get("low", 20):
        st.success("✅ **LOW RISK**: This entity has a low risk score but should still be monitored.")
    else:
        st.success("✅ **VERY LOW RISK**: This entity has a very low risk score.")
