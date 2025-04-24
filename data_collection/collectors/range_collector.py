"""
Range API collector for SolanaGuard.
Provides methods to fetch address risk information and cross-chain transaction flows.
"""
import json
import time
import logging
import requests
import os
import pandas as pd
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from data_collection.config import RANGE_API_KEY, RANGE_API_URL, REQUEST_TIMEOUT, DATA_DIR, CACHE_DIR, RATE_LIMIT

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(DATA_DIR, "range_collector.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("range_collector")

class RangeCollector:
    """
    Collector class for interacting with the Range API.
    Provides methods to fetch address risk information and transaction flows.
    """
    
    def __init__(self, cache_enabled: bool = True):
        """
        Initialize the Range collector.
        
        Args:
            cache_enabled: Whether to cache API responses to disk
        """
        self.api_url = RANGE_API_URL
        self.api_key = RANGE_API_KEY
        self.cache_enabled = cache_enabled
        self.cache_dir = os.path.join(CACHE_DIR, "range")
        self.rate_limit = RATE_LIMIT["range"]
        self.last_request_time = 0
        
        if self.cache_enabled:
            os.makedirs(self.cache_dir, exist_ok=True)
        
        logger.info("Initialized Range collector")
    
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
    
    def _get_cache_path(self, endpoint: str, params: Dict) -> str:
        """
        Generate a cache file path based on the endpoint and parameters.
        
        Args:
            endpoint: The API endpoint
            params: The parameters for the API call
            
        Returns:
            The path to the cache file
        """
        # Create a deterministic hash of the parameters
        param_str = json.dumps(params, sort_keys=True)
        param_hash = hash(param_str) % 10000000  # Simple hash for filename
        endpoint_clean = endpoint.replace("/", "_")
        timestamp = datetime.now().strftime("%Y%m%d")
        return os.path.join(self.cache_dir, f"{endpoint_clean}_{param_hash}_{timestamp}.json")
    
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
    
    def _make_api_request(self, endpoint: str, method: str = "GET", params: Optional[Dict] = None) -> Dict:
        """
        Make a request to the Range API.
        
        Args:
            endpoint: The API endpoint
            method: HTTP method (GET or POST)
            params: The parameters for the API call
            
        Returns:
            The API response data
            
        Raises:
            Exception: If the API request fails
        """
        self._rate_limit_wait()
        
        # Check if in cache
        cache_params = params or {}
        cache_path = self._get_cache_path(endpoint, cache_params)
        cached_data = self._load_from_cache(cache_path)
        if cached_data:
            logger.debug(f"Loaded {endpoint} from cache")
            return cached_data
        
        # Prepare the API request
        url = f"{self.api_url}{endpoint}"
        
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            logger.debug(f"Making {method} request to {endpoint}")
            
            if method.upper() == "GET":
                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=REQUEST_TIMEOUT
                )
            elif method.upper() == "POST":
                response = requests.post(
                    url,
                    headers=headers,
                    json=params,
                    timeout=REQUEST_TIMEOUT
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Check if the request was successful
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            # Cache the successful response
            self._save_to_cache(cache_path, data)
            
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to make API request: {e}")
            raise Exception(f"Request failed: {e}")
    
    def get_address_info(self, address: str, network: str = "solana") -> Dict:
        """
        Get information about a blockchain address.
        
        Args:
            address: The blockchain address
            network: The blockchain network
            
        Returns:
            Address information
        """
        logger.info(f"Getting address info for {address} on {network}")
        endpoint = "/address"
        params = {
            "address": address,
            "network": network
        }
        
        return self._make_api_request(endpoint, params=params)
    
    def get_address_risk_score(self, address: str, network: str = "solana") -> Dict:
        """
        Get risk score for a blockchain address.
        
        Args:
            address: The blockchain address
            network: The blockchain network
            
        Returns:
            Risk score information
        """
        logger.info(f"Getting risk score for {address} on {network}")
        endpoint = "/risk/address"
        params = {
            "address": address,
            "network": network
        }
        
        return self._make_api_request(endpoint, params=params)
    
    def get_address_counterparties(self, address: str, network: str = "solana") -> Dict:
        """
        Get addresses that have interacted with a specific address.
        
        Args:
            address: The blockchain address
            network: The blockchain network
            
        Returns:
            Counterparty information
        """
        logger.info(f"Getting counterparties for {address} on {network}")
        endpoint = "/address/counterparties"
        params = {
            "address": address,
            "network": network
        }
        
        return self._make_api_request(endpoint, params=params)
    
    def get_address_statistics(self, address: str, network: str = "solana") -> Dict:
        """
        Get statistics for a blockchain address.
        
        Args:
            address: The blockchain address
            network: The blockchain network
            
        Returns:
            Address statistics
        """
        logger.info(f"Getting statistics for {address} on {network}")
        endpoint = "/address/statistics"
        params = {
            "address": address,
            "network": network
        }
        
        return self._make_api_request(endpoint, params=params)
    
    def get_address_transactions(
        self, 
        address: str, 
        network: str = "solana",
        limit: int = 100,
        page: int = 1,
        from_timestamp: Optional[int] = None,
        to_timestamp: Optional[int] = None
    ) -> Dict:
        """
        Get transactions for a blockchain address.
        
        Args:
            address: The blockchain address
            network: The blockchain network
            limit: Maximum number of transactions to return
            page: Page number for pagination
            from_timestamp: Start timestamp for filtering
            to_timestamp: End timestamp for filtering
            
        Returns:
            Transaction information
        """
        logger.info(f"Getting transactions for {address} on {network}")
        endpoint = "/address/transactions"
        params = {
            "address": address,
            "network": network,
            "limit": limit,
            "page": page
        }
        
        if from_timestamp:
            params["from"] = from_timestamp
        if to_timestamp:
            params["to"] = to_timestamp
        
        return self._make_api_request(endpoint, params=params)
    
    def get_transaction_details(self, tx_hash: str, network: str = "solana") -> Dict:
        """
        Get details for a specific transaction.
        
        Args:
            tx_hash: The transaction hash
            network: The blockchain network
            
        Returns:
            Transaction details
        """
        logger.info(f"Getting transaction details for {tx_hash} on {network}")
        endpoint = "/transaction"
        params = {
            "hash": tx_hash,
            "network": network
        }
        
        return self._make_api_request(endpoint, params=params)
    
    def get_transaction_risk_score(self, tx_hash: str, network: str = "solana") -> Dict:
        """
        Get risk score for a specific transaction.
        
        Args:
            tx_hash: The transaction hash
            network: The blockchain network
            
        Returns:
            Transaction risk score
        """
        logger.info(f"Getting risk score for transaction {tx_hash} on {network}")
        endpoint = "/risk/transaction"
        params = {
            "hash": tx_hash,
            "network": network
        }
        
        return self._make_api_request(endpoint, params=params)
    
    def get_cross_chain_transaction(self, tx_hash: str) -> Dict:
        """
        Get cross-chain transaction information.
        
        Args:
            tx_hash: The transaction hash
            
        Returns:
            Cross-chain transaction details
        """
        logger.info(f"Getting cross-chain transaction {tx_hash}")
        endpoint = "/transaction/hash"
        params = {
            "hash": tx_hash
        }
        
        return self._make_api_request(endpoint, params=params)
    
    def get_cross_chain_transactions_by_address(
        self, 
        address: str, 
        limit: int = 100,
        page: int = 1
    ) -> Dict:
        """
        Get cross-chain transactions for a specific address.
        
        Args:
            address: The blockchain address
            limit: Maximum number of transactions to return
            page: Page number for pagination
            
        Returns:
            Cross-chain transaction information
        """
        logger.info(f"Getting cross-chain transactions for {address}")
        endpoint = "/transactions/address"
        params = {
            "address": address,
            "limit": limit,
            "page": page
        }
        
        return self._make_api_request(endpoint, params=params)
    
    def analyze_money_laundering_routes(self, address: str) -> pd.DataFrame:
        """
        Analyze potential money laundering routes for a specific address.
        
        Args:
            address: The blockchain address to analyze
            
        Returns:
            DataFrame with potential money laundering routes
        """
        logger.info(f"Analyzing money laundering routes for {address}")
        
        # Get address risk score
        try:
            risk_info = self.get_address_risk_score(address)
            risk_score = risk_info.get("risk_score", 0)
        except Exception as e:
            logger.warning(f"Failed to get risk score for {address}: {e}")
            risk_score = 0
        
        # Get transactions data
        transactions = []
        page = 1
        
        while True:
            try:
                tx_data = self.get_address_transactions(address, page=page, limit=100)
                if not tx_data.get("transactions"):
                    break
                    
                transactions.extend(tx_data.get("transactions", []))
                
                if len(tx_data.get("transactions", [])) < 100:
                    break
                    
                page += 1
            except Exception as e:
                logger.warning(f"Failed to get transactions for {address} (page {page}): {e}")
                break
        
        logger.info(f"Retrieved {len(transactions)} transactions for {address}")
        
        # Get counterparties
        try:
            counterparties_data = self.get_address_counterparties(address)
            counterparties = counterparties_data.get("counterparties", [])
        except Exception as e:
            logger.warning(f"Failed to get counterparties for {address}: {e}")
            counterparties = []
        
        # Analyze transaction flows for suspicious patterns
        suspicious_flows = []
        
        # Check for transactions to high-risk counterparties
        high_risk_counterparties = []
        
        for cp in counterparties:
            cp_address = cp.get("address")
            
            # Skip if no address
            if not cp_address:
                continue
                
            # Check if counterparty has labels
            labels = cp.get("labels", [])
            entity = cp.get("entity", {})
            entity_name = entity.get("name", "")
            
            # Check for high-risk labels
            is_high_risk = any(label in ["mixer", "high_risk", "scam", "sanctioned", "darknet"] 
                              for label in labels)
            
            interaction_count = cp.get("interaction_count", 0)
            sent_volume_usd = cp.get("sent_volume_usd", 0)
            received_volume_usd = cp.get("received_volume_usd", 0)
            
            # Add to high-risk list if matches criteria
            if is_high_risk or (risk_score >= 75):
                high_risk_counterparties.append({
                    "address": cp_address,
                    "labels": labels,
                    "entity_name": entity_name,
                    "interaction_count": interaction_count,
                    "sent_volume_usd": sent_volume_usd,
                    "received_volume_usd": received_volume_usd,
                    "risk_score": risk_score
                })
        
        logger.info(f"Identified {len(high_risk_counterparties)} high-risk counterparties for {address}")
        
        # Analyze transactions to high-risk counterparties
        for hrcp in high_risk_counterparties:
            counterparty_addr = hrcp["address"]
            
            # Find transactions to/from this counterparty
            for tx in transactions:
                tx_counterparties = tx.get("counterparties", [])
                
                # Check if this transaction involves the high-risk counterparty
                cp_in_tx = any(cp.get("address") == counterparty_addr for cp in tx_counterparties)
                
                if cp_in_tx:
                    tx_hash = tx.get("signature", "")
                    
                    # Get risk score for this transaction
                    try:
                        tx_risk_data = self.get_transaction_risk_score(tx_hash)
                        tx_risk_score = tx_risk_data.get("risk_score", 0)
                        tx_risk_factors = tx_risk_data.get("risk_factors", [])
                    except Exception as e:
                        logger.warning(f"Failed to get risk score for transaction {tx_hash}: {e}")
                        tx_risk_score = 0
                        tx_risk_factors = []
                    
                    # Analyze the transaction flow
                    flow_type = "unknown"
                    
                    # Check for cross-chain activity
                    is_cross_chain = any(factor.get("name") == "cross_chain" for factor in tx_risk_factors)
                    
                    # Determine flow type based on risk factors
                    if any(factor.get("name") == "mixer_interaction" for factor in tx_risk_factors):
                        flow_type = "mixer"
                    elif is_cross_chain:
                        flow_type = "cross_chain_bridge"
                    elif any(factor.get("name") == "layering" for factor in tx_risk_factors):
                        flow_type = "layering"
                    elif "exchange" in hrcp["labels"]:
                        flow_type = "exchange_withdrawal" if tx.get("type") == "outgoing" else "exchange_deposit"
                    
                    suspicious_flows.append({
                        "source_address": address,
                        "target_address": counterparty_addr,
                        "transaction_hash": tx_hash,
                        "timestamp": tx.get("timestamp"),
                        "amount_usd": tx.get("amount_usd", 0),
                        "transaction_type": tx.get("type"),
                        "flow_type": flow_type,
                        "risk_score": tx_risk_score,
                        "counterparty_labels": hrcp["labels"],
                        "counterparty_entity": hrcp["entity_name"],
                        "is_cross_chain": is_cross_chain
                    })
        
        # Create DataFrame
        if suspicious_flows:
            flow_df = pd.DataFrame(suspicious_flows)
            logger.info(f"Detected {len(flow_df)} suspicious transaction flows for {address}")
            return flow_df
        else:
            logger.info(f"No suspicious transaction flows detected for {address}")
            return pd.DataFrame()
    
    def detect_cross_chain_flows(self, address: str) -> pd.DataFrame:
        """
        Detect cross-chain funds flows for a specific address.
        
        Args:
            address: The blockchain address to analyze
            
        Returns:
            DataFrame with cross-chain flows
        """
        logger.info(f"Detecting cross-chain flows for {address}")
        
        try:
            # Get cross-chain transactions
            cross_chain_data = self.get_cross_chain_transactions_by_address(address)
            transactions = cross_chain_data.get("transactions", [])
        except Exception as e:
            logger.warning(f"Failed to get cross-chain transactions for {address}: {e}")
            return pd.DataFrame()
        
        logger.info(f"Retrieved {len(transactions)} cross-chain transactions for {address}")
        
        if not transactions:
            return pd.DataFrame()
            
        # Process cross-chain transactions
        cross_chain_flows = []
        
        for tx in transactions:
            source_chain = tx.get("source_chain")
            destination_chain = tx.get("destination_chain")
            
            # Skip if missing chain info
            if not source_chain or not destination_chain:
                continue
                
            source_tx = tx.get("source_transaction")
            destination_tx = tx.get("destination_transaction")
            
            # Add to cross-chain flows
            cross_chain_flows.append({
                "address": address,
                "source_chain": source_chain,
                "destination_chain": destination_chain,
                "source_tx_hash": source_tx.get("hash") if source_tx else None,
                "destination_tx_hash": destination_tx.get("hash") if destination_tx else None,
                "source_timestamp": source_tx.get("timestamp") if source_tx else None,
                "destination_timestamp": destination_tx.get("timestamp") if destination_tx else None,
                "asset": tx.get("asset"),
                "amount": tx.get("amount"),
                "amount_usd": tx.get("amount_usd"),
                "bridge": tx.get("bridge"),
                "risk_score": tx.get("risk_score", 0)
            })
        
        if cross_chain_flows:
            flow_df = pd.DataFrame(cross_chain_flows)
            logger.info(f"Detected {len(flow_df)} cross-chain flows for {address}")
            return flow_df
        else:
            logger.info(f"No cross-chain flows detected for {address}")
            return pd.DataFrame()