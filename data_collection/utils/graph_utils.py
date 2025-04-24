"""
Graph utilities for transaction flow analysis.
"""
import networkx as nx
import json
from typing import Dict, List, Any, Optional, Tuple, Set

class TransactionFlowGraph:
    """
    Graph representation of transaction flows for analysis.
    """
    
    def __init__(self):
        """
        Initialize an empty directed graph.
        """
        self.graph = nx.DiGraph()
    
    def add_transaction(self, source: str, target: str, **kwargs):
        """
        Add a transaction edge to the graph.
        
        Args:
            source: Source address
            target: Target address
            **kwargs: Additional transaction attributes (amount, timestamp, etc.)
        """
        if not source or not target:
            return
        
        # Add nodes if they don't exist
        if source not in self.graph:
            self.graph.add_node(source)
        
        if target not in self.graph:
            self.graph.add_node(target)
        
        # Check if edge already exists
        if self.graph.has_edge(source, target):
            # Get existing transactions list or create empty list
            if "transactions" not in self.graph[source][target]:
                self.graph[source][target]["transactions"] = []
            
            # Add this transaction to the list
            self.graph[source][target]["transactions"].append(kwargs)
        else:
            # Create new edge with first transaction
            self.graph.add_edge(source, target, transactions=[kwargs])
    
    def get_nodes(self) -> List[str]:
        """
        Get all nodes in the graph.
        
        Returns:
            List of node identifiers
        """
        return list(self.graph.nodes())
    
    def get_edge_count(self) -> int:
        """
        Get the number of edges in the graph.
        
        Returns:
            Edge count
        """
        return len(self.graph.edges())
    
    def set_node_attribute(self, node: str, attr: str, value: Any):
        """
        Set an attribute for a node.
        
        Args:
            node: Node identifier
            attr: Attribute name
            value: Attribute value
        """
        if node in self.graph:
            self.graph.nodes[node][attr] = value
    
    def get_node_attribute(self, node: str, attr: str, default: Any = None) -> Any:
        """
        Get an attribute from a node.
        
        Args:
            node: Node identifier
            attr: Attribute name
            default: Default value if attribute doesn't exist
            
        Returns:
            Attribute value or default
        """
        if node in self.graph and attr in self.graph.nodes[node]:
            return self.graph.nodes[node][attr]
        return default
    
    def get_in_neighbors(self, node: str) -> List[str]:
        """
        Get all incoming neighbor nodes.
        
        Args:
            node: Target node
            
        Returns:
            List of nodes with edges pointing to the target node
        """
        return list(self.graph.predecessors(node)) if node in self.graph else []
    
    def get_out_neighbors(self, node: str) -> List[str]:
        """
        Get all outgoing neighbor nodes.
        
        Args:
            node: Source node
            
        Returns:
            List of nodes that the source node points to
        """
        return list(self.graph.successors(node)) if node in self.graph else []
    
    def get_edge_attributes(self, source: str, target: str) -> Dict:
        """
        Get all attributes for an edge.
        
        Args:
            source: Source node
            target: Target node
            
        Returns:
            Dictionary of edge attributes
        """
        if self.graph.has_edge(source, target):
            return self.graph[source][target]
        return {"transactions": []}
    
    def calculate_centrality(self) -> Dict[str, float]:
        """
        Calculate centrality metrics for nodes.
        
        Returns:
            Dictionary mapping nodes to their centrality scores
        """
        if len(self.graph) == 0:
            return {}
            
        try:
            # Calculate betweenness centrality
            betweenness = nx.betweenness_centrality(self.graph)
            
            # Calculate eigenvector centrality
            eigenvector = nx.eigenvector_centrality(self.graph, max_iter=1000, tol=1e-04)
            
            # Combine centrality measures (weighted average)
            combined = {}
            for node in self.graph.nodes():
                combined[node] = 0.5 * betweenness.get(node, 0) + 0.5 * eigenvector.get(node, 0)
                
            return combined
        except Exception:
            # Fall back to simpler degree centrality if the other methods fail
            return nx.degree_centrality(self.graph)
    
    def identify_communities(self) -> List[List[str]]:
        """
        Identify communities within the graph.
        
        Returns:
            List of communities (each community is a list of node identifiers)
        """
        if len(self.graph) == 0:
            return []
            
        try:
            # Convert directed graph to undirected for community detection
            undirected = self.graph.to_undirected()
            
            # Use Louvain algorithm for community detection
            from networkx.algorithms import community
            communities = community.louvain_communities(undirected)
            
            return [list(comm) for comm in communities]
        except Exception:
            # Fall back to connected components if community detection fails
            return [list(comp) for comp in nx.connected_components(self.graph.to_undirected())]
    
    def export_to_json(self) -> Dict:
        """
        Export the graph to a JSON-serializable dictionary.
        
        Returns:
            Dictionary with nodes and edges
        """
        nodes = []
        for node in self.graph.nodes(data=True):
            node_id = node[0]
            node_data = node[1].copy()
            node_data["id"] = node_id
            nodes.append(node_data)
        
        edges = []
        for edge in self.graph.edges(data=True):
            source, target = edge[0], edge[1]
            edge_data = edge[2].copy()
            edge_data["source"] = source
            edge_data["target"] = target
            
            # Process transactions to ensure they're JSON serializable
            if "transactions" in edge_data:
                processed_txs = []
                for tx in edge_data["transactions"]:
                    processed_tx = {}
                    for k, v in tx.items():
                        # Handle non-serializable types
                        if isinstance(v, (set, tuple)):
                            processed_tx[k] = list(v)
                        elif hasattr(v, 'tolist'):  # numpy arrays
                            processed_tx[k] = v.tolist()
                        else:
                            processed_tx[k] = v
                    processed_txs.append(processed_tx)
                edge_data["transactions"] = processed_txs
                
            edges.append(edge_data)
        
        return {
            "nodes": nodes,
            "edges": edges
        }
