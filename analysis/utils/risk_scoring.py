"""
Utility functions for risk scoring and assessment.
Provides methods to calculate risk scores for addresses, tokens, and transactions.
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

logger = logging.getLogger(__name__)

# Risk scoring thresholds
RISK_THRESHOLDS = {
    "very_low": {"min": 0, "max": 20},
    "low": {"min": 21, "max": 40},
    "medium": {"min": 41, "max": 60},
    "high": {"min": 61, "max": 80},
    "very_high": {"min": 81, "max": 100}
}

# Risk categories and weights
RISK_CATEGORIES = {
    "address": {
        "transaction_patterns": 0.25,
        "interaction_entities": 0.30,
        "account_history": 0.15,
        "token_activity": 0.20,
        "external_risk": 0.10
    },
    "token": {
        "creator_risk": 0.25,
        "liquidity_risk": 0.20,
        "ownership_distribution": 0.25,
        "price_manipulation": 0.15,
        "contract_risk": 0.15
    },
    "transaction": {
        "involved_entities": 0.35,
        "transaction_amount": 0.20,
        "transaction_complexity": 0.15,
        "temporal_patterns": 0.10,
        "program_risk": 0.20
    }
}

def calculate_address_risk(
    address: str,
    tx_history: pd.DataFrame,
    token_transfers: pd.DataFrame,
    external_risk_score: Optional[Dict] = None,
    money_laundering_routes: Optional[pd.DataFrame] = None,
    dusting_attacks: Optional[pd.DataFrame] = None
) -> Dict:
    """
    Calculate comprehensive risk score for a Solana address.
    
    Args:
        address: The Solana address to score
        tx_history: Transaction history DataFrame
        token_transfers: Token transfers DataFrame
        external_risk_score: External risk score (e.g., from Range API)
        money_laundering_routes: Money laundering routes DataFrame
        dusting_attacks: Dusting attacks DataFrame
        
    Returns:
        Dictionary with risk score and factors
    """
    logger.info(f"Calculating risk score for address: {address}")
    
    risk_scores = {
        "transaction_patterns": 0,
        "interaction_entities": 0,
        "account_history": 0,
        "token_activity": 0,
        "external_risk": 0
    }
    
    risk_factors = []
    
    # 1. Analyze transaction patterns
    if not tx_history.empty:
        # Check transaction velocity
        if "block_time" in tx_history.columns:
            tx_history['datetime'] = pd.to_datetime(tx_history['block_time'], unit='s')
            
            # Calculate active days
            if len(tx_history) > 1:
                min_time = tx_history['datetime'].min()
                max_time = tx_history['datetime'].max()
                active_days = (max_time - min_time).total_seconds() / (60 * 60 * 24)
                
                if active_days > 0:
                    tx_per_day = len(tx_history) / active_days
                    
                    # High velocity is suspicious
                    if tx_per_day > 100:
                        risk_scores["transaction_patterns"] += 50
                        risk_factors.append({
                            "category": "transaction_patterns",
                            "name": "high_tx_velocity",
                            "description": f"High transaction velocity ({tx_per_day:.1f} tx/day)",
                            "severity": "high",
                            "score": 50
                        })
                    elif tx_per_day > 20:
                        risk_scores["transaction_patterns"] += 25
                        risk_factors.append({
                            "category": "transaction_patterns",
                            "name": "elevated_tx_velocity",
                            "description": f"Elevated transaction velocity ({tx_per_day:.1f} tx/day)",
                            "severity": "medium",
                            "score": 25
                        })
            
            # Check for rapid transactions (multiple tx within short time periods)
            tx_history = tx_history.sort_values('datetime')
            tx_history['time_diff'] = tx_history['datetime'].diff().dt.total_seconds()
            
            rapid_tx_count = (tx_history['time_diff'] < 60).sum()
            
            if rapid_tx_count > 20:
                risk_scores["transaction_patterns"] += 50
                risk_factors.append({
                    "category": "transaction_patterns",
                    "name": "rapid_transactions",
                    "description": f"Many rapid transactions ({rapid_tx_count} tx < 60s apart)",
                    "severity": "high",
                    "score": 50
                })
            elif rapid_tx_count > 5:
                risk_scores["transaction_patterns"] += 25
                risk_factors.append({
                    "category": "transaction_patterns",
                    "name": "some_rapid_transactions",
                    "description": f"Some rapid transactions ({rapid_tx_count} tx < 60s apart)",
                    "severity": "medium",
                    "score": 25
                })
    
    # 2. Analyze entity interactions
    if not token_transfers.empty:
        # Count unique counterparties
        counterparties = set()
        
        # Add token account counterparties
        counterparties.update(token_transfers["token_account"].unique())
        
        # Add owner counterparties if available
        if "owner" in token_transfers.columns:
            counterparties.update(token_transfers["owner"].unique())
        
        # Remove the original address
        if address in counterparties:
            counterparties.remove(address)
        
        # Analyze counterparty patterns
        counterparty_count = len(counterparties)
        
        # Very high counterparty count is suspicious (unless it's an exchange)
        if counterparty_count > 1000:
            risk_scores["interaction_entities"] += 30
            risk_factors.append({
                "category": "interaction_entities",
                "name": "very_high_counterparties",
                "description": f"Very high number of counterparties ({counterparty_count})",
                "severity": "medium",
                "score": 30
            })
    
    # Check for money laundering patterns
    if money_laundering_routes is not None and not money_laundering_routes.empty:
        risk_scores["interaction_entities"] += 75
        risk_factors.append({
            "category": "interaction_entities",
            "name": "money_laundering_patterns",
            "description": f"Money laundering patterns detected ({len(money_laundering_routes)} routes)",
            "severity": "high",
            "score": 75
        })
    
    # 3. Analyze account history
    if not tx_history.empty:
        # Check account age
        if "block_time" in tx_history.columns:
            # Get first transaction time
            first_tx_time = tx_history["block_time"].min()
            current_time = datetime.now().timestamp()
            
            account_age_days = (current_time - first_tx_time) / (60 * 60 * 24)
            
            # Very new accounts are slightly suspicious
            if account_age_days < 1:
                risk_scores["account_history"] += 20
                risk_factors.append({
                    "category": "account_history",
                    "name": "very_new_account",
                    "description": f"Account is very new (< 1 day old)",
                    "severity": "low",
                    "score": 20
                })
            elif account_age_days < 7:
                risk_scores["account_history"] += 10
                risk_factors.append({
                    "category": "account_history",
                    "name": "new_account",
                    "description": f"Account is new (< 7 days old)",
                    "severity": "very_low",
                    "score": 10
                })
    
    # 4. Analyze token activity
    if not token_transfers.empty:
        # Check for token diversity
        token_count = token_transfers["mint"].nunique()
        
        # Unusually high token diversity can be suspicious
        if token_count > 100:
            risk_scores["token_activity"] += 30
            risk_factors.append({
                "category": "token_activity",
                "name": "high_token_diversity",
                "description": f"High token diversity ({token_count} tokens)",
                "severity": "medium",
                "score": 30
            })
    
    # Check for dusting attacks
    if dusting_attacks is not None and not dusting_attacks.empty:
        risk_scores["token_activity"] += 40
        risk_factors.append({
            "category": "token_activity",
            "name": "dusting_attacks",
            "description": f"Potential dusting attacks detected ({len(dusting_attacks)} instances)",
            "severity": "medium",
            "score": 40
        })
    
    # 5. Incorporate external risk score
    if external_risk_score:
        external_score = external_risk_score.get("risk_score", 0)
        risk_scores["external_risk"] = external_score
        
        if external_score >= 75:
            risk_factors.append({
                "category": "external_risk",
                "name": "high_external_risk",
                "description": f"High external risk score ({external_score})",
                "severity": "high",
                "score": external_score
            })
        elif external_score >= 50:
            risk_factors.append({
                "category": "external_risk",
                "name": "medium_external_risk",
                "description": f"Medium external risk score ({external_score})",
                "severity": "medium",
                "score": external_score
            })
    
    # Calculate weighted risk score
    total_risk_score = 0
    
    for category, score in risk_scores.items():
        weight = RISK_CATEGORIES["address"].get(category, 0)
        total_risk_score += score * weight
    
    # Ensure score is within 0-100 range
    total_risk_score = min(100, max(0, total_risk_score))
    
    # Determine risk level
    risk_level = "unknown"
    for level, thresholds in RISK_THRESHOLDS.items():
        if thresholds["min"] <= total_risk_score <= thresholds["max"]:
            risk_level = level
            break
    
    # Build final result
    result = {
        "address": address,
        "risk_score": total_risk_score,
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "category_scores": risk_scores,
        "timestamp": datetime.now().timestamp()
    }
    
    logger.info(f"Calculated risk score for {address}: {total_risk_score} ({risk_level})")
    return result

def calculate_token_risk(
    token_mint: str,
    token_details: Dict,
    token_holders: Optional[List[Dict]] = None,
    token_transfers: Optional[pd.DataFrame] = None,
    token_insider_data: Optional[Dict] = None,
    rugcheck_risk: Optional[pd.DataFrame] = None
) -> Dict:
    """
    Calculate comprehensive risk score for a Solana token.
    
    Args:
        token_mint: The token mint address
        token_details: Token details from Vybe API
        token_holders: Top token holders
        token_transfers: Token transfer history
        token_insider_data: Token insider analysis data
        rugcheck_risk: Risk data from RugCheck API
        
    Returns:
        Dictionary with risk score and factors
    """
    logger.info(f"Calculating risk score for token: {token_mint}")
    
    risk_scores = {
        "creator_risk": 0,
        "liquidity_risk": 0,
        "ownership_distribution": 0,
        "price_manipulation": 0,
        "contract_risk": 0
    }
    
    risk_factors = []
    
    # 1. Creator risk
    creator_address = token_details.get("creator")
    
    if creator_address:
        # Check if creator has other tokens
        creator_tokens = token_details.get("creatorTokens", [])
        
        # Many tokens from same creator can be suspicious
        if len(creator_tokens) > 10:
            risk_scores["creator_risk"] += 50
            risk_factors.append({
                "category": "creator_risk",
                "name": "prolific_creator",
                "description": f"Creator has launched many tokens ({len(creator_tokens)})",
                "severity": "high",
                "score": 50
            })
        elif len(creator_tokens) > 3:
            risk_scores["creator_risk"] += 30
            risk_factors.append({
                "category": "creator_risk",
                "name": "multiple_tokens",
                "description": f"Creator has launched multiple tokens ({len(creator_tokens)})",
                "severity": "medium",
                "score": 30
            })
    
    # 2. Liquidity risk
    # Check if markets info available
    markets = token_details.get("markets", [])
    
    if markets:
        # Calculate total liquidity
        total_liquidity = 0
        
        for market in markets:
            market_liquidity = 0
            
            # Extract liquidity information if available
            market_liquidity_a = market.get("liquidityA", "0")
            market_liquidity_b = market.get("liquidityB", "0")
            
            try:
                # Convert to numbers
                if isinstance(market_liquidity_a, str):
                    market_liquidity_a = float(market_liquidity_a)
                if isinstance(market_liquidity_b, str):
                    market_liquidity_b = float(market_liquidity_b)
                
                # Add to total
                market_liquidity = market_liquidity_a + market_liquidity_b
            except:
                pass
            
            total_liquidity += market_liquidity
        
        # Low liquidity is risky
        if total_liquidity == 0:
            risk_scores["liquidity_risk"] += 100
            risk_factors.append({
                "category": "liquidity_risk",
                "name": "no_liquidity",
                "description": "Token has no liquidity",
                "severity": "very_high",
                "score": 100
            })
        elif total_liquidity < 1000:
            risk_scores["liquidity_risk"] += 80
            risk_factors.append({
                "category": "liquidity_risk",
                "name": "very_low_liquidity",
                "description": f"Token has very low liquidity ({total_liquidity:.2f})",
                "severity": "high",
                "score": 80
            })
        elif total_liquidity < 10000:
            risk_scores["liquidity_risk"] += 50
            risk_factors.append({
                "category": "liquidity_risk",
                "name": "low_liquidity",
                "description": f"Token has low liquidity ({total_liquidity:.2f})",
                "severity": "medium",
                "score": 50
            })
    
    # 3. Ownership distribution
    if token_holders:
        # Calculate concentration metrics
        top_holder_percentage = 0
        top5_holder_percentage = 0
        
        # Sort holders by percentage
        holders_sorted = sorted(token_holders, key=lambda x: x.get("percentage", 0), reverse=True)
        
        # Get top holder percentage
        if holders_sorted:
            top_holder_percentage = holders_sorted[0].get("percentage", 0)
        
        # Get top 5 holder percentage
        if len(holders_sorted) >= 5:
            top5_holder_percentage = sum(h.get("percentage", 0) for h in holders_sorted[:5])
        
        # High concentration is risky
        if top_holder_percentage > 50:
            risk_scores["ownership_distribution"] += 80
            risk_factors.append({
                "category": "ownership_distribution",
                "name": "single_holder_dominance",
                "description": f"Single holder owns majority of supply ({top_holder_percentage:.1f}%)",
                "severity": "high",
                "score": 80
            })
        elif top5_holder_percentage > 80:
            risk_scores["ownership_distribution"] += 60
            risk_factors.append({
                "category": "ownership_distribution",
                "name": "high_concentration",
                "description": f"Top 5 holders own most of supply ({top5_holder_percentage:.1f}%)",
                "severity": "medium",
                "score": 60
            })
    
    # 4. Price manipulation
    if token_transfers is not None and not token_transfers.empty:
        # Analyze price movements if available
        pass
    
    # 5. Contract risk
    mint_authority = token_details.get("mintAuthority")
    freeze_authority = token_details.get("freezeAuthority")
    
    # Check for mint authority
    if mint_authority:
        risk_scores["contract_risk"] += 50
        risk_factors.append({
            "category": "contract_risk",
            "name": "mint_authority",
            "description": "Token has active mint authority",
            "severity": "medium",
            "score": 50
        })
    
    # Check for freeze authority
    if freeze_authority:
        risk_scores["contract_risk"] += 30
        risk_factors.append({
            "category": "contract_risk",
            "name": "freeze_authority",
            "description": "Token has active freeze authority",
            "severity": "medium",
            "score": 30
        })
    
    # Incorporate RugCheck risk data if available
    if rugcheck_risk is not None and not rugcheck_risk.empty:
        # Extract overall risk score
        overall_score = rugcheck_risk.get("normalized_score", 0)
        if isinstance(overall_score, pd.Series):
            overall_score = overall_score.iloc[0]
        
        # Override contract risk with RugCheck data
        risk_scores["contract_risk"] = max(risk_scores["contract_risk"], overall_score)
        
        # Add RugCheck risk factors
        for _, factor in rugcheck_risk.iterrows():
            name = factor.get("name", "unknown")
            description = factor.get("description", "")
            score = factor.get("score", 0)
            
            if score > 0:
                severity = "low"
                if score > 75:
                    severity = "high"
                elif score > 50:
                    severity = "medium"
                
                risk_factors.append({
                    "category": "contract_risk",
                    "name": name,
                    "description": description,
                    "severity": severity,
                    "score": score
                })
    
    # Calculate weighted risk score
    total_risk_score = 0
    
    for category, score in risk_scores.items():
        weight = RISK_CATEGORIES["token"].get(category, 0)
        total_risk_score += score * weight
    
    # Ensure score is within 0-100 range
    total_risk_score = min(100, max(0, total_risk_score))
    
    # Determine risk level
    risk_level = "unknown"
    for level, thresholds in RISK_THRESHOLDS.items():
        if thresholds["min"] <= total_risk_score <= thresholds["max"]:
            risk_level = level
            break
    
    # Build final result
    result = {
        "token_mint": token_mint,
        "token_name": token_details.get("name", ""),
        "token_symbol": token_details.get("symbol", ""),
        "risk_score": total_risk_score,
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "category_scores": risk_scores,
        "timestamp": datetime.now().timestamp()
    }
    
    logger.info(f"Calculated risk score for token {token_mint}: {total_risk_score} ({risk_level})")
    return result

def calculate_transaction_risk(
    tx_hash: str,
    tx_data: Dict,
    address_risk_scores: Optional[Dict[str, Dict]] = None,
    token_risk_scores: Optional[Dict[str, Dict]] = None,
    external_risk_score: Optional[Dict] = None
) -> Dict:
    """
    Calculate comprehensive risk score for a Solana transaction.
    
    Args:
        tx_hash: The transaction hash
        tx_data: Transaction data
        address_risk_scores: Risk scores for addresses involved in the transaction
        token_risk_scores: Risk scores for tokens involved in the transaction
        external_risk_score: External risk score (e.g., from Range API)
        
    Returns:
        Dictionary with risk score and factors
    """
    logger.info(f"Calculating risk score for transaction: {tx_hash}")
    
    risk_scores = {
        "involved_entities": 0,
        "transaction_amount": 0,
        "transaction_complexity": 0,
        "temporal_patterns": 0,
        "program_risk": 0
    }
    
    risk_factors = []
    
    # 1. Analyze involved entities
    involved_addresses = set()
    
    # Extract addresses from account keys
    account_keys = tx_data.get("transaction", {}).get("message", {}).get("accountKeys", [])
    
    # Convert to list of strings if necessary
    if account_keys:
        for key in account_keys:
            if isinstance(key, dict) and "pubkey" in key:
                involved_addresses.add(key["pubkey"])
            elif isinstance(key, str):
                involved_addresses.add(key)
    
    # Check risk scores of involved addresses
    if address_risk_scores:
        high_risk_addresses = []
        
        for address in involved_addresses:
            if address in address_risk_scores:
                score = address_risk_scores[address].get("risk_score", 0)
                
                if score >= 75:
                    high_risk_addresses.append({
                        "address": address,
                        "risk_score": score
                    })
        
        # High risk addresses involved
        if high_risk_addresses:
            max_score = max(addr["risk_score"] for addr in high_risk_addresses)
            risk_scores["involved_entities"] = max_score
            
            risk_factors.append({
                "category": "involved_entities",
                "name": "high_risk_addresses",
                "description": f"Transaction involves {len(high_risk_addresses)} high-risk addresses",
                "severity": "high",
                "score": max_score
            })
    
    # 2. Analyze transaction amount
    # Extract pre and post token balances to identify transfers
    pre_token_balances = tx_data.get("meta", {}).get("preTokenBalances", [])
    post_token_balances = tx_data.get("meta", {}).get("postTokenBalances", [])
    
    # Calculate total transfer value
    if pre_token_balances and post_token_balances:
        # Create mapping of account indices to simplify lookup
        pre_balances_map = {item.get("accountIndex"): item for item in pre_token_balances}
        post_balances_map = {item.get("accountIndex"): item for item in post_token_balances}
        
        # Find all account indices that appear in either pre or post balances
        all_indices = set(pre_balances_map.keys()).union(set(post_balances_map.keys()))
        
        total_transfer_value = 0
        
        for idx in all_indices:
            pre_balance = pre_balances_map.get(idx, {"uiTokenAmount": {"uiAmount": 0}})
            post_balance = post_balances_map.get(idx, {"uiTokenAmount": {"uiAmount": 0}})
            
            pre_amount = pre_balance.get("uiTokenAmount", {}).get("uiAmount", 0) or 0
            post_amount = post_balance.get("uiTokenAmount", {}).get("uiAmount", 0) or 0
            
            # Calculate change in token balance
            amount_change = abs(post_amount - pre_amount)
            
            # Get token mint
            token_mint = pre_balance.get("mint") or post_balance.get("mint")
            
            # Check token risk score
            token_risk = 0
            if token_risk_scores and token_mint in token_risk_scores:
                token_risk = token_risk_scores[token_mint].get("risk_score", 0)
            
            # Adjust value based on token risk
            risk_adjusted_value = amount_change * (1 + token_risk / 100)
            total_transfer_value += risk_adjusted_value
        
        # Assign risk based on transfer value
        if total_transfer_value > 100000:
            risk_scores["transaction_amount"] = 60
            risk_factors.append({
                "category": "transaction_amount",
                "name": "very_high_value",
                "description": f"Very high value transaction (${total_transfer_value:.2f})",
                "severity": "medium",
                "score": 60
            })
        elif total_transfer_value > 10000:
            risk_scores["transaction_amount"] = 30
            risk_factors.append({
                "category": "transaction_amount",
                "name": "high_value",
                "description": f"High value transaction (${total_transfer_value:.2f})",
                "severity": "low",
                "score": 30
            })
    
    # 3. Analyze transaction complexity
    inner_instructions = tx_data.get("meta", {}).get("innerInstructions", [])
    
    # Calculate complexity based on number of instructions
    total_instructions = len(inner_instructions)
    
    for inner_ix in inner_instructions:
        if "instructions" in inner_ix:
            total_instructions += len(inner_ix["instructions"])
    
    # Complex transactions can be suspicious
    if total_instructions > 20:
        risk_scores["transaction_complexity"] = 50
        risk_factors.append({
            "category": "transaction_complexity",
            "name": "very_complex",
            "description": f"Very complex transaction ({total_instructions} instructions)",
            "severity": "medium",
            "score": 50
        })
    elif total_instructions > 10:
        risk_scores["transaction_complexity"] = 25
        risk_factors.append({
            "category": "transaction_complexity",
            "name": "complex",
            "description": f"Complex transaction ({total_instructions} instructions)",
            "severity": "low",
            "score": 25
        })
    
    # 4. Analyze temporal patterns
    # This would require context of other transactions
    
    # 5. Analyze program risk
    program_ids = set()
    
    # Extract program IDs from instructions
    instructions = tx_data.get("transaction", {}).get("message", {}).get("instructions", [])
    
    for ix in instructions:
        if "programId" in ix:
            program_ids.add(ix["programId"])
    
    # Check for high-risk programs
    high_risk_programs = {
        "worm2ZoG2kUd4vFXhvjh93UUH596ayRfgQ2MgjNMTth": {
            "name": "Wormhole Token Bridge",
            "risk_score": 60
        },
        "3u8hJUVTA4jH1wYAyUur7FFZVQ8H635K3tSHHF4ssjQ5": {
            "name": "Wormhole Portal",
            "risk_score": 70
        },
        "tor1xzb2Zyy1cUxXmyJfR8aNXuWnwHG8AwgaG7UGD4K": {
            "name": "Tornado Cash Solana (suspected)",
            "risk_score": 90
        }
    }
    
    risky_programs = []
    
    for program_id in program_ids:
        if program_id in high_risk_programs:
            risky_programs.append({
                "program_id": program_id,
                "name": high_risk_programs[program_id]["name"],
                "risk_score": high_risk_programs[program_id]["risk_score"]
            })
    
    if risky_programs:
        max_program_risk = max(p["risk_score"] for p in risky_programs)
        risk_scores["program_risk"] = max_program_risk
        
        risk_factors.append({
            "category": "program_risk",
            "name": "high_risk_programs",
            "description": f"Transaction uses {len(risky_programs)} high-risk programs",
            "severity": "high" if max_program_risk >= 75 else "medium",
            "score": max_program_risk
        })
    
    # Incorporate external risk score if available
    if external_risk_score:
        external_score = external_risk_score.get("risk_score", 0)
        
        # Use maximum risk score between our calculation and external
        for category in risk_scores.keys():
            risk_scores[category] = max(risk_scores[category], external_score * RISK_CATEGORIES["transaction"][category])
        
        if external_score >= 75:
            risk_factors.append({
                "category": "external_risk",
                "name": "high_external_risk",
                "description": f"High external risk score ({external_score})",
                "severity": "high",
                "score": external_score
            })
    
    # Calculate weighted risk score
    total_risk_score = 0
    
    for category, score in risk_scores.items():
        weight = RISK_CATEGORIES["transaction"].get(category, 0)
        total_risk_score += score * weight
    
    # Ensure score is within 0-100 range
    total_risk_score = min(100, max(0, total_risk_score))
    
    # Determine risk level
    risk_level = "unknown"
    for level, thresholds in RISK_THRESHOLDS.items():
        if thresholds["min"] <= total_risk_score <= thresholds["max"]:
            risk_level = level
            break
    
    # Build final result
    result = {
        "transaction_hash": tx_hash,
        "risk_score": total_risk_score,
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "category_scores": risk_scores,
        "timestamp": datetime.now().timestamp()
    }
    
    logger.info(f"Calculated risk score for transaction {tx_hash}: {total_risk_score} ({risk_level})")
    return result