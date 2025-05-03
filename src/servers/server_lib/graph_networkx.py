"""
Supply Network Graph NetworkX Adapter

This module provides functionality to load supply network data from a JSON
file into NetworkX for analysis and visualization.
"""

import json
import networkx as nx
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np


class NetworkXGraph:
    """Class to load and analyze supply chain network data with NetworkX."""
    
    def __init__(self, json_path: Optional[str] = None):
        """Initialize with path to supply_network.json file."""
        if json_path is None:
            this_dir = Path(__file__).parent.parent  # project/src/servers
            json_path = this_dir / 'supply_network.json'
        self.json_path = Path(json_path)
        
        # Default colors for supply chain relationship types
        self.edge_colors = {
            'partnership': 'blue',
            'contract': 'green',
            'order': 'orange',
            'shipment': 'purple',
            'certify': 'red'
        }
    
    def load_graph(self, directed: bool = True) -> nx.Graph:
        """
        Load supply chain data from JSON into a NetworkX graph.
        
        Args:
            directed: If True, creates a directed graph, otherwise undirected
            
        Returns:
            NetworkX graph object with loaded data
        """
        # Create directed or undirected graph
        if directed:
            G = nx.DiGraph()
        else:
            G = nx.Graph()
        
        # Read JSON file
        data = json.loads(self.json_path.read_text())
        # Add nodes
        for node in data.get('nodes', []):
            G.add_node(
                node['id'],
                name=node.get('name'),
                industry=node.get('industry'),
                region=node.get('region'),
                segments=node.get('segments', []),
                network_joined=node.get('network_joined')
            )
        
        # Add edges
        for rel in data.get('edges', []):
            G.add_edge(
                rel['source'],
                rel['target'],
                type=rel.get('type'),
                description=rel.get('description'),
                created=rel.get('created'),
                strength=rel.get('strength')
            )
        
        # Save and return
        self.graph = G
        return G
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """Calculate various statistics about the graph."""
        if not hasattr(self, 'graph'):
            raise ValueError("Graph not loaded. Call load_graph() first.")
            
        G = self.graph
        is_directed = G.is_directed()
        
        stats = {
            'node_count': G.number_of_nodes(),
            'edge_count': G.number_of_edges(),
            'is_directed': is_directed,
            'is_connected': nx.is_strongly_connected(G) if is_directed else nx.is_connected(G),
            'average_clustering': nx.average_clustering(G),
            'density': nx.density(G),
        }
        
        # Calculate degree statistics
        if is_directed:
            in_degrees = dict(G.in_degree())
            out_degrees = dict(G.out_degree())
            stats['avg_in_degree'] = sum(in_degrees.values()) / len(in_degrees)
            stats['avg_out_degree'] = sum(out_degrees.values()) / len(out_degrees)
            stats['max_in_degree'] = max(in_degrees.values()) if in_degrees else 0
            stats['max_out_degree'] = max(out_degrees.values()) if out_degrees else 0
        else:
            degrees = dict(G.degree())
            stats['avg_degree'] = sum(degrees.values()) / len(degrees)
            stats['max_degree'] = max(degrees.values()) if degrees else 0
        
        # Count relationships by type
        rel_types = {}
        for _, _, data in G.edges(data=True):
            rel_type = data.get('type', 'unknown')
            rel_types[rel_type] = rel_types.get(rel_type, 0) + 1
            
        stats['relationship_types'] = rel_types
        
        # Compute additional metrics if graph is not too large
        if G.number_of_nodes() <= 1000:  # Avoid computation for large graphs
            try:
                stats['diameter'] = nx.diameter(G) if not is_directed and nx.is_connected(G) else 'N/A'
            except nx.NetworkXError:
                stats['diameter'] = 'N/A (disconnected graph)'
                
            try:
                # Average shortest path length
                if is_directed:
                    stats['avg_path_length'] = nx.average_shortest_path_length(G)
                else:
                    # For undirected graphs with disconnected components
                    if nx.is_connected(G):
                        stats['avg_path_length'] = nx.average_shortest_path_length(G)
                    else:
                        stats['avg_path_length'] = 'N/A (disconnected graph)'
            except (nx.NetworkXError, nx.NetworkXNoPath):
                stats['avg_path_length'] = 'N/A (no path)'
        
        return stats
    
    def get_communities(self) -> Dict[str, List]:
        """
        Detect communities in the graph using the Louvain method.
        
        Returns:
            Dictionary mapping community IDs to lists of node IDs
        """
        if not hasattr(self, 'graph'):
            raise ValueError("Graph not loaded. Call load_graph() first.")
            
        # Use community detection algorithm (Louvain method)
        try:
            import community as community_louvain
            
            # For directed graphs, convert to undirected for community detection
            G_undirected = self.graph.to_undirected() if self.graph.is_directed() else self.graph
            
            # Compute the partition
            partition = community_louvain.best_partition(G_undirected)
            
            # Restructure to community -> nodes format
            communities = {}
            for node, community_id in partition.items():
                if community_id not in communities:
                    communities[community_id] = []
                communities[community_id].append(node)
            
            return communities
        except ImportError:
            # Fallback to connected components if community-detection package not available
            print("Warning: python-louvain package not found, using connected components instead.")
            if self.graph.is_directed():
                components = list(nx.weakly_connected_components(self.graph))
            else:
                components = list(nx.connected_components(self.graph))
                
            return {i: list(component) for i, component in enumerate(components)}
    
    def get_central_nodes(self, measure: str = 'degree', top_n: int = 10) -> List[Tuple[int, float]]:
        """
        Get the most central nodes according to various centrality measures.
        
        Args:
            measure: Centrality measure ('degree', 'betweenness', 'eigenvector', 'closeness', 'pagerank')
            top_n: Number of top nodes to return
            
        Returns:
            List of (node_id, centrality_score) tuples
        """
        if not hasattr(self, 'graph'):
            raise ValueError("Graph not loaded. Call load_graph() first.")
            
        G = self.graph
        
        # Calculate centrality based on the specified measure
        if measure == 'degree':
            if G.is_directed():
                centrality = nx.in_degree_centrality(G)  # Use in-degree for directed graphs
            else:
                centrality = nx.degree_centrality(G)
        elif measure == 'betweenness':
            centrality = nx.betweenness_centrality(G)
        elif measure == 'eigenvector':
            centrality = nx.eigenvector_centrality_numpy(G)
        elif measure == 'closeness':
            centrality = nx.closeness_centrality(G)
        elif measure == 'pagerank':
            centrality = nx.pagerank(G)
        else:
            raise ValueError(f"Unknown centrality measure: {measure}")
            
        # Sort nodes by centrality (descending)
        sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        
        # Return top N nodes
        return sorted_nodes[:top_n]
    
    def visualize(self, 
                  layout: str = 'spring', 
                  node_size_attr: Optional[str] = None,
                  color_by: str = 'community', 
                  edge_width_attr: str = 'strength',
                  show_labels: bool = False,
                  figsize: Tuple[int, int] = (12, 10)):
        """
        Visualize the graph using matplotlib.
        
        Args:
            layout: Graph layout algorithm ('spring', 'kamada_kawai', 'spectral', 'circular')
            node_size_attr: Node attribute to determine node size (None for uniform size)
            color_by: How to color nodes ('community', 'location', 'interest' or None)
            edge_width_attr: Edge attribute to determine line width ('strength' or None)
            show_labels: Whether to show node labels
            figsize: Figure size as (width, height) tuple
        """
        if not hasattr(self, 'graph'):
            raise ValueError("Graph not loaded. Call load_graph() first.")
        
        G = self.graph
        
        # Create figure
        plt.figure(figsize=figsize)
        
        # Determine layout
        if layout == 'spring':
            pos = nx.spring_layout(G, seed=42)
        elif layout == 'kamada_kawai':
            pos = nx.kamada_kawai_layout(G)
        elif layout == 'spectral':
            pos = nx.spectral_layout(G)
        elif layout == 'circular':
            pos = nx.circular_layout(G)
        else:
            pos = nx.spring_layout(G, seed=42)  # Default to spring layout
            
        # Node colors
        node_colors = []
        
        if color_by == 'community':
            try:
                # Try to get communities
                communities = self.get_communities()
                # Create a color map for nodes based on their community
                node_to_community = {}
                for comm_id, nodes in communities.items():
                    for node in nodes:
                        node_to_community[node] = comm_id
                
                # Generate enough distinct colors
                cmap = plt.cm.rainbow
                comm_ids = sorted(communities.keys())
                norm = mcolors.Normalize(vmin=min(comm_ids), vmax=max(comm_ids))
                
                for node in G.nodes():
                    comm = node_to_community.get(node, 0)
                    node_colors.append(cmap(norm(comm)))
            except:
                # Fallback to default
                node_colors = 'skyblue'
        
        elif color_by == 'location':
            # Color by location
            locations = {data['location'] for _, data in G.nodes(data=True)}
            location_to_color = {loc: plt.cm.tab20(i/len(locations)) 
                               for i, loc in enumerate(locations)}
            
            node_colors = [location_to_color.get(G.nodes[node].get('location'), 'gray') 
                         for node in G.nodes()]
                         
        elif color_by == 'interest':
            # Try to color by primary interest (first in list)
            primary_interests = {}
            for node, data in G.nodes(data=True):
                if 'interests' in data and data['interests']:
                    primary_interests[node] = data['interests'][0]
                    
            interest_types = set(primary_interests.values())
            interest_to_color = {interest: plt.cm.tab20(i/len(interest_types)) 
                               for i, interest in enumerate(interest_types)}
                               
            node_colors = [interest_to_color.get(primary_interests.get(node), 'gray') 
                         for node in G.nodes()]
        else:
            # Default color
            node_colors = 'skyblue'
        
        # Node sizes
        if node_size_attr:
            # Use specified attribute to determine size
            node_sizes = []
            for node in G.nodes():
                try:
                    size = G.nodes[node].get(node_size_attr, 300)
                    # Scale size appropriately if it's not in a reasonable range
                    if not 100 <= size <= 1000:
                        size = 100 + (size * 20)
                    node_sizes.append(size)
                except:
                    node_sizes.append(300)  # Default size
        else:
            # Use degree for size if no attribute specified
            node_sizes = [300 + 20 * G.degree(node) for node in G.nodes()]

        # Edge widths
        if edge_width_attr and edge_width_attr in [data.keys() for _, _, data in G.edges(data=True)][0]:
            edge_widths = [data.get(edge_width_attr, 1.0) for _, _, data in G.edges(data=True)]
            # Scale to reasonable values
            if edge_widths:
                min_width = min(edge_widths)
                max_width = max(edge_widths)
                if min_width == max_width:
                    edge_widths = [1.0] * len(edge_widths)
                else:
                    edge_widths = [1.0 + 3.0 * (w - min_width) / (max_width - min_width) 
                                 for w in edge_widths]
        else:
            edge_widths = 1.0

        # Edge colors
        edge_colors = [self.edge_colors.get(data.get('type', 'unknown'), 'gray') 
                     for _, _, data in G.edges(data=True)]
        
        # Draw nodes
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes, alpha=0.8)
        
        # Draw edges
        nx.draw_networkx_edges(G, pos, width=edge_widths, edge_color=edge_colors, alpha=0.6,
                             arrowsize=10 if G.is_directed() else 0)
        
        # Draw labels if requested
        if show_labels:
            labels = {node: G.nodes[node].get('username', str(node)) for node in G.nodes()}
            nx.draw_networkx_labels(G, pos, labels=labels, font_size=8, font_weight='bold')
        
        # Setup figure
        plt.title("Supply Network Graph Visualization", fontsize=16)
        plt.axis('off')
        plt.tight_layout()
        
        return plt
    
    def get_subgraph_by_relationship(self, rel_type: str) -> nx.Graph:
        """
        Extract a subgraph containing only edges of a specific relationship type.
        
        Args:
            rel_type: Relationship type to filter by
            
        Returns:
            Subgraph containing only the specified relationship type
        """
        if not hasattr(self, 'graph'):
            raise ValueError("Graph not loaded. Call load_graph() first.")
            
        # Create a new graph of the same type (directed or undirected)
        subgraph = self.graph.__class__()
        
        # Add all nodes to maintain node numbering
        for node, data in self.graph.nodes(data=True):
            subgraph.add_node(node, **data)
        
        # Add only edges of the specified type
        for source, target, data in self.graph.edges(data=True):
            if data.get('type') == rel_type:
                subgraph.add_edge(source, target, **data)
        
        return subgraph
    
    def get_attribute_distribution(self, attribute: str, is_edge_attr: bool = False) -> Dict:
        """
        Calculate distribution of a node or edge attribute.
        
        Args:
            attribute: Name of the attribute to analyze
            is_edge_attr: True if it's an edge attribute, False if node attribute
            
        Returns:
            Dictionary with attribute values as keys and counts as values
        """
        if not hasattr(self, 'graph'):
            raise ValueError("Graph not loaded. Call load_graph() first.")
            
        distribution = {}
        
        if is_edge_attr:
            # Edge attribute
            for _, _, data in self.graph.edges(data=True):
                if attribute in data:
                    value = data[attribute]
                    # Handle special types
                    if isinstance(value, list):
                        value = tuple(value)  # Make hashable if it's a list
                    elif isinstance(value, dict):
                        value = 'dict'  # Just count it as 'dict'
                        
                    distribution[value] = distribution.get(value, 0) + 1
        else:
            # Node attribute
            for _, data in self.graph.nodes(data=True):
                if attribute in data:
                    value = data[attribute]
                    # Handle special types
                    if isinstance(value, list):
                        for item in value:  # Count each interest separately
                            distribution[item] = distribution.get(item, 0) + 1
                    else:
                        distribution[value] = distribution.get(value, 0) + 1
                        
        return distribution


# Example usage
if __name__ == "__main__":
    # Load graph into NetworkX
    nx_graph = NetworkXGraph()
    G = nx_graph.load_graph(directed=True)
    
    # Print basic statistics
    stats = nx_graph.get_graph_stats()
    print(f"Graph has {stats['node_count']} nodes and {stats['edge_count']} edges")
    print(f"Graph density: {stats['density']:.4f}")
    print("Relationship counts:")
    for rel_type, count in stats['relationship_types'].items():
        print(f"  - {rel_type}: {count}")
    
    # Find communities and central nodes
    communities = nx_graph.get_communities()
    print(f"Found {len(communities)} communities")
    print(f"Largest community has {max(len(nodes) for nodes in communities.values())} nodes")
    
    central_nodes = nx_graph.get_central_nodes(measure='pagerank', top_n=5)
    print("Top 5 central nodes by PageRank:")
    for node_id, score in central_nodes:
        print(f"  - Node {node_id}: {score:.4f}")
    
    # Visualize the graph
    plt = nx_graph.visualize(layout='spring', color_by='community', 
                           show_labels=True, figsize=(12, 10))
    plt.savefig("supply_network_graph.png")
    plt.close()
    
    print("Graph visualization saved as 'supply_network_graph.png'")