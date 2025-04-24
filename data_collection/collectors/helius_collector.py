"""
Helius API collector for SolanaGuard.
Provides methods to fetch transaction data and account information.
"""
import json
import time
import logging
import requests
from typing import Dict, List, Optional, Union, Any
import os
import pandas as pd
from datetime import datetime

# Fix the import by using the correct package path
from data_collection.config import HELIUS_RPC_URL, REQUEST_TIMEOUT, DATA_DIR, CACHE_DIR, RATE_LIMIT

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(DATA_DIR, "helius_collector.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("helius_collector")

class HeliusCollector:
    """
    Collector class for interacting with the Helius RPC API.
    Provides methods to fetch and process Solana transaction data.
    """
    
    def __init__(self, cache_enabled: bool = True):
        """
        Initialize the Helius collector.
        
        Args:
            cache_enabled: Whether to cache API responses to disk
        """
        self.rpc_url = HELIUS_RPC_URL
        self.cache_enabled = cache_enabled
        self.cache_dir = os.path.join(CACHE_DIR, "helius")
        self.rate_limit = RATE_LIMIT["helius"]
        self.last_request_time = 0
        
        if self.cache_enabled:
            os.makedirs(self.cache_dir, exist_ok=True)
        
        logger.info("Initialized Helius collector")
    
    def _rate_limit_wait(self):
        """
        Implement rate limiting to avoid API throttling.
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        wait_time = (1.0 / self.rate_limit) - time_since_last_request
        
        if wait_time > 0:
            time.sleep(wait_time)
            
        self.last_request_time = time.time()
    
    def _get_cache_path(self, method: str, params: Dict) -> str:
        """
        Generate a cache file path based on the method and parameters.
        
        Args:
            method: The RPC method name
            params: The parameters for the RPC call
            
        Returns:
            The path to the cache file
        """
        # Create a deterministic hash of the parameters
        param_str = json.dumps(params, sort_keys=True)
        param_hash = hash(param_str) % 10000000  # Simple hash for filename
        timestamp = datetime.now().strftime("%Y%m%d")
        return os.path.join(self.cache_dir, f"{method}_{param_hash}_{timestamp}.json")
    
    def _load_from_cache(self, cache_path: str) -> Optional[Dict]:
        """
        Load data from cache if available.
        
        Args:
            cache_path: Path to the cache file
            
        Returns:
            The cached data or None if not available
        """
        if not self.cache_enabled or not os.path.exists(cache_path):
            return None
        
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load from cache: {e}")
            return None
    
    def _save_to_cache(self, cache_path: str, data: Dict):
        """
        Save data to cache.
        
        Args:
            cache_path: Path to the cache file
            data: Data to cache
        """
        if not self.cache_enabled:
            return
        
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save to cache: {e}")
    
    def _make_rpc_request(self, method: str, params: List[Any]) -> Dict:
        """
        Make an RPC request to the Helius API.
        
        Args:
            method: The RPC method name
            params: The parameters for the RPC call
            
        Returns:
            The API response data
            
        Raises:
            Exception: If the API request fails
        """
        self._rate_limit_wait()
        
        # Check if in cache
        cache_path = self._get_cache_path(method, params)
        cached_data = self._load_from_cache(cache_path)
        if cached_data:
            logger.debug(f"Loaded {method} from cache")
            return cached_data
        
        # Prepare the RPC request
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            logger.debug(f"Making RPC request: {method}")
            response = requests.post(
                self.rpc_url,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            
            # Check if the request was successful
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            # Check for RPC errors
            if "error" in data:
                logger.error(f"RPC error: {data['error']}")
                raise Exception(f"RPC error: {data['error']}")
            
            # Cache the successful response
            self._save_to_cache(cache_path, data)
            
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to make RPC request: {e}")
            raise Exception(f"Request failed: {e}")
    
    def get_account_info(self, address: str, encoding: str = "jsonParsed") -> Dict:
        """
        Get account information for a Solana address.
        
        Args:
            address: The Solana account address
            encoding: The encoding format for the response
            
        Returns:
            Account information
        """
        logger.info(f"Getting account info for {address}")
        params = [
            address,
            {"encoding": encoding}
        ]
        
        response = self._make_rpc_request("getAccountInfo", params)
        return response["result"]
    
    def get_balance(self, address: str) -> int:
        """
        Get SOL balance for a Solana address.
        
        Args:
            address: The Solana account address
            
        Returns:
            The account balance in lamports
        """
        logger.info(f"Getting SOL balance for {address}")
        params = [address]
        
        response = self._make_rpc_request("getBalance", params)
        return response["result"]["value"]
    
    def get_token_accounts_by_owner(self, owner_address: str) -> Dict:
        """
        Get all token accounts owned by a specific address.
        
        Args:
            owner_address: The owner's Solana address
            
        Returns:
            Token account information
        """
        logger.info(f"Getting token accounts for {owner_address}")
        params = [
            owner_address,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding": "jsonParsed"}
        ]
        
        response = self._make_rpc_request("getTokenAccountsByOwner", params)
        return response["result"]
    
    def get_transaction(self, signature: str, encoding: str = "jsonParsed") -> Dict:
        """
        Get detailed information about a transaction by its signature.
        
        Args:
            signature: The transaction signature
            encoding: The encoding format for the response
            
        Returns:
            Transaction details
        """
        logger.info(f"Getting transaction {signature}")
        params = [
            signature,
            {"encoding": encoding, "maxSupportedTransactionVersion": 0}
        ]
        
        response = self._make_rpc_request("getTransaction", params)
        return response["result"]
    
    def get_signatures_for_address(
        self, 
        address: str, 
        limit: int = 100, 
        before: Optional[str] = None,
        until: Optional[str] = None
    ) -> List[Dict]:
        """
        Get transaction signatures for a specific address.
        
        Args:
            address: The Solana account address
            limit: Maximum number of signatures to return
            before: Signature to start searching from (backwards in time)
            until: Signature to search until (forwards in time)
            
        Returns:
            List of transaction signatures
        """
        logger.info(f"Getting signatures for {address} (limit: {limit})")
        params = [
            address,
            {"limit": limit}
        ]
        
        # Add optional parameters if provided
        if before:
            params[1]["before"] = before
        if until:
            params[1]["until"] = until
        
        response = self._make_rpc_request("getSignaturesForAddress", params)
        return response["result"]
    
    def get_program_accounts(
        self,
        program_id: str,
        filters: Optional[List[Dict]] = None,
        encoding: str = "jsonParsed"
    ) -> List[Dict]:
        """
        Get all accounts owned by a specific program.
        
        Args:
            program_id: The program ID to query
            filters: Optional filters for the query
            encoding: The encoding format for the response
            
        Returns:
            List of program accounts
        """
        logger.info(f"Getting program accounts for {program_id}")
        params = [
            program_id,
            {"encoding": encoding}
        ]
        
        if filters:
            params[1]["filters"] = filters
        
        response = self._make_rpc_request("getProgramAccounts", params)
        return response["result"]
    
    def simulate_transaction(self, transaction: str) -> Dict:
        """
        Simulate a transaction without submitting it to the network.
        
        Args:
            transaction: The transaction data as a base64 string
            
        Returns:
            Simulation results
        """
        logger.info("Simulating transaction")
        params = [
            transaction,
            {"encoding": "base64", "commitment": "processed"}
        ]
        
        response = self._make_rpc_request("simulateTransaction", params)
        return response["result"]
    
    def fetch_transaction_history(self, address: str, limit: int = 1000) -> pd.DataFrame:
        """
        Fetch and process complete transaction history for an address.
        
        Args:
            address: The Solana account address
            limit: Maximum number of transactions to fetch
            
        Returns:
            DataFrame containing processed transaction data
        """
        logger.info(f"Fetching transaction history for {address} (limit: {limit})")
        
        all_signatures = []
        batch_size = 100
        before_signature = None
        
        # Paginate through signatures until we reach the limit
        while len(all_signatures) < limit:
            batch_limit = min(batch_size, limit - len(all_signatures))
            
            signatures_batch = self.get_signatures_for_address(
                address, 
                limit=batch_limit,
                before=before_signature
            )
            
            if not signatures_batch:
                break
                
            all_signatures.extend(signatures_batch)
            
            # Update the before_signature for the next batch
            before_signature = signatures_batch[-1]["signature"]
        
        logger.info(f"Fetched {len(all_signatures)} signatures for {address}")
        
        # Fetch full transaction details for each signature
        transactions = []
        for sig_info in all_signatures:
            try:
                tx_data = self.get_transaction(sig_info["signature"])
                if tx_data:
                    transactions.append({
                        "signature": sig_info["signature"],
                        "block_time": tx_data.get("blockTime"),
                        "slot": tx_data.get("slot"),
                        "success": tx_data.get("meta", {}).get("err") is None,
                        "fee": tx_data.get("meta", {}).get("fee"),
                        "log_messages": tx_data.get("meta", {}).get("logMessages", []),
                        "raw_data": tx_data  # Store full data for detailed analysis
                    })
            except Exception as e:
                logger.warning(f"Failed to fetch transaction {sig_info['signature']}: {e}")
        
        logger.info(f"Processed {len(transactions)} transactions for {address}")
        
        # Convert to DataFrame for easier analysis
        if transactions:
            df = pd.DataFrame(transactions)
            return df
        else:
            return pd.DataFrame()
    
    def analyze_token_transfers(self, address: str, limit: int = 1000) -> pd.DataFrame:
        """
        Analyze token transfers for a specific address.
        
        Args:
            address: The Solana account address
            limit: Maximum number of transactions to analyze
            
        Returns:
            DataFrame with processed token transfer data
        """
        logger.info(f"Analyzing token transfers for {address}")
        
        # Get transaction history
        tx_df = self.fetch_transaction_history(address, limit)
        
        if tx_df.empty:
            return pd.DataFrame()
        
        # Extract token transfers from transaction data
        token_transfers = []
        
        for _, row in tx_df.iterrows():
            tx_data = row["raw_data"]
            
            # Check pre and post token balances to identify transfers
            pre_token_balances = tx_data.get("meta", {}).get("preTokenBalances", [])
            post_token_balances = tx_data.get("meta", {}).get("postTokenBalances", [])
            
            # Create mapping of account indices to simplify lookup
            pre_balances_map = {item["accountIndex"]: item for item in pre_token_balances}
            post_balances_map = {item["accountIndex"]: item for item in post_token_balances}
            
            # Find all account indices that appear in either pre or post balances
            all_indices = set(pre_balances_map.keys()).union(set(post_balances_map.keys()))
            
            for idx in all_indices:
                pre_balance = pre_balances_map.get(idx, {"uiTokenAmount": {"uiAmount": 0}})
                post_balance = post_balances_map.get(idx, {"uiTokenAmount": {"uiAmount": 0}})
                
                pre_amount = pre_balance.get("uiTokenAmount", {}).get("uiAmount", 0) or 0
                post_amount = post_balance.get("uiTokenAmount", {}).get("uiAmount", 0) or 0
                
                # Calculate change in token balance
                amount_change = post_amount - pre_amount
                
                # Skip if no change in balance
                if amount_change == 0:
                    continue
                
                token_data = post_balance if idx in post_balances_map else pre_balance
                mint = token_data.get("mint", "")
                owner = token_data.get("owner", "")
                
                # Determine if this is a send or receive for the target address
                direction = "received" if owner == address and amount_change > 0 else "sent"
                if owner != address and amount_change < 0:
                    direction = "received_by_other"
                elif owner != address and amount_change > 0:
                    direction = "sent_by_other"
                
                token_transfers.append({
                    "signature": row["signature"],
                    "block_time": row["block_time"],
                    "slot": row["slot"],
                    "mint": mint,
                    "owner": owner,
                    "token_account": token_data.get("pubkey", ""),
                    "amount_change": abs(amount_change),
                    "decimals": token_data.get("uiTokenAmount", {}).get("decimals", 0),
                    "direction": direction,
                    "success": row["success"]
                })
        
        if token_transfers:
            transfers_df = pd.DataFrame(token_transfers)
            logger.info(f"Extracted {len(transfers_df)} token transfers for {address}")
            return transfers_df
        else:
            logger.info(f"No token transfers found for {address}")
            return pd.DataFrame()
    
    def detect_dusting_attacks(self, address: str, threshold: float = 0.1) -> pd.DataFrame:
        """
        Detect potential dusting attacks by analyzing small value transfers.
        
        Args:
            address: The Solana account address
            threshold: Maximum token value (in USD) to consider as dust
            
        Returns:
            DataFrame with potential dusting attack transactions
        """
        logger.info(f"Detecting dusting attacks for {address} (threshold: {threshold} USD)")
        
        # Get token transfers
        transfers_df = self.analyze_token_transfers(address)
        
        if transfers_df.empty:
            return pd.DataFrame()
        
        # Filter for received transfers only
        received_transfers = transfers_df[transfers_df["direction"] == "received"]
        
        if received_transfers.empty:
            return pd.DataFrame()
        
        # Group by mint to find potential dust attacks
        # This is a simplified detection - in a real implementation, we would
        # also need to fetch token prices to convert to USD value
        dust_candidates = []
        
        for mint, group in received_transfers.groupby("mint"):
            # Detect common patterns in dust attacks:
            # 1. Very small amounts
            # 2. Multiple transfers from different accounts
            # 3. Unique senders (we'd need to extend the analysis to include sender info)
            
            # For now, we'll use the amount and count as indicators
            avg_amount = group["amount_change"].mean()
            count = len(group)
            
            # In a real implementation, we'd convert avg_amount to USD
            # For now, we'll assume amount < threshold is potentially dust
            if avg_amount < threshold and count >= 1:
                for _, row in group.iterrows():
                    dust_candidates.append({
                        "signature": row["signature"],
                        "block_time": row["block_time"],
                        "mint": mint,
                        "amount": row["amount_change"],
                        "decimals": row["decimals"],
                        "risk_score": (1 / (avg_amount + 0.001)) * min(count, 10) / 10,
                        "type": "potential_dust"
                    })
        
        if dust_candidates:
            dust_df = pd.DataFrame(dust_candidates)
            logger.info(f"Detected {len(dust_df)} potential dusting transactions for {address}")
            return dust_df
        else:
            logger.info(f"No dusting attacks detected for {address}")
            return pd.DataFrame()
    
    def detect_address_poisoning(self, address: str) -> pd.DataFrame:
        """
        Detect potential address poisoning attacks by analyzing transaction patterns.
        
        Args:
            address: The Solana account address
            
        Returns:
            DataFrame with potential address poisoning transactions
        """
        logger.info(f"Detecting address poisoning for {address}")
        
        # Get transaction history
        tx_df = self.fetch_transaction_history(address)
        
        if tx_df.empty:
            return pd.DataFrame()
        
        # Get token transfers
        transfers_df = self.analyze_token_transfers(address)
        
        if transfers_df.empty:
            return pd.DataFrame()
            
        # Address poisoning typically involves small transfers to establish a transaction history
        # and create visual similarity in transaction lists
        
        # Get all unique addresses that have interacted with the target
        all_owners = list(transfers_df["owner"].unique())
        
        # Calculate similarity between addresses
        # In a real implementation, we'd use more sophisticated similarity metrics
        poisoning_candidates = []
        
        for owner in all_owners:
            if owner == address:
                continue
                
            # Calculate visual similarity (simplified)
            # In a real scenario, we'd use more advanced techniques to detect
            # prefix/suffix similarity, character swapping, etc.
            similarity = self._calculate_address_similarity(address, owner)
            
            if similarity > 0.5:  # Adjust threshold as needed
                # Check if there are small transfers from this similar address
                owner_transfers = transfers_df[transfers_df["owner"] == owner]
                
                for _, row in owner_transfers.iterrows():
                    poisoning_candidates.append({
                        "signature": row["signature"],
                        "block_time": row["block_time"],
                        "similar_address": owner,
                        "similarity_score": similarity,
                        "amount": row["amount_change"],
                        "mint": row["mint"],
                        "risk_score": similarity * 100,
                        "type": "potential_poisoning"
                    })
        
        if poisoning_candidates:
            poisoning_df = pd.DataFrame(poisoning_candidates)
            logger.info(f"Detected {len(poisoning_df)} potential address poisoning transactions for {address}")
            return poisoning_df
        else:
            logger.info(f"No address poisoning detected for {address}")
            return pd.DataFrame()
    
    def _calculate_address_similarity(self, addr1: str, addr2: str) -> float:
        """
        Calculate visual similarity between two addresses.
        
        Args:
            addr1: First address
            addr2: Second address
            
        Returns:
            Similarity score between 0 and 1
        """
        # This is a simplified implementation
        # In a real scenario, we'd use more sophisticated similarity metrics
        
        # Check for common prefix (first few characters)
        prefix_length = min(8, min(len(addr1), len(addr2)))
        prefix_similarity = sum(a == b for a, b in zip(addr1[:prefix_length], addr2[:prefix_length])) / prefix_length
        
        # Check for common suffix (last few characters)
        suffix_length = min(8, min(len(addr1), len(addr2)))
        suffix_similarity = sum(a == b for a, b in zip(addr1[-suffix_length:], addr2[-suffix_length:])) / suffix_length
        
        # Weighted similarity score
        return (0.6 * prefix_similarity) + (0.4 * suffix_similarity)