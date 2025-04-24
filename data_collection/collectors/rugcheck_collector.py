"""
RugCheck API collector for SolanaGuard.
Provides methods to analyze tokens, detect insiders, and assess risk.
"""
import json
import time
import logging
import requests
import os
import pandas as pd
import networkx as nx
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from data_collection.config import RUGCHECK_JWT_TOKEN, RUGCHECK_API_URL, REQUEST_TIMEOUT, DATA_DIR, CACHE_DIR, RATE_LIMIT

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(DATA_DIR, "rugcheck_collector.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("rugcheck_collector")

class RugCheckCollector:
    """
    Collector class for interacting with the RugCheck API.
    Provides methods to analyze tokens, detect insiders, and assess risk.
    """
    
    def __init__(self, cache_enabled: bool = True):
        """
        Initialize the RugCheck collector.
        
        Args:
            cache_enabled: Whether to cache API responses to disk
        """
        self.api_url = RUGCHECK_API_URL
        self.jwt_token = RUGCHECK_JWT_TOKEN
        self.cache_enabled = cache_enabled
        self.cache_dir = os.path.join(CACHE_DIR, "rugcheck")
        self.rate_limit = RATE_LIMIT["rugcheck"]
        self.last_request_time = 0
        
        if self.cache_enabled:
            os.makedirs(self.cache_dir, exist_ok=True)
        
        logger.info("Initialized RugCheck collector")
    
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
        Make a request to the RugCheck API.
        
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
            "Authorization": f"Bearer {self.jwt_token}",
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
    
    def get_token_report(self, token_mint: str) -> Dict:
        """
        Get a full report for a token.
        
        Args:
            token_mint: The token mint address
            
        Returns:
            Token report data
        """
        logger.info(f"Getting token report for {token_mint}")
        endpoint = f"/tokens/{token_mint}/report"
        
        return self._make_api_request(endpoint)
    
    def get_token_report_summary(self, token_mint: str, cache_only: bool = False) -> Dict:
        """
        Get a summary report for a token.
        
        Args:
            token_mint: The token mint address
            cache_only: Only return cached reports
            
        Returns:
            Token report summary
        """
        logger.info(f"Getting token report summary for {token_mint}")
        endpoint = f"/tokens/{token_mint}/report/summary"
        params = {"cacheOnly": "true" if cache_only else "false"}
        
        return self._make_api_request(endpoint, params=params)
    
    def get_token_insider_graph(self, token_mint: str) -> Dict:
        """
        Get the insider graph for a token.
        
        Args:
            token_mint: The token mint address
            
        Returns:
            Token insider graph data
        """
        logger.info(f"Getting insider graph for {token_mint}")
        endpoint = f"/tokens/{token_mint}/insiders/graph"
        
        return self._make_api_request(endpoint)
    
    def get_token_lockers(self, token_mint: str) -> Dict:
        """
        Get information about token liquidity lockers.
        
        Args:
            token_mint: The token mint address
            
        Returns:
            Token locker information
        """
        logger.info(f"Getting lockers for {token_mint}")
        endpoint = f"/tokens/{token_mint}/lockers"
        
        return self._make_api_request(endpoint)
    
    def check_token_eligibility(self, token_mint: str) -> Dict:
        """
        Check if a token is eligible for verification.
        
        Args:
            token_mint: The token mint address
            
        Returns:
            Token eligibility information
        """
        logger.info(f"Checking eligibility for {token_mint}")
        endpoint = "/tokens/verify/eligible"
        data = {"mint": token_mint}
        
        return self._make_api_request(endpoint, method="POST", params=data)
    
    def get_token_votes(self, token_mint: str) -> Dict:
        """
        Get voting statistics for a token.
        
        Args:
            token_mint: The token mint address
            
        Returns:
            Token voting statistics
        """
        logger.info(f"Getting votes for {token_mint}")
        endpoint = f"/tokens/{token_mint}/votes"
        
        return self._make_api_request(endpoint)
    
    def get_trending_tokens(self) -> Dict:
        """
        Get most voted for tokens in the past 24 hours.
        
        Returns:
            Trending token information
        """
        logger.info("Getting trending tokens")
        endpoint = "/stats/trending"
        
        return self._make_api_request(endpoint)
    
    def get_recently_verified_tokens(self) -> Dict:
        """
        Get recently verified tokens.
        
        Returns:
            Recently verified token information
        """
        logger.info("Getting recently verified tokens")
        endpoint = "/stats/verified"
        
        return self._make_api_request(endpoint)
    
    def analyze_token_risk(self, token_mint: str) -> pd.DataFrame:
        """
        Perform comprehensive risk analysis for a token.
        
        Args:
            token_mint: The token mint address
            
        Returns:
            DataFrame with token risk analysis
        """
        logger.info(f"Analyzing token risk for {token_mint}")
        
        try:
            # Get full token report
            report = self.get_token_report(token_mint)
        except Exception as e:
            logger.warning(f"Failed to get token report for {token_mint}: {e}")
            
            # Try to get summary report
            try:
                report = self.get_token_report_summary(token_mint)
            except Exception as e:
                logger.error(f"Failed to get token report summary for {token_mint}: {e}")
                return pd.DataFrame()
        
        # Extract risk factors
        risk_factors = report.get("risks", [])
        
        if not risk_factors:
            logger.info(f"No risk factors found for {token_mint}")
            return pd.DataFrame()
        
        # Create DataFrame from risk factors
        risk_df = pd.DataFrame(risk_factors)
        
        # Add overall risk score
        risk_df["overall_score"] = report.get("score", 0)
        risk_df["normalized_score"] = report.get("score_normalised", 0)
        risk_df["token_mint"] = token_mint
        risk_df["token_symbol"] = report.get("tokenMeta", {}).get("symbol", "")
        risk_df["token_name"] = report.get("tokenMeta", {}).get("name", "")
        risk_df["is_rugged"] = report.get("rugged", False)
        
        logger.info(f"Analyzed {len(risk_factors)} risk factors for {token_mint}")
        return risk_df
    
    def analyze_token_insiders(self, token_mint: str) -> pd.DataFrame:
        """
        Analyze token insiders and their relationships.
        
        Args:
            token_mint: The token mint address
            
        Returns:
            DataFrame with token insider analysis
        """
        logger.info(f"Analyzing token insiders for {token_mint}")
        
        try:
            # Get insider graph
            insider_graph = self.get_token_insider_graph(token_mint)
        except Exception as e:
            logger.warning(f"Failed to get insider graph for {token_mint}: {e}")
            return pd.DataFrame()
        
        # Check if we received valid data
        if not insider_graph:
            logger.info(f"No insider graph data found for {token_mint}")
            return pd.DataFrame()
        
        # Get full token report for additional information
        try:
            report = self.get_token_report(token_mint)
        except Exception as e:
            logger.warning(f"Failed to get token report for {token_mint}: {e}")
            report = {}
        
        # Extract insider networks
        insider_networks = report.get("insiderNetworks", [])
        
        if not insider_networks:
            logger.info(f"No insider networks found for {token_mint}")
            
        # Create DataFrame from insider networks
        insider_df = pd.DataFrame(insider_networks) if insider_networks else pd.DataFrame()
        
        # Add token information
        if not insider_df.empty:
            insider_df["token_mint"] = token_mint
            insider_df["token_symbol"] = report.get("tokenMeta", {}).get("symbol", "")
            insider_df["token_name"] = report.get("tokenMeta", {}).get("name", "")
            insider_df["creator"] = report.get("creator", "")
            insider_df["total_insiders_detected"] = report.get("graphInsidersDetected", 0)
        
        logger.info(f"Analyzed {len(insider_networks)} insider networks for {token_mint}")
        return insider_df
    
    def analyze_liquidity_locks(self, token_mint: str) -> pd.DataFrame:
        """
        Analyze token liquidity locks.
        
        Args:
            token_mint: The token mint address
            
        Returns:
            DataFrame with liquidity lock analysis
        """
        logger.info(f"Analyzing liquidity locks for {token_mint}")
        
        try:
            # Get locker information
            lockers_data = self.get_token_lockers(token_mint)
        except Exception as e:
            logger.warning(f"Failed to get lockers for {token_mint}: {e}")
            return pd.DataFrame()
        
        # Extract locker information
        lockers = lockers_data.get("lockers", {})
        total_info = lockers_data.get("total", {})
        
        if not lockers:
            logger.info(f"No lockers found for {token_mint}")
            return pd.DataFrame()
        
        # Convert lockers dictionary to a list of records
        locker_records = []
        for locker_key, locker_data in lockers.items():
            locker_record = {
                "locker_key": locker_key,
                **locker_data,
                "token_mint": token_mint
            }
            locker_records.append(locker_record)
        
        # Create DataFrame from locker records
        lockers_df = pd.DataFrame(locker_records)
        
        # Add total information
        if not lockers_df.empty and total_info:
            lockers_df["total_locked_pct"] = total_info.get("pct", 0)
            lockers_df["total_locked_usdc"] = total_info.get("totalUSDC", 0)
        
        logger.info(f"Analyzed {len(locker_records)} lockers for {token_mint}")
        return lockers_df
    
    def analyze_token_creator_patterns(self, creator_address: str) -> pd.DataFrame:
        """
        Analyze token creation patterns for a specific creator address.
        
        Args:
            creator_address: The creator's address
            
        Returns:
            DataFrame with token creation pattern analysis
        """
        logger.info(f"Analyzing token creation patterns for {creator_address}")
        
        # Get a token report for a token created by this address
        # This requires first finding a token by this creator
        
        # In a real implementation, we'd have a way to search for tokens by creator
        # For now, we'll just return an empty DataFrame
        logger.warning(f"Token creator pattern analysis not implemented")
        return pd.DataFrame()
    
    def identify_suspicious_tokens(self, top_n: int = 10) -> pd.DataFrame:
        """
        Identify suspicious tokens based on risk scores.
        
        Args:
            top_n: Number of suspicious tokens to return
            
        Returns:
            DataFrame with suspicious token analysis
        """
        logger.info(f"Identifying top {top_n} suspicious tokens")
        
        try:
            # Get trending tokens
            trending = self.get_trending_tokens()
            trending_tokens = trending or []
        except Exception as e:
            logger.warning(f"Failed to get trending tokens: {e}")
            trending_tokens = []
        
        # Analyze each token for risk
        risk_analyses = []
        
        for token_info in trending_tokens[:top_n]:
            mint = token_info.get("mint")
            if not mint:
                continue
                
            try:
                risk_df = self.analyze_token_risk(mint)
                if not risk_df.empty:
                    risk_analyses.append(risk_df)
            except Exception as e:
                logger.warning(f"Failed to analyze token {mint}: {e}")
        
        # Combine all analyses
        if risk_analyses:
            combined_df = pd.concat(risk_analyses, ignore_index=True)
            logger.info(f"Identified {len(combined_df)} suspicious token risk factors")
            return combined_df
        else:
            logger.info("No suspicious tokens identified")
            return pd.DataFrame()
    
    def build_token_insider_network(self, token_mint: str) -> Optional[nx.Graph]:
        """
        Build a network graph of token insiders.
        
        Args:
            token_mint: The token mint address
            
        Returns:
            NetworkX graph object or None if data not available
        """
        logger.info(f"Building insider network for {token_mint}")
        
        try:
            # Get insider graph
            insider_graph = self.get_token_insider_graph(token_mint)
        except Exception as e:
            logger.warning(f"Failed to get insider graph for {token_mint}: {e}")
            return None
        
        # Check if we received valid data
        if not insider_graph:
            logger.info(f"No insider graph data found for {token_mint}")
            return None
        
        # Extract nodes and edges
        nodes = insider_graph.get("nodes", [])
        edges = insider_graph.get("edges", [])
        
        if not nodes or not edges:
            logger.info(f"No nodes or edges found in insider graph for {token_mint}")
            return None
        
        # Create graph
        G = nx.DiGraph()
        
        # Add nodes
        for node in nodes:
            node_id = node.get("id")
            if node_id:
                G.add_node(node_id, **node)
        
        # Add edges
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source and target:
                G.add_edge(source, target, **edge)
        
        logger.info(f"Built insider network with {len(nodes)} nodes and {len(edges)} edges for {token_mint}")
        return G