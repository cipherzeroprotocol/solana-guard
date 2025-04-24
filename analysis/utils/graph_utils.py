"""
Utility functions for graph-based analysis of Solana transactions.
Provides methods for building transaction flow graphs and analyzing entity relationships.
"""
import logging
import networkx as nx
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class TransactionFlowGraph:
    """
    Class for building and analyzing transaction flow graphs.
    """
    
    def __init__(self):
        """
        Initialize the transaction flow graph.
        """
        # Initialize directed graph
        self.graph = nx.DiGraph()
        
        # Track node types
        self.node_types = {}
        
        # Track edge weights (transaction counts and volumes)
        self.edge_weights = {}
        
        logger.info("Initialized transaction flow graph")
    
    def add_token_transfers(self, token_transfers: pd.DataFrame):
        """
        Add token transfers to the graph.
        
        Args:
            token_transfers: DataFrame of token transfers
        """
        if token_transfers.empty:
            logger.warning("No token transfers to add to graph")
            return
        
        logger.info(f"Adding {len(token_transfers)} token transfers to graph")
        
        required_columns = ["token_account", "direction", "mint", "amount_change", "block_time"]
        missing_columns = [col for col in required_columns if col not in token_transfers.columns]
        
        if missing_columns:
            logger.warning(f"Token transfers missing required columns: {missing_columns}")
            return
        
        # Process each transfer
        for _, transfer in token_transfers.iterrows():
            # Determine source and target based on direction
            if transfer["direction"] == "sent":
                source = transfer.get("owner", transfer.get("address", "unknown"))
                target = transfer["token_account"]
                amount = transfer["amount_change"]
            elif transfer["direction"] == "received":
                source = transfer["token_account"]
                target = transfer.get("owner", transfer.get("address", "unknown"))
                amount = transfer["amount_change"]
            else:
                # Skip transfers with unknown direction
                continue
            
            # Add nodes if they don't exist
            if source not in self.graph:
                self.graph.add_node(source, type="address")
                self.node_types[source] = "address"
            
            if target not in self.graph:
                self.graph.add_node(target, type="address")
                self.node_types[target] = "address"
            
            # Add or update edge
            if self.graph.has_edge(source, target):
                # Update existing edge
                self.graph[source][target]["weight"] += 1
                self.graph[source][target]["volume"] += amount
                self.graph[source][target]["tokens"].add(transfer["mint"])
                self.graph[source][target]["last_time"] = max(
                    self.graph[source][target]["last_time"],
                    transfer["block_time"]
                )
            else:
                # Add new edge
                self.graph.add_edge(
                    source,
                    target,
                    weight=1,
                    volume=amount,
                    tokens={transfer["mint"]},
                    first_time=transfer["block_time"],
                    last_time=transfer["block_time"]
                )
        
        logger.info(f"Graph now has {len(self.graph.nodes)} nodes and {len(self.graph.edges)} edges")
    
    def add_labeled_entities(self, entities: List[Dict]):
        """
        Add labeled entities to the graph.
        
        Args:
            entities: List of entity dictionaries with address and label information
        """
        logger.info(f"Adding {len(entities)} labeled entities to graph")
        
        for entity in entities:
            address = entity.get("address")
            if not address:
                continue
            
            # Add node if it doesn't exist
            if address not in self.graph:
                self.graph.add_node(address, type="entity")
                self.node_types[address] = "entity"
            
            # Update node attributes
            for key, value in entity.items():
                if key != "address":
                    self.graph.nodes[address][key] = value
            
            # If entity has a label, set it
            if "labels" in entity:
                self.graph.nodes[address]["label"] = ", ".join(entity["labels"])
            elif "entity" in entity and "name" in entity["entity"]:
                self.graph.nodes[address]["label"] = entity["entity"]["name"]
        
        logger.info(f"Added entity labels to graph")
    
    def find_paths(
        self, 
        source: str, 
        target: Optional[str] = None,
        max_length: int = 5
    ) -> List[List[str]]:
        """
        Find paths between source and target nodes.
        
        Args:
            source: Source node address
            target: Target node address (if None, find paths to all nodes)
            max_length: Maximum path length
            
        Returns:
            List of paths as lists of node addresses
        """
        if source not in self.graph:
            logger.warning(f"Source node {source} not in graph")
            return []
        
        if target and target not in self.graph:
            logger.warning(f"Target node {target} not in graph")
            return []
        
        logger.info(f"Finding paths from {source}" + (f" to {target}" if target else ""))
        
        paths = []
        
        if target:
            # Find paths between specific source and target
            for path in nx.all_simple_paths(self.graph, source, target, cutoff=max_length):
                paths.append(path)
        else:
            # Find paths from source to all other nodes
            for node in self.graph.nodes:
                if node == source:
                    continue
                    
                try:
                    for path in nx.all_simple_paths(self.graph, source, node, cutoff=max_length):
                        paths.append(path)
                except nx.NetworkXNoPath:
                    continue
        
        logger.info(f"Found {len(paths)} paths")
        return paths
    
    def find_cycles(self, max_length: int = 5) -> List[List[str]]:
        """
        Find cycles in the transaction graph.
        
        Args:
            max_length: Maximum cycle length
            
        Returns:
            List of cycles as lists of node addresses
        """
        logger.info(f"Finding cycles with max length {max_length}")
        
        cycles = []
        
        # Find simple cycles
        for cycle in nx.simple_cycles(self.graph):
            if len(cycle) <= max_length:
                cycles.append(cycle)
        
        logger.info(f"Found {len(cycles)} cycles")
        return cycles
    
    def identify_communities(self) -> Dict[str, List[str]]:
        """
        Identify communities in the transaction graph.
        
        Returns:
            Dictionary with community IDs as keys and lists of node addresses as values
        """
        logger.info("Identifying communities in graph")
        
        # Use Louvain method for community detection
        try:
            import community as community_louvain
            
            # Convert directed graph to undirected for community detection
            undirected_graph = self.graph.to_undirected()
            
            # Detect communities
            communities = community_louvain.best_partition(undirected_graph)
            
            # Organize nodes by community
            community_nodes = {}
            for node, community_id in communities.items():
                community_id_str = str(community_id)
                if community_id_str not in community_nodes:
                    community_nodes[community_id_str] = []
                community_nodes[community_id_str].append(node)
            
            logger.info(f"Identified {len(community_nodes)} communities")
            return community_nodes
            
        except ImportError:
            logger.warning("Community detection requires the python-louvain package. "
                           "Please install it using 'pip install python-louvain' and try again.")
            
            # Fallback to connected components
            communities = {}
            for i, component in enumerate(nx.weakly_connected_components(self.graph)):
                communities[str(i)] = list(component)
            
            logger.info(f"Identified {len(communities)} connected components")
            return communities
    
    def calculate_centrality(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate centrality metrics for nodes in the graph.
        
        Returns:
            Dictionary with node addresses as keys and centrality metrics as values
        """
        logger.info("Calculating centrality metrics")
        
        centrality = {}
        
        # Calculate various centrality metrics
        degree_centrality = nx.degree_centrality(self.graph)
        in_degree_centrality = nx.in_degree_centrality(self.graph)
        out_degree_centrality = nx.out_degree_centrality(self.graph)
        
        try:
            betweenness_centrality = nx.betweenness_centrality(self.graph)
        except:
            logger.warning("Failed to calculate betweenness centrality")
            betweenness_centrality = {node: 0 for node in self.graph.nodes}
        
        try:
            pagerank = nx.pagerank(self.graph)
        except:
            logger.warning("Failed to calculate pagerank")
            pagerank = {node: 0 for node in self.graph.nodes}
        
        # Combine metrics
        for node in self.graph.nodes:
            centrality[node] = {
                "degree": degree_centrality.get(node, 0),
                "in_degree": in_degree_centrality.get(node, 0),
                "out_degree": out_degree_centrality.get(node, 0),
                "betweenness": betweenness_centrality.get(node, 0),
                "pagerank": pagerank.get(node, 0)
            }
        
        logger.info(f"Calculated centrality metrics for {len(centrality)} nodes")
        return centrality
    
    def detect_suspicious_patterns(self) -> List[Dict]:
        """
        Detect suspicious patterns in the transaction graph.
        
        Returns:
            List of suspicious patterns detected
        """
        logger.info("Detecting suspicious patterns in graph")
        
        suspicious_patterns = []
        
        # Detect cycles (potential wash trading or layering)
        cycles = self.find_cycles(max_length=5)
        if cycles:
            suspicious_patterns.append({
                "type": "cycles",
                "description": "Cyclic transaction flows detected",
                "count": len(cycles),
                "examples": cycles[:5],
                "risk_score": min(100, len(cycles) * 10)
            })
        
        # Detect hub-and-spoke patterns (potential splitting/combining)
        high_degree_nodes = []
        for node, degree in self.graph.degree:
            if degree > 10:
                high_degree_nodes.append((node, degree))
        
        if high_degree_nodes:
            suspicious_patterns.append({
                "type": "hub_and_spoke",
                "description": "Hub-and-spoke transaction patterns detected",
                "count": len(high_degree_nodes),
                "examples": high_degree_nodes[:5],
                "risk_score": min(100, max(degree for _, degree in high_degree_nodes) * 2)
            })
        
        # Detect fan-out patterns (one sender, many recipients)
        fan_out_nodes = []
        for node in self.graph.nodes:
            in_degree = self.graph.in_degree(node)
            out_degree = self.graph.out_degree(node)
            
            if in_degree <= 2 and out_degree >= 10:
                fan_out_nodes.append((node, out_degree))
        
        if fan_out_nodes:
            suspicious_patterns.append({
                "type": "fan_out",
                "description": "Fan-out transaction patterns detected",
                "count": len(fan_out_nodes),
                "examples": fan_out_nodes[:5],
                "risk_score": min(100, max(out_degree for _, out_degree in fan_out_nodes) * 2)
            })
        
        # Detect fan-in patterns (many senders, one recipient)
        fan_in_nodes = []
        for node in self.graph.nodes:
            in_degree = self.graph.in_degree(node)
            out_degree = self.graph.out_degree(node)
            
            if in_degree >= 10 and out_degree <= 2:
                fan_in_nodes.append((node, in_degree))
        
        if fan_in_nodes:
            suspicious_patterns.append({
                "type": "fan_in",
                "description": "Fan-in transaction patterns detected",
                "count": len(fan_in_nodes),
                "examples": fan_in_nodes[:5],
                "risk_score": min(100, max(in_degree for _, in_degree in fan_in_nodes) * 2)
            })
        
        logger.info(f"Detected {len(suspicious_patterns)} suspicious patterns")
        return suspicious_patterns
    
    def export_to_networkx(self) -> nx.DiGraph:
        """
        Export the graph to a NetworkX DiGraph.
        
        Returns:
            NetworkX DiGraph object
        """
        return self.graph
    
    def export_to_json(self) -> Dict:
        """
        Export the graph to a JSON-serializable format.
        
        Returns:
            Dictionary with nodes and edges
        """
        nodes = []
        for node, attrs in self.graph.nodes(data=True):
            node_data = {"id": node}
            node_data.update(attrs)
            nodes.append(node_data)
        
        edges = []
        for source, target, attrs in self.graph.edges(data=True):
            edge_data = {
                "source": source,
                "target": target
            }
            
            # Convert set to list for JSON serialization
            if "tokens" in attrs and isinstance(attrs["tokens"], set):
                attrs = attrs.copy()
                attrs["tokens"] = list(attrs["tokens"])
                
            edge_data.update(attrs)
            edges.append(edge_data)
        
        return {
            "nodes": nodes,
            "edges": edges
        }

def build_money_laundering_graph(money_laundering_routes: pd.DataFrame) -> TransactionFlowGraph:
    """
    Build a transaction flow graph from money laundering routes.
    
    Args:
        money_laundering_routes: DataFrame with money laundering routes
        
    Returns:
        TransactionFlowGraph object
    """
    logger.info("Building money laundering graph")
    
    if money_laundering_routes.empty:
        logger.warning("No money laundering routes provided")
        return TransactionFlowGraph()
    
    graph = TransactionFlowGraph()
    
    # Required columns
    required_columns = ["source_address", "target_address", "transaction_hash", "flow_type"]
    missing_columns = [col for col in required_columns if col not in money_laundering_routes.columns]
    
    if missing_columns:
        logger.warning(f"Money laundering routes missing required columns: {missing_columns}")
        return graph
    
    # Process each route
    for _, route in money_laundering_routes.iterrows():
        source = route["source_address"]
        target = route["target_address"]
        
        # Add nodes if they don't exist
        if source not in graph.graph:
            graph.graph.add_node(
                source, 
                type="address",
                is_source=True
            )
            graph.node_types[source] = "address"
        
        if target not in graph.graph:
            graph.graph.add_node(
                target, 
                type="address",
                flow_type=route["flow_type"],
                risk_score=route.get("risk_score", 0)
            )
            graph.node_types[target] = "address"
        
        # Add edge
        graph.graph.add_edge(
            source,
            target,
            transaction_hash=route["transaction_hash"],
            flow_type=route["flow_type"],
            amount_usd=route.get("amount_usd", 0),
            risk_score=route.get("risk_score", 0)
        )
    
    logger.info(f"Built money laundering graph with {len(graph.graph.nodes)} nodes and {len(graph.graph.edges)} edges")
    return graph

def build_token_insider_graph(insider_data: Dict) -> TransactionFlowGraph:
    """
    Build a transaction flow graph from token insider data.
    
    Args:
        insider_data: Dictionary with insider graph data
        
    Returns:
        TransactionFlowGraph object
    """
    logger.info("Building token insider graph")
    
    graph = TransactionFlowGraph()
    
    # Check if we have nodes and edges
    nodes = insider_data.get("nodes", [])
    edges = insider_data.get("edges", [])
    
    if not nodes or not edges:
        logger.warning("No nodes or edges in insider data")
        return graph
    
    # Process nodes
    for node_data in nodes:
        node_id = node_data.get("id")
        if not node_id:
            continue
            
        # Add node with all attributes
        attrs = {k: v for k, v in node_data.items() if k != "id"}
        graph.graph.add_node(node_id, **attrs)
        graph.node_types[node_id] = node_data.get("type", "unknown")
    
    # Process edges
    for edge_data in edges:
        source = edge_data.get("source")
        target = edge_data.get("target")
        
        if not source or not target:
            continue
            
        # Add edge with all attributes
        attrs = {k: v for k, v in edge_data.items() if k not in ["source", "target"]}
        graph.graph.add_edge(source, target, **attrs)
    
    logger.info(f"Built token insider graph with {len(graph.graph.nodes)} nodes and {len(graph.graph.edges)} edges")
    return graph

def analyze_exfiltration_routes(flow_graph: TransactionFlowGraph, source_address: str) -> List[Dict]:
    """
    Analyze potential fund exfiltration routes from a source address.
    
    Args:
        flow_graph: TransactionFlowGraph object
        source_address: Source address to analyze
        
    Returns:
        List of exfiltration routes
    """
    logger.info(f"Analyzing exfiltration routes from {source_address}")
    
    exfiltration_routes = []
    
    if source_address not in flow_graph.graph:
        logger.warning(f"Source address {source_address} not in graph")
        return exfiltration_routes
    
    # Find all paths from source address
    paths = []
    for target in flow_graph.graph.nodes:
        if target == source_address:
            continue
            
        # Look for paths to high-risk nodes
        node_attrs = flow_graph.graph.nodes[target]
        is_high_risk = (
            node_attrs.get("risk_score", 0) >= 75 or
            (node_attrs.get("flow_type") in ["mixer", "cross_chain_bridge", "exchange_withdrawal"])
        )
        
        if not is_high_risk:
            continue
            
        try:
            # Find paths
            for path in nx.all_simple_paths(flow_graph.graph, source_address, target, cutoff=5):
                paths.append(path)
        except nx.NetworkXNoPath:
            continue
    
    # Analyze each path
    for path in paths:
        # Skip paths with only source and target
        if len(path) <= 2:
            continue
            
        target = path[-1]
        
        # Calculate path risk and metadata
        path_transactions = []
        path_volume = 0
        path_risk = 0
        
        for i in range(len(path) - 1):
            source = path[i]
            dest = path[i + 1]
            
            # Get edge attributes
            edge_attrs = flow_graph.graph.get_edge_data(source, dest)
            
            path_transactions.append({
                "source": source,
                "target": dest,
                "transaction_hash": edge_attrs.get("transaction_hash", ""),
                "flow_type": edge_attrs.get("flow_type", "unknown"),
                "amount_usd": edge_attrs.get("amount_usd", 0),
                "risk_score": edge_attrs.get("risk_score", 0)
            })
            
            path_volume += edge_attrs.get("amount_usd", 0)
            path_risk = max(path_risk, edge_attrs.get("risk_score", 0))
        
        # Get target metadata
        target_attrs = flow_graph.graph.nodes[target]
        
        # Create route record
        exfiltration_routes.append({
            "source_address": source_address,
            "target_address": target,
            "path_length": len(path),
            "intermediate_addresses": path[1:-1],
            "path_transactions": path_transactions,
            "total_volume_usd": path_volume,
            "risk_score": path_risk,
            "target_type": target_attrs.get("flow_type", "unknown"),
            "target_risk_score": target_attrs.get("risk_score", 0)
        })
    
    # Sort routes by risk score
    exfiltration_routes.sort(key=lambda x: x["risk_score"], reverse=True)
    
    logger.info(f"Identified {len(exfiltration_routes)} potential exfiltration routes")
    return exfiltration_routes