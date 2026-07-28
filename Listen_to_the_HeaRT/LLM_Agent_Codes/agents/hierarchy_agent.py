import json
import sys
import os
import argparse
from typing import Any, Dict, List
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt


# Add parent directory (Multi_Agent) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from contexts.global_context import GlobalContext

working_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Possible algorithms to ground the Hierarchy Agent:
#   1. Signal-flow graph
#   2. Min-cut, max-flow
#   3. Personalized PageRank (PPR) Clustering
#   4. LLM-assisted flows. Recursive for building the hierarchihcal agglomeration tree. These can be for example Information Gain or Entropy Metrics?

# GPT plan: We will build a hierarchical agglomeration tree by computing seed-wise PPR diffusion profiles, converting them into a pairwise affinity/similarity matrix, and repeatedly merging the most similar nodes/clusters with cluster-level PPR recomputation.


# Step 1: Build the system-level graph

SUPPLY_NETS = {"vdd", "vss", "gnd", "vdda", "vssa", "avdd", "avss", "dvdd", "dvss"}


def find_next_run_to_process(parent_netlist_path: str) -> str:
    """Return the LOWEST-numbered Runs/Run_NNN/ that has splitter output but no
    hierarchy/ folder yet (i.e. the oldest run still waiting to be processed).

    Skips runs that don't have splitter/circuit_global_context.json (incomplete
    splitter runs cannot be consumed). Raises FileNotFoundError if nothing
    qualifies.
    """
    runs_dir = os.path.join(parent_netlist_path, "Runs")
    if not os.path.isdir(runs_dir):
        raise FileNotFoundError(
            f"No Runs/ directory at {runs_dir}. Run the splitter first."
        )
    run_ids = sorted(
        int(name[4:]) for name in os.listdir(runs_dir)
        if name.startswith("Run_") and name[4:].isdigit()
    )
    for n in run_ids:
        candidate = os.path.join(runs_dir, f"Run_{n:03d}")
        has_splitter = os.path.isfile(
            os.path.join(candidate, "splitter", "circuit_global_context.json")
        )
        has_hierarchy = os.path.isdir(os.path.join(candidate, "hierarchy"))
        if has_splitter and not has_hierarchy:
            return candidate
    raise FileNotFoundError(
        f"No Run_NNN/ in {runs_dir} has splitter output without an already-built "
        f"hierarchy/ folder. Either every run is processed, or splitter never ran."
    )


def _normalize_net_name(net: str) -> str:
    return net.strip().lower()


def load_subcircuit_blocks_from_global_context(
    global_subcircuits_list: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build the leaf-node block list directly from the splitter's global context.

    The splitter LLM call now produces `class_category` and `port_annotations`
    per subcircuit, so the hierarchy agent makes ZERO LLM calls.
    """
    blocks: List[Dict[str, Any]] = []
    for subckt in global_subcircuits_list or []:
        block_id = str(subckt.get("id", "")).strip()
        if not block_id:
            continue
        blocks.append(
            {
                "unique_name":      block_id,
                "id":               block_id,
                "netlist":          subckt.get("netlist", "") or "",
                "role_hint":        subckt.get("role_hint", "") or "",
                "signal_ports":     subckt.get("signal_ports", []) or [],
                "class_category":   subckt.get("class_category", "Unknown"),
                "port_annotations": subckt.get("port_annotations", []) or [],
                "children":         [],
            }
        )
    return blocks


def _make_shared_net_id(node_a: str, node_b: str, net_name: str) -> str:
    a, b = sorted([str(node_a), str(node_b)])
    return f"{a}|{b}|{_normalize_net_name(net_name)}"


def build_system_level_graph(blocks: List[Dict[str, Any]]) -> nx.MultiGraph:
    """
    Nodes:
      - one per block

    Edges:
      - one per shared signal port between two blocks

    Intended for later:
      - signal-flow variants
      - PPR / random-walk clustering
      - affinity-matrix construction
    """
    
    G_system = nx.MultiGraph()

    def build_port_annotation_map(block: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        port_map: Dict[str, Dict[str, str]] = {}

        for ann in block.get("port_annotations", []) or []:
            port_name = _normalize_net_name(ann.get("port_name", ""))
            if not port_name:
                continue

            port_map[port_name] = {
                "port_type": ann.get("port_type", ""),
                "direction": ann.get("direction", ""),
            }

        return port_map
    
    # Add identified blocks/nodes as atomic system-level blocks
    for block in blocks:
        node_id = block.get("id", "")
        
        signal_ports = [
            _normalize_net_name(port)
            for port in (block.get("signal_ports", []) or [])
            if str(port).strip()
        ]

        G_system.add_node(
            node_id,
            #class_category=block.get("class_category", ""),
            #role_description=block.get("role_description", block.get("role_hint","")),
            role_hint=block.get("role_hint", ""),
            signal_ports=signal_ports,
            netlist=block.get("netlist", ""),
            class_category=block.get("class_category", "")
        )

    # Add interaction edges between leaf nodes
    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            block_a = blocks[i]
            block_b = blocks[j]

            node_a = block_a.get("id", "")
            node_b = block_b.get("id", "")

            ports_a = {
                _normalize_net_name(port)
                for port in (block_a.get("signal_ports", []) or [])
                if str(port).strip()
            }
            ports_b = {
                _normalize_net_name(port)
                for port in (block_b.get("signal_ports", []) or [])
                if str(port).strip()
            }

            shared_ports = sorted((ports_a & ports_b) - SUPPLY_NETS)
            
            if not shared_ports:
                continue
            
            ann_a = build_port_annotation_map(block_a)
            ann_b = build_port_annotation_map(block_b)

            for net_name in shared_ports:
                edge_id = _make_shared_net_id(node_a, node_b, net_name)
                a_info = ann_a.get(net_name, {})
                b_info = ann_b.get(net_name, {})

                signal_type = a_info.get("port_type", "")
                
                G_system.add_edge(
                    node_a,
                    node_b,
                    key=edge_id,
                    net_name=net_name,
                    edge_type=signal_type,
                )

    return G_system


def compute_personalized_pagerank_scores(
    G_system: nx.MultiGraph,
    alpha: float = 0.85,
) -> Dict[str, Dict[str, float]]:
    """
    Compute a seed-wise Personalized PageRank (PPR) score dictionary.

    Returns:
        {
            seed_node_a: {node_1: score, node_2: score, ...},
            seed_node_b: {node_1: score, node_2: score, ...},
            ...
        }

    Notes:
    - We convert the MultiGraph to a simple weighted Graph first.
    - Edge weight between two nodes = number of parallel shared-net edges.
    - Each seed gets its own personalization vector.
    """

    # We should delete the current mirror biasing edges for this. We can do this later
    
    ppr_scores: Dict[str, Dict[str, float]] = {}

    if G_system.number_of_nodes() == 0:
        return ppr_scores

    # Collapse MultiGraph -> weighted simple Graph
    # WE CAN USE SOME PHYSICS_AWARE WEIGHTED: LLM ASSISTANCE. ALSO REMOVE THE CURRENT MIRROR/BIASING EDGES.
    G_weighted = nx.Graph()

    for node, attrs in G_system.nodes(data=True):
        G_weighted.add_node(node, **attrs)

    for node_a, node_b, edge_data in G_system.edges(data=True):
        edge_type = edge_data.get("edge_type", "")
        if "dc_bias" in edge_type:
            edge_weight = 0.5
        elif "control_signal" in edge_type:
            edge_weight = 1.0
        else:
            edge_weight = 1.0

        if G_weighted.has_edge(node_a, node_b):
            G_weighted[node_a][node_b]["weight"] += edge_weight
        else:
            G_weighted.add_edge(node_a, node_b, weight=edge_weight)

    nodes = list(G_weighted.nodes())
    for seed_node in nodes:
        personalization = {node: 0.0 for node in nodes}
        personalization[seed_node] = 1.0

        seed_ppr = nx.pagerank(
            G_weighted,
            alpha=alpha,
            personalization=personalization,
            weight="weight",
            max_iter=1000,
            tol=1e-6,
        )

        ppr_scores[seed_node] = seed_ppr

    return ppr_scores

def build_affinity_matrix_from_ppr(
    G_system: nx.MultiGraph,
    ppr_scores: Dict[str, Dict[str, float]],
) -> tuple[List[str], np.ndarray]:
    """
    Build a symmetric affinity matrix from seed-wise PPR scores.

    Similarity definition:
        sim(u, v) = 0.5 * (PPR_u[v] + PPR_v[u])

    Returns:
        nodes: node ordering used for the matrix
        affinity_matrix: NxN numpy array
    """
    nodes = list(G_system.nodes())
    n = len(nodes)
    affinity_matrix = np.zeros((n, n), dtype=float)

    for i, node_u in enumerate(nodes):
        for j, node_v in enumerate(nodes):
            if i == j:
                affinity_matrix[i, j] = 1.0
            else:
                score_uv = ppr_scores.get(node_u, {}).get(node_v, 0.0)
                score_vu = ppr_scores.get(node_v, {}).get(node_u, 0.0)
                affinity_matrix[i, j] = 0.5 * (score_uv + score_vu)

    return nodes, affinity_matrix

def plot_affinity_matrix(
    nodes: List[str],
    affinity_matrix: np.ndarray,
    out_dir: str,
    title: str = "PPR Affinity Matrix",
):
    plt.figure(figsize=(8, 6))
    plt.imshow(affinity_matrix, cmap="viridis", interpolation="nearest")
    plt.colorbar(label="Similarity")
    plt.xticks(range(len(nodes)), nodes, rotation=90)
    plt.yticks(range(len(nodes)), nodes)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "ppr_affinity_matrix.png"), dpi=200, bbox_inches="tight")
    plt.close()
    plt.show()


def plot_system_level_graph(
    G_system: nx.MultiGraph,
    title: str = "System-Level Graph",
    save_path: str = None,
) -> None:
    """
    Plot a simple weighted view of the system-level MultiGraph.

    - Node labels = block ids
    - Edge labels = number of shared signal nets between node pairs
    """
    G_plot = nx.Graph()

    # Copy nodes and attrs
    for node, attrs in G_system.nodes(data=True):
        G_plot.add_node(node, **attrs)

    # Collapse parallel edges into one weighted edge
    for u, v, edge_data in G_system.edges(data=True):
        edge_type = edge_data.get("edge_type", "")

        if "dc_bias" in edge_type:
            edge_weight = 0.5
        elif "control_signal" in edge_type:
            edge_weight = 1.0
        else:
            edge_weight = 1.0

        if G_plot.has_edge(u, v):
            G_plot[u][v]["weight"] += edge_weight
        else:
            G_plot.add_edge(u, v, weight=edge_weight)

    plt.figure(figsize=(10, 8))

    pos = nx.spring_layout(G_plot, seed=42)

    nx.draw_networkx_nodes(
        G_plot,
        pos,
        node_size=2200,
        node_color="lightblue",
        edgecolors="black",
    )

    nx.draw_networkx_labels(
        G_plot,
        pos,
        font_size=9,
        font_weight="bold",
    )

    edge_widths = [1.0 + 1.5 * G_plot[u][v]["weight"] for u, v in G_plot.edges()]

    nx.draw_networkx_edges(
        G_plot,
        pos,
        width=edge_widths,
        edge_color="gray",
    )

    edge_labels = {
        (u, v): G_plot[u][v]["weight"]
        for u, v in G_plot.edges()
    }

    nx.draw_networkx_edge_labels(
        G_plot,
        pos,
        edge_labels=edge_labels,
        font_size=8,
    )

    plt.title(title)
    plt.axis("off")
    plt.tight_layout()

    if save_path is not None:
        plt.savefig(save_path, dpi=200, bbox_inches="tight")
        plt.close()
    else:
        plt.show()

def normalize_affinity_matrix(
    affinity_matrix: np.ndarray,
) -> np.ndarray:
    """
    Min-max normalize the off-diagonal affinity values to [0, 1].

    Diagonal entries are reset to 1.0 after normalization.
    """
    A = affinity_matrix.copy().astype(float)
    n = A.shape[0]

    if n == 0:
        return A

    # Special case: with only 2 nodes, there is only one off-diagonal value.
    # Keep the raw similarity instead of trying to min-max normalize it.
    if n == 2:
        np.fill_diagonal(A, 1.0)
        return A


    off_diag_values = []
    for i in range(n):
        for j in range(n):
            if i != j:
                off_diag_values.append(A[i, j])

    if not off_diag_values:
        np.fill_diagonal(A, 1.0)
        return A

    min_val = min(off_diag_values)
    max_val = max(off_diag_values)

    if np.isclose(max_val, min_val):
        # All off-diagonal values are effectively the same
        for i in range(n):
            for j in range(n):
                if i != j:
                    A[i, j] = 0.0
        np.fill_diagonal(A, 1.0)
        return A

    for i in range(n):
        for j in range(n):
            if i != j:
                A[i, j] = (A[i, j] - min_val) / (max_val - min_val)

    np.fill_diagonal(A, 1.0)
    return A

def build_level_clusters_from_normalized_affinity(
    nodes: List[str],
    normalized_affinity_matrix: np.ndarray,
    level: int,
    similarity_threshold: float = 0.6,
) -> List[Dict[str, Any]]:
    """
    NOW: Build clusters at any hierarchy level
    BEFORE: Build level-1 clusters from level-0 blocks using a thresholded
    normalized affinity matrix.

    Rule:
    - connect two blocks if normalized similarity >= similarity_threshold
    - each connected component becomes one level-1 cluster
    """
    G_cluster = nx.Graph()

    for node in nodes:
        G_cluster.add_node(node)

    n = len(nodes)

    for i in range(n):
        for j in range(i + 1, n):
            sim_ij = float(normalized_affinity_matrix[i, j])

            if sim_ij >= similarity_threshold:
                G_cluster.add_edge(nodes[i], nodes[j], weight=sim_ij)

    level_clusters = []

    for cluster_idx, component in enumerate(nx.connected_components(G_cluster)):
        children = sorted(component)

        # compute average internal similarity for reporting
        child_indices = [nodes.index(child) for child in children]
        internal_sims = []

        for a in range(len(child_indices)):
            for b in range(a + 1, len(child_indices)):
                i = child_indices[a]
                j = child_indices[b]
                internal_sims.append(float(normalized_affinity_matrix[i, j]))

        avg_internal_similarity = (
            sum(internal_sims) / len(internal_sims) if internal_sims else 1.0
        )

        level_clusters.append(
            {
                "cluster_id": f"level_{level}_cluster_{cluster_idx}",
                "level": level,
                "children": children,
                "avg_internal_similarity": avg_internal_similarity,
            }
        )

    return level_clusters


def build_supernodes_from_clusters(
    clusters: List[Dict[str, Any]],
    current_nodes: List[Dict[str, Any]],
    original_ckt_netlist:str,
) -> List[Dict[str, Any]]:
    """
    Build next-level supernodes from current-level nodes.
    """
    node_by_id = {node["id"]: node for node in current_nodes}
    supernodes = []

    def extract_netlist_body(netlist_text: str) -> List[str]:
        kept_lines = []

        for raw_line in (netlist_text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(".") or line.startswith("*"):
                continue
            kept_lines.append(raw_line)

        return kept_lines

    def compute_net_degree_in_netlist(netlist_text: str, target_nets: set[str]) -> Dict[str, int]:
        degree_map = {net: 0 for net in target_nets}
        device_map = {
            "mos": {
                "nmos",
                "pmos",
                "nch",
                "pch",
                "nch_25ud18_mac",
                "pch_25ud18_mac",
                "nch_25ud18",
                "pch_25ud18",
                "nch_lvt",
                "pch_lvt",
                "nch_hvt",
                "pch_hvt",
            },
            "res": {
                "res",
                "rppolywo_m",
                "rppolywo",
            },
            "cap": {
                "cap",
                "cfmom",
                "cfmom_2t",
            },
        }

        for raw_line in (netlist_text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("*") or line.startswith("."):
                continue

            tokens = line.split()
            if len(tokens) < 2:
                continue

            line_lower = line.lower()
            connection_nets = []

            # count all occurrences of target nets in this line
            # MOS: assume SPICE order Mname D G S B ...
            if any(dev in line_lower for dev in device_map["mos"]):
                if len(tokens) >= 5:
                    connection_nets = tokens[1:5]

            # Resistor: Rname N1 N2 ...
            elif any(dev in line_lower for dev in device_map["res"]):
                if len(tokens) >= 3:
                    connection_nets = tokens[1:3]

            # Capacitor: Cname N1 N2 ...
            elif any(dev in line_lower for dev in device_map["cap"]):
                if len(tokens) >= 3:
                    connection_nets = tokens[1:3]

            else:
                continue

            for net in connection_nets:
                net_name = _normalize_net_name(net)
                if net_name in target_nets:
                    degree_map[net_name] += 1

        return degree_map


    for cluster in clusters:
        child_ids = cluster.get("children", [])
        
        merged_netlist_lines = []
        candidate_ports = set()

        for child_id in child_ids:
            child_node = node_by_id[child_id]
            
            for port in child_node.get("signal_ports", []) or []:
                #candidate_ports.add(port)
                candidate_ports.add(_normalize_net_name(port))


            merged_netlist_lines.extend(
                extract_netlist_body(child_node.get("netlist", ""))
            )
        
        merged_netlist = "\n".join(merged_netlist_lines)
        merged_degree = compute_net_degree_in_netlist(merged_netlist, candidate_ports)
        original_degree = compute_net_degree_in_netlist(original_ckt_netlist, candidate_ports)

        final_signal_ports = sorted(
            [
                net
                for net in candidate_ports
                if original_degree.get(net, 0) > merged_degree.get(net, 0)
            ]
        )

        final_signal_port_set = set(final_signal_ports)
        final_port_annotations = []
        seen_ports = set()

        for child_id in child_ids:
            child_node = node_by_id[child_id]

            for ann in child_node.get("port_annotations", []) or []:
                port_name = _normalize_net_name(ann.get("port_name", ""))
                if not port_name:
                    continue

                if port_name in final_signal_port_set and port_name not in seen_ports:
                    final_port_annotations.append(ann)
                    seen_ports.add(port_name)

        supernodes.append(
            {
                "id": cluster["cluster_id"],
                "level": cluster["level"],
                "children": child_ids,
                "netlist": merged_netlist,
                "signal_ports": final_signal_ports,
                "port_annotations": final_port_annotations,
                "class_category": "unknown", # For now. Later LLM can decide either here, or while performing automorphism (LLM-assisted)
            }
        )

    return supernodes


def build_hierarchy_dendrogram(
    current_nodes: List[Dict[str, Any]],
    original_ckt_netlist: str,
    level: int = 1,
    similarity_threshold: float = 0.5,
    alpha: float = 0.95,
) -> Dict[str, Any]:
    """
    Recursively build a hierarchy / dendrogram from the current nodes.
    """
    G_system = build_system_level_graph(current_nodes)
    ppr_scores = compute_personalized_pagerank_scores(G_system, alpha=alpha)
    nodes, affinity_matrix = build_affinity_matrix_from_ppr(G_system, ppr_scores)
    normalized_affinity_matrix = normalize_affinity_matrix(affinity_matrix)

    adaptive_threshold = compute_level_similarity_threshold(
        similarity_threshold,
        level=level,
        decay=0.9,
    )


    level_clusters = build_level_clusters_from_normalized_affinity(
        nodes,
        normalized_affinity_matrix,
        level=level,
        similarity_threshold=adaptive_threshold,
    )


    #print(adaptive_threshold)
    #exit()

    result = {
        "level": level,
        "node_ids": nodes,
        "similarity_threshold": adaptive_threshold,
        "clusters": level_clusters,
        "affinity_matrix": affinity_matrix.tolist(),
        "normalized_affinity_matrix": normalized_affinity_matrix.tolist(),
    }

    print(f"\nLevel {level}")
    print("Nodes:", nodes)
    print("Adaptive threshold:", adaptive_threshold)
    print("Clusters:")
    print(json.dumps(level_clusters, indent=2))

    # Stop if only one cluster remains
    if len(level_clusters) == 1:
        result["stop_reason"] = "single_cluster_remaining"
        return result

    # Stop if no merges happened
    if len(level_clusters) == len(current_nodes):
        result["stop_reason"] = "no_more_merges"
        return result

    next_level_nodes = build_supernodes_from_clusters(
        level_clusters,
        current_nodes,
        original_ckt_netlist,
    )

    result["supernodes"] = next_level_nodes

    result["next_level"] = build_hierarchy_dendrogram(
        current_nodes=next_level_nodes,
        original_ckt_netlist=original_ckt_netlist,
        level=level + 1,
        similarity_threshold=similarity_threshold,
        alpha=alpha,
    )

    return result

def compute_level_similarity_threshold(
    base_threshold: float,
    level: int,
    decay: float = 0.9
) -> float:
    """
    Smoothly relax the clustering threshold as hierarchy level increases.

    level 1 -> base_threshold
    level 2 -> base_threshold * decay
    level 3 -> base_threshold * decay^2
    ...
    """
    threshold = base_threshold * (decay ** (level - 1))
    return threshold


def format_hierarchy_dendrogram_for_save(tree: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save only level-wise clustering summary, while preserving which nodes
    each cluster contains.
    """
    formatted = {}
    cur = tree

    while cur is not None:
        level = cur.get("level")
        formatted[f"level_{level}"] = {
            "node_ids": cur.get("node_ids", []),
            "clusters": cur.get("clusters", []),
            "affinity_matrix": cur.get("affinity_matrix", []),
            "normalized_affinity_matrix": cur.get("normalized_affinity_matrix", []),
        }
        cur = cur.get("next_level")

    return formatted


def ensure_single_top_cluster(tree_for_save: Dict[str, Any]) -> Dict[str, Any]:
    """If the highest level has >1 clusters (clustering didn't converge to a
    single root — e.g., very small circuits like ota4 with only 2 leaves),
    append one synthetic level whose single cluster is the virtual root of
    every top-level cluster.

    No-op when the top level already has exactly one cluster, so circuits that
    historically converged (LDO, StrongArm, OTAs 1-3, Comp, ...) yield a
    byte-identical JSON. Clustering math is NOT affected — this only adds a
    presentational wrapper so downstream plotting / cleaning code sees a
    single rooted tree.
    """
    if not tree_for_save:
        return tree_for_save
    level_keys = sorted(tree_for_save.keys(), key=lambda k: int(k.split("_")[1]))
    top_key = level_keys[-1]
    top_clusters = tree_for_save[top_key].get("clusters", []) or []
    if len(top_clusters) <= 1:
        return tree_for_save

    next_level = int(top_key.split("_")[1]) + 1
    child_ids = [c.get("cluster_id") for c in top_clusters if c.get("cluster_id")]
    tree_for_save[f"level_{next_level}"] = {
        "node_ids": list(child_ids),
        "clusters": [{
            "cluster_id": f"level_{next_level}_cluster_0",
            "level": next_level,
            "children": child_ids,
            "avg_internal_similarity": None,
            "synthetic_root": True,
        }],
        "affinity_matrix": [],
        "normalized_affinity_matrix": [],
    }
    return tree_for_save

def hierarchy_pos(G, root, width=1.5, vert_gap=0.25, vert_loc=0, xcenter=0.5):
    def _hierarchy_pos(
        G,
        root,
        width=1.5,
        vert_gap=0.25,
        vert_loc=0,
        xcenter=0.5,
        pos=None,
    ):
        if pos is None:
            pos = {root: (xcenter, vert_loc)}
        else:
            pos[root] = (xcenter, vert_loc)

        children = list(G.successors(root))
        if len(children) != 0:
            dx = width / len(children)
            nextx = xcenter - width / 2 - dx / 2
            for child in children:
                nextx += dx
                pos = _hierarchy_pos(
                    G,
                    child,
                    width=dx,
                    vert_gap=vert_gap,
                    vert_loc=vert_loc - vert_gap,
                    xcenter=nextx,
                    pos=pos,
                )
        return pos

    return _hierarchy_pos(G, root, width, vert_gap, vert_loc, xcenter)

def plot_hierarchy_dendrogram_from_json(
    json_path: str,
    save_path: str = None,
    title: str = "Hierarchy Dendrogram",
) -> None:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    G = nx.DiGraph()

    # Add edges level by level
    for level_key, level_info in data.items():
        for cluster in level_info.get("clusters", []):
            cluster_id = cluster["cluster_id"]
            G.add_node(cluster_id)

            for child in cluster.get("children", []):
                G.add_node(child)
                G.add_edge(cluster_id, child)

    # Root = cluster from highest level
    level_keys = sorted(data.keys(), key=lambda x: int(x.split("_")[1]))
    highest_level_key = level_keys[-1]
    highest_level_clusters = data[highest_level_key].get("clusters", [])

    if not highest_level_clusters:
        raise ValueError("No clusters found in highest level of dendrogram JSON.")

    root = highest_level_clusters[0]["cluster_id"]

    pos = hierarchy_pos(G, root, width=2.0, vert_gap=0.25)

    plt.figure(figsize=(16, 10))
    nx.draw(
        G,
        pos=pos,
        with_labels=True,
        arrows=True,
        node_size=1800,
        node_color="#A0CBE2",
        edgecolors="black",
        font_size=8,
    )

    plt.title(title)
    plt.axis("off")
    plt.subplots_adjust(left=0.03, right=0.97, top=0.92, bottom=0.05)

    if save_path:
        plt.savefig(save_path, dpi=250, bbox_inches="tight")
        plt.close()
    else:
        plt.show()


def convert_levelwise_dendrogram_to_nested_tree(tree: Dict[str, Any]) -> Dict[str, Any]:
    cluster_lookup = {}

    for level_key, level_info in tree.items():
        for cluster in level_info.get("clusters", []):
            cluster_lookup[cluster["cluster_id"]] = cluster

    def build_node(node_name: str) -> Dict[str, Any]:
        if node_name not in cluster_lookup:
            return {
                "unique_name": node_name,
                "children": [],
            }

        cluster = cluster_lookup[node_name]
        return {
            "unique_name": cluster["cluster_id"],
            "children": [build_node(child) for child in cluster.get("children", [])],
        }

    highest_level_key = sorted(tree.keys(), key=lambda x: int(x.split("_")[1]))[-1]
    root_cluster_id = tree[highest_level_key]["clusters"][0]["cluster_id"]

    return build_node(root_cluster_id)


def clean_leaf_nodes_and_collapse(node):
    if "children" in node:
        new_children = []
        for child in node["children"]:
            cleaned_child = clean_leaf_nodes_and_collapse(child)
            if cleaned_child is not None:
                new_children.append(cleaned_child)
        node["children"] = new_children

        if len(node["children"]) == 1:
            only_child = node["children"][0]
            return only_child

    return node

def add_edges_from_json(node, G, parent=None):
    node_name = node.get("unique_name", node.get("id", "Unnamed"))
    G.add_node(node_name)
    if parent is not None:
        G.add_edge(parent, node_name)

    for child in node.get("children", []):
        add_edges_from_json(child, G, node_name)

def plot_nested_hierarchy_tree(
    tree: Dict[str, Any],
    save_path: str = None,
    title: str = "Hierarchy Dendrogram Cleaned",
):
    G = nx.DiGraph()
    add_edges_from_json(tree, G)

    root = tree.get("unique_name", tree.get("id", "Unnamed"))
    pos = hierarchy_pos(G, root, width=2.0, vert_gap=0.25)

    plt.figure(figsize=(16, 10))
    nx.draw(
        G,
        pos=pos,
        with_labels=True,
        arrows=True,
        node_size=1800,
        node_color="#A0CBE2",
        edgecolors="black",
        font_size=8,
    )

    plt.title(title)
    plt.axis("off")
    plt.subplots_adjust(left=0.03, right=0.97, top=0.92, bottom=0.05)

    if save_path:
        plt.savefig(save_path, dpi=250, bbox_inches="tight")
        plt.close()
    else:
        plt.show()


def main():
    """
    ######################## LDO #############################
    parent_netlist_path = os.path.join(
        parent_dir,
        "netlists/LDO_Simple",
    )
    """
    
    """
    ############## Strong Arm Latch Comparator ################
    parent_netlist_path = os.path.join(
        parent_dir,
        "netlists/StrongArm_Latch_Comparator",
    )
    """
    
    """
    # MAGICAL circuits
    parent_netlist_path = os.path.join(
        parent_dir,
        "netlists/OTAs/ota1",
    )
    """
    
    # OTA Topology 1: Inverter Input-Based OTA
    parent_netlist_path = os.path.join(
        parent_dir,
        "netlists/OTAs/ota4",
    )

    netlist_filepath = os.path.join(
        parent_netlist_path, "Input_Netlist/unknown_circuit.sp"
    )

    top_level_netlist_filename = os.path.basename(netlist_filepath)
    top_level_circuit_name = os.path.splitext(top_level_netlist_filename)[0]

    # Resolve which run to consume + write hierarchy artifacts into its hierarchy/ folder
    run_dir = find_next_run_to_process(parent_netlist_path)
    splitter_dir = os.path.join(run_dir, "splitter")
    hierarchy_dir = os.path.join(run_dir, "hierarchy")
    os.makedirs(hierarchy_dir, exist_ok=True)
    print(f"[hierarchy] Reading splitter output from: {splitter_dir}")
    print(f"[hierarchy] Writing artifacts to:        {hierarchy_dir}")

    # Read in the Global Context JSON produced by the splitter
    circuit_global_context = GlobalContext()
    circuit_global_context.load(
        os.path.join(splitter_dir, "circuit_global_context.json")
    )

    global_ctx_data = circuit_global_context._store
    global_subcircuits_list = global_ctx_data.get("subcircuits", [])

    # Load full netlist text
    with open(netlist_filepath, "r") as f:
        full_netlist_content = f.read()

    blocks = load_subcircuit_blocks_from_global_context(global_subcircuits_list)
    G_system = build_system_level_graph(blocks)
    ppr_scores = compute_personalized_pagerank_scores(G_system, alpha=0.95)
    nodes, affinity_matrix = build_affinity_matrix_from_ppr(G_system, ppr_scores)
    normalized_affinity_matrix = normalize_affinity_matrix(affinity_matrix)
    
    #print("Nodes order:")
    #print(nodes)

    #print("\nAffinity matrix:")
    #print(affinity_matrix)
    #print(normalized_affinity_matrix)


    level1_clusters = build_level_clusters_from_normalized_affinity(
        nodes,
        normalized_affinity_matrix,
        level=1,
        similarity_threshold=0.5,
    )

    #print(json.dumps(level1_clusters, indent=2))


    hierarchy_tree = build_hierarchy_dendrogram(
        current_nodes=blocks,
        original_ckt_netlist=full_netlist_content,
        level=1,
        similarity_threshold=0.5,
        alpha=0.95,
    )

    hierarchy_tree_for_save = format_hierarchy_dendrogram_for_save(hierarchy_tree)
    # Guard for tiny circuits where clustering doesn't converge to a single
    # root (e.g. ota4 with only 2 leaves). No-op when already single-rooted.
    hierarchy_tree_for_save = ensure_single_top_cluster(hierarchy_tree_for_save)

    with open(os.path.join(hierarchy_dir, "hierarchy_dendrogram.json"), "w") as f:
        json.dump(hierarchy_tree_for_save, f, indent=2)

    #print(json.dumps(hierarchy_tree_for_save, indent=2))

    plot_hierarchy_dendrogram_from_json(
        json_path=os.path.join(hierarchy_dir, "hierarchy_dendrogram.json"),
        save_path=os.path.join(hierarchy_dir, "hierarchy_dendrogram.png"),
    )

    nested_tree = convert_levelwise_dendrogram_to_nested_tree(hierarchy_tree_for_save)
    cleaned_tree = clean_leaf_nodes_and_collapse(nested_tree)

    with open(os.path.join(hierarchy_dir, "hierarchy_dendrogram_cleaned.json"), "w") as f:
        json.dump(cleaned_tree, f, indent=2)

    plot_nested_hierarchy_tree(
        cleaned_tree,
        save_path=os.path.join(hierarchy_dir, "hierarchy_dendrogram_cleaned.png"),
        title="Hierarchy Dendrogram Cleaned",
    )

    
    """
    cleaned_hierarchy_tree_for_save = clean_levelwise_dendrogram(hierarchy_tree_for_save)
    with open(os.path.join(hierarchy_dir, "hierarchy_dendrogram_cleaned.json"), "w") as f:
        json.dump(cleaned_hierarchy_tree_for_save, f, indent=2)
    
    plot_hierarchy_dendrogram_from_json(
        json_path=os.path.join(hierarchy_dir, "hierarchy_dendrogram_cleaned.json"),
        save_path=os.path.join(hierarchy_dir, "hierarchy_dendrogram_cleaned.png"),
        title="Hierarchy Dendrogram Cleaned",
    )
    """

    
if __name__ == "__main__":
    main()


# Affinity needs normalization
# Implement the recursive clustering and build the agglomration tree
# plot system level graph to visualize if everything is happening as expected
# Eventually we have to remove the current mirroring edges somehow as they will add unnecessary bias for clustering.
# Using directed signal flow graph can solve this issue of "noisy" DC bias signals like current mirrors influencing the clustering algorithm.