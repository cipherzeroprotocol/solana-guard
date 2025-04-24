"""
Utility functions for Solana address analysis.
Provides methods for address classification, clustering, and pattern detection.
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def classify_address(
    address: str,
    tx_history: pd.DataFrame,
    token_transfers: pd.DataFrame,
    risk_score: Dict
) -> Dict:
    """
    Classify a Solana address based on transaction patterns and risk score.
    
    Args:
        address: The Solana address to classify
        tx_history: Transaction history DataFrame
        token_transfers: Token transfers DataFrame
        risk_score: Risk score data from Range API
        
    Returns:
        Dictionary with address classification
    """
    logger.info(f"Classifying address: {address}")
    
    classification = {
        "address": address,
        "type": "unknown",
        "confidence": 0,
        "risk_level": "unknown",
        "activity_level": "unknown",
        "features": {}
    }
    
    # Extract classification features
    features = {}
    
    # Basic transaction metrics
    if not tx_history.empty:
        features["tx_count"] = len(tx_history)
        features["first_tx_time"] = tx_history["block_time"].min()
        features["last_tx_time"] = tx_history["block_time"].max()
        
        if features.get("first_tx_time") and features.get("last_tx_time"):
            features["active_days"] = (features["last_tx_time"] - features["first_tx_time"]) / (60 * 60 * 24)
            features["tx_per_day"] = features["tx_count"] / max(1, features["active_days"])
    else:
        features["tx_count"] = 0
        features["active_days"] = 0
        features["tx_per_day"] = 0
    
    # Token transfer metrics
    if not token_transfers.empty:
        # Identify sent and received transfers
        sent_mask = token_transfers["direction"] == "sent"
        received_mask = token_transfers["direction"] == "received"
        
        sent_transfers = token_transfers[sent_mask]
        received_transfers = token_transfers[received_mask]
        
        features["sent_count"] = len(sent_transfers)
        features["received_count"] = len(received_transfers)
        features["token_count"] = token_transfers["mint"].nunique()
        
        if not sent_transfers.empty:
            features["unique_recipients"] = sent_transfers["token_account"].nunique()
        else:
            features["unique_recipients"] = 0
            
        if not received_transfers.empty:
            features["unique_senders"] = received_transfers["token_account"].nunique()
        else:
            features["unique_senders"] = 0
    else:
        features["sent_count"] = 0
        features["received_count"] = 0
        features["token_count"] = 0
        features["unique_recipients"] = 0
        features["unique_senders"] = 0
    
    # Extract risk information
    risk_level = "unknown"
    risk_score_value = 0
    
    if risk_score:
        risk_score_value = risk_score.get("risk_score", 0)
        
        if risk_score_value >= 75:
            risk_level = "high"
        elif risk_score_value >= 50:
            risk_level = "medium"
        elif risk_score_value >= 25:
            risk_level = "low"
        else:
            risk_level = "very_low"
    
    features["risk_score"] = risk_score_value
    classification["risk_level"] = risk_level
    
    # Determine activity level
    if features["tx_count"] > 1000 or features["tx_per_day"] > 50:
        activity_level = "very_high"
    elif features["tx_count"] > 100 or features["tx_per_day"] > 10:
        activity_level = "high"
    elif features["tx_count"] > 10 or features["tx_per_day"] > 1:
        activity_level = "medium"
    elif features["tx_count"] > 0:
        activity_level = "low"
    else:
        activity_level = "inactive"
    
    classification["activity_level"] = activity_level
    
    # Apply classification rules to determine address type
    address_type, confidence = _determine_address_type(features, risk_score)
    
    classification["type"] = address_type
    classification["confidence"] = confidence
    classification["features"] = features
    
    logger.info(f"Classified {address} as {address_type} (confidence: {confidence:.2f})")
    return classification

def _determine_address_type(features: Dict, risk_score: Dict) -> Tuple[str, float]:
    """
    Determine address type based on extracted features.
    
    Args:
        features: Extracted address features
        risk_score: Risk score data
        
    Returns:
        Tuple of (address_type, confidence)
    """
    # Default values
    address_type = "unknown"
    confidence = 0.0
    
    # Extract relevant features
    tx_count = features.get("tx_count", 0)
    active_days = features.get("active_days", 0)
    tx_per_day = features.get("tx_per_day", 0)
    sent_count = features.get("sent_count", 0)
    received_count = features.get("received_count", 0)
    token_count = features.get("token_count", 0)
    unique_recipients = features.get("unique_recipients", 0)
    unique_senders = features.get("unique_senders", 0)
    risk_score_value = features.get("risk_score", 0)
    
    # Calculate in/out ratio
    in_out_ratio = received_count / max(1, sent_count)
    
    # Define classification rules
    
    # Check for exchange pattern
    if (tx_count > 10000 and unique_recipients > 1000 and unique_senders > 1000 and 
        active_days > 100 and token_count > 10):
        address_type = "exchange"
        confidence = min(1.0, tx_count / 50000 * 0.5 + unique_recipients / 5000 * 0.3 + active_days / 365 * 0.2)
    
    # Check for mixer pattern
    elif (risk_score_value > 80 and 0.9 < in_out_ratio < 1.1 and token_count < 5):
        address_type = "mixer"
        confidence = risk_score_value / 100
    
    # Check for whale pattern
    elif (tx_count > 100 and token_count < 20 and active_days > 30 and 
          risk_score_value < 50 and tx_per_day < 10):
        address_type = "whale"
        confidence = 0.6
    
    # Check for bot pattern
    elif tx_per_day > 50 and active_days > 7:
        address_type = "bot"
        confidence = min(1.0, tx_per_day / 100)
    
    # Check for mule pattern
    elif (received_count < 5 and sent_count > 10 and unique_recipients > 8 and 
          active_days < 7 and risk_score_value > 60):
        address_type = "mule"
        confidence = 0.7
    
    # Check for user pattern
    elif (tx_count > 0 and tx_count < 1000 and tx_per_day < 10 and 
          active_days > 0 and risk_score_value < 40):
        address_type = "user"
        confidence = 0.5
    
    # Check for contract pattern
    elif sent_count > 5 * received_count:
        address_type = "contract"
        confidence = 0.5
    
    return address_type, confidence

def detect_money_laundering_patterns(
    address: str,
    tx_history: pd.DataFrame,
    token_transfers: pd.DataFrame,
    risk_score: Dict,
    money_laundering_routes: pd.DataFrame
) -> Dict:
    """
    Detect potential money laundering patterns for an address.
    
    Args:
        address: The Solana address to analyze
        tx_history: Transaction history DataFrame
        token_transfers: Token transfers DataFrame
        risk_score: Risk score data
        money_laundering_routes: Money laundering routes DataFrame
        
    Returns:
        Dictionary with detected money laundering patterns
    """
    logger.info(f"Detecting money laundering patterns for: {address}")
    
    results = {
        "address": address,
        "is_suspicious": False,
        "risk_score": risk_score.get("risk_score", 0),
        "patterns": [],
        "routes": [],
        "suspicious_counterparties": []
    }
    
    # Check if we already have money laundering routes
    if not money_laundering_routes.empty:
        results["is_suspicious"] = True
        results["routes"] = money_laundering_routes.to_dict(orient='records')
        
    # Check risk score
    if risk_score.get("risk_score", 0) > 75:
        results["is_suspicious"] = True
        results["patterns"].append({
            "type": "high_risk_score",
            "description": "Address has a high risk score",
            "confidence": min(1.0, risk_score.get("risk_score", 0) / 100)
        })
    
    # Look for layering patterns in transaction history
    if not tx_history.empty:
        # Check for high velocity of transactions
        if len(tx_history) > 100:
            # Convert block_time to datetime
            if "block_time" in tx_history.columns:
                tx_history['datetime'] = pd.to_datetime(tx_history['block_time'], unit='s')
                
                # Calculate time between transactions
                tx_history = tx_history.sort_values('datetime')
                tx_history['time_diff'] = tx_history['datetime'].diff().dt.total_seconds()
                
                # Check for rapid transactions (multiple tx within short time periods)
                rapid_tx_count = (tx_history['time_diff'] < 60).sum()
                
                if rapid_tx_count > 10:
                    results["is_suspicious"] = True
                    results["patterns"].append({
                        "type": "high_velocity",
                        "description": f"Address has {rapid_tx_count} transactions within 60 seconds of each other",
                        "confidence": min(1.0, rapid_tx_count / 50)
                    })
    
    # Look for mixer interaction in token transfers
    if not token_transfers.empty:
        # Extract unique counterparties
        counterparties = pd.concat([
            token_transfers[["token_account", "direction"]].rename(columns={"token_account": "address"}),
        ])
        
        # Count transactions by counterparty
        counterparty_counts = counterparties['address'].value_counts()
        
        # Check for many small transactions to different counterparties
        if counterparty_counts.shape[0] > 50 and counterparty_counts.max() < 3:
            results["is_suspicious"] = True
            results["patterns"].append({
                "type": "dispersion",
                "description": f"Address has small transactions to {counterparty_counts.shape[0]} different counterparties",
                "confidence": min(1.0, counterparty_counts.shape[0] / 100)
            })
    
    logger.info(f"Detected {len(results['patterns'])} money laundering patterns for {address}")
    return results

def identify_related_addresses(
    address: str,
    tx_history: pd.DataFrame,
    token_transfers: pd.DataFrame
) -> Dict:
    """
    Identify addresses potentially related to the target address.
    
    Args:
        address: The Solana address to analyze
        tx_history: Transaction history DataFrame
        token_transfers: Token transfers DataFrame
        
    Returns:
        Dictionary with related addresses
    """
    logger.info(f"Identifying related addresses for: {address}")
    
    results = {
        "address": address,
        "related_addresses": []
    }
    
    if token_transfers.empty:
        return results
    
    # Extract counterparties from token transfers
    counterparties = set()
    
    # Add token account counterparties
    counterparties.update(token_transfers["token_account"].unique())
    
    # Add owner counterparties if available
    if "owner" in token_transfers.columns:
        counterparties.update(token_transfers["owner"].unique())
    
    # Remove the original address
    if address in counterparties:
        counterparties.remove(address)
    
    # Analyze relationship patterns
    for counterparty in counterparties:
        # Filter transfers involving this counterparty
        cp_transfers = token_transfers[
            (token_transfers["token_account"] == counterparty) | 
            (token_transfers.get("owner", "") == counterparty)
        ]
        
        if cp_transfers.empty:
            continue
        
        # Calculate transaction metrics
        sent_to_cp = cp_transfers[cp_transfers["direction"] == "sent"]
        received_from_cp = cp_transfers[cp_transfers["direction"] == "received"]
        
        sent_count = len(sent_to_cp)
        received_count = len(received_from_cp)
        total_count = sent_count + received_count
        
        # Calculate time patterns
        time_diffs = []
        if "block_time" in cp_transfers.columns and len(cp_transfers) > 1:
            cp_transfers = cp_transfers.sort_values("block_time")
            time_diffs = np.diff(cp_transfers["block_time"].values)
        
        # Determine relationship type and strength
        relationship_type = "unknown"
        relationship_strength = 0.0
        
        if sent_count > 0 and received_count > 0:
            # Bidirectional relationship
            if sent_count > 2 * received_count:
                relationship_type = "recipient"
                relationship_strength = 0.6
            elif received_count > 2 * sent_count:
                relationship_type = "source"
                relationship_strength = 0.6
            else:
                relationship_type = "peer"
                relationship_strength = 0.7
        elif sent_count > 0:
            # Outgoing relationship
            relationship_type = "recipient"
            relationship_strength = 0.5
        elif received_count > 0:
            # Incoming relationship
            relationship_type = "source"
            relationship_strength = 0.5
        
        # Check for time pattern indicators of relationship
        if time_diffs and len(time_diffs) > 0:
            # Regular time intervals suggest stronger relationship
            if np.std(time_diffs) / np.mean(time_diffs) < 0.5 and len(time_diffs) > 5:
                relationship_strength += 0.2
            
            # Very quick responses suggest stronger relationship
            quick_responses = sum(1 for td in time_diffs if td < 60)  # within 1 minute
            if quick_responses > 3:
                relationship_strength += 0.2
        
        # Add counterparty to related addresses
        results["related_addresses"].append({
            "address": counterparty,
            "relationship_type": relationship_type,
            "relationship_strength": min(1.0, relationship_strength),
            "total_transactions": total_count,
            "sent_count": sent_count,
            "received_count": received_count
        })
    
    # Sort by relationship strength (descending)
    results["related_addresses"] = sorted(
        results["related_addresses"],
        key=lambda x: x["relationship_strength"],
        reverse=True
    )
    
    logger.info(f"Identified {len(results['related_addresses'])} related addresses for {address}")
    return results

def detect_dusting_and_poisoning(
    address: str,
    token_transfers: pd.DataFrame,
    dusting_attacks: pd.DataFrame,
    address_poisoning: pd.DataFrame
) -> Dict:
    """
    Analyze dusting attacks and address poisoning for an address.
    
    Args:
        address: The Solana address to analyze
        token_transfers: Token transfers DataFrame
        dusting_attacks: Dusting attacks DataFrame
        address_poisoning: Address poisoning DataFrame
        
    Returns:
        Dictionary with dusting and poisoning analysis
    """
    logger.info(f"Analyzing dusting and poisoning for: {address}")
    
    results = {
        "address": address,
        "dusting_detected": False,
        "poisoning_detected": False,
        "dusting_attacks": [],
        "poisoning_attempts": []
    }
    
    # Process dusting attacks
    if not dusting_attacks.empty:
        results["dusting_detected"] = True
        results["dusting_attacks"] = dusting_attacks.to_dict(orient='records')
    
    # Process address poisoning
    if not address_poisoning.empty:
        results["poisoning_detected"] = True
        results["poisoning_attempts"] = address_poisoning.to_dict(orient='records')
    
    # If we don't have explicit detection results, try to analyze from token transfers
    if token_transfers.empty:
        return results
    
    if not results["dusting_detected"]:
        # Look for small value incoming transfers from unknown addresses
        if "direction" in token_transfers.columns and "amount_change" in token_transfers.columns:
            # Filter for received transfers
            received = token_transfers[token_transfers["direction"] == "received"]
            
            if not received.empty:
                # Look for small transfers (we'll consider the bottom 10% as potential dust)
                threshold = received["amount_change"].quantile(0.1)
                potential_dust = received[received["amount_change"] <= threshold]
                
                if len(potential_dust) > 3:
                    results["dusting_detected"] = True
                    results["dusting_attacks"] = [{
                        "type": "suspicious_small_transfers",
                        "count": len(potential_dust),
                        "threshold": threshold,
                        "confidence": 0.5,
                        "transfers": potential_dust.to_dict(orient='records')
                    }]
    
    logger.info(f"Completed dusting and poisoning analysis for {address}")
    return results