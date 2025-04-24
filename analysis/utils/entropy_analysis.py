"""
Utility functions for analyzing transaction entropy and detecting anomalies.
Provides methods to identify unusual patterns in transaction behavior.
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
from scipy import stats
import math

logger = logging.getLogger(__name__)

def calculate_transaction_entropy(transactions: pd.DataFrame, 
                                 time_window: str = "1D",
                                 address_column: str = "address",
                                 timestamp_column: str = "block_time") -> pd.DataFrame:
    """
    Calculate entropy of transaction patterns for addresses.
    
    Args:
        transactions: DataFrame containing transaction data
        time_window: Time window for grouping transactions (e.g., '1H', '1D', '7D')
        address_column: Column name for the address field
        timestamp_column: Column name for the timestamp field
        
    Returns:
        DataFrame with entropy values for each address and time window
    """
    logger.info(f"Calculating transaction entropy with {time_window} time window")
    
    if transactions.empty:
        logger.warning("No transactions provided for entropy calculation")
        return pd.DataFrame()
    
    # Ensure timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(transactions[timestamp_column]):
        transactions = transactions.copy()
        transactions[timestamp_column] = pd.to_datetime(transactions[timestamp_column])
    
    # Group transactions by address and time window
    transactions['time_window'] = transactions[timestamp_column].dt.floor(time_window)
    
    # Calculate entropy features
    entropy_results = []
    
    # Get unique addresses
    addresses = transactions[address_column].unique()
    
    for address in addresses:
        # Get transactions for this address
        addr_txns = transactions[transactions[address_column] == address]
        
        # Group by time window
        grouped = addr_txns.groupby('time_window')
        
        for window, group in grouped:
            # Calculate features for entropy
            if len(group) < 2:
                continue
                
            # Transaction interval entropy
            intervals = []
            sorted_group = group.sort_values(timestamp_column)
            for i in range(1, len(sorted_group)):
                interval = (sorted_group[timestamp_column].iloc[i] - 
                           sorted_group[timestamp_column].iloc[i-1]).total_seconds()
                intervals.append(interval)
            
            interval_entropy = calculate_entropy(intervals) if intervals else 0
            
            # Transaction amount entropy
            if 'amount' in group.columns:
                amount_entropy = calculate_entropy(group['amount'].values)
            else:
                amount_entropy = 0
            
            # Transaction count
            tx_count = len(group)
            
            # Input-output ratio entropy
            if all(col in group.columns for col in ['inputs', 'outputs']):
                io_ratios = group['outputs'] / (group['inputs'] + 1e-10)  # Avoid division by zero
                io_entropy = calculate_entropy(io_ratios.values)
            else:
                io_entropy = 0
            
            # Save results
            entropy_results.append({
                'address': address,
                'time_window': window,
                'tx_count': tx_count,
                'interval_entropy': interval_entropy,
                'amount_entropy': amount_entropy,
                'io_entropy': io_entropy,
                'total_entropy': (interval_entropy + amount_entropy + io_entropy) / 3
            })
    
    if not entropy_results:
        logger.warning("No entropy results calculated")
        return pd.DataFrame()
    
    result_df = pd.DataFrame(entropy_results)
    logger.info(f"Calculated entropy for {len(addresses)} addresses across {result_df['time_window'].nunique()} time windows")
    return result_df

def calculate_entropy(values: List[float]) -> float:
    """
    Calculate Shannon entropy of a list of values.
    
    Args:
        values: List of numerical values
        
    Returns:
        Entropy value
    """
    # Convert to numpy array
    values = np.array(values)
    
    # Handle empty or single-value lists
    if len(values) <= 1:
        return 0.0
    
    # Discretize data using histogram
    hist, bin_edges = np.histogram(values, bins='auto')
    
    # Calculate probabilities
    probabilities = hist / len(values)
    
    # Remove zero probabilities
    probabilities = probabilities[probabilities > 0]
    
    # Calculate entropy
    entropy = -np.sum(probabilities * np.log2(probabilities))
    
    return entropy

def detect_entropy_anomalies(entropy_df: pd.DataFrame, 
                           threshold: float = 2.0,
                           window_size: int = 5) -> pd.DataFrame:
    """
    Detect anomalies in transaction entropy values.
    
    Args:
        entropy_df: DataFrame with entropy values from calculate_transaction_entropy
        threshold: Z-score threshold for anomaly detection (default: 2.0)
        window_size: Rolling window size for baseline comparison
        
    Returns:
        DataFrame with anomaly flags and scores
    """
    logger.info(f"Detecting entropy anomalies with threshold {threshold}")
    
    if entropy_df.empty:
        logger.warning("No entropy data provided for anomaly detection")
        return pd.DataFrame()
    
    # Make a copy to avoid modifying original DataFrame
    result_df = entropy_df.copy()
    
    # Sort by address and time window
    result_df = result_df.sort_values(['address', 'time_window'])
    
    # Initialize anomaly columns
    result_df['anomaly_flag'] = False
    result_df['anomaly_score'] = 0.0
    
    # Process each address separately
    for address, group in result_df.groupby('address'):
        if len(group) < window_size:
            continue
            
        # Calculate rolling statistics for total entropy
        rolling_mean = group['total_entropy'].rolling(window=window_size, min_periods=2).mean()
        rolling_std = group['total_entropy'].rolling(window=window_size, min_periods=2).std()
        
        # Replace NaN with 0 for first elements
        rolling_mean = rolling_mean.fillna(0)
        rolling_std = rolling_std.fillna(group['total_entropy'].std())
        
        # Add a small value to std to avoid division by zero
        rolling_std = rolling_std.replace(0, group['total_entropy'].std() or 0.1)
        
        # Calculate z-scores
        z_scores = (group['total_entropy'] - rolling_mean) / rolling_std
        
        # Flag anomalies
        anomaly_flags = abs(z_scores) > threshold
        
        # Update the result DataFrame
        result_df.loc[group.index, 'anomaly_flag'] = anomaly_flags
        result_df.loc[group.index, 'anomaly_score'] = abs(z_scores)
    
    # Count anomalies
    anomaly_count = result_df['anomaly_flag'].sum()
    logger.info(f"Detected {anomaly_count} anomalies across {result_df['address'].nunique()} addresses")
    
    return result_df

def identify_anomalous_patterns(transactions: pd.DataFrame, 
                               anomalies: pd.DataFrame,
                               pattern_types: List[str] = ['sudden_increase', 'unusual_time', 'value_pattern']) -> List[Dict]:
    """
    Identify specific patterns in anomalous transaction behavior.
    
    Args:
        transactions: DataFrame containing transaction data
        anomalies: DataFrame with anomaly data from detect_entropy_anomalies
        pattern_types: List of pattern types to identify
        
    Returns:
        List of identified anomalous patterns
    """
    logger.info(f"Identifying anomalous patterns: {pattern_types}")
    
    if transactions.empty or anomalies.empty:
        logger.warning("No transaction or anomaly data provided")
        return []
    
    patterns = []
    
    # Get anomalous addresses and time windows
    anomalous_entries = anomalies[anomalies['anomaly_flag']].copy()
    
    for _, entry in anomalous_entries.iterrows():
        address = entry['address']
        time_window = entry['time_window']
        anomaly_score = entry['anomaly_score']
        
        # Get transactions for this address and time window
        addr_txns = transactions[
            (transactions['address'] == address) & 
            (pd.to_datetime(transactions['block_time']).dt.floor('1D') == time_window)
        ]
        
        if addr_txns.empty:
            continue
        
        # Analyze for specific patterns
        detected_patterns = []
        
        if 'sudden_increase' in pattern_types:
            # Check for sudden increase in transaction count or value
            if len(addr_txns) > 10:  # Arbitrary threshold
                detected_patterns.append('sudden_increase')
        
        if 'unusual_time' in pattern_types and 'block_time' in addr_txns.columns:
            # Check for transactions at unusual times
            hours = pd.to_datetime(addr_txns['block_time']).dt.hour
            unusual_hours = (hours < 6) | (hours > 22)  # Late night/early morning
            if unusual_hours.sum() > len(hours) * 0.5:  # More than half at unusual hours
                detected_patterns.append('unusual_time')
        
        if 'value_pattern' in pattern_types and 'amount' in addr_txns.columns:
            # Check for suspicious patterns in transaction values
            amounts = addr_txns['amount'].values
            if len(amounts) >= 3:
                # Check for exactly equal amounts (suspicious)
                unique_amounts = np.unique(amounts)
                if len(unique_amounts) / len(amounts) < 0.3:  # Low variety in amounts
                    detected_patterns.append('repeated_amounts')
                
                # Check for round number amounts
                round_amounts = sum(amount == round(amount, 0) for amount in amounts)
                if round_amounts / len(amounts) > 0.7:  # Mostly round numbers
                    detected_patterns.append('round_amounts')
        
        if detected_patterns:
            patterns.append({
                'address': address,
                'time_window': time_window,
                'anomaly_score': anomaly_score,
                'transaction_count': len(addr_txns),
                'detected_patterns': detected_patterns,
                'sample_transactions': addr_txns.iloc[:5]['transaction_id'].tolist() if 'transaction_id' in addr_txns.columns else []
            })
    
    logger.info(f"Identified {len(patterns)} anomalous patterns")
    return patterns
