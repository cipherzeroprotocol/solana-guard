"""
Address utility functions for analyzing dusting attacks and address poisoning.
"""
from typing import Dict, List, Any, Union, Optional
import pandas as pd
import numpy as np

def calculate_address_similarity(address1: str, address2: str) -> float:
    """
    Calculate similarity between two addresses.
    
    Args:
        address1: First address
        address2: Second address
        
    Returns:
        Similarity score (0-1)
    """
    if not address1 or not address2:
        return 0.0
    
    # Identical addresses have similarity 1.0
    if address1 == address2:
        return 1.0
    
    # Calculate similarity based on matching characters in same positions
    min_len = min(len(address1), len(address2))
    
    # Count matching characters at same positions
    matching_chars = sum(1 for i in range(min_len) if address1[i] == address2[i])
    
    # Weight similarity by matching prefix and suffix more heavily
    prefix_len = min(4, min_len)
    suffix_len = min(4, min_len)
    
    prefix_match = sum(1 for i in range(prefix_len) if address1[i] == address2[i])
    suffix_match = sum(1 for i in range(1, suffix_len + 1) 
                       if address1[-i] == address2[-i])
    
    # Calculate weighted similarity
    char_similarity = matching_chars / max(len(address1), len(address2))
    prefix_similarity = prefix_match / prefix_len
    suffix_similarity = suffix_match / suffix_len
    
    # Final score with higher weight on prefix/suffix matches
    return (0.5 * char_similarity + 0.25 * prefix_similarity + 0.25 * suffix_similarity)

def detect_address_poisoning(target_address: str, 
                             transaction_history: Union[pd.DataFrame, List[Dict]], 
                             similarity_threshold: float = 0.8) -> pd.DataFrame:
    """
    Detect potential address poisoning attacks by finding similar addresses
    in transaction history.
    
    Args:
        target_address: Address to check for poisoning attacks
        transaction_history: Transaction history data
        similarity_threshold: Threshold for address similarity (0-1)
        
    Returns:
        DataFrame with similar addresses and similarity scores
    """
    # Convert to DataFrame if necessary
    if not isinstance(transaction_history, pd.DataFrame):
        tx_df = pd.DataFrame(transaction_history)
    else:
        tx_df = transaction_history
    
    if tx_df.empty:
        return pd.DataFrame()
    
    # Find all unique addresses in transactions
    all_addresses = set()
    
    # Check common fields where addresses might be found
    address_fields = ["source_address", "target_address", "sender_address", 
                      "receiver_address", "from", "to"]
    
    for field in address_fields:
        if field in tx_df.columns:
            addresses = tx_df[field].dropna().unique()
            all_addresses.update(addresses)
    
    # Remove the target address itself
    if target_address in all_addresses:
        all_addresses.remove(target_address)
    
    # Check each address for similarity
    similar_addresses = []
    
    for address in all_addresses:
        similarity = calculate_address_similarity(target_address, address)
        if similarity >= similarity_threshold:
            # Find transactions where this address appears
            address_txs = pd.DataFrame()
            for field in address_fields:
                if field in tx_df.columns:
                    matches = tx_df[tx_df[field] == address]
                    if not matches.empty:
                        address_txs = pd.concat([address_txs, matches])
            
            # Extract timestamps if available
            timestamps = []
            if "block_time" in address_txs.columns:
                timestamps = address_txs["block_time"].tolist()
            
            similar_addresses.append({
                "similar_address": address,
                "similarity_score": similarity,
                "transaction_count": len(address_txs),
                "block_time": timestamps[0] if timestamps else None
            })
    
    # Create DataFrame from results
    if similar_addresses:
        return pd.DataFrame(similar_addresses)
    
    return pd.DataFrame()

def detect_dusting_attacks(target_address: str, 
                          token_transfers: Union[pd.DataFrame, List[Dict]], 
                          dust_threshold: float = 0.01,
                          min_dust_transfers: int = 1) -> pd.DataFrame:
    """
    Detect potential dusting attacks by finding very small value transfers.
    
    Args:
        target_address: Address to check for dusting attacks
        token_transfers: Token transfer data
        dust_threshold: Maximum value to be considered dust
        min_dust_transfers: Minimum number of dust transfers to be considered an attack
        
    Returns:
        DataFrame with detected dust transfers
    """
    # Convert to DataFrame if necessary
    if not isinstance(token_transfers, pd.DataFrame):
        transfers_df = pd.DataFrame(token_transfers)
    else:
        transfers_df = token_transfers
    
    if transfers_df.empty:
        return pd.DataFrame()
    
    # Find potential dust transfers
    if "amount" in transfers_df.columns:
        dust_transfers = transfers_df[transfers_df["amount"] <= dust_threshold]
    else:
        # Can't determine dust without amounts
        return pd.DataFrame()
    
    # Count dust transfers by token (if mint column exists)
    if "mint" in dust_transfers.columns:
        token_counts = dust_transfers["mint"].value_counts()
        
        # Filter by tokens with multiple dust transfers
        suspicious_tokens = token_counts[token_counts >= min_dust_transfers].index
        if len(suspicious_tokens) > 0:
            dust_attacks = dust_transfers[dust_transfers["mint"].isin(suspicious_tokens)]
        else:
            dust_attacks = pd.DataFrame()
    else:
        # If no mint column, use all dust transfers as potential attacks
        dust_attacks = dust_transfers
    
    return dust_attacks

def detect_dusting_and_poisoning(address: str, 
                                token_transfers: Union[pd.DataFrame, List[Dict]], 
                                dusting_attacks: Optional[Union[pd.DataFrame, List[Dict]]] = None,
                                poisoning_attempts: Optional[Union[pd.DataFrame, List[Dict]]] = None):
    """
    Combined detection for dusting attacks and address poisoning.
    
    Args:
        address: Address to analyze
        token_transfers: Token transfers data
        dusting_attacks: Pre-detected dusting attacks (optional)
        poisoning_attempts: Pre-detected poisoning attempts (optional)
        
    Returns:
        Dictionary with combined analysis results
    """
    results = {
        "address": address,
        "dusting_detected": False,
        "poisoning_detected": False,
        "dusting_attacks": [],
        "poisoning_attempts": [],
        "risk_score": 0
    }
    
    # Process pre-detected dusting attacks if provided
    if dusting_attacks is not None:
        if isinstance(dusting_attacks, pd.DataFrame):
            results["dusting_detected"] = not dusting_attacks.empty
            if not dusting_attacks.empty:
                # Convert DataFrame to list of dicts for easier processing
                results["dusting_attacks"] = dusting_attacks.to_dict("records")
        else:
            results["dusting_detected"] = bool(dusting_attacks)
            results["dusting_attacks"] = dusting_attacks
    # Otherwise, try to detect dusting attacks
    else:
        dust_df = detect_dusting_attacks(address, token_transfers)
        results["dusting_detected"] = not dust_df.empty
        if not dust_df.empty:
            results["dusting_attacks"] = dust_df.to_dict("records")
    
    # Process pre-detected poisoning attempts if provided
    if poisoning_attempts is not None:
        if isinstance(poisoning_attempts, pd.DataFrame):
            results["poisoning_detected"] = not poisoning_attempts.empty
            if not poisoning_attempts.empty:
                # Convert DataFrame to list of dicts for easier processing
                results["poisoning_attempts"] = poisoning_attempts.to_dict("records")
        else:
            results["poisoning_detected"] = bool(poisoning_attempts)
            results["poisoning_attempts"] = poisoning_attempts
    
    # Calculate risk score based on attack patterns
    # Higher score = higher risk
    risk_score = 0
    
    if results["dusting_detected"]:
        dust_count = len(results["dusting_attacks"])
        risk_score += min(50, dust_count * 5)  # Max 50 points from dusting
    
    if results["poisoning_detected"]:
        poison_count = len(results["poisoning_attempts"])
        risk_score += min(70, poison_count * 10)  # Max 70 points from poisoning
    
    results["risk_score"] = min(100, risk_score)  # Cap at 100
    
    return results
