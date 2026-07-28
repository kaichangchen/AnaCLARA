import argparse
import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Tuple
import networkx as nx
import matplotlib.pyplot as plt
import re
from typing import Optional, Any, Dict, List, Set
import copy

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
LEAF_ENGINE_DIR = os.path.join(PROJECT_ROOT, "Expert_Leaf_Constraint_Engine")
parent_dir = os.path.dirname(CURRENT_DIR)


def find_next_run_to_process(parent_netlist_path: str) -> str:
    """Return the LOWEST-numbered Runs/Run_NNN/ that has both splitter/ and
    hierarchy/ outputs but no system_level/ folder yet.

    Mirrors the queue-style helper in hierarchy_agent so each agent picks up
    the oldest run that's waiting to be processed.
    """
    runs_dir = os.path.join(parent_netlist_path, "Runs")
    if not os.path.isdir(runs_dir):
        raise FileNotFoundError(
            f"No Runs/ directory at {runs_dir}. Run the splitter + hierarchy_agent first."
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
        has_hierarchy = os.path.isfile(
            os.path.join(candidate, "hierarchy", "hierarchy_dendrogram_cleaned.json")
        )
        has_constraints = os.path.isdir(os.path.join(candidate, "constraints"))
        if has_splitter and has_hierarchy and not has_constraints:
            return candidate
    raise FileNotFoundError(
        f"No Run_NNN/ in {runs_dir} has splitter + hierarchy outputs without an "
        f"already-built constraints/ folder. Either every run is processed, "
        f"or upstream agents have not been run yet."
    )

if LEAF_ENGINE_DIR not in sys.path:
    sys.path.append(LEAF_ENGINE_DIR)

from hybrid_constraint_engine import (
    HybridConstraintEngine, LLMHelper, CONSTRAINT_SCHEMA,
    parse_netlist_general, build_bipartite_graph,
    detect_power_ground, deduplicate_constraints,
    _device_type_lookup, _filter_bad_sym_pairs,
    _clean_symmetric_blocks, _reconcile_supply_ports,
    _graphwalk_symmetry_seeds, SUPPLY_RAILS_LOWER,
)


SUPPLY_NETS = {"vdd", "vss", "gnd", "vdda", "vssa", "avdd", "avss", "dvdd", "dvss"}

NVIDIA_OPENAI_BASE_URL = os.getenv("NVIDIA_OPENAI_BASE_URL", "https://inference-api.nvidia.com/v1")
NVIDIA_MODEL_ENDPOINTS = {
    "GPT_BEST": "azure/openai/gpt-5.5",
    "CLAUDE_SONNET": "azure/anthropic/claude-sonnet-4-6",
    "CLAUDE_OPUS": "azure/anthropic/claude-opus-4-7",
    "GEMINI_PRO": "gcp/google/gemini-3.1-pro-preview",
    "GEMINI_STABLE": "gcp/google/gemini-2.5-pro",
}
DEFAULT_MODEL_ENDPOINT = NVIDIA_MODEL_ENDPOINTS["GPT_BEST"]


def resolve_model_endpoint(model: str) -> str:
    return NVIDIA_MODEL_ENDPOINTS.get(model, model)


mosfet_terminals = ["D", "G", "S"]  # For simplicity: removing "B"
    
# Using actual process technolgy device names from tsmcN40
device_map = {
    "nmos": {
        "nmos",
        "nch", 
        "nch_25ud18_mac",
        "nch_25ud18",
        "nch_lvt",
        "nch_hvt",
    },
    "pmos": {
        "pmos",
        "pch",
        "pch_25ud18_mac",
        "pch_25ud18",
        "pch_lvt",
        "pch_hvt",
    },
    "cap": {
        "cap",
        "cfmom",
        "cfmom_2t",
    },
    "res": {
        "res",
        "rppolywo_m",
        "rppolywo",
    }
}



def _normalize_net_name(net: str) -> str:
    return net.strip().lower()



BOTTOM_UP_FINAL_ALIGN_SYSTEM_PROMPT = """You are an expert analog IC layout constraint engineer.

You are given:
1. A compact analog hierarchy tree
2. Leaf-level ALIGN-compatible constraints for the leaf nodes
3. Non-leaf node structural evidence from deterministic system-level analysis
4. System-level net driver/load metadata

{schema}

YOUR TASK:
Generate the FINAL full-circuit ALIGN-compatible constraint list.

IMPORTANT RULES:
- Output ONLY a valid JSON array of ALIGN-compatible constraint objects.
- Do NOT output node-wise grouped JSON.
- Do NOT output explanations or markdown.
- Device-matching evidence at non-leaf nodes represents system-level matching relationships inferred across multiple child blocks/leaves.
- Prefer preserving valid leaf constraints where appropriate.
- Treat all node names (`unique_name` or `id`) as logical analysis labels, not final physical instance names.
- Do NOT use any node name as an `instance` in the final ALIGN constraints.
- Final ALIGN constraints must be written using only real device/instance names and net names, not analysis-created block or node labels.
- If a higher-level structural pattern is identified at the block/node level, translate it into device/instance-level ALIGN constraints only using names grounded in the provided leaf-level constraints and leaf-level netlist information.

"""



if not hasattr(argparse.Namespace, "with_reasoning"):
    argparse.Namespace.with_reasoning = False


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, payload: Any) -> None:
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        #json.dump(payload, f, indent=2)
        json.dump(payload, f, indent=2, default=list)


def identify_leaf_nodes(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
    leaves: List[Dict[str, Any]] = []

    def dfs(node: Dict[str, Any]) -> None:
        children = node.get("children", [])
        if not children:
            leaves.append(node)
            return
        for child in children:
            dfs(child)

    dfs(tree)
    return leaves


def build_bipartite_graph_from_netlist(node_netlist_str: str) -> nx.MultiGraph:
    """
    Parse a SPICE netlist into a bipartite graph:
      - Device nodes
      - Net nodes
      - Edges annotated by terminal name
    """
    G = nx.MultiGraph()

    for raw_line in node_netlist_str.splitlines():
        line = raw_line.strip().lower()
        if not line or line.startswith(("*", ".", "+")):
            continue

        tokens = line.split()
        dev_name = tokens[0]

        dev_type = None
        for canon_type, variants in device_map.items():
            if any(variant in tokens for variant in variants):
                dev_type = canon_type
                break

        if dev_type is None:
            raise ValueError(f"Unsupported device type: {dev_name}")

        if "mos" in dev_type:
            nets = tokens[1:4]
            params = tokens[6:]

            G.add_node(
                dev_name, bipartite="device", type=dev_type, params=" ".join(params)
            )

            for term, net in zip(mosfet_terminals, nets):
                if net in SUPPLY_NETS:
                    role = "SUPPLY_PORT"
                else:
                    role = "INTERNAL_NET"

                G.add_node(net, bipartite="net", role=role)

                edge_id = f"{dev_name}.{term}"
                G.add_edge(
                    dev_name,
                    net,
                    key=edge_id,
                    terminal=term,
                    edge_id=edge_id,
                )

        # SPECIFIC TO TSMCN40
        elif "res" in dev_type:
            nets = tokens[1:3]
            params = tokens[5:]
            G.add_node(dev_name, bipartite="device", type="resistor", params=" ".join(params))

            for i, net in enumerate(nets):
                if net in SUPPLY_NETS:
                    role = "SUPPLY_PORT"
                else:
                    role = "INTERNAL_NET"

                G.add_node(net, bipartite="net", role=role)
                term = f"N{i+1}"
                edge_id = f"{dev_name}.{term}"
                G.add_edge(
                    dev_name,
                    net,
                    key=edge_id,
                    terminal=term,
                    edge_id=edge_id,
                )

        # SPECIFIC TO TSMCN40
        elif "cap" in dev_type:
            nets = tokens[1:3]
            params = tokens[5:]
            G.add_node(dev_name, bipartite="device", type="capacitor", params=" ".join(params))

            for i, net in enumerate(nets):
                if net in SUPPLY_NETS:
                    role = "SUPPLY_PORT"
                else:
                    role = "INTERNAL_NET"

                G.add_node(net, bipartite="net", role=role)
                term = f"N{i+1}"
                edge_id = f"{dev_name}.{term}"
                G.add_edge(
                    dev_name,
                    net,
                    key=edge_id,
                    terminal=term,
                    edge_id=edge_id,
                )

    return G


def compute_signature_for_node(node: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keeping this simple and deterministic (prototype) so we can later replace/extend it.
    """
    node_ID = node.get("unique_name", "")
    class_category = node.get("class_category", "")
    node_netlist_str = node.get("netlist", "")

    G = build_bipartite_graph_from_netlist(node_netlist_str)
    structure_signature = nx.node_link_data(G)
    
    G_round_trip = nx.node_link_graph(structure_signature)
    if not _is_SameTemplate(G, G_round_trip):
        raise ValueError(f"Round-trip graph serialization mismatch for node {node_ID}")
    
    return {
        "node_id": node_ID,
        "class_category": class_category,
        "structure_signature": structure_signature,
    }



"""
#### VERY IMPORTANT: REMEMBER THIS CONVENTION ALWAYS......

structure_signature stores the full graph payload
_is_SameTemplate(...) defines what “same template” actually means
Therefore matching must always go through _is_SameTemplate(...), not direct raw dict/key equality. 

`build_node_signature_database` follows this convention. For all future iterations requiring database lookups, the same convention must be followed.

"""

def build_node_signature_database(tree: Dict[str, Any]) -> Dict[str, Any]:
    template_db: Dict[str, Dict[str, Any]] = {}
    same_templates_identified: Dict[str, List[str]] = {}
    template_counter = 0

    def dfs(node: Dict[str, Any]) -> None:
        nonlocal template_counter
        signature_record = compute_signature_for_node(node)
        current_graph = nx.node_link_graph(signature_record["structure_signature"])
        matched_template_key = None

        for template_key, template_record in template_db.items():
            representative_template_graph = nx.node_link_graph(template_record["structure_signature"])
            if _is_SameTemplate(current_graph, representative_template_graph):
                matched_template_key = template_key
                break

        if matched_template_key is None:
            template_key = f"template_{template_counter}"
            template_counter += 1

            template_db[template_key] = signature_record
            same_templates_identified[template_key] = [signature_record["node_id"]]

        else:
            same_templates_identified[matched_template_key].append(signature_record["node_id"])

        for child in node.get("children", []) or []:
            dfs(child)

    dfs(tree)

    return {
        "template_db": template_db,    # canonical templates
        "same_templates_identified": same_templates_identified,    # grouped structural duplicates
    }



def _is_SameTemplate(GA, GB):
    # Isomorphism check between 2 graphs: Attribute-aware isomorphism (Selected Attributes only).
    """
    # Exact topology match between 2 bipartite circuit graphs, while ignoring instance names and net names.
    # Rules for topology matching between 2 Bipartite Graphs (Since imporant in analog circuits):

    - For device node matching:
        bipartite == "device"
        "type" must match, e.g. "pmos", "cap", etc.

    - For net node matching:
        bipartite == "net"
    
    - For edge matching:
        "terminal" must match

    """

    def _node_match(a, b):
        if a.get("bipartite") != b.get("bipartite"):
            return False

        if a.get("bipartite") == "device":
            return a.get("type") == b.get("type")

        if a.get("bipartite") == "net":
            return True

        return False

    def _edge_match(a, b):
        return a.get("terminal") == b.get("terminal")
    

    matcher = nx.isomorphism.MultiGraphMatcher(
        GA,
        GB,
        node_match=_node_match,
        edge_match=_edge_match,
    )

    return matcher.is_isomorphic()


def build_system_level_leaf_graph(tree: Dict[str, Any]) -> nx.MultiGraph:    
    """
        Building a leaf-only system-level interaction graph.
        - Nodes are leaf blocks only
        - Edges are shared non-supply net interactions between leaves
        - Each edge is assigned to the LCA of its two endpoint leaves
    """

    add_local_net_set_to_all_nodes(tree)
    leaves = identify_leaf_nodes(tree)
    lca_index = index_tree_for_lca(tree)
    parent_map = lca_index["parent_map"]
    depth_map = lca_index["depth_map"]

    signature_db = build_node_signature_database(tree)
    node_to_template_key: Dict[str, str] = {}
    for template_key, node_ids in signature_db["same_templates_identified"].items():
        for node_id in node_ids:
            node_to_template_key[node_id] = template_key

    G_system = nx.MultiGraph()

    # Add leaf nodes as atomic system-level blocks
    for leaf in leaves:
        node_id = leaf.get("unique_name", "")
        G_system.add_node(
            node_id,
            class_category=leaf.get("class_category", ""),
            role_description=leaf.get("role_description", leaf.get("role_hint","")),
            template_key=node_to_template_key.get(node_id),
            # Stashed so deterministic_driver_load can resolve per-block port direction
            # without needing the original leaf list.
            port_info_keyed_by_name=leaf.get("port_info_keyed_by_name", {}) or {},
        )

    # Add interaction edges between leaf pairs
    for i in range(len(leaves)):
        for j in range(i + 1, len(leaves)):
            leaf_a = leaves[i]
            leaf_b = leaves[j]

            node_a = leaf_a.get("unique_name", "")
            node_b = leaf_b.get("unique_name", "")

            a_nets = leaf_a.get("_local_net_set", set()) or set()
            b_nets = leaf_b.get("_local_net_set", set()) or set()

            shared_nets = sorted((a_nets & b_nets) - SUPPLY_NETS)
            
            if not shared_nets:
                continue
            
            a_map = leaf_a.get("_local_net_to_devices", {}) or {}
            b_map = leaf_b.get("_local_net_to_devices", {}) or {}

            a_port_info = leaf_a.get("port_info_keyed_by_name", {}) or {}

            lca_name = find_lca_name(node_a, node_b, parent_map, depth_map)
            lca_level = depth_map.get(lca_name, None)

            if lca_level is None:
                raise ValueError(f"LCA depth missing for leaf pair: {node_a}, {node_b}, lca={lca_name}")

            for net_name in shared_nets:
                edge_id = _make_shared_net_id(node_a, node_b, net_name)
                port_type = (a_port_info.get(net_name, {}) or {}).get("port_type", "")

                # DEFAULT:
                matching_signature_node_a = None
                matching_signature_node_b = None
                matching_summary = {}

                if port_type in {"dc_bias", "control_signal"}:
                    matching_signature_node_a = compute_typed_signature_per_touching_matching_group(
                        leaf_node=leaf_a,
                        net_name=net_name,
                    )
                    matching_signature_node_b = compute_typed_signature_per_touching_matching_group(
                        leaf_node=leaf_b,
                        net_name=net_name,
                    )
                    matching_summary = summarize_matching_signature_interaction(
                        node_a_signature=matching_signature_node_a,
                        node_b_signature=matching_signature_node_b,
                    )
                
                G_system.add_edge(
                    node_a,
                    node_b,
                    key=edge_id,
                    net_name=net_name,
                    devices_in_node_a=a_map.get(net_name, []),
                    devices_in_node_b=b_map.get(net_name, []),
                    port_type = port_type,
                    matching_summary=matching_summary,
                    lca_name=lca_name,
                    lca_level=lca_level,
                )

    return G_system


def build_lca_matching_summary_from_system_edges(
    G_system: nx.MultiGraph,
) -> Dict[str, Any]:
    """
    Collect all matching summaries from the system-level net edges and store them in the edge's lca_name node
    """
    lca_matching_summary: Dict[str, Any] = {}
    for node_a, node_b, edge_key, edge_data in G_system.edges(keys=True, data=True):
        matching_summary = edge_data.get("matching_summary", {}) or {}
        
        if not matching_summary.get("matched", False):
            continue

        lca_name = edge_data.get("lca_name", "")
        if not lca_name:
            continue

        if lca_name not in lca_matching_summary:
            lca_matching_summary[lca_name] = {
                "lca_name": lca_name,
                "matching_edge_summaries": [],
            }

        lca_matching_summary[lca_name]["matching_edge_summaries"].append(
            {
                "node_a": node_a,
                "node_b": node_b,
                "edge_key": edge_key,
                "net_name": edge_data.get("net_name", ""),
                "port_type": edge_data.get("port_type", ""),
                #"matching_group": matching_summary.get("matching_group", []),
                #"typed_signature": matching_summary.get("typed_signature", []),
                "matching_summary": matching_summary,
            }
        )
    return lca_matching_summary


def print_lca_matching_summary(lca_matching_summary: Dict[str, Any]) -> None:
    print("\nNon-empty LCA matching summaries:")

    if not lca_matching_summary:
        print("No matching summaries found.")
        return

    for lca_name, summary in lca_matching_summary.items():
        print("\n" + "=" * 80)
        print(f"LCA: {lca_name}")
        print(json.dumps(summary.get("matching_edge_summaries", []), indent=2, default=list))



def deterministic_driver_load(
    G_system: nx.MultiGraph,
    out_json_path: str = "",
) -> Dict[str, Any]:
    """Per-net driver/load annotation derived deterministically from the
    splitter's port_annotations (no LLM call).

    Walks G_system to collect, for every signal net shared between 2+ blocks,
    the hyperedge of endpoint blocks. For each hyperedge, uses each block's
    port_info_keyed_by_name to pick exactly one driver (the block whose port
    direction == "output") and treat the rest as loads.

    Filters:
      - skip dc_bias edges
      - skip supply nets (vdd/vss/gnd/...)
      - skip empty net names

    Driver-pick rules (same logic as the LLM prompt):
      - exactly one endpoint with direction == "output" → that block is driver,
        all others are loads.
      - zero outputs                                    → driver_block_name =
        "outside_circuit", all endpoints are loads (externally driven).
      - two or more outputs                             → ambiguous; fall back
        to "outside_circuit" with all endpoints as loads, and flag the reason.

    Returns the same {"net_driver_metadata": [...]} shape as the LLM version.
    """
    net_to_endpoint_blocks: Dict[str, Set[str]] = {}

    for node_a, node_b, _edge_key, edge_data in G_system.edges(keys=True, data=True):
        if edge_data.get("port_type", "") == "dc_bias":
            continue
        net_name = _normalize_net_name(edge_data.get("net_name", ""))
        if not net_name or net_name in SUPPLY_NETS:
            continue
        net_to_endpoint_blocks.setdefault(net_name, set()).update([str(node_a), str(node_b)])

    records: List[Dict[str, Any]] = []
    for net_name, endpoint_blocks in sorted(net_to_endpoint_blocks.items()):
        endpoints = sorted(endpoint_blocks)
        outputs: List[str] = []
        inputs: List[str] = []
        unknown: List[str] = []
        for block in endpoints:
            port_info = (
                G_system.nodes[block].get("port_info_keyed_by_name", {}) or {}
            ).get(net_name, {}) or {}
            direction = (port_info.get("direction") or "").strip().lower()
            if direction == "output":
                outputs.append(block)
            elif direction == "input":
                inputs.append(block)
            else:
                unknown.append(block)

        if len(outputs) == 1:
            driver = outputs[0]
            loads = [b for b in endpoints if b != driver]
            reason = f"Splitter annotation: '{driver}' has direction=output; others are inputs/unknown."
        elif len(outputs) == 0:
            driver = "outside_circuit"
            loads = endpoints
            reason = "No endpoint annotated as output — treating net as externally driven."
        else:
            driver = "outside_circuit"
            loads = endpoints
            reason = (
                f"Ambiguous: {len(outputs)} endpoints annotated as output ({outputs}); "
                f"falling back to outside_circuit."
            )

        records.append({
            "net_name": net_name,
            "driver_block_name": driver,
            "load_block_names": loads,
            "reason": reason,
        })

    result = {"net_driver_metadata": records}
    if out_json_path:
        with open(out_json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    return result



def run_bottom_up_system_level_analysis(
    tree: Dict[str, Any],
    driver_load_json_path: str,
    model: str = DEFAULT_MODEL_ENDPOINT,
) -> Dict[str, Any]: # Also the bottom-up engine. Call the leaf-level constraint engine here as well.
    # Bucket the system-level net naems into lca_names and their levels
    # Sort the lca_names by their levels, start with the deepest lca
    # each lca becomes the focus point/view point where we have enough global context for an LLM as well as automorphism
    # Also stores the final summaries into the LCAs... for bottom-up by an LLM at the final stage
    # Will also contain the electrical-based constraints going forward

    # First do the structural pass and store info into the LCAs
    # Then do the electrical pass

    # Will also need to take care of inter-node interactions (device matching etc.), by building a "constraint graph" over the hierarchy tree.
    # Should we combine this with the electrical pass? Since anyways deterministic signal edges have been added to buidl a system-level graph.

    # SHould have a call to the leaf engine at the start.
    # SHould have a final LLM pass for bottom-up final intergtation

    G_system = build_system_level_leaf_graph(tree)
    lca_index = index_tree_for_lca(tree)
    parent_map = lca_index["parent_map"]

    # Driver/load per net is derived deterministically from the splitter's
    # port_annotations (direction) stashed on each G_system node — no LLM call.
    driver_load_electrical_intent_net_metadata = deterministic_driver_load(
        G_system,
        out_json_path=driver_load_json_path,
    )

    lca_matching_summary = build_lca_matching_summary_from_system_edges(G_system)
    # print_lca_matching_summary(lca_matching_summary)

    lca_buckets: Dict[str, Dict[str, Any]] = {}

    for node_a, node_b, edge_key, edge_data in G_system.edges(keys=True, data=True):
        lca_name = edge_data.get("lca_name")
        lca_level = edge_data.get("lca_level")
        
        if lca_name not in lca_buckets:
            lca_buckets[lca_name] = {
                "lca_name": lca_name,
                "lca_level": lca_level,
                "edge_keys": [],
                "edge_records": [],
            }
        
        lca_buckets[lca_name]["edge_keys"].append(edge_key)
        lca_buckets[lca_name]["edge_records"].append(
            {
                "node_a": node_a,
                "node_b": node_b,
                "edge_key": edge_key,
                **edge_data,
            }
        )

    lca_processing_order = sorted(
        lca_buckets.keys(),
        key=lambda lca_name: lca_buckets[lca_name]["lca_level"],
        reverse=True,
    )

    '''
    # FUTURE MAY BE. NOT NEEDED NOW.
        G_level_0 : raw leaf-level system graph (G_system)
        G_level_1 : after compressing deepest LCA results
        G_level_2 : after next round
        and so on....
        final top-level graph
    '''

    lca_automorphism_results: Dict[str, Dict[str, Any]] = {}
    lca_net_matching_candidate_results: Dict[str, Dict[str, Any]] = {}

    for lca_name in lca_processing_order:
        local_subgraph = build_lca_local_subgraph(G_system, lca_buckets, lca_name, parent_map=parent_map)
        automorphism_result = run_graph_automorphism_at_lca(local_subgraph) # Block-level
        #hybrid_net_matching_result = run_hybrid_net_matching_at_lca(local_subgraph, automorphism_result, ann_json_path=driver_load_json_path)# Net-Level using the Block-Level Annotations 
        hybrid_net_matching_result = run_hybrid_net_matching_at_lca(local_subgraph, automorphism_result, driver_load_electrical_intent_net_metadata)
        lca_automorphism_results[lca_name] = automorphism_result
        lca_net_matching_candidate_results[lca_name] = hybrid_net_matching_result
    
    # return lca_automorphism_results
    return {
        "structural_automorphism": lca_automorphism_results,
        "hybrid_net_matching": lca_net_matching_candidate_results,
        "matching_summary_by_lca": lca_matching_summary,
    }


def run_hybrid_net_matching_at_lca(
    local_subgraph: nx.MultiGraph,
    automorphism_result: Dict[str, Any],
    driver_load_electrical_intent_net_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    net_to_endpoint_blocks: Dict[str, Set[str]] = {}
    for node_a, node_b, edge_key, edge_data in local_subgraph.edges(keys=True, data=True):
        port_type = edge_data.get("port_type", "")
        if port_type == "dc_bias":
            continue
        
        net_name = _normalize_net_name(edge_data.get("net_name", ""))
        
        if not net_name:
            continue
        
        if net_name in SUPPLY_NETS:
            continue


        if net_name not in net_to_endpoint_blocks:
            net_to_endpoint_blocks[net_name] = set()

        net_to_endpoint_blocks[net_name].add(str(node_a))
        net_to_endpoint_blocks[net_name].add(str(node_b))

    # 2. Build block -> orbit signatures (label).
    # Blocks in the same nontrivial automorphism group get the same label.
    # Singleton/non-symmetric blocks get their own label.
    block_to_orbit_signature: Dict[str, str] = {}
    orbit_groups = (
        automorphism_result.get("candidate_system_level_symmetry_groups", []) or []
    )

    for orbit_index, orbit_group in enumerate(orbit_groups):
        orbit_signature = f"orbit_{orbit_index}"
        for block_name in orbit_group:
            block_to_orbit_signature[str(block_name)] = orbit_signature
    
    for block_name in local_subgraph.nodes():
        block_name = str(block_name)

        if block_name not in block_to_orbit_signature: # Non-symmetric blocks...
            block_to_orbit_signature[block_name] = f"singleton::{block_name}"

    # 3. Now convert each net endpoint block set to an orbit signature.
    net_to_endpoint_orbit_signature: Dict[str, List[str]] = {}
    for net_name, endpoint_blocks in net_to_endpoint_blocks.items():
        endpoint_block_signatures = sorted(block_to_orbit_signature[str(block_name)] for block_name in endpoint_blocks)
        net_to_endpoint_orbit_signature[net_name] = endpoint_block_signatures

    # 4. Convert LLM driver metadata into driver orbit signatures.
    driver_metadata_by_net: Dict[str, Dict[str, Any]] = {}
    for record in driver_load_electrical_intent_net_metadata.get("net_driver_metadata", []) or []:
        if not isinstance(record, dict):
            continue
        net_name = _normalize_net_name(record.get("net_name", ""))
        if not net_name:
            continue
        driver_metadata_by_net[net_name] = record

    net_to_driver_orbit_signature: Dict[str, str] = {}
    for net_name in net_to_endpoint_blocks:
        driver_block_name = str(
            driver_metadata_by_net.get(net_name, {}).get("driver_block_name","")
        )

        if driver_block_name not in block_to_orbit_signature:
            continue

        driver_orbit_signature = block_to_orbit_signature[driver_block_name]
        net_to_driver_orbit_signature[net_name] = driver_orbit_signature

    # 5. Group nets by endpoint orbit signatures + driver orbit signatures.
    endpoint_orbit_signature_to_nets: Dict[Tuple[str, ...], List[str]] = {}
    for net_name, endpoint_block_signature in net_to_endpoint_orbit_signature.items():
        if net_name not in net_to_driver_orbit_signature:
            continue

        driver_orbit_signature = net_to_driver_orbit_signature.get(net_name)
        endpoint_block_signature_key = tuple(
            list(endpoint_block_signature) + [f"driver::{driver_orbit_signature}"]
        )
        if endpoint_block_signature_key not in endpoint_orbit_signature_to_nets:
            endpoint_orbit_signature_to_nets[endpoint_block_signature_key] = []
        endpoint_orbit_signature_to_nets[endpoint_block_signature_key].append(net_name)
    
    # 6. Structural candidate groups are signatures with >1 nets.
    structural_symmetric_net_candidates: List[Dict[str, Any]] = []
    for endpoint_signature_key, nets in endpoint_orbit_signature_to_nets.items():
        if len(nets) <= 1:
            continue
        structural_symmetric_net_candidates.append(
            {
                "candidate_nets": sorted(nets),
                "endpoint_orbit_signature": list(endpoint_signature_key)
            }
        )
    
    
    return {
        "net_to_endpoint_blocks": {
            net_name: sorted(endpoint_blocks)
            for net_name, endpoint_blocks in sorted(net_to_endpoint_blocks.items())
        },
        "net_to_endpoint_orbit_signature": { # Also driver signature?
            net_name: signature
            for net_name, signature in sorted(net_to_endpoint_orbit_signature.items())
        },
        "net_to_driver_orbit_signature": {
            net_name: signature
            for net_name, signature in sorted(net_to_driver_orbit_signature.items())
        },
        "structural_symmetric_net_candidates": structural_symmetric_net_candidates,
    }


    
def build_lca_local_subgraph(
    G_input: nx.MultiGraph,
    lca_buckets: Dict[str, Dict[str, Any]],
    lca_name: str,
    parent_map: Dict[str, Optional[str]],
) -> nx.MultiGraph:
    """
    Build a local subgraph for the LCA buckets and the given system graph.
    - the graph may be G_level_0, G_level_1, ... in future
    """
    if lca_name not in lca_buckets:
        raise ValueError(f"LCA bucket not found: {lca_name}")
    
    local_subgraph = nx.MultiGraph()
    edge_records_to_add: List[Dict[str, Any]] = []

    for bucket_lca_name, bucket in lca_buckets.items():
        if bucket_lca_name == lca_name or is_ancestor(
            ancestor_name=lca_name,
            node_name=bucket_lca_name,
            parent_map=parent_map,
        ):
            edge_records_to_add.extend(bucket.get("edge_records", []))

    for edge_record in edge_records_to_add:
        node_a = edge_record["node_a"]
        node_b = edge_record["node_b"]
        edge_key = edge_record["edge_key"]

        if node_a not in local_subgraph:
            local_subgraph.add_node(node_a, **G_input.nodes[node_a])

        if node_b not in local_subgraph:
            local_subgraph.add_node(node_b, **G_input.nodes[node_b])

        edge_data = G_input.get_edge_data(node_a, node_b, key=edge_key)
        local_subgraph.add_edge(
            node_a,
            node_b,
            key=edge_key,
            **edge_data,
        )

    return local_subgraph

def run_graph_automorphism_at_lca(local_subgraph: nx.MultiGraph) -> Dict[str, Any]:
    # We can use the above LCAs as focus points and call LLMs to assign "intents"and "roles" to the containing edges and "role_description" to the containing nodes.
    """
    # Here are the attributes I plan to use when running system-level automorphism 
    ( attribute-aware automorphism on one LCA-local system graph)

    For block node matching, attributes we will use:
        - `class_category`
        - `template_key`
        - `role_description` would be good (ignoring for now), but since free-text a bit hard unless LLM-driven
    
    For edge matching, attributes we will use:
        - `intent`/`purpose` if possible, but same issue as above.
        - any?
         
    """

    # We can add some LLM-based annotations at this stage to add role behavior and intent of the nets. (FUTURE)

    def _node_match(a, b):
        return (
            a.get("class_category") == b.get("class_category")
            and a.get("template_key") == b.get("template_key")
        )

    matcher = nx.isomorphism.MultiGraphMatcher(
        local_subgraph,
        local_subgraph,
        node_match=_node_match,
    )

    automorphisms = list(matcher.isomorphisms_iter())

    node_orbit_groups: List[List[str]] = []
    seen_nodes = set()
    all_nodes = list(local_subgraph.nodes())

    for node in all_nodes:
        if node in seen_nodes:
            continue
        
        orbit = set()
        for mapping in automorphisms:
            orbit.add(mapping[node])

        node_orbit = sorted(orbit)
        node_orbit_groups.append(node_orbit)
        seen_nodes.update(node_orbit)

    nontrivial_orbit_groups = [
        orbit_group for orbit_group in node_orbit_groups if len(orbit_group) > 1
    ]

    return {
        "candidate_system_level_symmetry_groups": nontrivial_orbit_groups,
        "has_nontrivial_symmetry": len(nontrivial_orbit_groups) > 0,
    }
    



def hierarchy_pos(G, root, width=1.5, vert_gap=0.2, vert_loc=0, xcenter=0.5):
    def _hierarchy_pos(
        G, root, width=1.0, vert_gap=0.2, vert_loc=0, xcenter=0.5, pos=None
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


def _add_edges_from_json_tree(node: Dict[str, Any], G) -> None:
    parent_name = node.get("unique_name", "Unnamed")
    G.add_node(parent_name)

    for child in node.get("children", []) or []:
        child_name = child.get("unique_name", "Unnamed")
        G.add_node(child_name)
        G.add_edge(parent_name, child_name)
        _add_edges_from_json_tree(child, G)


def plot_constraint_tree(tree: Dict[str, Any], title: str = "Constraint Tree", save_path: str = None) -> None:
    G = nx.DiGraph()
    _add_edges_from_json_tree(tree, G)

    root = tree.get("unique_name", "Unnamed")
    pos = hierarchy_pos(G, root, width=1.5, vert_gap=0.2)

    plt.figure(figsize=(14, 8))
    nx.draw(
        G,
        pos=pos,
        with_labels=True,
        arrows=True,
        node_size=1400,
        node_color="#A0CBE2",
        font_size=8,
    )
    plt.title(title)
    plt.axis("off")

    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches="tight")
        print(f"Saved tree plot: {save_path}")
        plt.close()
    else:
        plt.show()


def extract_net_names_from_netlist_str(netlist_text: str) -> Dict[str, Any]:
    """
    Modified parser:
    - Returns both net names and net-to-device mapping
    - Parses only MOS / RES / CAP lines

    Returns:
    {
        "net_name": [
            {
                "M1": {
                    "device_family": "nmos",
                    "model_type": "nch_25ud18_mac",
                    "terminal": "G"
                }
            },
            {
                "M2": {
                    "device_family": "pmos",
                    "model_type": "pch_25ud18_mac",
                    "terminal": "D"
                }
            }
        ]
    }
    """

    net_to_devices: Dict[str, List[Dict[str, Dict[str, str]]]] = {}

    if not netlist_text or not isinstance(netlist_text, str):
        return net_to_devices
    
    def detect_device_model(tokens: List[str]) -> tuple[str, str]:
        lower_tokens = [tok.lower() for tok in tokens]

        for canon_type, variants in device_map.items():
            for variant in variants:
                if variant in lower_tokens:
                    return canon_type, variant

        return "", ""
    
    def add_touch(
        net_name: str,
        dev_name: str,
        device_family: str,
        model_type: str,
        terminal: str,
    ) -> None:
        n = _normalize_net_name(net_name)
        if not n:
            return

        if n not in net_to_devices:
            net_to_devices[n] = []

        net_to_devices[n].append(
            {
                dev_name: {
                    "device_family": device_family,
                    "model_type": model_type,
                    "terminal": terminal,
                }
            }
        )
    
    lines = netlist_text.splitlines()
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("*"):
            continue

        # Handle .SUBCKT ports
        if line.upper().startswith(".SUBCKT"):
            toks = line.split()
            # .SUBCKT <name> <ports...>
            for t in toks[2:]:
                n = _normalize_net_name(t)
                if n not in net_to_devices:
                    net_to_devices[n] = []
            continue

        # Skip most directives
        if line.startswith(".") or line.startswith("+"):
            continue

        toks = line.split()
        if len(toks) < 2:
            continue

        dev_name = toks[0]
        device_family, model_type = detect_device_model(toks)

        if not device_family:
            continue

        # Case: MOSFET: INST_NAME D G S B ...
        if device_family in {"nmos", "pmos"}:
            if len(toks) >= 5:
                for terminal, net_name in zip(("D", "G", "S", "B"), toks[1:5]):
                    add_touch(
                        net_name=net_name,
                        dev_name=dev_name,
                        device_family=device_family,
                        model_type=model_type,
                        terminal=terminal,
                    )
            continue
        
        # Resistor line: first 2 nets after instance name
        if device_family == "res":
            if len(toks) >= 3:
                for terminal, net_name in zip(("N1", "N2"), toks[1:3]):
                    add_touch(
                            net_name=net_name,
                            dev_name=dev_name,
                            device_family=device_family,
                            model_type=model_type,
                            terminal=terminal,
                        )
            continue

        # Capacitor line: first 2 nets after instance name
        if device_family == "cap":
            if len(toks) >= 3:
                for terminal, net_name in zip(("N1", "N2"), toks[1:3]):
                    add_touch(
                        net_name=net_name,
                        dev_name=dev_name,
                        device_family=device_family,
                        model_type=model_type,
                        terminal=terminal,
                    )
            continue

        # Ignore all other device type cases for now (prototype)
        continue

    return net_to_devices


def add_local_net_set_to_all_nodes(node: Dict[str, Any]) -> None:
    """
    Annotate each node with deterministic local net metadata from node["netlist"].

    Stores:
      node["_local_net_set"]: set
      node["_local_net_to_devices"]: dict[str, list[dict]]

    """
    netlist_text = node.get("netlist", "") or ""
    net_to_devices = extract_net_names_from_netlist_str(netlist_text)
    net_names = set(sorted(net_to_devices.keys()))
    node["_local_net_set"] = net_names
    node["_local_net_to_devices"] = net_to_devices
    
    for child in (node.get("children", []) or []):
        add_local_net_set_to_all_nodes(child)


def _make_shared_net_id(node_a: str, node_b: str, net_name: str) -> str:
    a, b = sorted([str(node_a), str(node_b)])
    return f"{a}|{b}|{_normalize_net_name(net_name)}"



def index_tree_for_lca(tree: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds lookup maps using unique_name as node id.
    Returns:
      {
        "node_map": {name: node_dict},
        "parent_map": {child_name: parent_name_or_None},
        "depth_map": {name: depth}
      }
    """
    node_map: Dict[str, Dict[str, Any]] = {}
    parent_map: Dict[str, Optional[str]] = {}
    depth_map: Dict[str, int] = {}

    def dfs(node: Dict[str, Any], parent: Optional[str], depth: int) -> None:
        name = node.get("unique_name")
        if not name:
            raise ValueError("Every node must have unique_name for LCA/indexing.")
        if name in node_map:
            raise ValueError(f"Duplicate unique_name detected: {name}")

        node_map[name] = node
        parent_map[name] = parent
        depth_map[name] = depth

        for child in node.get("children", []) or []:
            dfs(child, name, depth + 1)

    dfs(tree, None, 0)
    return {
        "node_map": node_map,
        "parent_map": parent_map,
        "depth_map": depth_map,
    }


def is_ancestor(
    ancestor_name: str,
    node_name: str,
    parent_map: Dict[str, Optional[str]],
) -> bool:
    """
    True if ancestor_name is a strict ancestor of node_name.
    """
    cur = parent_map.get(node_name)
    while cur is not None:
        if cur == ancestor_name:
            return True
        cur = parent_map.get(cur)
    return False



def find_lca_name(
    node_a: str,
    node_b: str,
    parent_map: Dict[str, Optional[str]],
    depth_map: Dict[str, int],
) -> Optional[str]:
    """
    Lowest Common Ancestor by climbing parents.
    Returns the unique_name of the LCA.
    """
    a = node_a
    b = node_b
    da = depth_map[a]
    db = depth_map[b]

    # Lift deeper one
    while da > db:
        a = parent_map[a]
        da -= 1
    while db > da:
        b = parent_map[b]
        db -= 1

    # Climb together
    while a != b:
        a = parent_map[a]
        b = parent_map[b]
        if a is None or b is None:
            return None

    return a

def build_enriched_tree_from_split_sources(
    hierarchy_tree_path: str,
    circuit_global_context_path: str,
) -> Dict[str, Any]:
    """
    Merge:
    - hierarchy_dendrogram_cleaned.json
    - circuit_global_context.json   (now embeds class_category + port_annotations
                                     directly per subcircuit, produced by the splitter)

    into one hierarchy tree usable by run_bottom_up_system_level_analysis(...).
    """
    hierarchy_tree = load_json(hierarchy_tree_path)
    circuit_global_context = load_json(circuit_global_context_path)

    subcircuits = circuit_global_context.get("subcircuits", []) or []

    global_info_by_id: Dict[str, Dict[str, Any]] = {}
    for subckt_block in subcircuits:
        key = subckt_block.get("id", subckt_block.get("unique_name", ""))
        if key:
            global_info_by_id[key] = subckt_block

    # The splitter's per-subcircuit dict already carries class_category and
    # port_annotations, so port_info_by_id and global_info_by_id are the same map.
    port_info_by_id = global_info_by_id

    def enrich_node(node: Dict[str, Any]) -> Dict[str, Any]:
        node_id = node.get("unique_name", "")
        children = node.get("children", []) or []
        port_info = port_info_by_id.get(node_id, {})
        global_info = global_info_by_id.get(node_id, {})

        enriched_node = {
            "unique_name": node_id,
        }

        # Adding metadata/payload
        if "class_category" in port_info:
            enriched_node["class_category"] = port_info.get("class_category", "")

        if "role_hint" in global_info:
            enriched_node["role_hint"] = global_info.get("role_hint", "")
            # Keep role_description aligned with role_hint for now
            enriched_node["role_description"] = global_info.get("role_hint", "")

        if "netlist" in global_info:
            enriched_node["netlist"] = global_info.get("netlist", "")

        if "port_annotations" in port_info:
            port_info_keyed_by_name = {}

            for port_record in port_info.get("port_annotations", []) or []:
                #port_name = port_record.get("port_name")
                port_name = _normalize_net_name(port_record.get("port_name", ""))
                if not port_name:
                    continue

                port_info_keyed_by_name[port_name] = {
                    "port_type": port_record.get("port_type", ""),
                    "direction": port_record.get("direction", ""),
                }

            enriched_node["port_info_keyed_by_name"] = port_info_keyed_by_name

        enriched_node["children"] = [enrich_node(child) for child in children]
        return enriched_node

    return enrich_node(hierarchy_tree)


# Inverse for net_to_devices
def build_device_terminal_lookup(
    net_to_devices: Dict[str, List[Dict[str, Dict[str, str]]]]
) -> Dict[str, Dict[str, Any]]:
    device_lookup = {}

    for net_name, device_records in net_to_devices.items():
        normalized_net = _normalize_net_name(net_name)

        for device_record in device_records:
            for device_name, device_info in device_record.items():
                if device_name not in device_lookup:
                    device_lookup[device_name] = {
                        "device_family": device_info.get("device_family", ""),
                        "model_type": device_info.get("model_type", ""),
                        "terminals": {},
                    }

                terminal = device_info.get("terminal", "")
                device_lookup[device_name]["terminals"][terminal] = normalized_net

    return device_lookup


def find_simple_conduction_signature_to_supply(
    seed_device_name: str,
    net_to_devices: Dict[str, List[Dict[str, Dict[str, str]]]],
) -> Dict[str, Any]:
    device_lookup = build_device_terminal_lookup(net_to_devices)

    seed_device = device_lookup[seed_device_name]
    seed_model = seed_device.get("model_type", "")
    current_net = seed_device["terminals"]["S"]

    typed_signature = [f"{seed_model}.G-S"]
    
    path_devices = [seed_device_name]
    used_devices = {seed_device_name}

    while current_net not in SUPPLY_NETS:
        next_step_found = False

        for device_record in net_to_devices.get(current_net, []):
            for device_name, device_info in device_record.items():
                if device_name in used_devices:
                    continue

                terminal = device_info.get("terminal", "")

                # Only D/S are valid conduction path entry terminals.
                if terminal not in {"D", "S", "N1", "N2"}:
                    continue

                device = device_lookup[device_name]
                device_family = device.get("device_family", "")
                model_type = device.get("model_type", "")
                terminals = device["terminals"]

                if device_family == "nmos" and terminal == "D":
                    exit_terminal = "S"
                elif device_family == "pmos" and terminal == "D":
                    exit_terminal = "S"
                elif terminal == "N1":
                    exit_terminal = "N2"
                elif terminal == "N2":
                    exit_terminal = "N1"
                else:
                    continue

                typed_signature.append(f"{model_type}.{terminal}-{exit_terminal}")
                path_devices.append(device_name)
                used_devices.add(device_name)
                current_net = terminals[exit_terminal]

                next_step_found = True
                break

            if next_step_found:
                break

        if not next_step_found:
            break

    closest_supply = current_net if current_net in SUPPLY_NETS else ""

    if closest_supply:
        typed_signature.append(f"SUPPLY:{closest_supply}")

    return {
        "typed_signature": typed_signature,
        "path_length": len(path_devices),
        "closest_supply": closest_supply,
        "path_devices": path_devices,
    }


def compute_typed_signature_per_touching_matching_group(
    leaf_node: Dict[str, Any],
    net_name: str,
) -> Dict[str, Any]:
    """
    Compute typed path signatures for devices touching `net_name` in one leaf node.

    Return format:
    {
        "matching_group": {...},
        "typed_signature": ["nch_25ud18_mac.G-S", "nch_25ud18_mac.D-S", "SUPPLY:vss"], # Since "device matching" concerns correlated mismatch under PVT (for example similar Vt variation), which directly impacts current mirroring and influences the overdrive conditions of stacked devices. This signature therefore serves as a practical structural proxy for identifying device groups where matching is functionally required in the first place (e.g., current mirrors/cascodes).
        "path_length": 2,
        "driver": yes/no,
    }
    """
    # Case 1: the net is connected to a diode connected MOS. ("driver" node)
    # 1a. this that MOS already part of a matching group. If yes return the matching group.
    # 1b. if just 1 diode MOS and no other device gates, then return just the mos name as matching group (singleton set)
    # So return (matching group, signature)

    # Case 2: the net is connected to only gates and not diodes, then load
    # 2a. 
    # return [(matching_groups, signatures),....]
    # If signatures match with node "driver" and node "load", then matching groups be merged

    ##### Assume at the net name is tagged dc_bias within this function. We will add more logic outside (similar to dc_bias_edge_to_nodes)

    def _is_diode_connected_from_touching_terminals(terminals: Set[str]) -> bool:
        return "G" in terminals and "D" in terminals and "S" not in terminals

    def _find_matching_group_for_device_sym(
        leaf_node: Dict[str, Any],
        device_name: str,
    ) -> Set[str]:
        constraints = leaf_node.get("constraints", {}) or {}
        
        # Manual prototype....
        # matching_groups = constraints.get("matching_groups", []) or []
        
        # Leaf Integration Now.....
        # constraints is now ALIGN-style list (Kaichang constraints)
        matching_groups = []
        if isinstance(constraints, list):
            # Collect only real 2-device pairs from SymmetricBlocks
            pair_list = []
            for c in constraints:
                if not isinstance(c, dict) or c.get("constraint") != "SymmetricBlocks":
                    continue
                for p in (c.get("pairs", []) or []):
                    if not isinstance(p, list) or len(p) != 2:
                        continue  # skip singleton/self-axis entries like ["M1"]
                    a, b = str(p[0]).lower(), str(p[1]).lower()
                    if not a or not b or a == b:
                        continue
                    pair_list.append((a, b))

            # Merge chain-overlapping pairs into groups
            if pair_list:
                nodes = set()
                for a, b in pair_list:
                    nodes.add(a)
                    nodes.add(b)
                
                parent = {n: n for n in nodes}
                rank = {n: 0 for n in nodes}

                def find(x):
                    while parent[x] != x:
                        parent[x] = parent[parent[x]]
                        x = parent[x]
                    return x

                def union(a, b):
                    ra, rb = find(a), find(b)
                    if ra == rb:
                        return
                    if rank[ra] < rank[rb]:
                        parent[ra] = rb
                    elif rank[ra] > rank[rb]:
                        parent[rb] = ra
                    else:
                        parent[rb] = ra
                        rank[ra] += 1

                for a, b in pair_list:
                    union(a, b)

                comps = {}
                for n in nodes:
                    r = find(n)
                    comps.setdefault(r, set()).add(n)

                gid = 0
                for devs in comps.values():
                    devs_sorted = sorted(devs)
                    if len(devs_sorted) >= 2:
                        matching_groups.append({
                            "group_id": f"match_group_{gid}",
                            "devices": devs_sorted
                        })
                        gid += 1


        device_name_l = str(device_name).lower()
        for group in matching_groups:
            devices = {str(d).lower() for d in (group.get("devices", []) or [])}
            #devices = set(group.get("devices", []) or [])
            #if device_name in devices:
            if device_name_l in devices:
                return devices

        return set()

    
    def _find_matching_group_for_device_match(
        leaf_node: Dict[str, Any],
        device_name: str,
    ) -> Set[str]:
        constraints = leaf_node.get("constraints", {}) or {}
        
        # Manual prototype....
        # matching_groups = constraints.get("matching_groups", []) or []
        
        # Leaf Integration Now.....
        # constraints is now ALIGN-style list (Kaichang constraints)
        matching_groups = []
        if isinstance(constraints, list):
            # Collect only real 2-device pairs from MatchDevices
            pair_list = []
            for c in constraints:
                if not isinstance(c, dict) or c.get("constraint") != "MatchDevices":
                    continue
                for p in (c.get("pairs", []) or []):
                    if not isinstance(p, list) or len(p) != 2:
                        continue  # skip singleton/self-axis entries like ["M1"]
                    a, b = str(p[0]).lower(), str(p[1]).lower()
                    if not a or not b or a == b:
                        continue
                    pair_list.append((a, b))

            # Merge chain-overlapping pairs into groups
            if pair_list:
                nodes = set()
                for a, b in pair_list:
                    nodes.add(a)
                    nodes.add(b)
                
                parent = {n: n for n in nodes}
                rank = {n: 0 for n in nodes}

                def find(x):
                    while parent[x] != x:
                        parent[x] = parent[parent[x]]
                        x = parent[x]
                    return x

                def union(a, b):
                    ra, rb = find(a), find(b)
                    if ra == rb:
                        return
                    if rank[ra] < rank[rb]:
                        parent[ra] = rb
                    elif rank[ra] > rank[rb]:
                        parent[rb] = ra
                    else:
                        parent[rb] = ra
                        rank[ra] += 1

                for a, b in pair_list:
                    union(a, b)

                comps = {}
                for n in nodes:
                    r = find(n)
                    comps.setdefault(r, set()).add(n)

                gid = 0
                for devs in comps.values():
                    devs_sorted = sorted(devs)
                    if len(devs_sorted) >= 2:
                        matching_groups.append({
                            "group_id": f"match_group_{gid}",
                            "devices": devs_sorted
                        })
                        gid += 1


        device_name_l = str(device_name).lower()
        for group in matching_groups:
            devices = {str(d).lower() for d in (group.get("devices", []) or [])}
            #devices = set(group.get("devices", []) or [])
            #if device_name in devices:
            if device_name_l in devices:
                return devices

        return set()
    
    normalized_net_name = _normalize_net_name(net_name)
    net_to_devices = leaf_node.get("_local_net_to_devices", {}) or {}
    touching_devices_in_node_info = net_to_devices.get(normalized_net_name, [])

    # device_name -> collected info for this net and node only
    device_touch_summary: Dict[str, Dict[str, Any]] = {}

    for device_record in touching_devices_in_node_info:
        for device_name, device_info in device_record.items():
            terminal = device_info.get("terminal", "")
            
            # Only MOS devices matter for now: concept testing....
            if device_info.get("device_family") not in {"nmos", "pmos"}:
                continue

            # Drop body terminal touches for this prototype.
            if terminal == "B":
                continue

            if device_name not in device_touch_summary:
                device_touch_summary[device_name] = {
                    "device_name": device_name,
                    "device_family": device_info.get("device_family", ""),
                    "model_type": device_info.get("model_type", ""),
                    "terminals": set(),
                }

            device_touch_summary[device_name]["terminals"].add(terminal)

    diode_connected_devices = []
    gate_only_devices = []

    for device_name, summary in device_touch_summary.items():
        terminals = summary["terminals"]

        if _is_diode_connected_from_touching_terminals(terminals):
            diode_connected_devices.append(summary)

        elif terminals == {"G"}:
            gate_only_devices.append(summary)
    
    # Case 1: driver side
    if diode_connected_devices:
        is_driver = True
    
    # Case 2: load side
    else:
        is_driver = False

    # Now derive the signature. Preference order as follows...        
    if diode_connected_devices: # Since driver so #1 priority
        # Using only the first device of this list for now
        seed_device_name = diode_connected_devices[0]["device_name"]
        #matching_group = {seed_device_name}
        
        '''
        matching_group = {str(seed_device_name).lower()}
        
        # See if any matching group of this leaf node consists of this device. If yes, we have to retrieve that group set as well.

        retrieved_group = _find_matching_group_for_device_sym(
            leaf_node=leaf_node,
            device_name=seed_device_name,
        )
        matching_group.update(retrieved_group)
        '''

        matching_group_sym = {str(seed_device_name).lower()}
        matching_group_match = {str(seed_device_name).lower()}
        
        # See if any matching group of this leaf node consists of this device. If yes, we have to retrieve that group set as well.
        retrieved_group_sym = _find_matching_group_for_device_sym(
            leaf_node=leaf_node,
            device_name=seed_device_name,
        )
        matching_group_sym.update(retrieved_group_sym)

        retrieved_group_match = _find_matching_group_for_device_match(
            leaf_node=leaf_node,
            device_name=seed_device_name,
        )
        matching_group_match.update(retrieved_group_match)

        conduction_path_info = find_simple_conduction_signature_to_supply(seed_device_name=seed_device_name, net_to_devices=net_to_devices) 
        typed_signature = conduction_path_info["typed_signature"]
        path_length = conduction_path_info["path_length"]
        closest_supply = conduction_path_info["closest_supply"]
        path_devices = conduction_path_info["path_devices"]


    elif gate_only_devices: # Since then load, and thus #2 priority
        # Similar logic as the above diode connected case
        seed_device_name = gate_only_devices[0]["device_name"]
        #matching_group = {seed_device_name}
        
        '''
        matching_group = {str(seed_device_name).lower()}
        retrieved_group = _find_matching_group_for_device_sym(
            leaf_node=leaf_node,
            device_name=seed_device_name,
        )
        matching_group.update(retrieved_group)
        '''

        matching_group_sym = {str(seed_device_name).lower()}
        matching_group_match = {str(seed_device_name).lower()}

        retrieved_group_sym = _find_matching_group_for_device_sym(
            leaf_node=leaf_node,
            device_name=seed_device_name,
        )
        matching_group_sym.update(retrieved_group_sym)

        retrieved_group_match = _find_matching_group_for_device_match(
            leaf_node=leaf_node,
            device_name=seed_device_name,
        )
        matching_group_match.update(retrieved_group_match)

        conduction_path_info = find_simple_conduction_signature_to_supply(seed_device_name=seed_device_name, net_to_devices=net_to_devices) 
        typed_signature = conduction_path_info["typed_signature"]
        path_length = conduction_path_info["path_length"]
        closest_supply = conduction_path_info["closest_supply"]
        path_devices = conduction_path_info["path_devices"]

    else: # default
        # Since that means neither signature nor the matching group message not important to be passed from this node 
        
        #matching_group = []

        matching_group_sym = []
        matching_group_match = []
        typed_signature = []
        path_length = 0
        closest_supply = None
        path_devices = []
        
    

    return {
        #"matching_group": sorted(matching_group), #matching_group,
        "matching_group": {
            "sym": sorted(matching_group_sym),
            "match": sorted(matching_group_match),
        },
        "typed_signature": typed_signature,
        "path_length": path_length,
        "driver": is_driver,
        "closest_supply": closest_supply,
        "path_devices": path_devices,
    }


    

def load_leaf_constraints_from_directory(
    tree: Dict[str, Any],
    constraints_dir: str,
) -> Dict[str, Any]:
    leaves = identify_leaf_nodes(tree)
    for leaf in leaves:
        leaf_name = leaf.get("unique_name", leaf.get("id", ""))
        safe_leaf_name = leaf_name.replace(" ", "_")
        constraint_path = os.path.join(constraints_dir, f"{safe_leaf_name}.json")

        if not os.path.exists(constraint_path):
            leaf["constraints"] = {}
            continue

        with open(constraint_path, "r", encoding="utf-8") as f:
            raw_text = f.read().strip()
        
        if not raw_text:
            leaf["constraints"] = {}
        else:
            leaf["constraints"] = json.loads(raw_text)
    
    return tree


def initialize_manual_leaf_constraint_files(
    leaves: List[Dict[str, Any]],
    generated_dir: str,
) -> None:
    manual_constraint_dir = os.path.join(generated_dir,"Leaf_Constraints", "Manual_Testing")
    os.makedirs(manual_constraint_dir, exist_ok=True)
    for leaf in leaves:
        leaf_name = leaf.get("unique_name", leaf.get("id",""))
        safe_file_name = leaf_name.replace(" ", "_")
        constraint_path = os.path.join(manual_constraint_dir, f"{safe_file_name}.json")

        if os.path.exists(constraint_path):
            continue

        with open(constraint_path, "w", encoding="utf-8"):
            pass


def summarize_matching_signature_interaction(
    node_a_signature: Dict[str, Any],
    node_b_signature: Dict[str, Any],
) -> Dict[str, Any]:
    signature_a = node_a_signature.get("typed_signature", []) if node_a_signature else []
    signature_b = node_b_signature.get("typed_signature", []) if node_b_signature else []

    empty_matching_group = {
        "sym": [],
        "match": [],
    }

    if not signature_a or not signature_b:
        return {
            "matching_group": empty_matching_group,
            "typed_signature": [],
            "matched": False,
        }

    if signature_a != signature_b:
        return {
            "matching_group": empty_matching_group,
            "typed_signature": [],
            "matched": False,
        }

    group_a = node_a_signature.get("matching_group", {}) or {}
    group_b = node_b_signature.get("matching_group", {}) or {}

    matching_group = {
        "sym": sorted(
            set(group_a.get("sym", []) or [])
            | set(group_b.get("sym", []) or [])
        ),
        "match": sorted(
            set(group_a.get("match", []) or [])
            | set(group_b.get("match", []) or [])
        ),
    }

    return {
        "matching_group": matching_group,
        "typed_signature": signature_a,
        "matched": True
    }


def accumulate_constraints_bottom_up_v0(
    tree: Dict[str, Any],
    generated_dir:str,
    output_dir: Optional[str] = None,
    with_reasoning: bool = False,
    leaf_variation: int = 0,
    kb_only_threshold: float = 0.50,
    complexity_cap: int = 15,
    model: str = DEFAULT_MODEL_ENDPOINT,
) -> Dict[str, Any]:
    """
    V0 pipeline:
    1. Run leaf engine on leaves -> store in leaf["constraints"]. Initially is was being loaded from manual files.)
    2. Store the Leaf Constraints in :  mkdir Automated_Hybrid_Engine within the same Leaf_Constraints folder if not present and just refer to this instead of the manual
    3. Run the message passing for inter-node interactions/devcie maching, structural automorphism, System-level net matching and SameTemplate flows instead of running in the main function
    4. Store and Verify all the above info into the LCAs. Build per-LCA summary buckets:
        - SameTemplate
        - SymmetricBlocks
        - System-Level_Net_Matching
        - Device_Matching
    5. Placeholder for future agentic LCA-guided bottom-up accumulation.
    6. Schema to make it compitable to ALIGN compiler
    """
    
    output_dir = output_dir or generated_dir
    # All constraint-related artifacts live under a single constraints/ umbrella:
    #   <output_dir>/constraints/
    #       Leaf_Constraints/Automated_Hybrid_Engine/<leaf>.json
    #       system_level/Net_Driver_Load.json, System_Level_*.json
    constraints_dir = os.path.join(output_dir, "constraints")
    system_level_dir = os.path.join(constraints_dir, "system_level")
    os.makedirs(system_level_dir, exist_ok=True)
    driver_load_json_path = os.path.join(system_level_dir, "Net_Driver_Load.json")
    
    
    # -----------------------------
    # Step 1: leaf-level constraints (Either run the engine or just load from the directory): supports both manual and automated
    # -----------------------------
    # Expected to create a leaf-wise folder just like manual constraints and fill leaf["constraints"] now
    
    automated_constraints_dir = os.path.join(constraints_dir, "Leaf_Constraints", "Automated_Hybrid_Engine")

    tree = run_constraint_extraction_on_leaves(
        tree=tree,
        constraints_dir=automated_constraints_dir,
        with_reasoning=with_reasoning,
        rerun=False,   # False = read cached files, True = regenerate
        variation=leaf_variation,
        kb_only_threshold=kb_only_threshold,
        complexity_cap=complexity_cap,
        model=model,
        metrics_save_path=os.path.join(constraints_dir, "Leaf_Constraints", "llm_metrics.json"),
    )

    # exit()

    # Then just repeat what we are doing in the main function currently.
    bottom_up_results = run_bottom_up_system_level_analysis(
        tree,
        driver_load_json_path=driver_load_json_path,
        model=model,
    )
    save_json(
        os.path.join(system_level_dir, "System_Level_Automorphism.json"),
        bottom_up_results["structural_automorphism"],
    )

    print("Saved system-level automorphism analysis.")

    save_json(
        os.path.join(system_level_dir, "System_Level_Matching_Summary.json"),
        bottom_up_results["matching_summary_by_lca"],
    )

    print("Saved system-level inter-node message passing-based matching analysis.")

    save_json(
        os.path.join(system_level_dir, "System_Level_Net_Matching_Candidates.json"),
        bottom_up_results["hybrid_net_matching"],
    )

    print("Saved system-level net-matching analysis.")

    # Agentic Call to Summarize and return
    tree = prepare_bottom_up_payload_nodewise(
        tree=tree,
        bottom_up_results=bottom_up_results,
    )

    # print_device_matching_payloads(tree)
    # exit()

    final_align_constraints = summarize_final_align_constraints_bottom_up(
        tree=tree,
        driver_load_json_path=driver_load_json_path,
        bottom_up_results=bottom_up_results,
        model=model,
        metrics_save_path=os.path.join(system_level_dir, "llm_metrics.json"),
    )
    save_json(
        os.path.join(system_level_dir, "Final_ALIGN_Constraints.json"),
        final_align_constraints,
    )
    
    print("Saved final full-circuit ALIGN constraints.")

    return tree


def prepare_bottom_up_payload_nodewise(
    tree: Dict[str, Any],
    bottom_up_results: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Attach a compact per-node payload into the tree for later LLM translation.

    Each node gets:
    node["bottom_up_payload"] = {
        "same_template_blocks": [...],
        "device_matching_sym": [...],
        "device_matching": [...],
        "system_level_net_matching": [...],
        "block_symmetry": [...],
    }
    """
    inter_node_device_matching_summary_by_lca = bottom_up_results["matching_summary_by_lca"]
    system_level_net_matching_by_lca = bottom_up_results["hybrid_net_matching"]
    block_level_structural_automorphism_by_lca = bottom_up_results["structural_automorphism"]

    def _extract_device_group(node_name: str, group_tag: str) -> List[List[str]]: # Cleaning
        summary_payload = inter_node_device_matching_summary_by_lca.get(node_name, {}) or {}
        edge_summaries = summary_payload.get("matching_edge_summaries", []) or []
        out = []
        seen = set()

        for edge_record in edge_summaries:
            matching_summary = edge_record.get("matching_summary", {}) or {}
            matching_group_payload = matching_summary.get("matching_group", {}) or {}
            matching_group = matching_group_payload.get(group_tag, []) or []
            matching_group = sorted({str(x).lower() for x in matching_group if str(x)})
            if len(matching_group) < 2:
                continue
            
            fp = tuple(matching_group)
            if fp in seen:
                continue
            seen.add(fp)
            out.append(matching_group)

        return out


    def _extract_system_level_net_matching(node_name: str) -> List[List[str]]: # Cleaning
        summary_payload = system_level_net_matching_by_lca.get(node_name, {}) or {}
        groups = summary_payload.get("structural_symmetric_net_candidates", []) or []

        out = []
        for group in groups:
            if not isinstance(group, dict):
                continue
            out.append(group.get("candidate_nets",[]) or [])

        return out


    def _extract_block_symmetry(node_name: str) -> List[List[str]]: # Cleaning
        summary_payload = block_level_structural_automorphism_by_lca.get(node_name, {}) or {}
        groups = summary_payload.get("candidate_system_level_symmetry_groups", []) or []
        out = []
        seen = set()

        for group in groups:
            if not isinstance(group, list):
                continue

            group_sorted = sorted([str(x) for x in group if str(x)])
            if len(group_sorted) < 2:
                continue

            fp = tuple(group_sorted)
            if fp in seen:
                continue
            seen.add(fp)

            out.append(group_sorted)

        return out


    def _walk(node: Dict[str, Any]) -> None:
        node_name = node.get("unique_name", node.get("id", ""))

        node["bottom_up_payload"] = {
            #"same_template_blocks": [],   # ignored for now
            "device_matching_sym": _extract_device_group(node_name, "sym"),
            "device_matching": _extract_device_group(node_name, "match"),
            "system_level_net_matching": _extract_system_level_net_matching(node_name),
            "block_symmetry": _extract_block_symmetry(node_name),
        }

        for child in (node.get("children", []) or []):
            _walk(child)

    _walk(tree)
    return tree


def print_device_matching_payloads(tree: Dict[str, Any]) -> None:
    def _walk(node: Dict[str, Any]) -> None:
        node_name = node.get("unique_name", node.get("id", ""))
        payload = node.get("bottom_up_payload", {}) or {}
        device_matching_sym = payload.get("device_matching_sym", []) or []
        device_matching = payload.get("device_matching", []) or []

        print("\n" + "=" * 80)
        print(f"Node: {node_name}")
        print("device_matching_sym:")
        print(json.dumps(device_matching_sym, indent=2))
        print("device_matching:")
        print(json.dumps(device_matching, indent=2))
        

        for child in (node.get("children", []) or []):
            _walk(child)

    _walk(tree)


def build_compact_tree_for_llm(node: Dict[str, Any]) -> Dict[str, Any]:
    children = node.get("children", []) or []
    compact_node = {
        "unique_name": node.get("unique_name", ""),
        "class_category": node.get("class_category", ""),
        "role_description": node.get("role_description", ""),
        "children": [
            build_compact_tree_for_llm(child)
            for child in children
        ],
    }

    if children:
        compact_node["node_constraint_evidence"] = node.get("bottom_up_payload", {}) or {}
    else: #leaves
        compact_node["constraints"] = node.get("constraints")
        compact_node["netlist"] = node.get("netlist")

    return compact_node


# ═══════════════════════════════════════════════════════════════════════════════
# M3 — Hygiene post-pass for the final system-level ALIGN constraints.
# Mirrors what the leaf engine does after every LLM variation
# (engine:2587-2593), but executed at the full-circuit level.
# ═══════════════════════════════════════════════════════════════════════════════

_CONSTRAINT_REQUIRED_FIELDS: Dict[str, List[str]] = {
    "SymmetricBlocks": ["direction", "pairs"],
    "MatchDevices": ["direction", "pairs"],
    "Order": ["instances", "direction"],
    "Align": ["instances", "line"],
    "AlignInOrder": ["instances", "line", "direction"],
    "GroupBlocks": ["name", "instances"],
    "SymmetricNets": ["net1", "net2", "direction"],
    "NetConst": ["nets"],
    "PowerPorts": ["ports"],
    "GroundPorts": ["ports"],
    "PortLocation": ["ports", "location"],
    "CompactPlacement": ["style"],
    "SameTemplate": ["instances"],
}


def _collect_leaf_netlist_artifacts(
    tree: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, str]]:
    """Walk all leaves, parse each leaf's SPICE netlist, and return:

    * merged device list across leaves,
    * union of circuit ports across leaves,
    * device_name -> leaf unique_name map.
    """
    leaves = identify_leaf_nodes(tree)
    merged_devices: List[Dict[str, Any]] = []
    merged_ports: List[str] = []
    dev_to_leaf: Dict[str, str] = {}
    seen_ports: Set[str] = set()
    seen_devs: Set[str] = set()

    for leaf in leaves:
        netlist_text = leaf.get("netlist") or ""
        if not netlist_text.strip():
            continue
        try:
            _cname, cports, devs = parse_netlist_general(netlist_text)
        except ValueError:
            continue
        for p in cports:
            pl = p.lower()
            if pl not in seen_ports:
                seen_ports.add(pl)
                merged_ports.append(p)
        leaf_name = leaf.get("unique_name", "")
        for d in devs:
            name = d.get("name", "")
            key = name.lower()
            if not name or key in seen_devs:
                continue
            seen_devs.add(key)
            merged_devices.append(d)
            dev_to_leaf[key] = leaf_name

    return merged_devices, merged_ports, dev_to_leaf


def _normalize_case_recursive(constraints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Lowercase every instance / pair / port / net field per ALIGN convention."""
    lower_fields_listofstr = ("instances", "ports", "nets")
    lower_fields_str = ("net1", "net2", "name")

    out: List[Dict[str, Any]] = []
    for c in constraints:
        if not isinstance(c, dict):
            continue
        new_c = dict(c)
        for f in lower_fields_listofstr:
            if f in new_c and isinstance(new_c[f], list):
                new_c[f] = [str(x).lower() for x in new_c[f] if isinstance(x, (str, int))]
        for f in lower_fields_str:
            if f in new_c and isinstance(new_c[f], str):
                new_c[f] = new_c[f].lower()
        if new_c.get("constraint") in {"SymmetricBlocks", "MatchDevices"} and isinstance(new_c.get("pairs"), list):
            fixed_pairs = []
            for pr in new_c["pairs"]:
                if isinstance(pr, (list, tuple)):
                    fixed_pairs.append([str(x).lower() for x in pr])
            new_c["pairs"] = fixed_pairs
        out.append(new_c)
    return out


def _drop_unknown_instances(
    constraints: List[Dict[str, Any]],
    legal_names: Set[str],
) -> List[Dict[str, Any]]:
    """Drop references to device names that don't exist in any leaf netlist.

    Constraint-type-aware: `SymmetricBlocks.pairs`, `*.instances`,
    `SameTemplate.instances`, `GroupBlocks.instances` are filtered; constraints
    whose core reference list becomes empty are dropped entirely. Port / net
    constraints are passed through untouched (they reference nets, not insts).
    """
    out: List[Dict[str, Any]] = []
    for c in constraints:
        if not isinstance(c, dict):
            continue
        ctype = c.get("constraint")
        new_c = dict(c)
        if ctype in {"SymmetricBlocks", "MatchDevices"}:
            kept_pairs = []
            for pr in new_c.get("pairs", []) or []:
                if not isinstance(pr, list):
                    continue
                if all(str(x).lower() in legal_names for x in pr):
                    kept_pairs.append(pr)
            if not kept_pairs:
                continue
            new_c["pairs"] = kept_pairs
        elif ctype in ("Order", "Align", "AlignInOrder", "SameTemplate", "GroupBlocks"):
            kept = [x for x in new_c.get("instances", []) or []
                    if str(x).lower() in legal_names]
            min_needed = 1 if ctype == "GroupBlocks" else 2
            if len(kept) < min_needed:
                continue
            new_c["instances"] = kept
        out.append(new_c)
    return out


def _validate_schema(constraints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop constraints missing the mandatory fields for their type."""
    out: List[Dict[str, Any]] = []
    for c in constraints:
        if not isinstance(c, dict):
            continue
        ctype = c.get("constraint")
        if ctype not in _CONSTRAINT_REQUIRED_FIELDS:
            print(f"[hygiene] dropping unknown constraint type: {ctype!r}")
            continue
        missing = [f for f in _CONSTRAINT_REQUIRED_FIELDS[ctype]
                   if f not in c or c[f] in (None, "", [], {})]
        if missing:
            print(f"[hygiene] dropping malformed {ctype}: missing {missing}")
            continue
        out.append(c)
    return out


def _clean_match_devices(constraints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep only valid two-device MatchDevices pairs and dedupe them."""
    out: List[Dict[str, Any]] = []
    for c in constraints:
        if not isinstance(c, dict) or c.get("constraint") != "MatchDevices":
            out.append(c)
            continue

        clean_pairs: List[List[str]] = []
        seen_pairs: Set[frozenset] = set()
        for pr in c.get("pairs", []) or []:
            if not isinstance(pr, (list, tuple)) or len(pr) != 2:
                continue
            a, b = str(pr[0]).lower(), str(pr[1]).lower()
            if not a or not b or a == b:
                continue
            key = frozenset({a, b})
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            clean_pairs.append([a, b])

        if clean_pairs:
            new_c = dict(c)
            new_c["pairs"] = clean_pairs
            out.append(new_c)

    return out


def postprocess_system_align_constraints(
    raw_constraints: List[Dict[str, Any]],
    tree: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Apply the leaf-engine hygiene pipeline to the system-level LLM output.

    Flow: normalize_case -> drop_unknown_instances -> validate_schema ->
    _filter_bad_sym_pairs (with cross-coupled exempts) -> _clean_symmetric_blocks ->
    _reconcile_supply_ports -> deduplicate_constraints.

    Block-level constraints (those whose references are leaf/block unique_names
    rather than device names) bypass the device-level filters: they reference
    blocks, so graph-canonical pair checks don't apply. They still go through
    case normalisation, schema validation, and dedup.
    """
    if not isinstance(raw_constraints, list):
        return []

    merged_devices, merged_ports, _dev_to_leaf = _collect_leaf_netlist_artifacts(tree)
    if not merged_devices:
        print("[hygiene] no leaf devices parsed; skipping structural gates.")
        cs = _normalize_case_recursive(raw_constraints)
        cs = _validate_schema(cs)
        cs = _clean_match_devices(cs)
        return deduplicate_constraints(cs)

    legal_names: Set[str] = {d["name"].lower() for d in merged_devices if d.get("name")}

    # Collect every block (leaf + non-leaf) unique_name as an additional
    # legal reference target for block-level constraints.
    block_names: Set[str] = set()

    def _collect_block_names(node: Dict[str, Any]) -> None:
        un = node.get("unique_name", "")
        if un:
            block_names.add(str(un).lower())
        for ch in node.get("children", []) or []:
            _collect_block_names(ch)

    _collect_block_names(tree)

    G_merged = build_bipartite_graph(merged_devices, merged_ports)
    type_map = _device_type_lookup(G_merged, merged_devices)
    power_valid, ground_valid = detect_power_ground(merged_devices, merged_ports)

    # Cross-coupled pairs are exempted from the canonical-signature filter.
    supply_nets: Set[str] = {str(s).lower() for s in power_valid} | {str(g).lower() for g in ground_valid}
    try:
        seeds = _graphwalk_symmetry_seeds(G_merged, supply_nets)
    except Exception as exc:
        print(f"[hygiene] graphwalk seed extraction failed: {exc}")
        seeds = []
    exempt_pairs: Set[frozenset] = {
        frozenset({s["dev1"].lower(), s["dev2"].lower()})
        for s in seeds
        if s.get("motif") == "cross_coupled"
        and s.get("dev1") and s.get("dev2")
    }

    before = len(raw_constraints)
    cs_all = _normalize_case_recursive(raw_constraints)

    # ── Split: block-level vs device-level ─────────────────────────────────
    def _is_block_level(c: Dict[str, Any]) -> bool:
        ctype = c.get("constraint")
        if ctype == "SymmetricBlocks":
            for pr in c.get("pairs", []) or []:
                if isinstance(pr, list):
                    for x in pr:
                        if str(x).lower() in block_names and str(x).lower() not in legal_names:
                            return True
        elif ctype in ("SameTemplate", "GroupBlocks", "Order", "Align", "AlignInOrder"):
            for x in c.get("instances", []) or []:
                if str(x).lower() in block_names and str(x).lower() not in legal_names:
                    return True
        return False

    block_cs = [c for c in cs_all if _is_block_level(c)]
    dev_cs = [c for c in cs_all if not _is_block_level(c)]

    # Device-level path: full gauntlet.
    dev_cs = _drop_unknown_instances(dev_cs, legal_names)
    dev_cs = _validate_schema(dev_cs)
    dev_cs = _clean_match_devices(dev_cs)
    dev_cs = _filter_bad_sym_pairs(dev_cs, G_merged, type_map, exempt_pairs=exempt_pairs)
    dev_cs = _clean_symmetric_blocks(dev_cs)
    dev_cs = _reconcile_supply_ports(dev_cs, power_valid, ground_valid)

    # Block-level path: keep only refs that resolve to a known block / leaf;
    # drop malformed by schema; dedup comes later together.
    block_cs = _drop_unknown_instances(block_cs, block_names | legal_names)
    block_cs = _validate_schema(block_cs)
    block_cs = _clean_symmetric_blocks(block_cs)

    cs = deduplicate_constraints(dev_cs + block_cs)
    print(f"[hygiene] system-level constraints: {before} -> {len(cs)} after post-pass "
          f"(device-level: {len(dev_cs)}, block-level: {len(block_cs)}).")
    return cs


# ═══════════════════════════════════════════════════════════════════════════════
# M4 — Hierarchy-aware deterministic constraints
# ═══════════════════════════════════════════════════════════════════════════════

def _collect_leaf_device_names(node: Dict[str, Any]) -> List[str]:
    """Return all device names (lowercased) under a tree node (non-recursive safe)."""
    names: List[str] = []
    seen: Set[str] = set()

    def _walk(n: Dict[str, Any]) -> None:
        children = n.get("children", []) or []
        if not children:
            devs = n.get("device_list") or []
            if not devs:
                netlist_text = n.get("netlist") or ""
                if netlist_text.strip():
                    try:
                        _c, _p, parsed = parse_netlist_general(netlist_text)
                        devs = [d["name"] for d in parsed if d.get("name")]
                    except ValueError:
                        devs = []
            for d in devs:
                dl = str(d).lower()
                if dl not in seen:
                    seen.add(dl)
                    names.append(dl)
            return
        for child in children:
            _walk(child)

    _walk(node)
    return names


def emit_group_blocks_from_tree(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Emit one GroupBlocks per non-leaf, non-root subtree.

    The group's `instances` is the union of all leaf device names under
    that subtree; `name` is the node's `unique_name`. Skips the tree root
    and any subtree with fewer than 2 devices.
    """
    out: List[Dict[str, Any]] = []

    def _walk(node: Dict[str, Any], is_root: bool) -> None:
        children = node.get("children", []) or []
        if children and not is_root:
            devs = _collect_leaf_device_names(node)
            if len(devs) >= 2:
                raw_name = str(node.get("unique_name", "group") or "group")
                safe_name = re.sub(r"[^a-z0-9_]+", "_", raw_name.lower()).strip("_") or "group"
                out.append({
                    "constraint": "GroupBlocks",
                    "name": safe_name,
                    "instances": devs,
                })
        for child in children:
            _walk(child, is_root=False)

    _walk(tree, is_root=True)
    return out


def emit_same_template_from_tree(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Translate template groups (size >= 2) into device-level SameTemplate
    constraints. Requires that each grouped node resolves to a single leaf
    (or a single-leaf-equivalent set of devices) with the same cardinality.

    For every template group, we build one SameTemplate per device-index
    position across the leaves in that group: if three leaves
    ``[L1(devs=[m1,m2]), L2(devs=[m3,m4]), L3(devs=[m5,m6])]`` are in one
    template group, we emit ``SameTemplate(instances=[m1,m3,m5])`` and
    ``SameTemplate(instances=[m2,m4,m6])``.

    Falls back to leaf-granularity grouping when device counts differ
    (best-effort: skip group).
    """
    out: List[Dict[str, Any]] = []
    try:
        db = build_node_signature_database(tree)
    except Exception as exc:
        print(f"[M4] SameTemplate: signature DB failed ({exc}); skipping.")
        return out
    groups: Dict[str, List[str]] = db.get("same_templates_identified", {}) or {}

    # Build a unique_name -> list[device_name] (in stable order from netlist)
    node_index: Dict[str, List[str]] = {}

    def _index(n: Dict[str, Any]) -> None:
        uname = n.get("unique_name", "")
        if uname:
            node_index[uname] = _collect_leaf_device_names(n)
        for c in n.get("children", []) or []:
            _index(c)

    _index(tree)

    for _tkey, node_ids in groups.items():
        if len(node_ids) < 2:
            continue
        dev_lists = [node_index.get(nid, []) for nid in node_ids]
        if any(not dl for dl in dev_lists):
            continue
        sizes = {len(dl) for dl in dev_lists}
        if len(sizes) != 1:
            continue
        size = sizes.pop()
        for i in range(size):
            instances = [dl[i] for dl in dev_lists]
            if len(set(instances)) < 2:
                continue
            out.append({
                "constraint": "SameTemplate",
                "instances": instances,
            })
    return out



def _emit_pair_constraint_from_cross_node_device_groups(
    tree: Dict[str, Any],
    payload_key: str,
    constraint_type: str,
) -> List[Dict[str, Any]]:
    raw_groups: List[List[str]] = []

    def _walk(node: Dict[str, Any]) -> None:
        payload = node.get("bottom_up_payload", {}) or {}
        groups = payload.get(payload_key, []) or []

        for group in groups:
            if not isinstance(group, list):
                continue

            cleaned = sorted({str(x).lower() for x in group if str(x)})
            if len(cleaned) < 2:
                continue

            raw_groups.append(cleaned)

        for child in (node.get("children", []) or []):
            _walk(child)

    _walk(tree)

    if not raw_groups:
        return []

    # One final global union-find across overlapping groups now that we are merging different node pairs
    parent: Dict[str, str] = {}

    def _find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a: str, b: str) -> None:
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[ra] = rb

    for group in raw_groups:
        base = group[0]
        for dev in group[1:]:
            _union(base, dev)

    merged_groups: Dict[str, Set[str]] = {}
    for group in raw_groups:
        for dev in group:
            root = _find(dev)
            merged_groups.setdefault(root, set()).add(dev)

    out: List[Dict[str, Any]] = []
    seen: Set[Tuple[Tuple[str, str], ...]] = set()

    for devs in merged_groups.values():
        devs_sorted = sorted(devs)
        if len(devs_sorted) < 2:
            continue

        pairs: List[List[str]] = []
        for i in range(len(devs_sorted)):
            for j in range(i + 1, len(devs_sorted)):
                pairs.append([devs_sorted[i], devs_sorted[j]])

        if not pairs:
            continue

        fp = tuple(tuple(p) for p in pairs)
        if fp in seen:
            continue
        seen.add(fp)

        out.append({
            "constraint": constraint_type,
            "direction": "V",
            "pairs": pairs,
        })

    return out


def emit_symmetric_blocks_from_cross_node_device_matching(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Cross-node symmetry-style device groups from message passing.

    node["bottom_up_payload"]["device_matching_sym"]
    """
    return _emit_pair_constraint_from_cross_node_device_groups(
        tree=tree,
        payload_key="device_matching_sym",
        constraint_type="SymmetricBlocks",
    )


def emit_matching_blocks_from_cross_node_device_matching(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Cross-node electrical matching groups from message passing.

    node["bottom_up_payload"]["device_matching"]
    """
    return _emit_pair_constraint_from_cross_node_device_groups(
        tree=tree,
        payload_key="device_matching",
        constraint_type="MatchDevices",
    )


def emit_symmetric_nets_from_system_level_net_matching(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
    """

    node["bottom_up_payload"]["system_level_net_matching"]

    """
    raw_groups: List[List[str]] = []

    def _walk(node: Dict[str, Any]) -> None:
        payload = node.get("bottom_up_payload", {}) or {}
        groups = payload.get("system_level_net_matching", []) or []

        for group in groups:
            if not isinstance(group, list):
                continue

            cleaned = sorted({str(x).lower() for x in group if str(x)})
            if len(cleaned) < 2:
                continue

            raw_groups.append(cleaned)

        for child in (node.get("children", []) or []):
            _walk(child)

    _walk(tree)

    if not raw_groups:
        return []

    # One final global union-find across overlapping net groups
    parent: Dict[str, str] = {}

    def _find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a: str, b: str) -> None:
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[ra] = rb

    for group in raw_groups:
        base = group[0]
        for net in group[1:]:
            _union(base, net)

    merged_groups: Dict[str, Set[str]] = {}
    for group in raw_groups:
        for net in group:
            root = _find(net)
            merged_groups.setdefault(root, set()).add(net)

    out: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str]] = set()

    for nets in merged_groups.values():
        nets_sorted = sorted(nets)
        if len(nets_sorted) < 2:
            continue

        for i in range(len(nets_sorted)):
            for j in range(i + 1, len(nets_sorted)):
                net1, net2 = nets_sorted[i], nets_sorted[j]
                fp = (net1, net2)
                if fp in seen:
                    continue
                seen.add(fp)

                out.append({
                    "constraint": "SymmetricNets",
                    "net1": net1,
                    "net2": net2,
                    "direction": "V",
                })

    return out



def emit_symmetric_blocks_from_system_level_block_symmetry(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
    """

    node["bottom_up_payload"]["block_symmetry"]

    Here get a bijection (exact mapping), since:
        Device ↔ device correspondence is perfect
        Structure (edges, terminals) is preserved

    """

    def _find_node_by_name(node: Dict[str, Any], target_name: str) -> Optional[Dict[str, Any]]:
        if node.get("unique_name", "") == target_name:
            return node
        for child in (node.get("children", []) or []):
            found = _find_node_by_name(child, target_name)
            if found is not None:
                return found
        return None
    
    def _build_bipartite_graph_for_node_to_node_mapping(node_netlist_str: str) -> nx.MultiGraph:
        G = nx.MultiGraph()

        _cname, _ports, devices = parse_netlist_general(node_netlist_str)

        for dev in devices:
            dev_name = str(dev.get("name", ""))
            dev_type = str(dev.get("type", ""))

            params = dev.get("params", {}) or {}

            G.add_node(
                dev_name,
                bipartite="device",
                dev_type=dev_type,
                params=params,
            )

            if dev_type in ("nmos", "pmos"):
                terminals = [
                    ("D", dev.get("D", "")),
                    ("G", dev.get("G", "")),
                    ("S", dev.get("S", "")),
                    ("B", dev.get("B", "")),
                ]
            else:
                terminals = [
                    ("PLUS", dev.get("PLUS", "")),
                    ("MINUS", dev.get("MINUS", "")),
                ]

            for terminal_name, net_name in terminals:
                if not net_name:
                    continue

                if net_name not in G:
                    G.add_node(
                        net_name,
                        bipartite="net",
                    )

                edge_id = f"{dev_name}.{terminal_name}"
                G.add_edge(
                    dev_name,
                    net_name,
                    key=edge_id,
                    terminal=terminal_name,
                )

        return G
    
    def _device_pairs_from_isomorphism(
        left_node: Dict[str, Any],
        right_node: Dict[str, Any],
    ) -> List[List[str]]:
        
        left_name = left_node.get("unique_name", "")
        right_name = right_node.get("unique_name", "")
        left_netlist = left_node.get("netlist", "") or ""
        right_netlist = right_node.get("netlist", "") or ""

        #print("\n" + "=" * 100)
        #print(f"[block_symmetry] Testing node pair: {left_name}  <->  {right_name}")

        if not left_netlist.strip() or not right_netlist.strip():
            print("[block_symmetry] Missing netlist on one or both nodes. Skipping.")
            return []

        try:
            G_left = _build_bipartite_graph_for_node_to_node_mapping(left_netlist)
            G_right = _build_bipartite_graph_for_node_to_node_mapping(right_netlist)
        except ValueError:
            return []

        left_devices = [n for n, d in G_left.nodes(data=True) if d.get("bipartite") == "device"]
        right_devices = [n for n, d in G_right.nodes(data=True) if d.get("bipartite") == "device"]

        #print(f"[block_symmetry] Left devices ({len(left_devices)}): {sorted(left_devices)}")
        #print(f"[block_symmetry] Right devices ({len(right_devices)}): {sorted(right_devices)}")

        def _node_match(a, b):
            if a.get("bipartite") != b.get("bipartite"):
                return False

            if a.get("bipartite") == "device":
                return (
                    a.get("dev_type") == b.get("dev_type")
                    and a.get("params") == b.get("params")
                )

            if a.get("bipartite") == "net":
                return True

            return False

        def _edge_match(a, b):
            return a.get("terminal") == b.get("terminal")

        matcher = nx.isomorphism.MultiGraphMatcher(
            G_left,
            G_right,
            node_match=_node_match,
            edge_match=_edge_match,
        )

        iso_ok = matcher.is_isomorphic()
        #print(f"[block_symmetry] Isomorphic? {iso_ok}")

        if not iso_ok:
            return []

        mapping = dict(matcher.mapping)
        #print("[block_symmetry] Raw mapping:")
        #print(json.dumps({str(k): str(v) for k, v in mapping.items()}, indent=2))

        pairs: List[List[str]] = []
        for left_name, right_name in mapping.items():
            left_data = G_left.nodes.get(left_name, {})
            right_data = G_right.nodes.get(right_name, {})

            if left_data.get("bipartite") != "device":
                continue
            if right_data.get("bipartite") != "device":
                continue

            pairs.append([str(left_name).lower(), str(right_name).lower()])

        pairs.sort()
        #print("[block_symmetry] Device-level pairs:")
        #print(json.dumps(pairs, indent=2))
        return pairs

    raw_block_groups: List[List[str]] = []

    def _walk(node: Dict[str, Any]) -> None:
        payload = node.get("bottom_up_payload", {}) or {}
        groups = payload.get("block_symmetry", []) or []

        for group in groups:
            if not isinstance(group, list):
                continue

            cleaned = sorted({str(x) for x in group if str(x)})
            if len(cleaned) < 2:
                continue

            raw_block_groups.append(cleaned)

        for child in (node.get("children", []) or []):
            _walk(child)

    _walk(tree)

    if not raw_block_groups:
        return []

    out: List[Dict[str, Any]] = []
    seen: Set[Tuple[Tuple[str, str], ...]] = set()

    for group in raw_block_groups:
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                left_name = group[i]
                right_name = group[j]

                left_node = _find_node_by_name(tree, left_name)
                right_node = _find_node_by_name(tree, right_name)

                if left_node is None or right_node is None:
                    continue

                pairs = _device_pairs_from_isomorphism(left_node, right_node)
                if not pairs:
                    continue

                fp = tuple(tuple(p) for p in pairs)
                if fp in seen:
                    continue
                seen.add(fp)

                out.append({
                    "constraint": "SymmetricBlocks",
                    "direction": "V",
                    "pairs": pairs,
                })

    #print("\n" + "#" * 100)
    #print("[block_symmetry] Final emitted constraints:")
    #print(json.dumps(out, indent=2))

    return out



# ═══════════════════════════════════════════════════════════════════════════════
# M5 — Prompt hardening for the final ALIGN call
# ═══════════════════════════════════════════════════════════════════════════════

BOTTOM_UP_FINAL_ALIGN_USER_PREAMBLE = """Legal instance names (lowercased union of all leaf device names):
{instance_whitelist}

HARD RULES:
- EVERY instance / pair entry MUST be drawn from the whitelist above; anything else will be dropped.
- Use LOWERCASE for every instance, pair, port, and net name.
- SymmetricBlocks MUST include "direction" ("V" or "H").
  Positive example: {{"constraint": "SymmetricBlocks", "direction": "V", "pairs": [["m1","m2"]]}}
  Negative example (WRONG, missing direction): {{"constraint": "SymmetricBlocks", "pairs": [["m1","m2"]]}}
- GroupBlocks MUST use {{"constraint": "GroupBlocks", "name": "<snake_case>", "instances": [...]}}.
  Positive example: {{"constraint": "GroupBlocks", "name": "diff_pair", "instances": ["m1","m2"]}}
  Negative example (WRONG, uses node label as instance): {{"constraint": "GroupBlocks", "name": "diff_pair", "instances": ["Amplifier Signal Path"]}}
- Return ONLY the JSON array. No prose. No markdown fences.
"""


'''
# DELETING THIS FOR NOW SINCE LOGIC INCONSISTENT WITH THE REMAINING CODES ABOVE
def emit_cross_leaf_sym_from_matching_summary(
    bottom_up_results: Dict[str, Any],
    tree: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Translate system-level matched-edge summaries into BLOCK-LEVEL
    ``SymmetricBlocks`` entries (pairs of sibling leaf unique_names).

    Two kinds of block-level pairs are emitted:

    1. **Direct pair** — every ``matched == True`` ``matching_edge_summary``
       with ``node_a != node_b`` yields a ``SymmetricBlocks`` between those
       two blocks.

    2. **Bijection-closure pair** — two leaves ``L1`` and ``L2`` are declared
       symmetric when every device in ``L1`` has a unique counterpart in
       ``L2`` via the transitive closure of all matched device-pairs from
       every LCA (and vice versa). This captures topologies like a shared
       current-mirror master ``M1`` linking mirror slaves ``M2`` (in ``L1``)
       and ``M5`` (in ``L2``) — the matching summary records ``M1~M2`` and
       ``M1~M5`` but never ``M2~M5`` directly, yet ``{L1, L2}`` is the
       correct symmetric block pair.

    Device-level cross-leaf pairs are deliberately NOT emitted here because
    the agent operates at the block granularity.
    """
    summaries = (bottom_up_results or {}).get("matching_summary_by_lca", {}) or {}

    # ── Step 1: collect matched device pairs + block-pair direct hits ─────
    matched_device_pairs: Set[frozenset] = set()
    direct_block_pairs: Set[frozenset] = set()

    for _lca_name, lca_data in summaries.items():
        for summary in (lca_data.get("matching_edge_summaries") or []):
            if not isinstance(summary, dict):
                continue
            match = summary.get("matching_summary") or {}
            if not match.get("matched"):
                continue
            node_a = summary.get("node_a", "")
            node_b = summary.get("node_b", "")
            if not node_a or not node_b or node_a == node_b:
                continue
            direct_block_pairs.add(frozenset({node_a, node_b}))

            group = match.get("matching_group") or []
            group = [str(g).lower() for g in group if isinstance(g, (str, int))]
            # Every device pair in the matching_group is considered matched.
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    if group[i] != group[j]:
                        matched_device_pairs.add(frozenset({group[i], group[j]}))

    # ── Step 2: union-find over matched device pairs → eq-classes ─────────
    parent: Dict[str, str] = {}

    def _find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a: str, b: str) -> None:
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[ra] = rb

    for pair in matched_device_pairs:
        a, b = tuple(pair)
        _union(a, b)

    # ── Step 3: leaf device sets ──────────────────────────────────────────
    leaves = identify_leaf_nodes(tree)
    leaf_to_devs: Dict[str, Set[str]] = {}
    for lf in leaves:
        devs: Set[str] = set()
        for d in (lf.get("device_list") or []):
            devs.add(str(d).lower())
        if not devs:
            nl = lf.get("netlist") or ""
            if nl.strip():
                try:
                    _c, _p, parsed = parse_netlist_general(nl)
                    devs = {d["name"].lower() for d in parsed if d.get("name")}
                except ValueError:
                    devs = set()
        if devs:
            leaf_to_devs[lf.get("unique_name", "")] = devs

    # Restrict eq-classes to MOS-like devices (starts with 'm' / 'q'); ignore
    # resistors / caps when deciding bijection.
    def _is_active(d: str) -> bool:
        return bool(d) and d[0] in ("m", "q")

    # ── Step 4: bijection-closure detection ──────────────────────────────
    bijection_block_pairs: Set[frozenset] = set()
    leaf_names = list(leaf_to_devs.keys())
    for i in range(len(leaf_names)):
        for j in range(i + 1, len(leaf_names)):
            la, lb = leaf_names[i], leaf_names[j]
            devs_a = {d for d in leaf_to_devs[la] if _is_active(d)}
            devs_b = {d for d in leaf_to_devs[lb] if _is_active(d)}
            if not devs_a or not devs_b:
                continue
            if len(devs_a) != len(devs_b):
                continue  # size mismatch → cannot be a bijection
            # Every device in devs_a must have exactly one matched
            # counterpart in devs_b (via its eq-class).
            used_b: Set[str] = set()
            ok = True
            for da in devs_a:
                class_da = _find(da)
                partners = [db for db in devs_b
                            if _find(db) == class_da and db not in used_b]
                if not partners:
                    ok = False
                    break
                used_b.add(partners[0])
            if ok and used_b == devs_b:
                bijection_block_pairs.add(frozenset({la, lb}))

    # ── Step 5: emit ──────────────────────────────────────────────────────
    out: List[Dict[str, Any]] = []
    for pair in sorted({frozenset(p) for p in direct_block_pairs | bijection_block_pairs},
                       key=lambda fp: sorted(list(fp))):
        a, b = sorted(list(pair))
        out.append({
            "constraint": "SymmetricBlocks",
            "direction": "V",
            "pairs": [[a, b]],
        })
    return out
'''

def summarize_final_align_constraints_bottom_up(
    tree: Dict[str, Any],
    driver_load_json_path: str,
    bottom_up_results: Optional[Dict[str, Any]] = None,
    model: str = DEFAULT_MODEL_ENDPOINT,
    metrics_save_path: str = "",
) -> List[Dict[str, Any]]:
    llm = LLMHelper(model=model)

    compact_tree = build_compact_tree_for_llm(tree)
    driver_load_payload = load_json(driver_load_json_path)

    merged_devices, _merged_ports, _dev_to_leaf = _collect_leaf_netlist_artifacts(tree)
    instance_whitelist = sorted({d["name"].lower() for d in merged_devices if d.get("name")})

    system_prompt = BOTTOM_UP_FINAL_ALIGN_SYSTEM_PROMPT.format(
        schema=CONSTRAINT_SCHEMA
    )

    user_preamble = BOTTOM_UP_FINAL_ALIGN_USER_PREAMBLE.format(
        instance_whitelist=json.dumps(instance_whitelist),
    )

    user_prompt = f"""{user_preamble}

    Compact hierarchy tree:
    {json.dumps(compact_tree, indent=2)}

    System-level net driver/load metadata:
    {json.dumps(driver_load_payload, indent=2)}

    Output ONLY a valid JSON array of the final constraint objects for the full circuit.

    """

    ###########################################################################################################################################################
    ################################################ DEBUG AND VERIFY DETERMINISTIC EMITTER FUNCTIONS #########################################################
    ###########################################################################################################################################################
    '''
    debug_block_symmetry_constraints = emit_symmetric_blocks_from_system_level_block_symmetry(tree)
    print("[DEBUG] Block-level symmetry emitted constraints only:")
    print("=" * 120 + "\n")
    print(json.dumps(debug_block_symmetry_constraints, indent=2))
    print("=" * 120 + "\n")
    

    debug_block_symmetry_cross_node_constraints = emit_symmetric_blocks_from_cross_node_device_matching(tree)
    print("[DEBUG] Block symmetry (cross_node) emitted constraints only:")
    print("=" * 120 + "\n")
    print(json.dumps(debug_block_symmetry_cross_node_constraints, indent=2))
    print("=" * 120 + "\n")


    debug_system_level_net_symmetry_constraints = emit_symmetric_nets_from_system_level_net_matching(tree)
    print("[DEBUG] System-Level Net Symmetry emitted constraints only:")
    print("=" * 120 + "\n")
    print(json.dumps(debug_system_level_net_symmetry_constraints, indent=2))
    print("=" * 120 + "\n")

    exit()
    '''

    ################################################################################################################################################################################
    ################################################################################################################################################################################
    ################################################################################################################################################################################

    result = llm.call(system_prompt, user_prompt)

    raw = llm.extract_json(result.content)
    final_constraints = llm.normalize_constraints(raw)

    # M4: inject hierarchy-derived deterministic constraints before hygiene
    # so they also get validated / deduped.
    final_constraints = list(final_constraints or [])
    final_constraints.extend(emit_group_blocks_from_tree(tree))
    final_constraints.extend(emit_same_template_from_tree(tree))
    
    """
    if bottom_up_results is not None:
        final_constraints.extend(
            emit_cross_leaf_sym_from_matching_summary(bottom_up_results, tree)
        )
    """

    final_constraints.extend(emit_symmetric_blocks_from_cross_node_device_matching(tree))
    final_constraints.extend(emit_matching_blocks_from_cross_node_device_matching(tree))
    final_constraints.extend(emit_symmetric_nets_from_system_level_net_matching(tree))
    final_constraints.extend(emit_symmetric_blocks_from_system_level_block_symmetry(tree))

    final_constraints = postprocess_system_align_constraints(final_constraints, tree)

    if metrics_save_path:
        os.makedirs(os.path.dirname(metrics_save_path), exist_ok=True)
        with open(metrics_save_path, "w", encoding="utf-8") as f:
            json.dump(llm.aggregate_metrics(), f, indent=2)

    return final_constraints


def run_constraint_extraction_on_leaves(
    tree: Dict[str, Any],
    constraints_dir: str,
    with_reasoning: bool = False,
    rerun: bool = True,
    variation: int = 0,
    kb_only_threshold: float = 0.50,
    complexity_cap: int = 15,
    model: str = DEFAULT_MODEL_ENDPOINT,
    metrics_save_path: str = "",
) -> Dict[str, Any]:
    # variation=0 = KB-only adaptive gate: pure graph-based when KB match
    # is strong AND the subcircuit is small, otherwise the engine falls
    # back to variation=1 (single-shot LLM refinement).
    os.makedirs(constraints_dir, exist_ok=True)
    leaf_engine = HybridConstraintEngine(
        model=model,
        kb_only_threshold=kb_only_threshold,
        complexity_cap=complexity_cap,
    )
    leaves = identify_leaf_nodes(tree)

    for idx, leaf in enumerate(leaves, start=1):
        leaf_name = leaf.get("unique_name", leaf.get("id", ""))
        leaf_netlist = leaf.get("netlist", "")
        safe_leaf_name = leaf_name.replace(" ", "_")
        out_leaf_constraint_path = os.path.join(constraints_dir, f"{safe_leaf_name}.json")

        # Read existing automated file if rerun=False
        if (not rerun) and os.path.exists(out_leaf_constraint_path) and os.path.getsize(out_leaf_constraint_path) > 0:
            try:
                with open(out_leaf_constraint_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
            except Exception:
                raw = []
            leaf["constraints"] = raw if isinstance(raw, list) else []
            leaf["leaf_engine_info"] = {
                "source": "cached_file",
                "path": out_leaf_constraint_path,
            }
            print(f"[BottomUp V0][{idx}/{len(leaves)}] loaded cached: {leaf_name}")
            continue

        print(f"[BottomUp V0][{idx}/{len(leaves)}] Hybrid leaf engine: {leaf_name}")
        try:
            result = leaf_engine.generate_constraints(
                netlist_text=leaf_netlist,
                variation=variation,
                with_reasoning=with_reasoning,
            )
            constraints = result.get("constraints", [])
            if not isinstance(constraints, list):
                constraints = []

            leaf["constraints"] = constraints
            leaf["leaf_engine_info"] = {
                "metrics": result.get("metrics", {}),
                "variation": result.get("variation", variation),
                "kb_only_path": result.get("kb_only_path", False),
                "initial_constraints": result.get("initial_constraints", []),
                "source": "rerun",
            }
            save_json(out_leaf_constraint_path, constraints)

        except Exception as e:
            leaf["constraints"] = []
            leaf["leaf_engine_info"] = {
                "error": str(e),
                "metrics": {},
                "variation": variation,
                "kb_only_path": None,
                "source": "error",
            }


    # Sum per-leaf metrics. The leaf engine is adaptive: some leaves may hit
    # KB-only (0 LLM calls) while others fall back to LLM variations (>=1 call).
    if metrics_save_path:
        agg = {
            "model": model,
            "num_llm_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "llm_runtime_seconds": 0.0,
            "num_leaves": len(leaves),
            "num_leaves_kb_only": 0,
            "num_leaves_with_llm": 0,
            "num_leaves_cached": 0,
        }
        for leaf in leaves:
            info = leaf.get("leaf_engine_info", {}) or {}
            if info.get("source") == "cached_file":
                agg["num_leaves_cached"] += 1
                continue
            m = info.get("metrics", {}) or {}
            calls = int(m.get("num_llm_calls", 0) or 0)
            agg["num_llm_calls"]      += calls
            agg["input_tokens"]       += int(m.get("input_tokens", 0) or 0)
            agg["output_tokens"]      += int(m.get("output_tokens", 0) or 0)
            agg["total_tokens"]       += int(m.get("total_tokens", 0) or 0)
            agg["llm_runtime_seconds"] += float(m.get("llm_runtime_seconds", 0.0) or 0.0)
            if info.get("kb_only_path"):
                agg["num_leaves_kb_only"] += 1
            elif calls > 0:
                agg["num_leaves_with_llm"] += 1
        os.makedirs(os.path.dirname(metrics_save_path), exist_ok=True)
        with open(metrics_save_path, "w", encoding="utf-8") as f:
            json.dump(agg, f, indent=2)

    return tree


def resolve_hierarchy_tree_path(generated_dir: str) -> str:
    """Return the hierarchy-tree JSON to load for the given case.

    Prefers ``hierarchy_dendrogram_cleaned.json`` (the shape LDO_Simple
    ships). Falls back to ``hierarchical_agglomeration_tree.json`` when
    the cleaned file isn't present (Complex_OTA_1_Gao). Both carry the
    same ``unique_name`` / ``children`` schema.
    """
    candidates = [
        "hierarchy_dendrogram_cleaned.json",
        "hierarchical_agglomeration_tree.json",
    ]
    for name in candidates:
        p = os.path.join(generated_dir, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        f"No hierarchy tree found in {generated_dir}. "
        f"Expected one of: {candidates}"
    )


def check_case_files(case: str, generated_dir: str) -> Dict[str, bool]:
    """Preflight: validate that the files we actually consume exist.

    Only checks files produced by this agent or the leaf engine -- legacy
    inputs (e.g. port_annotations_by_block.json) are NOT required.
    Prints a green/red table and returns a dict for programmatic use.
    """
    required = {
        "hierarchy_tree": any(
            os.path.exists(os.path.join(generated_dir, n))
            for n in ("hierarchy_dendrogram_cleaned.json",
                      "hierarchical_agglomeration_tree.json")
        ),
        "circuit_global_context_NEW.json": os.path.exists(
            os.path.join(generated_dir, "circuit_global_context_NEW.json")
        ),
    }

    print(f"\n[preflight] case = {case}")
    print(f"[preflight] generated_dir = {generated_dir}")
    width = max(len(k) for k in required)
    for k, ok in required.items():
        mark = "OK " if ok else "MISSING"
        print(f"  [{mark}] {k:<{width}}")
    print()

    missing = [k for k, ok in required.items() if not ok]
    if missing:
        raise FileNotFoundError(
            f"Preflight failed for case '{case}': missing {missing}"
        )

    return required


def main() -> None:
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

    # Pick the next Run_NNN that has splitter + hierarchy outputs but no system_level/ yet.
    run_dir = find_next_run_to_process(parent_netlist_path)
    splitter_dir   = os.path.join(run_dir, "splitter")
    hierarchy_dir  = os.path.join(run_dir, "hierarchy")
    print(f"[system_level] Reading splitter output from:  {splitter_dir}")
    print(f"[system_level] Reading hierarchy output from: {hierarchy_dir}")
    print(f"[system_level] Writing artifacts under:       {run_dir}/constraints/")

    circuit_global_context_path = os.path.join(splitter_dir, "circuit_global_context.json")
    hierarchy_tree_path         = os.path.join(hierarchy_dir, "hierarchy_dendrogram_cleaned.json")

    # Use the model the splitter recorded into the global context, falling back to default.
    splitter_ctx = load_json(circuit_global_context_path)
    selected_model = resolve_model_endpoint(splitter_ctx.get("model", DEFAULT_MODEL_ENDPOINT))

    tree = build_enriched_tree_from_split_sources(
        hierarchy_tree_path=hierarchy_tree_path,
        circuit_global_context_path=circuit_global_context_path,
    )

    system_level_dir = os.path.join(run_dir, "constraints", "system_level")
    os.makedirs(system_level_dir, exist_ok=True)
    save_json(
        os.path.join(system_level_dir, "Enriched_Hierarchy_Dendogram_Agglomeration_Tree.json"),
        tree,
    )

    # FULL FLOW WITH AUTOMATED LEAF EXPERT ENGINE
    # All system-level artifacts (Net_Driver_Load.json, System_Level_*.json,
    # Final_ALIGN_Constraints.json) land under <run_dir>/constraints/system_level/
    # via the routing inside the pipeline.
    accumulate_constraints_bottom_up_v0(
        tree=tree,
        generated_dir=run_dir,
        output_dir=run_dir,
        with_reasoning=False,
        leaf_variation=0,
        kb_only_threshold=0.50,
        complexity_cap=15,
        model=selected_model,
    )



if __name__ == "__main__":
    main()
