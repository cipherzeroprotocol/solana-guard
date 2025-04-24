"""
Vybe API collector for SolanaGuard.
Provides methods to fetch token data, account balances, and program analytics.
"""
import json
import time
import logging
import requests
import os
import pandas as pd
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta

from data_collection.config import VYBE_API_KEY, VYBE_API_URL, REQUEST_TIMEOUT, DATA_DIR, CACHE_DIR, RATE_LIMIT

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(DATA_DIR, "vybe_collector.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("vybe_collector")

class VybeCollector:
    """
    Collector class for interacting with the Vybe API.
    Provides methods to fetch token data, account balances, and program analytics.
    """
    
    def __init__(self, cache_enabled: bool = True):
        """
        Initialize the Vybe collector.
        
        Args:
            cache_enabled: Whether to cache API responses to disk
        """
        self.api_url = VYBE_API_URL
        self.api_key = VYBE_API_KEY
        self.cache_enabled = cache_enabled
        self.cache_dir = os.path.join(CACHE_DIR, "vybe")
        self.rate_limit = RATE_LIMIT["vybe"]
        self.last_request_time = 0
        
        if self.cache_enabled:
            os.makedirs(self.cache_dir, exist_ok=True)
        
        logger.info("Initialized Vybe collector")
    
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
    
    def _make_api_request(self, endpoint: str, method: str = "GET", params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """
        Make a request to the Vybe API.
        
        Args:
            endpoint: The API endpoint
            method: HTTP method (GET or POST)
            params: Query parameters for the API call
            data: Body data for POST requests
            
        Returns:
            The API response data
            
        Raises:
            Exception: If the API request fails
        """
        self._rate_limit_wait()
        
        # Check if in cache
        cache_params = params or {}
        if data:
            cache_params.update(data)
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
                    params=params,
                    json=data,
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
    
    def get_known_accounts(
        self,
        owner_address: Optional[str] = None,
        name: Optional[str] = None,
        labels: Optional[List[str]] = None,
        entity_name: Optional[str] = None,
        entity_id: Optional[str] = None
    ) -> Dict:
        """
        Get a categorized list of labeled Solana accounts.
        
        Args:
            owner_address: Filter by owner address
            name: Filter by account name
            labels: Filter by labels
            entity_name: Filter by entity name
            entity_id: Filter by entity ID
            
        Returns:
            List of known accounts
        """
        logger.info("Getting known accounts")
        endpoint = "/account/known-accounts"
        
        params = {}
        if owner_address:
            params["ownerAddress"] = owner_address
        if name:
            params["name"] = name
        if labels:
            params["labels"] = ",".join(labels)
        if entity_name:
            params["entityName"] = entity_name
        if entity_id:
            params["entityId"] = entity_id
        
        return self._make_api_request(endpoint, params=params)
    
    def get_token_balance(
        self,
        owner_address: str,
        include_no_price_balance: bool = True,
        limit: int = 100,
        page: int = 1
    ) -> Dict:
        """
        Get SPL token balances for a provided account address.
        
        Args:
            owner_address: Account address
            include_no_price_balance: Include tokens without price info
            limit: Number of tokens to return
            page: Page number
            
        Returns:
            Token balance information
        """
        logger.info(f"Getting token balance for {owner_address}")
        endpoint = f"/account/token-balance/{owner_address}"
        
        params = {
            "includeNoPriceBalance": str(include_no_price_balance).lower(),
            "limit": limit,
            "page": page
        }
        
        return self._make_api_request(endpoint, params=params)
    
    def get_token_balance_ts(self, owner_address: str, days: int = 30) -> Dict:
        """
        Get time-series token balance data for an address.
        
        Args:
            owner_address: Account address
            days: Number of days of historical data
            
        Returns:
            Time-series token balance data
        """
        logger.info(f"Getting token balance time series for {owner_address}")
        endpoint = f"/account/token-balance-ts/{owner_address}"
        
        params = {"days": days}
        
        return self._make_api_request(endpoint, params=params)
    
    def get_multi_wallet_token_balances(
        self,
        wallets: List[str],
        include_no_price_balance: bool = True,
        limit: int = 100,
        page: int = 1
    ) -> Dict:
        """
        Get SPL token balances for multiple account addresses.
        
        Args:
            wallets: List of account addresses
            include_no_price_balance: Include tokens without price info
            limit: Number of tokens to return
            page: Page number
            
        Returns:
            Token balance information for multiple wallets
        """
        logger.info(f"Getting token balances for multiple wallets")
        endpoint = "/account/token-balances"
        
        params = {
            "includeNoPriceBalance": str(include_no_price_balance).lower(),
            "limit": limit,
            "page": page
        }
        
        data = {"wallets": wallets}
        
        return self._make_api_request(endpoint, method="POST", params=params, data=data)
    
    def get_token_transfers(
        self,
        mint_address: Optional[str] = None,
        signature: Optional[str] = None,
        calling_program: Optional[str] = None,
        wallet_address: Optional[str] = None,
        sender_address: Optional[str] = None,
        receiver_address: Optional[str] = None,
        min_usd_amount: Optional[float] = None,
        max_usd_amount: Optional[float] = None,
        time_start: Optional[int] = None,
        time_end: Optional[int] = None,
        limit: int = 100,
        page: int = 1
    ) -> Dict:
        """
        Get token transfer transactions with filtering options.
        
        Args:
            mint_address: Filter by token mint
            signature: Filter by transaction signature
            calling_program: Filter by calling program
            wallet_address: Filter by wallet address
            sender_address: Filter by sender address
            receiver_address: Filter by receiver address
            min_usd_amount: Filter by minimum USD amount
            max_usd_amount: Filter by maximum USD amount
            time_start: Filter by start timestamp
            time_end: Filter by end timestamp
            limit: Number of transfers to return
            page: Page number
            
        Returns:
            Token transfer information
        """
        logger.info("Getting token transfers")
        endpoint = "/token/transfers"
        
        params = {
            "limit": limit,
            "page": page
        }
        
        if mint_address:
            params["mintAddress"] = mint_address
        if signature:
            params["signature"] = signature
        if calling_program:
            params["callingProgram"] = calling_program
        if wallet_address:
            params["walletAddress"] = wallet_address
        if sender_address:
            params["senderAddress"] = sender_address
        if receiver_address:
            params["receiverAddress"] = receiver_address
        if min_usd_amount is not None:
            params["minUsdAmount"] = min_usd_amount
        if max_usd_amount is not None:
            params["maxUsdAmount"] = max_usd_amount
        if time_start:
            params["timeStart"] = time_start
        if time_end:
            params["timeEnd"] = time_end
        
        return self._make_api_request(endpoint, params=params)
    
    def get_token_details(self, mint_address: str) -> Dict:
        """
        Get token details and 24h activity overview.
        
        Args:
            mint_address: Token mint address
            
        Returns:
            Token details
        """
        logger.info(f"Getting token details for {mint_address}")
        endpoint = f"/token/{mint_address}"
        
        return self._make_api_request(endpoint)
    
    def get_token_top_holders(
        self,
        mint_address: str,
        limit: int = 100,
        page: int = 1
    ) -> Dict:
        """
        Get top token holders for a specific token.
        
        Args:
            mint_address: Token mint address
            limit: Number of holders to return
            page: Page number
            
        Returns:
            Top token holders
        """
        logger.info(f"Getting top holders for {mint_address}")
        endpoint = f"/token/{mint_address}/top-holders"
        
        params = {
            "limit": limit,
            "page": page
        }
        
        return self._make_api_request(endpoint, params=params)
    
    def get_token_holders_ts(
        self,
        mint_id: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        interval: Optional[str] = None,
        limit: int = 100,
        page: int = 1
    ) -> Dict:
        """
        Get time series data of token holders count.
        
        Args:
            mint_id: Token mint address
            start_time: Start timestamp
            end_time: End timestamp
            interval: Time interval
            limit: Number of data points to return
            page: Page number
            
        Returns:
            Time series data of token holders
        """
        logger.info(f"Getting token holders time series for {mint_id}")
        endpoint = f"/token/{mint_id}/holders-ts"
        
        params = {
            "limit": limit,
            "page": page
        }
        
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        if interval:
            params["interval"] = interval
        
        return self._make_api_request(endpoint, params=params)
    
    def get_program_details(self, program_id: str) -> Dict:
        """
        Get program details including metrics.
        
        Args:
            program_id: Program ID
            
        Returns:
            Program details
        """
        logger.info(f"Getting program details for {program_id}")
        endpoint = f"/program/{program_id}"
        
        return self._make_api_request(endpoint)
    
    def get_program_active_users(
        self,
        program_id: str,
        days: int = 30,
        limit: int = 100
    ) -> Dict:
        """
        Get active users with instruction/transaction counts.
        
        Args:
            program_id: Program ID
            days: Number of days to analyze
            limit: Number of users to return
            
        Returns:
            Active users data
        """
        logger.info(f"Getting active users for {program_id}")
        endpoint = f"/program/{program_id}/active-users"
        
        params = {
            "days": days,
            "limit": limit
        }
        
        return self._make_api_request(endpoint, params=params)
    
    def get_programs_list(
        self,
        labels: Optional[List[str]] = None,
        limit: int = 100,
        page: int = 1
    ) -> Dict:
        """
        Get list of all Solana programs with IDLs.
        
        Args:
            labels: Filter by labels
            limit: Number of programs to return
            page: Page number
            
        Returns:
            List of programs
        """
        logger.info("Getting programs list")
        endpoint = "/programs"
        
        params = {
            "limit": limit,
            "page": page
        }
        
        if labels:
            params["labels"] = ",".join(labels)
        
        return self._make_api_request(endpoint, params=params)
    
    def get_token_price_ohlcv(
        self,
        mint_address: str,
        resolution: Optional[str] = None,
        time_start: Optional[int] = None,
        time_end: Optional[int] = None,
        limit: int = 100,
        page: int = 1
    ) -> Dict:
        """
        Get OHLC price data for a token.
        
        Args:
            mint_address: Token mint address
            resolution: Time resolution
            time_start: Start timestamp
            time_end: End timestamp
            limit: Number of data points to return
            page: Page number
            
        Returns:
            OHLC price data
        """
        logger.info(f"Getting price OHLCV for {mint_address}")
        endpoint = f"/price/{mint_address}/token-ohlcv"
        
        params = {
            "limit": limit,
            "page": page
        }
        
        if resolution:
            params["resolution"] = resolution
        if time_start:
            params["timeStart"] = time_start
        if time_end:
            params["timeEnd"] = time_end
        
        return self._make_api_request(endpoint, params=params)
    
    def analyze_token_activity(self, mint_address: str) -> pd.DataFrame:
        """
        Analyze token activity including transfers, holders, and price movements.
        
        Args:
            mint_address: Token mint address
            
        Returns:
            DataFrame with token activity analysis
        """
        logger.info(f"Analyzing token activity for {mint_address}")
        
        try:
            # Get token details
            token_details = self.get_token_details(mint_address)
        except Exception as e:
            logger.warning(f"Failed to get token details for {mint_address}: {e}")
            return pd.DataFrame()
        
        # Get price history
        try:
            price_data = self.get_token_price_ohlcv(
                mint_address,
                resolution="1d",
                time_start=int((datetime.now() - timedelta(days=30)).timestamp()),
                time_end=int(datetime.now().timestamp())
            )
            price_history = price_data.get("data", [])
        except Exception as e:
            logger.warning(f"Failed to get price history for {mint_address}: {e}")
            price_history = []
        
        # Get top holders
        try:
            holders_data = self.get_token_top_holders(mint_address, limit=20)
            top_holders = holders_data.get("data", [])
        except Exception as e:
            logger.warning(f"Failed to get top holders for {mint_address}: {e}")
            top_holders = []
        
        # Get recent transfers
        try:
            transfers_data = self.get_token_transfers(
                mint_address=mint_address,
                time_start=int((datetime.now() - timedelta(days=7)).timestamp()),
                time_end=int(datetime.now().timestamp()),
                limit=100
            )
            recent_transfers = transfers_data.get("data", [])
        except Exception as e:
            logger.warning(f"Failed to get recent transfers for {mint_address}: {e}")
            recent_transfers = []
        
        # Analyze holder distribution
        holder_concentration = 0
        if top_holders:
            top5_holdings = sum(holder.get("percentage", 0) for holder in top_holders[:5])
            holder_concentration = top5_holdings
        
        # Analyze transfer patterns
        transfer_volume = 0
        unique_senders = set()
        unique_receivers = set()
        
        for transfer in recent_transfers:
            transfer_volume += transfer.get("amount_usd", 0)
            unique_senders.add(transfer.get("sender_address"))
            unique_receivers.add(transfer.get("receiver_address"))
        
        # Create activity dataset
        activity_data = {
            "token_mint": mint_address,
            "token_name": token_details.get("name", ""),
            "token_symbol": token_details.get("symbol", ""),
            "price_usd": token_details.get("price", 0),
            "market_cap": token_details.get("market_cap", 0),
            "volume_24h": token_details.get("volume_24h", 0),
            "holders_count": token_details.get("holders_count", 0),
            "holder_concentration": holder_concentration,
            "transfer_count_7d": len(recent_transfers),
            "transfer_volume_7d": transfer_volume,
            "unique_senders_7d": len(unique_senders),
            "unique_receivers_7d": len(unique_receivers),
            "price_change_30d": 0,
            "volatility_30d": 0
        }
        
        # Calculate price metrics if we have price history
        if price_history and len(price_history) > 1:
            start_price = price_history[0].get("close", 0)
            end_price = price_history[-1].get("close", 0)
            if start_price > 0:
                activity_data["price_change_30d"] = (end_price - start_price) / start_price * 100
            
            # Calculate volatility
            if len(price_history) > 1:
                prices = [p.get("close", 0) for p in price_history]
                returns = [prices[i+1]/prices[i] - 1 for i in range(len(prices)-1)]
                activity_data["volatility_30d"] = pd.Series(returns).std() * 100
        
        # Convert to DataFrame
        activity_df = pd.DataFrame([activity_data])
        logger.info(f"Analyzed token activity for {mint_address}")
        return activity_df
    
    def analyze_wallet_activity(self, wallet_address: str) -> pd.DataFrame:
        """
        Analyze wallet activity including token balances and transfers.
        
        Args:
            wallet_address: Wallet address
            
        Returns:
            DataFrame with wallet activity analysis
        """
        logger.info(f"Analyzing wallet activity for {wallet_address}")
        
        try:
            # Get token balances
            balance_data = self.get_token_balance(wallet_address)
            balances = balance_data.get("balances", [])
        except Exception as e:
            logger.warning(f"Failed to get token balances for {wallet_address}: {e}")
            balances = []
        
        # Get recent transfers (both sent and received)
        try:
            transfers_data = self.get_token_transfers(
                wallet_address=wallet_address,
                time_start=int((datetime.now() - timedelta(days=30)).timestamp()),
                time_end=int(datetime.now().timestamp()),
                limit=500
            )
            transfers = transfers_data.get("data", [])
        except Exception as e:
            logger.warning(f"Failed to get transfers for {wallet_address}: {e}")
            transfers = []
        
        # Analyze balance distribution
        total_balance_usd = sum(token.get("balance_usd", 0) for token in balances)
        token_count = len(balances)
        
        # Analyze transfer patterns
        sent_transfers = [t for t in transfers if t.get("sender_address") == wallet_address]
        received_transfers = [t for t in transfers if t.get("receiver_address") == wallet_address]
        
        sent_volume = sum(t.get("amount_usd", 0) for t in sent_transfers)
        received_volume = sum(t.get("amount_usd", 0) for t in received_transfers)
        
        unique_sent_destinations = len(set(t.get("receiver_address") for t in sent_transfers))
        unique_received_sources = len(set(t.get("sender_address") for t in received_transfers))
        
        # Calculate transfer patterns
        transfer_frequency = len(transfers) / 30 if transfers else 0  # Transfers per day
        
        # Create activity dataset
        activity_data = {
            "wallet_address": wallet_address,
            "token_count": token_count,
            "total_balance_usd": total_balance_usd,
            "sent_transfer_count_30d": len(sent_transfers),
            "received_transfer_count_30d": len(received_transfers),
            "sent_volume_30d": sent_volume,
            "received_volume_30d": received_volume,
            "unique_sent_destinations": unique_sent_destinations,
            "unique_received_sources": unique_received_sources,
            "transfer_frequency": transfer_frequency,
            "volume_ratio": received_volume / sent_volume if sent_volume > 0 else float('inf'),
            "is_active": len(transfers) > 0
        }
        
        # Extract top tokens by balance
        top_tokens = []
        for token in sorted(balances, key=lambda x: x.get("balance_usd", 0), reverse=True)[:5]:
            top_tokens.append({
                "mint": token.get("mint"),
                "symbol": token.get("symbol"),
                "balance_usd": token.get("balance_usd", 0),
                "percentage": token.get("balance_usd", 0) / total_balance_usd * 100 if total_balance_usd > 0 else 0
            })
        
        # Convert to DataFrame
        activity_df = pd.DataFrame([activity_data])
        logger.info(f"Analyzed wallet activity for {wallet_address}")
        return activity_df
    
    def detect_suspicious_programs(self, min_days: int = 30, max_active_users: int = 100) -> pd.DataFrame:
        """
        Detect potentially suspicious programs with low activity.
        
        Args:
            min_days: Minimum age of program in days
            max_active_users: Maximum number of active users for suspicious program
            
        Returns:
            DataFrame with suspicious program analysis
        """
        logger.info(f"Detecting suspicious programs")
        
        try:
            # Get programs list
            programs_data = self.get_programs_list(limit=500)
            programs = programs_data.get("data", [])
        except Exception as e:
            logger.warning(f"Failed to get programs list: {e}")
            return pd.DataFrame()
        
        # Analyze each program
        suspicious_programs = []
        
        for program in programs:
            program_id = program.get("program_id")
            if not program_id:
                continue
                
            # Get program details
            try:
                details = self.get_program_details(program_id)
                active_users = self.get_program_active_users(program_id, days=30, limit=max_active_users)
            except Exception as e:
                logger.warning(f"Failed to get details for program {program_id}: {e}")
                continue
            
            # Check if program meets suspicious criteria
            active_user_count = len(active_users.get("data", []))
            deployment_date = details.get("deployment_date")
            
            # Calculate program age in days
            program_age_days = 0
            if deployment_date:
                try:
                    deployment_dt = datetime.fromisoformat(deployment_date.replace("Z", "+00:00"))
                    program_age_days = (datetime.now() - deployment_dt).days
                except:
                    pass
            
            # Check if meets suspicious criteria
            if program_age_days >= min_days and active_user_count <= max_active_users:
                suspicious_programs.append({
                    "program_id": program_id,
                    "program_name": details.get("name", ""),
                    "deployment_date": deployment_date,
                    "program_age_days": program_age_days,
                    "active_users_30d": active_user_count,
                    "transaction_count_30d": details.get("transaction_count_30d", 0),
                    "instruction_count_30d": details.get("instruction_count_30d", 0),
                    "risk_score": (100 - min(active_user_count, 100)) * 0.5 + (100 - min(program_age_days, 365) / 3.65) * 0.5
                })
        
        # Convert to DataFrame
        if suspicious_programs:
            suspicious_df = pd.DataFrame(suspicious_programs)
            logger.info(f"Detected {len(suspicious_df)} suspicious programs")
            return suspicious_df
        else:
            logger.info("No suspicious programs detected")
            return pd.DataFrame()