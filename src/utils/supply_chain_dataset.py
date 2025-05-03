"""
SupplySphere Synthetic Supply Chain Generator

This module simulates a realistic supply chain network for a fictional global platform called
SupplySphere. It models manufacturers, suppliers, distributors, and partners in a directed
graph stored in SQLite.

Each node is a company, and each edge represents a business relationship such as contracts,
shipments, partnerships, certifications, or orders. The network structure and relationship
strengths are generated to reflect industry-standard dynamics and regional clustering.

This dataset is ideal for testing supply chain visibility tools, disruption simulations,
and logistics optimization algorithms.
"""
import networkx as nx
import random
import json
from datetime import datetime, timedelta
from typing import List, Dict

INDUSTRIES = [
    "Automotive", "Electronics", "Food", "Fashion", "Pharmaceuticals",
    "Machinery", "Aerospace", "Energy", "Retail", "Logistics"
]

REGIONS = [
    "New York", "Tokyo", "Berlin", "Shanghai", "São Paulo",
    "London", "Paris", "Mumbai", "Toronto", "Los Angeles"
]

RELATIONSHIP_TYPES = {
    "contract": {
        "bidirectional": True,
        "strength_range": (5, 10),
        "description": "Legally binding agreement between companies"
    },
    "shipment": {
        "bidirectional": False,
        "strength_range": (1, 7),
        "description": "One-way delivery of goods"
    },
    "order": {
        "bidirectional": False,
        "strength_range": (1, 6),
        "description": "Order placed by a company to a supplier"
    },
    "partnership": {
        "bidirectional": True,
        "strength_range": (3, 9),
        "description": "Strategic partnership"
    },
    "certify": {
        "bidirectional": False,
        "strength_range": (1, 5),
        "description": "Certification or endorsement"
    }
}

def random_join_date() -> str:
    start_date = datetime(2015, 1, 1)
    end_date = datetime(2024, 12, 31)
    delta = end_date - start_date
    random_days = random.randint(0, delta.days)
    return (start_date + timedelta(days=random_days)).strftime("%Y-%m-%d")

def generate_supply_chain_network(company_count: int = 100, edge_density: float = 0.05) -> nx.DiGraph:
    G = nx.DiGraph()
    
    # Step 1: Create Companies (nodes)
    companies = []
    for i in range(company_count):
        company_id = f"Company_{i:03d}"
        industry = random.choice(INDUSTRIES)
        region = random.choice(REGIONS)
        segments = random.sample([s for s in INDUSTRIES if s != industry], k=random.randint(1, 3))
        join_date = random_join_date()

        G.add_node(company_id, 
                   name=company_id, 
                   industry=industry, 
                   region=region,
                   segments=segments,
                   network_joined=join_date)
        companies.append(company_id)
    
    # Step 2: Create Relationships (edges)
    max_possible_edges = company_count * (company_count - 1)
    target_edge_count = int(max_possible_edges * edge_density)
    edges_created = 0
    attempts = 0
    max_attempts = target_edge_count * 3

    while edges_created < target_edge_count and attempts < max_attempts:
        attempts += 1
        source, target = random.sample(companies, 2)
        if G.has_edge(source, target):
            continue
        
        # Calculate affinity score
        source_data = G.nodes[source]
        target_data = G.nodes[target]
        shared_industry = source_data['industry'] == target_data['industry']
        same_region = source_data['region'] == target_data['region']
        shared_segments = len(set(source_data['segments']) & set(target_data['segments']))

        affinity = 0.1 + (0.2 if shared_industry else 0) + (0.2 if same_region else 0) + (0.1 * shared_segments)
        if random.random() > affinity:
            continue
        
        # Pick a relationship type
        rel_type = random.choice(list(RELATIONSHIP_TYPES.keys()))
        rel_def = RELATIONSHIP_TYPES[rel_type]
        strength = random.randint(*rel_def['strength_range'])
        created = random_join_date()
        props = {
            "description": rel_def['description'],
            "created": created,
            "strength": strength
        }

        # Add edge(s)
        G.add_edge(source, target, type=rel_type, **props)
        edges_created += 1

        if rel_def['bidirectional']:
            if not G.has_edge(target, source):
                G.add_edge(target, source, type=rel_type, **props)
                edges_created += 1

    print(f"Generated {edges_created} relationships between {company_count} companies.")
    return G

def export_to_json(G: nx.DiGraph, path: str = "supply_network.json"):
    data = {
        "nodes": [
            {**{"id": n}, **G.nodes[n]} for n in G.nodes()
        ],
        "edges": [
            {"source": u, "target": v, **G.edges[u, v]} for u, v in G.edges()
        ]
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Exported graph to {path}")

# Example usage
if __name__ == "__main__":
    G = generate_supply_chain_network(company_count=100, edge_density=0.06)
    export_to_json(G)
