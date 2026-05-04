"""Advanced graph analytics service for knowledge graph analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict, deque
import structlog

log = structlog.get_logger()


class GraphAnalytics:
    """
    Advanced graph analytics for knowledge graph analysis.
    
    Provides community detection, centrality analysis, path finding,
    and subgraph extraction capabilities.
    """
    
    def __init__(self, graph_store=None):
        """
        Initialize graph analytics.
        
        Args:
            graph_store: Optional graph store instance
        """
        self.graph_store = graph_store
        log.info("graph_analytics_initialized")
    
    def detect_communities(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        algorithm: str = "louvain"
    ) -> Dict[str, Any]:
        """
        Detect communities in the graph using various algorithms.
        
        Args:
            nodes: List of graph nodes
            edges: List of graph edges
            algorithm: Algorithm to use (louvain, label_propagation, girvan_newman)
            
        Returns:
            Dictionary with communities and modularity score
        """
        try:
            import networkx as nx
            from networkx.algorithms import community
            
            # Build NetworkX graph
            G = nx.Graph()
            
            for node in nodes:
                G.add_node(node['id'], **node.get('properties', {}))
            
            for edge in edges:
                G.add_edge(
                    edge['source'],
                    edge['target'],
                    **edge.get('properties', {})
                )
            
            # Detect communities based on algorithm
            if algorithm == "louvain":
                communities_gen = community.louvain_communities(G)
                communities_list = [list(c) for c in communities_gen]
            elif algorithm == "label_propagation":
                communities_gen = community.label_propagation_communities(G)
                communities_list = [list(c) for c in communities_gen]
            elif algorithm == "girvan_newman":
                communities_gen = community.girvan_newman(G)
                # Get first level of communities
                communities_list = [list(c) for c in next(communities_gen)]
            else:
                raise ValueError(f"Unknown algorithm: {algorithm}")
            
            # Calculate modularity
            modularity = community.modularity(G, communities_list)
            
            # Format communities
            formatted_communities = []
            for i, comm in enumerate(communities_list):
                formatted_communities.append({
                    "id": f"community_{i}",
                    "size": len(comm),
                    "nodes": comm,
                    "label": f"Community {i+1}"
                })
            
            log.info(
                "communities_detected",
                algorithm=algorithm,
                num_communities=len(communities_list),
                modularity=modularity
            )
            
            return {
                "communities": formatted_communities,
                "num_communities": len(communities_list),
                "modularity": modularity,
                "algorithm": algorithm
            }
            
        except ImportError:
            log.error("networkx_not_installed", msg="Install with: pip install networkx")
            raise
        except Exception as e:
            log.error("community_detection_failed", error=str(e))
            raise
    
    def calculate_centrality(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        metrics: List[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate centrality metrics for graph nodes.
        
        Args:
            nodes: List of graph nodes
            edges: List of graph edges
            metrics: List of metrics to calculate (degree, betweenness, closeness, eigenvector, pagerank)
            
        Returns:
            Dictionary with centrality scores for each node
        """
        if metrics is None:
            metrics = ["degree", "betweenness", "pagerank"]
        
        try:
            import networkx as nx
            
            # Build NetworkX graph
            G = nx.Graph()
            
            for node in nodes:
                G.add_node(node['id'], **node.get('properties', {}))
            
            for edge in edges:
                G.add_edge(
                    edge['source'],
                    edge['target'],
                    **edge.get('properties', {})
                )
            
            results = {}
            
            # Calculate requested metrics
            if "degree" in metrics:
                degree_cent = nx.degree_centrality(G)
                results["degree"] = degree_cent
            
            if "betweenness" in metrics:
                betweenness_cent = nx.betweenness_centrality(G)
                results["betweenness"] = betweenness_cent
            
            if "closeness" in metrics:
                closeness_cent = nx.closeness_centrality(G)
                results["closeness"] = closeness_cent
            
            if "eigenvector" in metrics:
                try:
                    eigenvector_cent = nx.eigenvector_centrality(G, max_iter=1000)
                    results["eigenvector"] = eigenvector_cent
                except:
                    log.warning("eigenvector_centrality_failed", msg="Graph may not be connected")
            
            if "pagerank" in metrics:
                pagerank_cent = nx.pagerank(G)
                results["pagerank"] = pagerank_cent
            
            # Find top nodes for each metric
            top_nodes = {}
            for metric, scores in results.items():
                sorted_nodes = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                top_nodes[metric] = [
                    {"node_id": node_id, "score": score}
                    for node_id, score in sorted_nodes[:10]
                ]
            
            log.info(
                "centrality_calculated",
                metrics=metrics,
                num_nodes=len(nodes)
            )
            
            return {
                "centrality_scores": results,
                "top_nodes": top_nodes,
                "metrics": metrics,
                "num_nodes": len(nodes)
            }
            
        except ImportError:
            log.error("networkx_not_installed", msg="Install with: pip install networkx")
            raise
        except Exception as e:
            log.error("centrality_calculation_failed", error=str(e))
            raise
    
    def find_shortest_path(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        source_id: str,
        target_id: str,
        max_length: int = 10
    ) -> Dict[str, Any]:
        """
        Find shortest path between two nodes.
        
        Args:
            nodes: List of graph nodes
            edges: List of graph edges
            source_id: Source node ID
            target_id: Target node ID
            max_length: Maximum path length to search
            
        Returns:
            Dictionary with path information
        """
        try:
            import networkx as nx
            
            # Build NetworkX graph
            G = nx.Graph()
            
            for node in nodes:
                G.add_node(node['id'], **node.get('properties', {}))
            
            for edge in edges:
                G.add_edge(
                    edge['source'],
                    edge['target'],
                    **edge.get('properties', {})
                )
            
            # Check if nodes exist
            if source_id not in G:
                raise ValueError(f"Source node {source_id} not found in graph")
            if target_id not in G:
                raise ValueError(f"Target node {target_id} not found in graph")
            
            # Find shortest path
            try:
                path = nx.shortest_path(G, source_id, target_id)
                path_length = len(path) - 1
                
                # Get edges in path
                path_edges = []
                for i in range(len(path) - 1):
                    for edge in edges:
                        if (edge['source'] == path[i] and edge['target'] == path[i+1]) or \
                           (edge['source'] == path[i+1] and edge['target'] == path[i]):
                            path_edges.append(edge)
                            break
                
                log.info(
                    "shortest_path_found",
                    source=source_id,
                    target=target_id,
                    length=path_length
                )
                
                return {
                    "path": path,
                    "path_length": path_length,
                    "edges": path_edges,
                    "source": source_id,
                    "target": target_id,
                    "found": True
                }
                
            except nx.NetworkXNoPath:
                log.warning(
                    "no_path_found",
                    source=source_id,
                    target=target_id
                )
                return {
                    "path": [],
                    "path_length": 0,
                    "edges": [],
                    "source": source_id,
                    "target": target_id,
                    "found": False,
                    "message": "No path exists between nodes"
                }
            
        except ImportError:
            log.error("networkx_not_installed", msg="Install with: pip install networkx")
            raise
        except Exception as e:
            log.error("shortest_path_failed", error=str(e))
            raise
    
    def extract_subgraph(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        node_ids: List[str],
        depth: int = 1
    ) -> Dict[str, Any]:
        """
        Extract subgraph around specified nodes.
        
        Args:
            nodes: List of graph nodes
            edges: List of graph edges
            node_ids: List of node IDs to extract around
            depth: Depth of neighborhood to include
            
        Returns:
            Dictionary with subgraph nodes and edges
        """
        try:
            import networkx as nx
            
            # Build NetworkX graph
            G = nx.Graph()
            
            node_map = {node['id']: node for node in nodes}
            
            for node in nodes:
                G.add_node(node['id'], **node.get('properties', {}))
            
            for edge in edges:
                G.add_edge(
                    edge['source'],
                    edge['target'],
                    **edge.get('properties', {})
                )
            
            # Find all nodes within depth
            subgraph_nodes = set(node_ids)
            
            for node_id in node_ids:
                if node_id not in G:
                    log.warning("node_not_found", node_id=node_id)
                    continue
                
                # BFS to find neighbors at each depth
                visited = {node_id}
                queue = deque([(node_id, 0)])
                
                while queue:
                    current, current_depth = queue.popleft()
                    
                    if current_depth < depth:
                        for neighbor in G.neighbors(current):
                            if neighbor not in visited:
                                visited.add(neighbor)
                                subgraph_nodes.add(neighbor)
                                queue.append((neighbor, current_depth + 1))
            
            # Extract subgraph
            subgraph_nodes_list = [
                node_map[nid] for nid in subgraph_nodes if nid in node_map
            ]
            
            subgraph_edges = [
                edge for edge in edges
                if edge['source'] in subgraph_nodes and edge['target'] in subgraph_nodes
            ]
            
            log.info(
                "subgraph_extracted",
                seed_nodes=len(node_ids),
                depth=depth,
                result_nodes=len(subgraph_nodes_list),
                result_edges=len(subgraph_edges)
            )
            
            return {
                "nodes": subgraph_nodes_list,
                "edges": subgraph_edges,
                "seed_nodes": node_ids,
                "depth": depth,
                "stats": {
                    "num_nodes": len(subgraph_nodes_list),
                    "num_edges": len(subgraph_edges)
                }
            }
            
        except ImportError:
            log.error("networkx_not_installed", msg="Install with: pip install networkx")
            raise
        except Exception as e:
            log.error("subgraph_extraction_failed", error=str(e))
            raise
