import networkx as nx

def nx_to_cytoscape(G, directed=False):
    """Convert a NetworkX graph to Cytoscape elements"""
    elements = []

    # Add nodes
    for node in G.nodes:
        elements.append({
            "data": {"id": node, "label": node},
            "classes": "node"
        })

    # Add edges
    for src, dst in G.edges:
        elements.append({
            "data": {
                "source": src,
                "target": dst,
                "label": f"{src} → {dst}" if directed else f"{src} -- {dst}"
            },
            "classes": "directed" if directed else "edge"
        })

    return elements


def extract_neighbors_subgraph(G, center_node, hops=1):
    """Return subgraph including center_node and k-hop neighbors."""
    if center_node not in G:
        return nx.DiGraph()  # empty graph

    nodes = {center_node}
    frontier = {center_node}

    for _ in range(hops):
        next_frontier = set()
        for n in frontier:
            next_frontier.update(G.predecessors(n))
            next_frontier.update(G.successors(n))
        nodes.update(next_frontier)
        frontier = next_frontier

    return G.subgraph(nodes).copy()
