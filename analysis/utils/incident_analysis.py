"""
Utility functions for analyzing security incidents and identifying vulnerability patterns.
Provides methods to investigate blockchain exploits and categorize attack vectors.
"""
import logging
import pandas as pd
import numpy as np
import json
import networkx as nx
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)

class SecurityIncident:
    """Class representing a security incident with analysis methods."""
    
    def __init__(self, incident_data: Dict[str, Any]):
        """
        Initialize a security incident.
        
        Args:
            incident_data: Dictionary containing incident information
        """
        self.name = incident_data.get("name", "Unknown Incident")
        self.date = pd.to_datetime(incident_data.get("date", datetime.now().strftime('%Y-%m-%d')))
        self.type = incident_data.get("type", "unknown")
        self.loss_usd = incident_data.get("loss_usd", 0)
        self.description = incident_data.get("description", "")
        self.exploit_addresses = incident_data.get("exploit_addresses", [])
        self.vulnerable_contracts = incident_data.get("vulnerable_contracts", [])
        self.attack_vector = incident_data.get("attack_vector", "unknown")
        self.references = incident_data.get("references", [])
        
        # Additional properties that may be populated during analysis
        self.transaction_graph = None
        self.root_cause = None
        self.affected_users = []
        self.recovery_status = "unrecovered"
        
        logger.info(f"Initialized security incident: {self.name}")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert incident to dictionary.
        
        Returns:
            Dictionary representation of the incident
        """
        return {
            "name": self.name,
            "date": self.date.strftime('%Y-%m-%d'),
            "type": self.type,
            "loss_usd": self.loss_usd,
            "description": self.description,
            "exploit_addresses": self.exploit_addresses,
            "vulnerable_contracts": self.vulnerable_contracts,
            "attack_vector": self.attack_vector,
            "references": self.references,
            "root_cause": self.root_cause,
            "affected_users": self.affected_users,
            "recovery_status": self.recovery_status
        }

def analyze_security_incident(
    incident_data: Dict[str, Any],
    transactions: Optional[pd.DataFrame] = None,
    token_transfers: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """
    Analyze a security incident with available transaction data.
    
    Args:
        incident_data: Dictionary with incident information
        transactions: DataFrame with transaction data (optional)
        token_transfers: DataFrame with token transfer data (optional)
        
    Returns:
        Dictionary with analysis results
    """
    logger.info(f"Analyzing security incident: {incident_data.get('name', 'Unknown')}")
    
    # Create incident object
    incident = SecurityIncident(incident_data)
    
    # Initialize analysis results
    analysis = {
        "incident": incident.to_dict(),
        "transaction_patterns": [],
        "fund_flows": [],
        "attacker_profiles": [],
        "vulnerability_details": {},
        "affected_accounts": [],
        "recommendations": []
    }
    
    # Skip detailed analysis if no transaction data provided
    if transactions is None or transactions.empty:
        logger.warning("No transaction data provided for detailed analysis")
        return analysis
    
    # Filter transactions related to the exploit addresses
    exploit_txns = transactions[
        transactions["address"].isin(incident.exploit_addresses) |
        transactions["signer"].isin(incident.exploit_addresses)
    ]
    
    if exploit_txns.empty:
        logger.warning("No transactions found for the exploit addresses")
        return analysis
    
    # Transaction patterns analysis
    tx_patterns = analyze_transaction_patterns(exploit_txns, incident.date)
    analysis["transaction_patterns"] = tx_patterns
    
    # Fund flow analysis
    if token_transfers is not None and not token_transfers.empty:
        fund_flows = analyze_fund_flows(token_transfers, incident.exploit_addresses)
        analysis["fund_flows"] = fund_flows
    
    # Identify affected accounts
    affected_accounts = identify_affected_accounts(exploit_txns, token_transfers)
    analysis["affected_accounts"] = affected_accounts
    
    # Generate recommendations based on attack vector
    recommendations = generate_security_recommendations(incident.attack_vector)
    analysis["recommendations"] = recommendations
    
    # Vulnerability details
    vulnerability = identify_vulnerability_details(incident)
    analysis["vulnerability_details"] = vulnerability
    
    logger.info(f"Completed security incident analysis for {incident.name}")
    return analysis

def analyze_transaction_patterns(transactions: pd.DataFrame, incident_date: datetime) -> List[Dict]:
    """
    Analyze transaction patterns in security incident.
    
    Args:
        transactions: DataFrame with transaction data
        incident_date: Date of the security incident
        
    Returns:
        List of identified transaction patterns
    """
    patterns = []
    
    # Convert incident_date to timestamp if it's not already
    if not isinstance(incident_date, pd.Timestamp):
        incident_date = pd.to_datetime(incident_date)
    
    # Filter transactions around incident date (1 day before to 3 days after)
    start_date = incident_date - timedelta(days=1)
    end_date = incident_date + timedelta(days=3)
    
    if "block_time" in transactions.columns:
        # Ensure block_time is datetime
        if not pd.api.types.is_datetime64_any_dtype(transactions["block_time"]):
            transactions = transactions.copy()
            transactions["block_time"] = pd.to_datetime(transactions["block_time"])
        
        time_filtered = transactions[
            (transactions["block_time"] >= start_date) &
            (transactions["block_time"] <= end_date)
        ]
    else:
        time_filtered = transactions
    
    if time_filtered.empty:
        return patterns
    
    # Group transactions by time windows
    hourly_counts = time_filtered.resample('1H', on='block_time').size()
    
    # Identify spike in transaction count
    threshold = hourly_counts.mean() + 2 * hourly_counts.std()
    spike_hours = hourly_counts[hourly_counts > threshold]
    
    if not spike_hours.empty:
        patterns.append({
            "type": "transaction_spike",
            "description": f"Abnormal transaction activity detected during incident timeframe",
            "details": {
                "spike_times": spike_hours.index.tolist(),
                "normal_hourly_avg": float(hourly_counts.mean()),
                "max_hourly_count": int(spike_hours.max())
            }
        })
    
    # Identify repeated transaction patterns
    if "instruction_type" in transactions.columns:
        # Find sequences of instructions
        address_groups = time_filtered.groupby("address")
        
        for address, group in address_groups:
            if len(group) < 3:
                continue
                
            # Sort by time
            sorted_group = group.sort_values("block_time")
            
            # Extract instruction sequences
            instructions = sorted_group["instruction_type"].tolist()
            
            # Look for repeated patterns
            repeated_patterns = find_repeated_sequences(instructions)
            
            if repeated_patterns:
                patterns.append({
                    "type": "repeated_instruction_sequence",
                    "description": f"Address {address} executed repeated instruction patterns during incident",
                    "details": {
                        "address": address,
                        "repeated_patterns": repeated_patterns[:5]  # Top 5 patterns
                    }
                })
    
    # Identify unusual transaction sizes
    if "amount" in transactions.columns:
        # Calculate statistics
        mean_amount = transactions["amount"].mean()
        std_amount = transactions["amount"].std()
        max_amount = transactions["amount"].max()
        
        # Look for outliers
        threshold = mean_amount + 3 * std_amount
        outliers = time_filtered[time_filtered["amount"] > threshold]
        
        if not outliers.empty:
            patterns.append({
                "type": "unusual_transaction_size",
                "description": "Unusually large transaction amounts detected during incident",
                "details": {
                    "normal_mean": float(mean_amount),
                    "threshold": float(threshold),
                    "outlier_count": len(outliers),
                    "max_amount": float(max_amount)
                }
            })
    
    return patterns

def analyze_fund_flows(token_transfers: pd.DataFrame, exploit_addresses: List[str]) -> Dict:
    """
    Analyze fund flows in security incident.
    
    Args:
        token_transfers: DataFrame with token transfer data
        exploit_addresses: List of addresses involved in the exploit
        
    Returns:
        Dictionary with fund flow analysis
    """
    if token_transfers.empty:
        return {"flows": [], "summary": {}}
    
    # Filter transfers related to exploit addresses
    exploit_transfers = token_transfers[
        token_transfers["address"].isin(exploit_addresses) | 
        token_transfers["token_account"].isin(exploit_addresses)
    ]
    
    if exploit_transfers.empty:
        return {"flows": [], "summary": {}}
    
    # Ensure block_time is datetime
    if not pd.api.types.is_datetime64_any_dtype(exploit_transfers["block_time"]):
        exploit_transfers = exploit_transfers.copy()
        exploit_transfers["block_time"] = pd.to_datetime(exploit_transfers["block_time"])
    
    # Sort by time
    exploit_transfers = exploit_transfers.sort_values("block_time")
    
    # Identify initial outflows
    initial_transfers = []
    
    for addr in exploit_addresses:
        # Find outgoing transfers
        outflows = exploit_transfers[
            (exploit_transfers["address"] == addr) & 
            (exploit_transfers["direction"] == "sent")
        ]
        
        if not outflows.empty:
            for _, transfer in outflows.iterrows():
                initial_transfers.append({
                    "from_address": addr,
                    "to_account": transfer["token_account"],
                    "token": transfer["mint"],
                    "amount": transfer["amount_change"],
                    "time": transfer["block_time"].isoformat(),
                    "transaction_id": transfer.get("tx_id", "")
                })
    
    # Track subsequent flows (up to 2 hops)
    subsequent_transfers = []
    
    # Get destination accounts from initial transfers
    dest_accounts = [t["to_account"] for t in initial_transfers]
    
    # Find transfers from these accounts
    if dest_accounts:
        second_hop = token_transfers[
            token_transfers["address"].isin(dest_accounts) & 
            (token_transfers["direction"] == "sent")
        ]
        
        for _, transfer in second_hop.iterrows():
            subsequent_transfers.append({
                "from_address": transfer["address"],
                "to_account": transfer["token_account"],
                "token": transfer["mint"],
                "amount": transfer["amount_change"],
                "time": pd.to_datetime(transfer["block_time"]).isoformat(),
                "transaction_id": transfer.get("tx_id", ""),
                "hop": 2
            })
    
    # Calculate volume by token
    token_volumes = {}
    for transfer in initial_transfers + subsequent_transfers:
        token = transfer["token"]
        amount = transfer["amount"]
        
        if token not in token_volumes:
            token_volumes[token] = 0
        
        token_volumes[token] += amount
    
    # Sort tokens by volume
    sorted_tokens = sorted(token_volumes.items(), key=lambda x: x[1], reverse=True)
    
    # Prepare summary
    summary = {
        "total_volume": sum(token_volumes.values()),
        "token_distribution": {token: volume for token, volume in sorted_tokens},
        "initial_count": len(initial_transfers),
        "subsequent_count": len(subsequent_transfers)
    }
    
    return {
        "flows": {
            "initial": initial_transfers,
            "subsequent": subsequent_transfers
        },
        "summary": summary
    }

def identify_affected_accounts(
    transactions: pd.DataFrame,
    token_transfers: Optional[pd.DataFrame] = None
) -> List[Dict]:
    """
    Identify accounts affected by a security incident.
    
    Args:
        transactions: DataFrame with transaction data
        token_transfers: DataFrame with token transfer data (optional)
        
    Returns:
        List of affected accounts with details
    """
    affected_accounts = []
    
    # Extract accounts that interacted with transactions
    accounts = set()
    
    if "address" in transactions.columns:
        accounts.update(transactions["address"].unique())
    
    if "signer" in transactions.columns:
        accounts.update(transactions["signer"].unique())
    
    if token_transfers is not None and not token_transfers.empty:
        if "address" in token_transfers.columns:
            accounts.update(token_transfers["address"].unique())
        
        if "token_account" in token_transfers.columns:
            accounts.update(token_transfers["token_account"].unique())
    
    # Analyze each account
    for account in accounts:
        # Skip null values
        if pd.isna(account):
            continue
        
        # Get account transactions
        account_txns = transactions[
            (transactions["address"] == account) | 
            (transactions["signer"] == account)
        ]
        
        # Skip if no transactions
        if account_txns.empty:
            continue
        
        # Determine account type
        account_type = "user"
        if "account_type" in account_txns.columns:
            types = account_txns["account_type"].unique()
            if "program" in types:
                account_type = "program"
            elif "token" in types:
                account_type = "token"
        
        # Calculate impact
        impact = {
            "transaction_count": len(account_txns),
            "first_interaction": pd.to_datetime(account_txns["block_time"]).min().isoformat()
            if "block_time" in account_txns.columns else None
        }
        
        # Add token transfer data if available
        if token_transfers is not None and not token_transfers.empty:
            account_transfers = token_transfers[
                (token_transfers["address"] == account) | 
                (token_transfers["token_account"] == account)
            ]
            
            if not account_transfers.empty:
                # Calculate net token changes
                token_changes = {}
                
                for _, transfer in account_transfers.iterrows():
                    token = transfer["mint"]
                    amount = transfer["amount_change"]
                    direction = transfer["direction"]
                    
                    if token not in token_changes:
                        token_changes[token] = 0
                    
                    if direction == "received":
                        token_changes[token] += amount
                    else:  # sent
                        token_changes[token] -= amount
                
                # Add to impact data
                impact["token_changes"] = {
                    token: float(amount) for token, amount in token_changes.items()
                }
                impact["net_token_count"] = len(token_changes)
        
        # Add to affected accounts list
        affected_accounts.append({
            "address": account,
            "type": account_type,
            "impact": impact
        })
    
    # Sort by transaction count
    affected_accounts.sort(key=lambda x: x["impact"]["transaction_count"], reverse=True)
    
    return affected_accounts

def identify_vulnerability_patterns(
    transactions: pd.DataFrame,
    contracts: List[str]
) -> Dict:
    """
    Identify vulnerability patterns in smart contracts based on transaction data.
    
    Args:
        transactions: DataFrame with transaction data
        contracts: List of contract addresses to analyze
        
    Returns:
        Dictionary with vulnerability pattern analysis
    """
    if transactions.empty:
        return {}
    
    # Filter transactions involving the contracts
    contract_txns = transactions[transactions["address"].isin(contracts)]
    
    if contract_txns.empty:
        return {}
    
    patterns = {
        "contract_activity": {},
        "vulnerability_indicators": [],
        "instruction_frequencies": {},
        "suspicious_sequences": []
    }
    
    # Analyze contract activity
    for contract in contracts:
        contract_data = contract_txns[contract_txns["address"] == contract]
        
        if contract_data.empty:
            continue
            
        # Count transactions by day
        if "block_time" in contract_data.columns:
            # Ensure datetime
            if not pd.api.types.is_datetime64_any_dtype(contract_data["block_time"]):
                contract_data = contract_data.copy()
                contract_data["block_time"] = pd.to_datetime(contract_data["block_time"])
                
            # Group by day
            daily_counts = contract_data.groupby(
                contract_data["block_time"].dt.date
            ).size()
            
            # Find unusual activity days
            threshold = daily_counts.mean() + 2 * daily_counts.std()
            unusual_days = daily_counts[daily_counts > threshold]
            
            patterns["contract_activity"][contract] = {
                "total_transactions": len(contract_data),
                "daily_average": float(daily_counts.mean()),
                "unusual_activity_days": [str(day) for day in unusual_days.index]
            }
    
    # Identify instruction patterns
    if "instruction_type" in contract_txns.columns:
        # Count instruction types
        instruction_counts = contract_txns["instruction_type"].value_counts()
        
        patterns["instruction_frequencies"] = {
            instr: int(count) for instr, count in instruction_counts.items()
        }
        
        # Look for suspicious instruction sequences
        suspicious_sequences = []
        
        # Common vulnerability patterns to look for
        vulnerability_patterns = {
            "reentrancy": ["withdraw", "transfer", "call"],
            "price_manipulation": ["swap", "deposit", "withdraw"],
            "flash_loan": ["flash_loan", "swap", "repay"],
            "access_control": ["set_authority", "set_owner", "upgrade"]
        }
        
        # Check for sequence patterns
        for vuln_type, seq_pattern in vulnerability_patterns.items():
            # Convert pattern to regex
            pattern_regex = ".*".join(seq_pattern)
            
            # Get addresses with transactions containing this pattern
            for contract in contracts:
                contract_instrs = contract_txns[contract_txns["address"] == contract]["instruction_type"].tolist()
                contract_instr_seq = " ".join(contract_instrs)
                
                if re.search(pattern_regex, contract_instr_seq, re.IGNORECASE):
                    suspicious_sequences.append({
                        "contract": contract,
                        "pattern_type": vuln_type,
                        "matched_sequence": seq_pattern
                    })
        
        patterns["suspicious_sequences"] = suspicious_sequences
    
    # Look for vulnerability indicators
    if len(patterns["suspicious_sequences"]) > 0:
        # Potential vulnerabilities based on detected patterns
        for seq in patterns["suspicious_sequences"]:
            patterns["vulnerability_indicators"].append({
                "type": seq["pattern_type"],
                "contract": seq["contract"],
                "confidence": "medium",
                "description": f"Potential {seq['pattern_type']} vulnerability detected based on instruction sequence"
            })
    
    return patterns

def identify_vulnerability_details(incident: SecurityIncident) -> Dict:
    """
    Identify details about the vulnerability exploited in a security incident.
    
    Args:
        incident: SecurityIncident object
        
    Returns:
        Dictionary with vulnerability details
    """
    # Map of attack vectors to common vulnerability details
    vulnerability_map = {
        "signature_verification_bypass": {
            "category": "Authentication",
            "cwe_id": "CWE-347",
            "description": "Improper verification of cryptographic signature",
            "severity": "critical",
            "mitigation": "Implement rigorous signature verification with proper error checking"
        },
        "oracle_manipulation": {
            "category": "Data Integrity",
            "cwe_id": "CWE-400",
            "description": "Manipulation of price oracle data leading to incorrect financial calculations",
            "severity": "critical",
            "mitigation": "Use time-weighted average prices, multiple oracle sources, and circuit breakers"
        },
        "verification_bypass": {
            "category": "Access Control",
            "cwe_id": "CWE-602",
            "description": "Client-side enforcement of server-side security",
            "severity": "critical",
            "mitigation": "Implement proper verification on program side, not relying on client inputs"
        },
        "flash_loan": {
            "category": "Timing/Financial",
            "cwe_id": "CWE-667",
            "description": "Improper locking or synchronization allowing economic manipulation",
            "severity": "high",
            "mitigation": "Implement circuit breakers, rate limiting, and proper price controls"
        },
        "reentrancy": {
            "category": "Control Flow",
            "cwe_id": "CWE-841",
            "description": "Improper handling of program control allowing repeat execution",
            "severity": "critical",
            "mitigation": "Use checks-effects-interactions pattern and reentrancy guards"
        }
    }
    
    # Get vulnerability details based on attack vector
    vulnerability = vulnerability_map.get(incident.attack_vector, {
        "category": "Unknown",
        "cwe_id": "Unknown",
        "description": "Vulnerability details not available",
        "severity": "unknown",
        "mitigation": "Unknown"
    })
    
    # Add incident-specific details
    vulnerability["attack_vector"] = incident.attack_vector
    vulnerability["vulnerable_contracts"] = incident.vulnerable_contracts
    
    return vulnerability

def generate_security_recommendations(attack_vector: str) -> List[Dict]:
    """
    Generate security recommendations based on the attack vector.
    
    Args:
        attack_vector: The attack vector used in the incident
        
    Returns:
        List of security recommendations
    """
    # Base recommendations for all incidents
    base_recommendations = [
        {
            "title": "Regular Security Audits",
            "description": "Conduct regular third-party security audits of all smart contract code",
            "priority": "high"
        },
        {
            "title": "Incident Response Plan",
            "description": "Develop and maintain an incident response plan for security breaches",
            "priority": "high"
        },
        {
            "title": "Monitoring System",
            "description": "Implement 24/7 monitoring for suspicious activities on-chain",
            "priority": "medium"
        }
    ]
    
    # Vector-specific recommendations
    vector_recommendations = {
        "signature_verification_bypass": [
            {
                "title": "Enhanced Signature Verification",
                "description": "Implement rigorous signature verification with proper error checking and rejection of invalid signatures",
                "priority": "critical"
            },
            {
                "title": "Multiple Signature Requirements",
                "description": "Consider requiring multiple signatures for critical operations",
                "priority": "high"
            }
        ],
        "oracle_manipulation": [
            {
                "title": "Multiple Oracle Sources",
                "description": "Use multiple independent price oracle sources and implement a median or weighted average",
                "priority": "critical"
            },
            {
                "title": "Time-Weighted Average Prices",
                "description": "Implement TWAP (Time-Weighted Average Price) to mitigate short-term price manipulation",
                "priority": "high"
            },
            {
                "title": "Circuit Breakers",
                "description": "Implement circuit breakers that pause operations when suspicious price movements are detected",
                "priority": "high"
            }
        ],
        "verification_bypass": [
            {
                "title": "Server-Side Verification",
                "description": "Ensure all security checks are performed on the program side, not relying on client inputs",
                "priority": "critical"
            },
            {
                "title": "Access Control Lists",
                "description": "Implement explicit access control lists for privileged operations",
                "priority": "high"
            }
        ],
        "flash_loan": [
            {
                "title": "Price Impact Limits",
                "description": "Implement maximum price impact limits for trades",
                "priority": "high"
            },
            {
                "title": "Transaction Ordering Protection",
                "description": "Design systems resistant to transaction ordering manipulation",
                "priority": "medium"
            }
        ],
        "reentrancy": [
            {
                "title": "Checks-Effects-Interactions Pattern",
                "description": "Follow the checks-effects-interactions pattern in all functions",
                "priority": "critical"
            },
            {
                "title": "Reentrancy Guards",
                "description": "Implement reentrancy guards in functions that perform external calls",
                "priority": "high"
            }
        ]
    }
    
    # Get recommendations for the specific attack vector
    specific_recommendations = vector_recommendations.get(attack_vector, [])
    
    # Combine recommendations
    all_recommendations = base_recommendations + specific_recommendations
    
    return all_recommendations

def find_repeated_sequences(items: List[Any], min_length: int = 2, min_occurrences: int = 2) -> List[Dict]:
    """
    Find repeated sequences in a list of items.
    
    Args:
        items: List of items to search for repeated sequences
        min_length: Minimum length of sequence to consider
        min_occurrences: Minimum number of occurrences to consider
        
    Returns:
        List of dictionaries with sequence information
    """
    if not items or len(items) < min_length * min_occurrences:
        return []
    
    # Dictionary to store sequences and their occurrences
    sequences = {}
    
    # Check sequences of different lengths
    for length in range(min_length, min(len(items) // 2 + 1, 10)):
        for i in range(len(items) - length + 1):
            # Convert sequence to hashable representation
            seq = tuple(items[i:i+length])
            
            if seq not in sequences:
                sequences[seq] = []
            
            sequences[seq].append(i)
    
    # Filter sequences with enough occurrences
    repeated = []
    for seq, positions in sequences.items():
        if len(positions) >= min_occurrences:
            # Check that the occurrences are not overlapping
            non_overlapping = []
            last_end = -1
            
            for pos in sorted(positions):
                if pos > last_end:
                    non_overlapping.append(pos)
                    last_end = pos + len(seq)
            
            if len(non_overlapping) >= min_occurrences:
                repeated.append({
                    "sequence": list(seq),
                    "length": len(seq),
                    "occurrences": len(non_overlapping),
                    "positions": non_overlapping
                })
    
    # Sort by number of occurrences and then by length
    repeated.sort(key=lambda x: (x["occurrences"], x["length"]), reverse=True)
    
    return repeated

def plot_incident_timeline(incidents: pd.DataFrame, output_file: Optional[str] = None) -> str:
    """
    Plot a timeline of security incidents.
    
    Args:
        incidents: DataFrame with security incident data
        output_file: Optional output file path
        
    Returns:
        Path to the saved visualization file
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.colors import LinearSegmentedColormap
    import seaborn as sns
    import os
    
    # Set up the plot
    plt.figure(figsize=(12, 8))
    
    # Create a colormap based on loss amount
    colors = sns.color_palette("viridis", n_colors=len(incidents))
    
    # Sort incidents by date
    incidents = incidents.sort_values("date")
    
    # Create the timeline
    plt.scatter(incidents["date"], range(len(incidents)), 
               s=incidents["loss_usd"] / 1e6, c=colors, alpha=0.7)
    
    # Add incident names
    for i, row in enumerate(incidents.itertuples()):
        plt.text(row.date, i, f"  {row.name} (${row.loss_usd/1e6:.1f}M)", 
                va="center", ha="left", fontsize=10)
    
    # Format the plot
    plt.yticks([])
    plt.grid(axis="x", alpha=0.3)
    plt.title("Timeline of Solana Security Incidents", fontsize=14)
    plt.xlabel("Date")
    
    # Format x-axis as dates
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.gcf().autofmt_xdate()
    
    # Add legend for bubble size
    sizes = [1e6, 10e6, 100e6, 500e6]
    labels = ["$1M", "$10M", "$100M", "$500M"]
    for size, label in zip(sizes, labels):
        plt.scatter([], [], s=size/1e6, c="gray", alpha=0.7, label=label)
    
    plt.legend(scatterpoints=1, title="Loss Amount", loc="upper left")
    
    # Set tight layout
    plt.tight_layout()
    
    # Save plot if output file specified
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        return output_file
    
    # Save to default location
    from datetime import datetime
    import os
    
    # Determine default save location
    default_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "visualizations")
    os.makedirs(default_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_file = os.path.join(default_dir, f"incident_timeline_{timestamp}.png")
    
    plt.savefig(default_file, dpi=300, bbox_inches="tight")
    plt.close()
    
    return default_file
