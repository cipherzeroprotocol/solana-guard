"""
Main entry point for SolanaGuard data collection.
This script orchestrates the different API collectors and provides 
high-level methods for data collection and analysis.
"""
import os
import logging
import argparse
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

# Import collectors using absolute paths
from data_collection.collectors.helius_collector import HeliusCollector
from data_collection.collectors.range_collector import RangeCollector
from data_collection.collectors.rugcheck_collector import RugCheckCollector
from data_collection.collectors.vybe_collector import VybeCollector

# Import configuration
from data_collection.config import DATA_DIR, LOG_LEVEL

# Set up logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(DATA_DIR, "solana_guard.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("solana_guard")

class SolanaGuard:
    """
    Main class for SolanaGuard data collection and analysis.
    Orchestrates the different API collectors and provides methods for various analyses.
    """
    
    def __init__(self, cache_enabled: bool = True):
        """
        Initialize SolanaGuard.
        
        Args:
            cache_enabled: Whether to enable caching of API responses
        """
        logger.info("Initializing SolanaGuard")
        
        # Initialize collectors
        self.helius = HeliusCollector(cache_enabled=cache_enabled)
        self.range = RangeCollector(cache_enabled=cache_enabled)
        self.rugcheck = RugCheckCollector(cache_enabled=cache_enabled)
        self.vybe = VybeCollector(cache_enabled=cache_enabled)
        
        # Create output directories
        self.output_dir = os.path.join(DATA_DIR, "output")
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info("SolanaGuard initialized successfully")
    
    def analyze_address(self, address: str) -> Dict:
        """
        Perform comprehensive analysis of a Solana address.
        
        Args:
            address: Solana wallet address to analyze
            
        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Analyzing address: {address}")
        
        results = {}
        
        # Collect basic address information
        try:
            logger.info("Collecting basic address information")
            account_info = self.helius.get_account_info(address)
            results["account_info"] = account_info
        except Exception as e:
            logger.error(f"Error collecting account info: {e}")
        
        # Collect token balances
        try:
            logger.info("Collecting token balances")
            token_accounts = self.helius.get_token_accounts_by_owner(address)
            results["token_accounts"] = token_accounts
        except Exception as e:
            logger.error(f"Error collecting token accounts: {e}")
        
        # Collect transaction history
        try:
            logger.info("Collecting transaction history")
            tx_history = self.helius.fetch_transaction_history(address, limit=500)
            results["transaction_history"] = tx_history.to_dict() if not tx_history.empty else {}
        except Exception as e:
            logger.error(f"Error collecting transaction history: {e}")
        
        # Collect token transfers
        try:
            logger.info("Analyzing token transfers")
            token_transfers = self.helius.analyze_token_transfers(address, limit=500)
            results["token_transfers"] = token_transfers.to_dict() if not token_transfers.empty else {}
        except Exception as e:
            logger.error(f"Error analyzing token transfers: {e}")
        
        # Detect dusting attacks
        try:
            logger.info("Detecting dusting attacks")
            dusting_attacks = self.helius.detect_dusting_attacks(address)
            results["dusting_attacks"] = dusting_attacks.to_dict() if not dusting_attacks.empty else {}
        except Exception as e:
            logger.error(f"Error detecting dusting attacks: {e}")
        
        # Detect address poisoning
        try:
            logger.info("Detecting address poisoning")
            address_poisoning = self.helius.detect_address_poisoning(address)
            results["address_poisoning"] = address_poisoning.to_dict() if not address_poisoning.empty else {}
        except Exception as e:
            logger.error(f"Error detecting address poisoning: {e}")
        
        # Risk analysis
        try:
            logger.info("Performing risk analysis")
            risk_score = self.range.get_address_risk_score(address)
            results["risk_score"] = risk_score
        except Exception as e:
            logger.error(f"Error performing risk analysis: {e}")
        
        # Money laundering route analysis
        try:
            logger.info("Analyzing money laundering routes")
            money_laundering = self.range.analyze_money_laundering_routes(address)
            results["money_laundering"] = money_laundering.to_dict() if not money_laundering.empty else {}
        except Exception as e:
            logger.error(f"Error analyzing money laundering routes: {e}")
        
        # Cross-chain flow analysis
        try:
            logger.info("Analyzing cross-chain flows")
            cross_chain = self.range.detect_cross_chain_flows(address)
            results["cross_chain"] = cross_chain.to_dict() if not cross_chain.empty else {}
        except Exception as e:
            logger.error(f"Error analyzing cross-chain flows: {e}")
        
        # Wallet activity analysis
        try:
            logger.info("Analyzing wallet activity")
            wallet_activity = self.vybe.analyze_wallet_activity(address)
            results["wallet_activity"] = wallet_activity.to_dict() if not wallet_activity.empty else {}
        except Exception as e:
            logger.error(f"Error analyzing wallet activity: {e}")
        
        logger.info(f"Completed analysis for address: {address}")
        return results
    
    def analyze_token(self, token_mint: str) -> Dict:
        """
        Perform comprehensive analysis of a Solana token.
        
        Args:
            token_mint: Token mint address to analyze
            
        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Analyzing token: {token_mint}")
        
        results = {}
        
        # Collect token details
        try:
            logger.info("Collecting token details")
            token_details = self.vybe.get_token_details(token_mint)
            results["token_details"] = token_details
        except Exception as e:
            logger.error(f"Error collecting token details: {e}")
        
        # Collect token holders
        try:
            logger.info("Collecting top token holders")
            token_holders = self.vybe.get_token_top_holders(token_mint)
            results["token_holders"] = token_holders
        except Exception as e:
            logger.error(f"Error collecting token holders: {e}")
        
        # Analyze token risk
        try:
            logger.info("Analyzing token risk")
            token_risk = self.rugcheck.analyze_token_risk(token_mint)
            results["token_risk"] = token_risk.to_dict() if not token_risk.empty else {}
        except Exception as e:
            logger.error(f"Error analyzing token risk: {e}")
        
        # Analyze token insiders
        try:
            logger.info("Analyzing token insiders")
            token_insiders = self.rugcheck.analyze_token_insiders(token_mint)
            results["token_insiders"] = token_insiders.to_dict() if not token_insiders.empty else {}
        except Exception as e:
            logger.error(f"Error analyzing token insiders: {e}")
        
        # Analyze liquidity locks
        try:
            logger.info("Analyzing liquidity locks")
            liquidity_locks = self.rugcheck.analyze_liquidity_locks(token_mint)
            results["liquidity_locks"] = liquidity_locks.to_dict() if not liquidity_locks.empty else {}
        except Exception as e:
            logger.error(f"Error analyzing liquidity locks: {e}")
        
        # Get token eligibility
        try:
            logger.info("Checking token eligibility")
            token_eligibility = self.rugcheck.check_token_eligibility(token_mint)
            results["token_eligibility"] = token_eligibility
        except Exception as e:
            logger.error(f"Error checking token eligibility: {e}")
        
        # Analyze token activity
        try:
            logger.info("Analyzing token activity")
            token_activity = self.vybe.analyze_token_activity(token_mint)
            results["token_activity"] = token_activity.to_dict() if not token_activity.empty else {}
        except Exception as e:
            logger.error(f"Error analyzing token activity: {e}")
        
        # Build token insider network
        try:
            logger.info("Building token insider network")
            insider_network = self.rugcheck.build_token_insider_network(token_mint)
            if insider_network:
                # Convert networkx graph to serializable format
                results["insider_network"] = {
                    "nodes": list(insider_network.nodes(data=True)),
                    "edges": list(insider_network.edges(data=True))
                }
        except Exception as e:
            logger.error(f"Error building token insider network: {e}")
        
        logger.info(f"Completed analysis for token: {token_mint}")
        return results
    
    def analyze_program(self, program_id: str) -> Dict:
        """
        Perform comprehensive analysis of a Solana program.
        
        Args:
            program_id: Program ID to analyze
            
        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Analyzing program: {program_id}")
        
        results = {}
        
        # Collect program details
        try:
            logger.info("Collecting program details")
            program_details = self.vybe.get_program_details(program_id)
            results["program_details"] = program_details
        except Exception as e:
            logger.error(f"Error collecting program details: {e}")
        
        # Collect program active users
        try:
            logger.info("Collecting program active users")
            active_users = self.vybe.get_program_active_users(program_id)
            results["active_users"] = active_users
        except Exception as e:
            logger.error(f"Error collecting program active users: {e}")
        
        # Collect program accounts
        try:
            logger.info("Collecting program accounts")
            program_accounts = self.helius.get_program_accounts(program_id)
            results["program_accounts"] = program_accounts
        except Exception as e:
            logger.error(f"Error collecting program accounts: {e}")
        
        logger.info(f"Completed analysis for program: {program_id}")
        return results
    
    def detect_suspicious_activity(self) -> Dict:
        """
        Detect suspicious activity across the Solana ecosystem.
        
        Returns:
            Dictionary with suspicious activity findings
        """
        logger.info("Detecting suspicious activity")
        
        results = {}
        
        # Identify suspicious tokens
        try:
            logger.info("Identifying suspicious tokens")
            suspicious_tokens = self.rugcheck.identify_suspicious_tokens(top_n=20)
            results["suspicious_tokens"] = suspicious_tokens.to_dict() if not suspicious_tokens.empty else {}
        except Exception as e:
            logger.error(f"Error identifying suspicious tokens: {e}")
        
        # Identify suspicious programs
        try:
            logger.info("Identifying suspicious programs")
            suspicious_programs = self.vybe.detect_suspicious_programs()
            results["suspicious_programs"] = suspicious_programs.to_dict() if not suspicious_programs.empty else {}
        except Exception as e:
            logger.error(f"Error identifying suspicious programs: {e}")
        
        logger.info("Completed suspicious activity detection")
        return results
    
    def save_results(self, results: Dict, filename: str):
        """
        Save analysis results to file.
        
        Args:
            results: Analysis results
            filename: Output filename
        """
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # Try to convert DataFrames to records for JSON serialization
            serializable_results = {}
            for key, value in results.items():
                if isinstance(value, dict) and any(k.startswith('df_') for k in value.keys()):
                    serializable_results[key] = {}
                    for k, v in value.items():
                        if k.startswith('df_') and isinstance(v, pd.DataFrame):
                            serializable_results[key][k] = v.to_dict(orient='records')
                        else:
                            serializable_results[key][k] = v
                else:
                    serializable_results[key] = value
            
            with open(filepath, 'w') as f:
                json.dump(serializable_results, f, indent=2)
            
            logger.info(f"Saved results to {filepath}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")

def main():
    """
    Main entry point for SolanaGuard.
    """
    parser = argparse.ArgumentParser(description='SolanaGuard - Solana blockchain analysis tool')
    parser.add_argument('--address', type=str, help='Analyze a Solana address')
    parser.add_argument('--token', type=str, help='Analyze a Solana token')
    parser.add_argument('--program', type=str, help='Analyze a Solana program')
    parser.add_argument('--suspicious', action='store_true', help='Detect suspicious activity')
    parser.add_argument('--no-cache', action='store_true', help='Disable API response caching')
    
    args = parser.parse_args()
    
    # Initialize SolanaGuard
    sg = SolanaGuard(cache_enabled=not args.no_cache)
    
    # Run requested analyses
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if args.address:
        results = sg.analyze_address(args.address)
        sg.save_results(results, f"address_analysis_{args.address}_{timestamp}.json")
    
    if args.token:
        results = sg.analyze_token(args.token)
        sg.save_results(results, f"token_analysis_{args.token}_{timestamp}.json")
    
    if args.program:
        results = sg.analyze_program(args.program)
        sg.save_results(results, f"program_analysis_{args.program}_{timestamp}.json")
    
    if args.suspicious:
        results = sg.detect_suspicious_activity()
        sg.save_results(results, f"suspicious_activity_{timestamp}.json")
    
    # If no analysis specified, show help
    if not (args.address or args.token or args.program or args.suspicious):
        parser.print_help()

if __name__ == "__main__":
    main()