"""
Risk scoring utilities for Solana addresses and transactions.
"""
import numpy as np
from typing import Dict, List, Any, Union, Optional

def calculate_address_risk(
    address: str, 
    mixer_interactions: int = 0, 
    high_risk_counterparties: int = 0,
    transaction_volume: float = 0,
    transaction_velocity: float = 0,
    cross_chain_activity: int = 0
) -> float:
    """
    Calculate risk score for an address based on various risk factors.
    
    Args:
        address: The blockchain address
        mixer_interactions: Number of interactions with mixer services
        high_risk_counterparties: Number of high-risk counterparties
        transaction_volume: Volume of transactions in USD
        transaction_velocity: Number of transactions per day
        cross_chain_activity: Number of cross-chain transactions
        
    Returns:
        Risk score between 0 and 100 (higher = more risky)
    """
    base_score = 0
    
    # Mixer interaction risk (highest weight)
    mixer_risk = min(70, mixer_interactions * 15)
    
    # High-risk counterparty risk
    counterparty_risk = min(50, high_risk_counterparties * 8)
    
    # Transaction volume risk
    volume_tiers = [10000, 50000, 100000, 500000, 1000000]
    volume_scores = [10, 20, 30, 40, 50]
    
    volume_risk = 0
    for tier, score in zip(volume_tiers, volume_scores):
        if transaction_volume > tier:
            volume_risk = score
    
    # Transaction velocity risk
    velocity_risk = min(30, transaction_velocity * 0.5)
    
    # Cross-chain activity risk
    cross_chain_risk = min(40, cross_chain_activity * 5)
    
    # Combine all risk factors with weights
    risk_factors = [
        (mixer_risk, 0.4),        # 40% weight
        (counterparty_risk, 0.2),  # 20% weight
        (volume_risk, 0.15),       # 15% weight
        (velocity_risk, 0.15),     # 15% weight
        (cross_chain_risk, 0.1)    # 10% weight
    ]
    
    weighted_score = sum(score * weight for score, weight in risk_factors)
    
    # Scale to 0-100 range and ensure we don't exceed 100
    return min(100, weighted_score)
