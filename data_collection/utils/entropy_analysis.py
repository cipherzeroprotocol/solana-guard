"""
Entropy analysis utilities for detecting mixer-like transaction patterns.
"""
import numpy as np
from typing import List, Dict, Any, Union, Optional

def calculate_transaction_entropy(data: np.ndarray) -> float:
    """
    Calculate Shannon entropy for transaction data.
    
    Args:
        data: Array of values (e.g., transaction amounts, time intervals)
        
    Returns:
        Entropy value (higher values indicate more randomness)
    """
    # Convert to numpy array if not already
    data_array = np.asarray(data)
    
    # For continuous data, we first bin the values
    if data_array.dtype.kind in 'fcmM':  # float, complex, timedelta, datetime
        # Use Freedman-Diaconis rule to determine bin width
        q75, q25 = np.percentile(data_array, [75, 25])
        iqr = q75 - q25
        bin_width = 2 * iqr / (len(data_array) ** (1/3)) if iqr > 0 else 0.1
        
        if bin_width > 0:
            bins = int(np.ceil((data_array.max() - data_array.min()) / bin_width))
            bins = max(5, min(50, bins))  # Keep bins in reasonable range
            
            # Create histogram
            hist, _ = np.histogram(data_array, bins=bins)
            
            # Calculate probabilities for each bin
            pk = hist / len(data_array)
            
            # Remove zeros (log(0) is undefined)
            pk = pk[pk > 0]
            
            # Calculate entropy: -sum(pk * log2(pk))
            return -np.sum(pk * np.log2(pk))
        else:
            return 0.0
    else:
        # For discrete data, count occurrences
        unique, counts = np.unique(data_array, return_counts=True)
        pk = counts / len(data_array)
        
        # Calculate entropy: -sum(pk * log2(pk))
        return -np.sum(pk * np.log2(pk))

def detect_entropy_anomalies(data: np.ndarray) -> List[Dict[str, Any]]:
    """
    Detect anomalies in transaction data based on entropy analysis.
    
    Args:
        data: Array of values (e.g., transaction amounts, time intervals)
        
    Returns:
        List of detected anomalies with descriptions
    """
    anomalies = []
    
    # Convert to numpy array if not already
    data_array = np.asarray(data)
    
    # Skip if not enough data points
    if len(data_array) < 5:
        return anomalies
    
    # Calculate entropy
    entropy = calculate_transaction_entropy(data_array)
    
    # Check if the data has suspiciously low entropy (high uniformity)
    if entropy < 1.0 and len(np.unique(data_array)) < len(data_array) * 0.1:
        anomalies.append({
            "type": "uniform_distribution",
            "description": "Suspiciously uniform values detected, common in mixer services",
            "entropy": entropy
        })
    
    # Check for suspiciously regular time intervals if this is time data
    # (This is a heuristic - assuming the data might represent time differences)
    if data_array.dtype.kind in 'fiu':  # float, integer, unsigned integer
        # Calculate coefficient of variation (CV) - std/mean
        mean = np.mean(data_array)
        std = np.std(data_array)
        cv = std / mean if mean > 0 else float('inf')
        
        if cv < 0.2 and len(data_array) > 10:
            anomalies.append({
                "type": "regular_intervals",
                "description": "Suspiciously regular intervals detected, common in automated mixer services",
                "cv": cv
            })
    
    # Check for potential multi-modal distribution (multiple peaks)
    if len(data_array) > 20:
        try:
            from scipy import stats
            
            # Use Gaussian kernel density estimation to find peaks
            kde = stats.gaussian_kde(data_array)
            sample_points = np.linspace(min(data_array), max(data_array), 1000)
            density = kde(sample_points)
            
            # Find peaks (local maxima)
            from scipy.signal import find_peaks
            peaks, _ = find_peaks(density)
            
            if len(peaks) >= 3:
                anomalies.append({
                    "type": "multiple_clusters",
                    "description": f"Multiple clusters detected ({len(peaks)} peaks), possible mixer service with different denomination tiers",
                    "num_peaks": len(peaks)
                })
        except ImportError:
            # Skip this check if scipy is not available
            pass
    
    return anomalies
