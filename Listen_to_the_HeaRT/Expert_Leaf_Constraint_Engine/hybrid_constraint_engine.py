"""
Hybrid Constraint Engine: Graph-Isomorphism + LLM for ALIGN layout constraints.

Four modes of constraint generation:
  KB-Only  – Pure graph-based generation when KB match is strong and circuit is small
  Variation 1 – Confidence-Gated Single-Shot Refinement
  Variation 2 – Iterative Constraint-by-Constraint Review (Surgical Audit)
  Variation 3 – Multi-Agent Debate with Graph Verifier (Propose-Verify-Merge)
"""

import json
import os
import re
import time
import copy
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np
from scipy.optimize import linear_sum_assignment

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

SUPPLY_RAILS = {"vdd", "vss", "gnd", "VDD", "VSS", "GND", "0"}
SUPPLY_RAILS_LOWER = {s.lower() for s in SUPPLY_RAILS}

DEVICE_TYPE_MAP = {
    "nmos": 0, "pmos": 1, "resistor": 2, "capacitor": 3,
}
NUM_DEVICE_TYPES = 4

DEFAULT_POWER_NAMES = {"vdd", "avdd", "dvdd", "vcc", "vdda", "vddd"}
DEFAULT_GROUND_NAMES = {"vss", "gnd", "avss", "dvss", "gnd!", "0"}

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


KB_DIR = Path(__file__).parent / "knowledge_base"

CONSTRAINT_SCHEMA = """
ALIGN Layout Constraint Types (JSON format, list of constraint objects):

1. SymmetricBlocks — mirror symmetry for matched device pairs
   {"constraint": "SymmetricBlocks", "direction": "V" or "H",
    "pairs": [["inst1", "inst2"], ["self_sym_inst"], ...]}

2. Order — placement ordering
   {"constraint": "Order", "instances": ["i1", "i2", ...],
    "direction": "left_to_right"|"right_to_left"|"bottom_to_top"|"top_to_bottom"|"horizontal"|"vertical",
    "abut": false}

3. Align — alignment without ordering
   {"constraint": "Align", "instances": ["i1", "i2"],
    "line": "h_any"|"h_top"|"h_bottom"|"h_center"|"v_any"|"v_left"|"v_right"|"v_center"}

4. AlignInOrder — align + order combined
   {"constraint": "AlignInOrder", "instances": [...],
    "line": "top"|"bottom"|"center"|"left"|"right",
    "direction": "horizontal"|"vertical"}

5. GroupBlocks — force hierarchy grouping
   {"constraint": "GroupBlocks", "name": "group_name", "instances": [...]}

6. SymmetricNets — symmetric routing for net pairs
   {"constraint": "SymmetricNets", "net1": "n1", "net2": "n2", "direction": "V"|"H"}

7. NetConst — net routing priority/shielding
   {"constraint": "NetConst", "nets": [...], "shield": "VSS", "criticality": 10}

8. PowerPorts — declare power supply ports
   {"constraint": "PowerPorts", "ports": ["vdd"]}

9. GroundPorts — declare ground ports
   {"constraint": "GroundPorts", "ports": ["gnd"]}

10. PortLocation — pin placement hints
    {"constraint": "PortLocation", "ports": [...],
     "location": "TL"|"TC"|"TR"|"RT"|"RC"|"RB"|"BL"|"BC"|"BR"|"LB"|"LC"|"LT"}

11. CompactPlacement — overall placement compaction
    {"constraint": "CompactPlacement", "style": "left"|"right"|"center"}

12. SameTemplate — force identical cell templates
    {"constraint": "SameTemplate", "instances": [...]}

13. MatchDevices — device pairs that require electrical (Vt / gm) matching
    via layout techniques such as common centroid, interdigitation, and
    dummy insertion. Emit for analog motifs whose function depends on
    tight device tracking under process variation, including:
      • Current mirrors (reference + output transistors of the same finger size)
      • Differential pair input transistors
      • Cascode partner pairs across symmetric branches
      • Cross-coupled latch / regenerative pairs (e.g. StrongArm comparator)
      • Complementary-clock switched-capacitor switch pairs
      • Resistor strings / capacitor arrays in ratio-critical networks (DAC, divider)
    Distinct from SymmetricBlocks (geometric mirror across an axis) and from
    SameTemplate (force identical cell layout only). A device pair may be
    BOTH SymmetricBlocks and MatchDevices — emit both when applicable.
    {"constraint": "MatchDevices", "direction": "V" or "H",
     "pairs": [["inst1", "inst2"], ...]}

CRITICAL RULES:
- Instance names must be LOWERCASE (ALIGN convention)
- Always include PowerPorts/GroundPorts
- Output must be a JSON array of constraint objects
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LLMCallResult:
    content: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    runtime_seconds: float
    model: str


@dataclass
class MatchResult:
    """Result of matching one KB template against the input netlist."""
    pattern_name: str
    similarity_score: float
    device_mapping: Dict[str, str]  # KB instance -> input instance
    net_mapping: Dict[str, str]
    translated_constraints: List[Dict[str, Any]]


@dataclass
class GraphMatchMetrics:
    """Aggregate metrics from the graph matching stage."""
    graph_match_time_seconds: float = 0.0
    num_kb_templates_matched: int = 0
    top_matches: List[Dict[str, Any]] = field(default_factory=list)
    total_initial_constraints: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# Generalized netlist parser (handles MOS, R, C)
# ═══════════════════════════════════════════════════════════════════════════════

def parse_netlist_general(netlist_text: str) -> Tuple[str, List[str], List[Dict[str, Any]]]:
    """Parse a SPICE .subckt netlist, extracting MOS, resistor, and capacitor devices."""
    lines = [ln.strip() for ln in netlist_text.splitlines() if ln.strip()]
    subckt = next((ln for ln in lines if ln.upper().startswith(".SUBCKT")), None)
    if not subckt:
        raise ValueError("Netlist must contain a .SUBCKT line.")

    parts = subckt.split()
    circuit_name = parts[1]
    circuit_ports = parts[2:]
    devices: List[Dict[str, Any]] = []

    for line in lines:
        if line.startswith(".") or line.startswith("*"):
            continue
        tokens = line.split()
        if len(tokens) < 2:
            continue

        name = tokens[0]
        low = line.lower()

        # --- MOS device: M... d g s b model [params] ---
        if name.upper().startswith("M") and len(tokens) >= 5:
            if any(k in low for k in ["pch", "pmos", "pfet"]):
                dev_type = "pmos"
            elif any(k in low for k in ["nch", "nmos", "nfet"]):
                dev_type = "nmos"
            else:
                dev_type = "nmos"  # default for M-prefix

            params = {}
            for t in tokens[5:]:
                if "=" in t:
                    k, v = t.split("=", 1)
                    params[k.lower()] = v

            devices.append({
                "name": name, "type": dev_type,
                "D": tokens[1], "G": tokens[2], "S": tokens[3], "B": tokens[4],
                "params": params,
            })

        # --- Resistor: R... n1 n2 model [params] ---
        elif name.upper().startswith("R") and len(tokens) >= 3:
            params = {}
            for t in tokens[3:]:
                if "=" in t:
                    k, v = t.split("=", 1)
                    params[k.lower()] = v
            devices.append({
                "name": name, "type": "resistor",
                "PLUS": tokens[1], "MINUS": tokens[2],
                "params": params,
            })

        # --- Capacitor: C... n1 n2 model [params] ---
        elif name.upper().startswith("C") and len(tokens) >= 3:
            params = {}
            for t in tokens[3:]:
                if "=" in t:
                    k, v = t.split("=", 1)
                    params[k.lower()] = v
            devices.append({
                "name": name, "type": "capacitor",
                "PLUS": tokens[1], "MINUS": tokens[2],
                "params": params,
            })

    return circuit_name, circuit_ports, devices


# ═══════════════════════════════════════════════════════════════════════════════
# Bipartite graph builder (generalized for MOS + R + C)
# ═══════════════════════════════════════════════════════════════════════════════

def build_bipartite_graph(
    devices: List[Dict[str, Any]],
    circuit_ports: List[str],
) -> nx.MultiGraph:
    """Build a bipartite device-net graph from parsed devices."""
    G = nx.MultiGraph()
    ports_lower = {p.lower() for p in circuit_ports}

    for dev in devices:
        G.add_node(dev["name"], bipartite="device", dev_type=dev["type"], params=dev["params"])

        if dev["type"] in ("nmos", "pmos"):
            terminals = [("D", dev["D"]), ("G", dev["G"]), ("S", dev["S"]), ("B", dev["B"])]
        else:
            terminals = [("PLUS", dev["PLUS"]), ("MINUS", dev["MINUS"])]

        for term_name, net in terminals:
            net_lower = net.lower()
            if net_lower in SUPPLY_RAILS_LOWER:
                role = "SUPPLY"
            elif net_lower in ports_lower:
                role = "SIGNAL_PORT"
            else:
                role = "INTERNAL"
            G.add_node(net, bipartite="net", role=role)
            eid = f"{dev['name']}.{term_name}"
            G.add_edge(dev["name"], net, key=eid, terminal=term_name)

    return G


# ═══════════════════════════════════════════════════════════════════════════════
# Node / graph embeddings
# ═══════════════════════════════════════════════════════════════════════════════

def _device_embedding(G: nx.MultiGraph, dev_name: str) -> np.ndarray:
    """Compute a 14-dim embedding vector for a device node."""
    data = G.nodes[dev_name]
    dev_type = data.get("dev_type", "nmos")

    # [0..3] device type one-hot
    type_vec = np.zeros(NUM_DEVICE_TYPES)
    type_vec[DEVICE_TYPE_MAP.get(dev_type, 0)] = 1.0

    # [4] degree (num distinct net neighbors)
    degree = len(set(G.neighbors(dev_name)))

    # [5..8] terminal connectivity roles: supply, signal_port, internal, self-connected
    role_counts = np.zeros(4)
    for _, nbr, edata in G.edges(dev_name, data=True):
        ndata = G.nodes[nbr]
        if ndata.get("bipartite") != "net":
            continue
        r = ndata.get("role", "INTERNAL")
        if r == "SUPPLY":
            role_counts[0] += 1
        elif r == "SIGNAL_PORT":
            role_counts[1] += 1
        else:
            role_counts[2] += 1
        if nbr == dev_name:
            role_counts[3] += 1
    total_terms = max(role_counts.sum(), 1)
    role_frac = role_counts / total_terms

    # [9..10] parameter signature: normalized W/L ratio bucket, or passive value bucket
    params = data.get("params", {})
    param_sig = np.zeros(2)
    if dev_type in ("nmos", "pmos"):
        try:
            w = float(re.sub(r'[a-zA-Z]', '', str(params.get("w", "1e-6"))))
            l = float(re.sub(r'[a-zA-Z]', '', str(params.get("l", "1e-7"))))
            ratio = w / max(l, 1e-15)
            param_sig[0] = np.clip(np.log10(max(ratio, 1e-3)), -3, 6) / 6
        except (ValueError, TypeError):
            pass
        try:
            nf = float(params.get("nf", "1"))
            param_sig[1] = np.clip(np.log2(max(nf, 1)), 0, 10) / 10
        except (ValueError, TypeError):
            pass
    else:
        try:
            val_str = params.get("r", params.get("c", "1"))
            val = float(re.sub(r'[a-zA-Z]', '', str(val_str)))
            param_sig[0] = np.clip(np.log10(max(abs(val), 1e-18) + 1e-18), -18, 12) / 30
        except (ValueError, TypeError):
            pass

    # [11..13] neighbor type distribution via shared non-supply nets
    neighbor_types = np.zeros(3)  # nmos_frac, pmos_frac, passive_frac
    neighbor_devs = set()
    for _, nbr in G.edges(dev_name):
        ndata = G.nodes.get(nbr, {})
        if ndata.get("bipartite") == "net" and ndata.get("role") != "SUPPLY":
            for _, dev2 in G.edges(nbr):
                if dev2 != dev_name and G.nodes.get(dev2, {}).get("bipartite") == "device":
                    neighbor_devs.add(dev2)
    for nd in neighbor_devs:
        nt = G.nodes[nd].get("dev_type", "")
        if nt == "nmos":
            neighbor_types[0] += 1
        elif nt == "pmos":
            neighbor_types[1] += 1
        else:
            neighbor_types[2] += 1
    total_nbr = max(neighbor_types.sum(), 1)
    neighbor_frac = neighbor_types / total_nbr

    return np.concatenate([
        type_vec,               # 4
        [degree / 10.0],        # 1
        role_frac,              # 4
        param_sig,              # 2
        neighbor_frac,          # 3
    ])  # total: 14


def _net_embedding(G: nx.MultiGraph, net_name: str, circuit_ports: List[str]) -> np.ndarray:
    """Compute a 7-dim embedding for a net node."""
    data = G.nodes[net_name]
    role = data.get("role", "INTERNAL")

    # [0..2] role one-hot: supply, signal_port, internal
    role_vec = np.zeros(3)
    if role == "SUPPLY":
        role_vec[0] = 1
    elif role == "SIGNAL_PORT":
        role_vec[1] = 1
    else:
        role_vec[2] = 1

    # [3] degree
    degree = len(set(G.neighbors(net_name)))

    # [4..6] connected device type distribution
    dev_types = np.zeros(3)
    for nbr in G.neighbors(net_name):
        ndata = G.nodes.get(nbr, {})
        if ndata.get("bipartite") == "device":
            dt = ndata.get("dev_type", "")
            if dt == "nmos":
                dev_types[0] += 1
            elif dt == "pmos":
                dev_types[1] += 1
            else:
                dev_types[2] += 1
    total = max(dev_types.sum(), 1)
    dev_frac = dev_types / total

    return np.concatenate([role_vec, [degree / 10.0], dev_frac])


def compute_graph_embedding(G: nx.MultiGraph, circuit_ports: List[str]) -> np.ndarray:
    """Compute a fixed-size graph-level embedding by aggregating node embeddings.

    Returns a 28-dim vector: [mean_device_emb(14) | histogram_features(14)].
    The histogram captures distribution statistics invariant to device count.
    """
    dev_nodes = [n for n, d in G.nodes(data=True) if d.get("bipartite") == "device"]
    if not dev_nodes:
        return np.zeros(28)

    embs = np.array([_device_embedding(G, d) for d in dev_nodes])

    mean_emb = embs.mean(axis=0)  # 14-dim
    std_emb = embs.std(axis=0)    # 14-dim (captures variance)

    return np.concatenate([mean_emb, std_emb])


def compute_device_embeddings(G: nx.MultiGraph) -> Dict[str, np.ndarray]:
    """Compute embeddings for all device nodes in the graph."""
    dev_nodes = [n for n, d in G.nodes(data=True) if d.get("bipartite") == "device"]
    return {d: _device_embedding(G, d) for d in dev_nodes}


# ═══════════════════════════════════════════════════════════════════════════════
# Similarity scoring
# ═══════════════════════════════════════════════════════════════════════════════

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def device_type_signature(G: nx.MultiGraph) -> Dict[str, int]:
    """Count devices by type."""
    counts: Dict[str, int] = defaultdict(int)
    for _, d in G.nodes(data=True):
        if d.get("bipartite") == "device":
            counts[d.get("dev_type", "unknown")] += 1
    return dict(counts)


def _mos_agnostic_signature(G: nx.MultiGraph) -> Dict[str, int]:
    """Count devices with MOS types merged (type-agnostic, as KB intends)."""
    counts: Dict[str, int] = defaultdict(int)
    for _, d in G.nodes(data=True):
        if d.get("bipartite") == "device":
            dt = d.get("dev_type", "unknown")
            if dt in ("nmos", "pmos"):
                counts["mos"] += 1
            else:
                counts[dt] += 1
    return dict(counts)


def structural_similarity(G_input: nx.MultiGraph, G_kb: nx.MultiGraph,
                          ports_input: List[str], ports_kb: List[str]) -> float:
    """Compute structural similarity between input and KB template graphs.

    Combines: (1) graph-level embedding cosine (with MOS-agnostic adjustment),
    (2) device count distribution overlap (MOS-agnostic), (3) port role alignment,
    (4) degree sequence similarity.
    """
    emb_in = compute_graph_embedding(G_input, ports_input)
    emb_kb = compute_graph_embedding(G_kb, ports_kb)

    # Zero out the NMOS/PMOS one-hot dimensions (indices 0,1 in mean and 14,15 in std)
    # to make the embedding MOS-type-agnostic
    emb_in_agnostic = emb_in.copy()
    emb_kb_agnostic = emb_kb.copy()
    for idx in [0, 1, 14, 15]:
        if idx < len(emb_in_agnostic):
            emb_in_agnostic[idx] = 0
            emb_kb_agnostic[idx] = 0

    cos_sim = cosine_similarity(emb_in_agnostic, emb_kb_agnostic)

    # MOS-agnostic device count Jaccard
    sig_in = _mos_agnostic_signature(G_input)
    sig_kb = _mos_agnostic_signature(G_kb)
    all_types = set(sig_in) | set(sig_kb)
    if all_types:
        intersection = sum(min(sig_in.get(t, 0), sig_kb.get(t, 0)) for t in all_types)
        union = sum(max(sig_in.get(t, 0), sig_kb.get(t, 0)) for t in all_types)
        type_jaccard = intersection / max(union, 1)
    else:
        type_jaccard = 0.0

    # Port role alignment
    sp_in = sum(1 for _, d in G_input.nodes(data=True) if d.get("role") == "SIGNAL_PORT")
    sp_kb = sum(1 for _, d in G_kb.nodes(data=True) if d.get("role") == "SIGNAL_PORT")
    port_sim = 1.0 - abs(sp_in - sp_kb) / max(sp_in + sp_kb, 1)

    # Device count similarity (penalize very different sizes)
    n_in = sum(1 for _, d in G_input.nodes(data=True) if d.get("bipartite") == "device")
    n_kb = sum(1 for _, d in G_kb.nodes(data=True) if d.get("bipartite") == "device")
    size_sim = min(n_in, n_kb) / max(n_in, n_kb, 1)

    score = 0.40 * cos_sim + 0.25 * type_jaccard + 0.20 * port_sim + 0.15 * size_sim
    return float(np.clip(score, 0.0, 1.0))


# ═══════════════════════════════════════════════════════════════════════════════
# Hungarian algorithm device mapping
# ═══════════════════════════════════════════════════════════════════════════════

def map_devices_hungarian(
    embs_input: Dict[str, np.ndarray],
    embs_kb: Dict[str, np.ndarray],
    G_input: nx.MultiGraph,
    G_kb: nx.MultiGraph,
) -> Dict[str, str]:
    """Map KB device names to input device names using Hungarian algorithm on
    embedding distances, restricted to same device type."""
    kb_devs = list(embs_kb.keys())
    in_devs = list(embs_input.keys())

    if not kb_devs or not in_devs:
        return {}

    def _type_class(dt: str) -> str:
        return "mos" if dt in ("nmos", "pmos") else dt

    kb_types = {d: _type_class(G_kb.nodes[d].get("dev_type", "")) for d in kb_devs}
    in_types = {d: _type_class(G_input.nodes[d].get("dev_type", "")) for d in in_devs}

    # Build cost matrix (KB rows x Input cols), large penalty for class mismatch
    # MOS devices match each other regardless of N/P polarity (type-agnostic)
    cost = np.full((len(kb_devs), len(in_devs)), 1e6)
    for i, kd in enumerate(kb_devs):
        for j, ind in enumerate(in_devs):
            if kb_types[kd] == in_types[ind]:
                dist = np.linalg.norm(embs_kb[kd] - embs_input[ind])
                cost[i, j] = dist

    row_ind, col_ind = linear_sum_assignment(cost)

    mapping = {}
    for r, c in zip(row_ind, col_ind):
        if cost[r, c] < 1e5:
            mapping[kb_devs[r]] = in_devs[c]

    return mapping


def map_nets(device_mapping: Dict[str, str], G_kb: nx.MultiGraph,
             G_input: nx.MultiGraph) -> Dict[str, str]:
    """Derive net mapping from device mapping by matching terminal connections."""
    net_map: Dict[str, str] = {}

    for kb_dev, in_dev in device_mapping.items():
        kb_edges = {edata["terminal"]: nbr for _, nbr, edata in G_kb.edges(kb_dev, data=True)
                    if G_kb.nodes.get(nbr, {}).get("bipartite") == "net"}
        in_edges = {edata["terminal"]: nbr for _, nbr, edata in G_input.edges(in_dev, data=True)
                    if G_input.nodes.get(nbr, {}).get("bipartite") == "net"}

        for term in kb_edges:
            if term in in_edges:
                kb_net = kb_edges[term]
                in_net = in_edges[term]
                if kb_net not in net_map:
                    net_map[kb_net] = in_net
    return net_map


# ═══════════════════════════════════════════════════════════════════════════════
# Constraint translation
# ═══════════════════════════════════════════════════════════════════════════════

def translate_constraints(
    constraints: List[Dict[str, Any]],
    device_mapping: Dict[str, str],
    net_mapping: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Translate KB constraint instances/nets to input netlist names."""
    name_map = {}
    name_map.update({k.lower(): v.lower() for k, v in device_mapping.items()})
    name_map.update({k.lower(): v.lower() for k, v in net_mapping.items()})

    def _remap(val: Any) -> Any:
        if isinstance(val, str):
            return name_map.get(val.lower(), val.lower())
        if isinstance(val, list):
            return [_remap(v) for v in val]
        if isinstance(val, dict):
            return {k: _remap(v) for k, v in val.items()}
        return val

    translated = []
    for c in constraints:
        new_c = {}
        for k, v in c.items():
            if k == "constraint":
                new_c[k] = v
            else:
                new_c[k] = _remap(v)
        translated.append(new_c)
    return translated


# ═══════════════════════════════════════════════════════════════════════════════
# Power/ground detection (analytical)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_power_ground(
    devices: List[Dict[str, Any]], circuit_ports: List[str],
) -> Tuple[List[str], List[str]]:
    """Detect power and ground ports from MOSFET bulk connections + name heuristics."""
    power_candidates = set()
    ground_candidates = set()
    port_set = {p.lower() for p in circuit_ports}

    for dev in devices:
        if dev["type"] == "pmos":
            b = dev.get("B", "")
            if b.lower() in port_set:
                power_candidates.add(b)
        elif dev["type"] == "nmos":
            b = dev.get("B", "")
            if b.lower() in port_set:
                ground_candidates.add(b)

    for p in circuit_ports:
        pl = p.lower()
        if pl in DEFAULT_POWER_NAMES:
            power_candidates.add(p)
        if pl in DEFAULT_GROUND_NAMES:
            ground_candidates.add(p)

    # NOTE: deliberately no fabrication fallback here. Previous code forced
    # `["VDD"]` / `["VSS"]` when nothing was detected, which emitted spurious
    # PowerPorts/GroundPorts on passive-only subcircuits (compensation_network,
    # feedback_divider, ...) and tanked precision on the F1 benchmark.
    power = sorted(power_candidates)
    ground = sorted(ground_candidates)
    return power, ground


# ═══════════════════════════════════════════════════════════════════════════════
# Knowledge Base Index
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class KBEntry:
    pattern_name: str
    sp_path: str
    netlist_text: str
    circuit_name: str
    circuit_ports: List[str]
    devices: List[Dict[str, Any]]
    graph: nx.MultiGraph
    constraints: List[Dict[str, Any]]
    device_embeddings: Dict[str, np.ndarray]
    graph_embedding: np.ndarray


class KnowledgeBaseIndex:
    """Loads and indexes all 16 KB templates at construction time."""

    def __init__(self, kb_dir: Optional[str] = None):
        self.kb_dir = Path(kb_dir) if kb_dir else KB_DIR
        self.entries: List[KBEntry] = []
        self._load_all()

    def _load_all(self):
        sp_files = sorted(self.kb_dir.glob("*.sp"))
        for sp_path in sp_files:
            pattern_name = sp_path.stem
            const_path = sp_path.with_suffix(".const.json")
            if not const_path.exists():
                continue

            netlist_text = sp_path.read_text(encoding="utf-8")
            with open(const_path, "r", encoding="utf-8") as f:
                constraints = json.load(f)

            try:
                cname, cports, devs = parse_netlist_general(netlist_text)
            except ValueError:
                continue

            G = build_bipartite_graph(devs, cports)
            dev_embs = compute_device_embeddings(G)
            graph_emb = compute_graph_embedding(G, cports)

            self.entries.append(KBEntry(
                pattern_name=pattern_name,
                sp_path=str(sp_path),
                netlist_text=netlist_text,
                circuit_name=cname,
                circuit_ports=cports,
                devices=devs,
                graph=G,
                constraints=constraints,
                device_embeddings=dev_embs,
                graph_embedding=graph_emb,
            ))

    def __len__(self):
        return len(self.entries)


# ═══════════════════════════════════════════════════════════════════════════════
# SubstructureMatcher
# ═══════════════════════════════════════════════════════════════════════════════

class SubstructureMatcher:
    """Matches an input netlist against the KB and produces initial constraints."""

    def __init__(self, kb_index: KnowledgeBaseIndex, top_k: int = 3, threshold: float = 0.45):
        self.kb = kb_index
        self.top_k = top_k
        self.threshold = threshold

    def match(
        self, devices: List[Dict[str, Any]], circuit_ports: List[str],
    ) -> Tuple[List[MatchResult], nx.MultiGraph, Dict[str, np.ndarray]]:
        """Find top-K KB templates matching the input, with translated constraints."""
        G_input = build_bipartite_graph(devices, circuit_ports)
        embs_input = compute_device_embeddings(G_input)

        scored: List[Tuple[float, KBEntry]] = []
        for entry in self.kb.entries:
            score = structural_similarity(G_input, entry.graph, circuit_ports, entry.circuit_ports)
            scored.append((score, entry))

        scored.sort(key=lambda x: -x[0])
        top = scored[: self.top_k]

        results = []
        for score, entry in top:
            if score < self.threshold:
                continue

            dev_map = map_devices_hungarian(embs_input, entry.device_embeddings, G_input, entry.graph)
            net_map = map_nets(dev_map, entry.graph, G_input)
            translated = translate_constraints(entry.constraints, dev_map, net_map)

            results.append(MatchResult(
                pattern_name=entry.pattern_name,
                similarity_score=score,
                device_mapping=dev_map,
                net_mapping=net_map,
                translated_constraints=translated,
            ))

        return results, G_input, embs_input

    def build_initial_constraints(
        self, matches: List[MatchResult], devices: List[Dict[str, Any]],
        circuit_ports: List[str],
    ) -> List[Dict[str, Any]]:
        """Merge constraints from all matched templates + power/ground detection."""
        constraints: List[Dict[str, Any]] = []
        seen_sigs: set = set()

        for m in matches:
            for c in m.translated_constraints:
                sig = json.dumps(c, sort_keys=True)
                if sig not in seen_sigs:
                    seen_sigs.add(sig)
                    constraints.append(c)

        # Option A: trust the netlist over the KB for supply ports.
        #
        # KB templates emit their own ``PowerPorts`` / ``GroundPorts`` using
        # template-boilerplate port names (``vdd`` / ``vss``). After
        # Hungarian translation those names are often mapped onto arbitrary
        # internal nets of the target (e.g. a transmission_gate template
        # mapped onto a PMOS-only current-source subcircuit can produce a
        # ``GroundPorts`` constraint pointing at an internal net, because
        # there is no NMOS bulk to anchor the mapping).  ``_reconcile_supply_ports``
        # later strips those bad entries, but the original guard below
        # ("skip detector if KB already emitted something") meant that the
        # correct netlist-detected port was never filled back in, causing
        # silent recall loss on Ground / Power F1 (see LDO_Simple/
        # gate_pull_driver_stage and pass_device_and_feedback).
        #
        # Fix: strip KB-translated PowerPorts / GroundPorts up front and
        # unconditionally emit exactly what ``detect_power_ground`` found
        # on the CURRENT netlist.  ``detect_power_ground`` already uses
        # both the MOSFET-bulk-on-port heuristic and the DEFAULT_*_NAMES
        # port-name heuristic on the real input ports, so it can never
        # produce ports that don't exist.  For passive-only subcircuits
        # it correctly returns empty lists, so no fabricated supplies.
        constraints = [
            c for c in constraints
            if c.get("constraint") not in ("PowerPorts", "GroundPorts")
        ]

        power, ground = detect_power_ground(devices, circuit_ports)
        if power:
            constraints.append({
                "constraint": "PowerPorts",
                "ports": [p.lower() for p in power],
            })
        if ground:
            constraints.append({
                "constraint": "GroundPorts",
                "ports": [g.lower() for g in ground],
            })

        return constraints


# ═══════════════════════════════════════════════════════════════════════════════
# LLM helper
# ═══════════════════════════════════════════════════════════════════════════════

class LLMHelper:
    """Thin wrapper around OpenAI chat completions."""

    def __init__(self, model: str = DEFAULT_MODEL_ENDPOINT):
        if OpenAI is None:
            raise ImportError("openai package is required for LLM calls. pip install openai")
        self.model = resolve_model_endpoint(model)
        self.client = OpenAI(
            base_url=NVIDIA_OPENAI_BASE_URL,
            api_key=os.getenv("NVIDIA_API_KEY"),
        )
        self._call_log: List[LLMCallResult] = []

    def call(self, system_prompt: str, user_prompt: str, temperature: float = 0.03) -> LLMCallResult:
        t0 = time.time()
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        dt = time.time() - t0
        usage = resp.usage
        result = LLMCallResult(
            content=resp.choices[0].message.content,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            runtime_seconds=dt,
            model=self.model,
        )
        self._call_log.append(result)
        return result

    def aggregate_metrics(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "num_llm_calls": len(self._call_log),
            "input_tokens": sum(r.input_tokens for r in self._call_log),
            "output_tokens": sum(r.output_tokens for r in self._call_log),
            "total_tokens": sum(r.total_tokens for r in self._call_log),
            "llm_runtime_seconds": sum(r.runtime_seconds for r in self._call_log),
        }

    def reset_log(self):
        self._call_log.clear()

    @staticmethod
    def extract_json(text: str) -> Any:
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        raw = fenced.group(1) if fenced else text
        for pattern in [r"\[.*\]", r"\{.*\}"]:
            match = re.search(pattern, raw, re.S)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        return json.loads(raw)

    @staticmethod
    def normalize_constraints(raw: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw, list):
            if isinstance(raw, dict) and "constraint" in raw:
                return [raw]
            raise ValueError("LLM output is not a JSON list.")
        return [c for c in raw if isinstance(c, dict) and "constraint" in c]


# ═══════════════════════════════════════════════════════════════════════════════
# Graph feature summary for LLM prompts
# ═══════════════════════════════════════════════════════════════════════════════

def graph_features_summary(G: nx.MultiGraph, devices: List[Dict[str, Any]],
                           circuit_ports: List[str]) -> Dict[str, Any]:
    """Extract graph features in a format suitable for LLM prompts."""
    dev_nodes = [n for n, d in G.nodes(data=True) if d.get("bipartite") == "device"]

    net_to_devs: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for u, v, edata in G.edges(data=True):
        dev_n = u if G.nodes[u].get("bipartite") == "device" else v
        net_n = v if G.nodes[v].get("bipartite") == "net" else u
        net_to_devs[net_n].append({"device": dev_n, "terminal": edata.get("terminal", "?")})

    device_degrees = {d: len(set(G.neighbors(d))) for d in dev_nodes}

    shared_nets = []
    for net, pins in net_to_devs.items():
        if len(pins) >= 2 and net.lower() not in SUPPLY_RAILS_LOWER:
            for i in range(len(pins)):
                for j in range(i + 1, len(pins)):
                    shared_nets.append({
                        "net": net, "dev1": pins[i]["device"], "pin1": pins[i]["terminal"],
                        "dev2": pins[j]["device"], "pin2": pins[j]["terminal"],
                    })

    nmos_devs = [d for d in dev_nodes if G.nodes[d].get("dev_type") == "nmos"]
    pmos_devs = [d for d in dev_nodes if G.nodes[d].get("dev_type") == "pmos"]

    param_matched = []
    for group in [nmos_devs, pmos_devs]:
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                p1 = G.nodes[group[i]].get("params", {})
                p2 = G.nodes[group[j]].get("params", {})
                if (p1.get("w") == p2.get("w") and p1.get("l") == p2.get("l")
                        and p1.get("nf", "1") == p2.get("nf", "1")
                        and p1.get("m", "1") == p2.get("m", "1")):
                    param_matched.append({
                        "dev1": group[i], "dev2": group[j],
                        "type": G.nodes[group[i]].get("dev_type"),
                    })

    return {
        "device_degrees": device_degrees,
        "shared_net_adjacencies": shared_nets,
        "parameter_matched_pairs": param_matched,
        "net_to_device_pins": dict(net_to_devs),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Constraint fingerprinting for dedup / merge
# ═══════════════════════════════════════════════════════════════════════════════

def constraint_fingerprint(c: Dict[str, Any]) -> str:
    """Produce a canonical fingerprint for deduplication."""
    ctype = c.get("constraint", "")
    key_parts = [ctype]
    if "instances" in c:
        key_parts.append("inst:" + ",".join(sorted(str(i).lower() for i in c["instances"])))
    if "pairs" in c:
        norm_pairs = sorted(tuple(sorted(str(x).lower() for x in p)) for p in c["pairs"])
        key_parts.append("pairs:" + str(norm_pairs))
    if "net1" in c and "net2" in c:
        nets = sorted([str(c["net1"]).lower(), str(c["net2"]).lower()])
        key_parts.append("nets:" + ",".join(nets))
    if "ports" in c:
        key_parts.append("ports:" + ",".join(sorted(str(p).lower() for p in c["ports"])))
    return "|".join(key_parts)


def deduplicate_constraints(constraints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate constraints based on fingerprinting."""
    seen = set()
    out = []
    for c in constraints:
        fp = constraint_fingerprint(c)
        if fp not in seen:
            seen.add(fp)
            out.append(c)
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
#
#  KB-ONLY: Pure graph-based constraint generation (zero LLM calls)
#
#  Ported from DATE'24 paper methodology (embedding + BFS symmetry expansion)
#  and the 1_Flow_Analysis_10_OneNetMultiNode.ipynb notebook.
#
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════


def _get_terminal_nets(G: nx.MultiGraph, dev: str) -> Dict[str, str]:
    """Return {terminal_name: net_name} for a device node."""
    term_nets = {}
    for _, nbr, edata in G.edges(dev, data=True):
        if G.nodes.get(nbr, {}).get("bipartite") == "net":
            term_nets[edata.get("terminal", "?")] = nbr
    return term_nets


def _get_pin_connection_vector(G: nx.MultiGraph, dev: str) -> List[str]:
    """Return ordered list of nets for a device (D,G,S,B for MOS; PLUS,MINUS for R/C)."""
    dtype = G.nodes[dev].get("dev_type", "")
    if dtype in ("nmos", "pmos"):
        order = ["D", "G", "S", "B"]
    else:
        order = ["PLUS", "MINUS"]
    tnets = _get_terminal_nets(G, dev)
    return [tnets.get(t, "") for t in order]


def _params_match(G: nx.MultiGraph, d1: str, d2: str) -> bool:
    """Check whether two devices have identical sizing parameters."""
    p1 = G.nodes[d1].get("params", {})
    p2 = G.nodes[d2].get("params", {})
    return (p1.get("w") == p2.get("w") and p1.get("l") == p2.get("l")
            and p1.get("nf", "1") == p2.get("nf", "1")
            and p1.get("m", "1") == p2.get("m", "1"))


def _is_power_net(G: nx.MultiGraph, net: str) -> bool:
    """Check if a net is a supply rail."""
    if net.lower() in SUPPLY_RAILS_LOWER:
        return True
    role = G.nodes.get(net, {}).get("role", "")
    return role == "SUPPLY"


def expand_symmetry_bfs(
    G: nx.MultiGraph,
    seed_pair: Tuple[str, str],
    power_nets: set,
    visited: set,
) -> Tuple[List[List[str]], List[str]]:
    """BFS-expand a seed symmetric device pair along the bipartite graph.

    Adapted from DATE'24 Algorithm 1 and the dual-queue BFS in
    1_Flow_Analysis_10_OneNetMultiNode.ipynb. Walks in parallel from both
    sides of the seed pair, matching neighbors that share the same pin role,
    component type, and parameters. Stops at power/supply nets.

    Returns:
        pairs: list of [dev_a, dev_b] symmetric device pairs (includes seed)
        self_sym: list of devices sitting on the symmetry axis
    """
    d0, d1 = seed_pair
    pairs = [[d0, d1]]
    self_sym = []
    local_visited = {d0, d1} | visited

    queue0 = deque([d0])
    queue1 = deque([d1])

    while queue0 and queue1:
        node0 = queue0.popleft()
        node1 = queue1.popleft()

        pins0 = _get_pin_connection_vector(G, node0)
        pins1 = _get_pin_connection_vector(G, node1)

        dtype0 = G.nodes[node0].get("dev_type", "")
        # For MOS, skip bulk terminal (last pin) to avoid trivial supply expansion
        if dtype0 in ("nmos", "pmos"):
            pins0 = pins0[:-1]
            pins1 = pins1[:-1]

        for i in range(min(len(pins0), len(pins1))):
            net0 = pins0[i]
            net1 = pins1[i]

            if not net0 or not net1:
                continue
            if net0.lower() in power_nets or net1.lower() in power_nets:
                continue
            if _is_power_net(G, net0) or _is_power_net(G, net1):
                continue

            # Same net => self-symmetry axis net; neighbors on it are self-symmetric
            if net0 == net1:
                for nbr in G.neighbors(net0):
                    ndata = G.nodes.get(nbr, {})
                    if (ndata.get("bipartite") == "device"
                            and nbr not in local_visited
                            and _params_match(G, node0, nbr)):
                        self_sym.append(nbr)
                        local_visited.add(nbr)
                continue

            # Gather unvisited device neighbors on each side
            neighbors0 = [n for n in G.neighbors(net0)
                          if G.nodes.get(n, {}).get("bipartite") == "device"
                          and n not in local_visited]
            neighbors1 = [n for n in G.neighbors(net1)
                          if G.nodes.get(n, {}).get("bipartite") == "device"
                          and n not in local_visited]

            for item0 in neighbors0:
                for item1 in neighbors1:
                    if item0 == item1 or item0 in local_visited or item1 in local_visited:
                        continue
                    if G.nodes[item0].get("dev_type") != G.nodes[item1].get("dev_type"):
                        continue
                    if not _params_match(G, item0, item1):
                        continue

                    # Pin-role alignment check: the connecting net must arrive
                    # at the same terminal index on both new devices
                    item0_pins = _get_pin_connection_vector(G, item0)
                    item1_pins = _get_pin_connection_vector(G, item1)
                    idx0 = {j for j, p in enumerate(item0_pins) if p == net0}
                    idx1 = {j for j, p in enumerate(item1_pins) if p == net1}
                    if idx0 & idx1:
                        pairs.append([item0, item1])
                        queue0.append(item0)
                        queue1.append(item1)
                        local_visited.add(item0)
                        local_visited.add(item1)

    return pairs, self_sym


def _find_symmetric_net_pairs(
    G: nx.MultiGraph,
    sym_pairs: List[List[str]],
    power_nets: set,
) -> List[Tuple[str, str]]:
    """For each device pair in a symmetry group, derive the corresponding net pairs."""
    net_pairs_set = set()
    for pair in sym_pairs:
        if len(pair) != 2:
            continue
        d0, d1 = pair
        tnets0 = _get_terminal_nets(G, d0)
        tnets1 = _get_terminal_nets(G, d1)
        for term in tnets0:
            if term in tnets1:
                n0 = tnets0[term]
                n1 = tnets1[term]
                if (n0 != n1
                        and n0.lower() not in power_nets
                        and n1.lower() not in power_nets
                        and not _is_power_net(G, n0)
                        and not _is_power_net(G, n1)):
                    key = tuple(sorted([n0.lower(), n1.lower()]))
                    net_pairs_set.add(key)
    return list(net_pairs_set)


def _device_type_lookup(
    G: nx.MultiGraph,
    devices: List[Dict[str, Any]],
) -> Dict[str, str]:
    """Build lowercase device-name -> MOS type map (``pmos``/``nmos``/other).

    Includes both the original and lowercase spellings so downstream filters
    can match constraints emitted with lowercase instance names.
    """
    out: Dict[str, str] = {}
    for d in devices:
        t = (d.get("type") or "").lower()
        name = d.get("name", "")
        if name:
            out[name] = t
            out[name.lower()] = t
    for n, data in G.nodes(data=True):
        if data.get("bipartite") != "device":
            continue
        t = (data.get("dev_type") or "").lower()
        if t:
            out[n] = out.get(n, t)
            out[str(n).lower()] = out.get(str(n).lower(), t)
    return out


def _same_mos_type(a: str, b: str, type_map: Dict[str, str]) -> bool:
    """Return True iff both devices are MOSFETs of the same type.

    Non-MOS devices (passives, etc.) always return False so cross-kind pairs
    never pass. Unknown devices (name not in map) also return False.
    """
    ta = type_map.get(a) or type_map.get(str(a).lower())
    tb = type_map.get(b) or type_map.get(str(b).lower())
    if ta not in ("nmos", "pmos") or tb not in ("nmos", "pmos"):
        return False
    return ta == tb


def _shared_pin_index_count(
    G: nx.MultiGraph, a: str, b: str,
) -> int:
    """Count how many of ``D/G/S/B`` are identical between two MOSFETs."""
    if a not in G.nodes or b not in G.nodes:
        return 0
    pins_a = _get_pin_connection_vector(G, a)
    pins_b = _get_pin_connection_vector(G, b)
    return sum(
        1 for pa, pb in zip(pins_a, pins_b)
        if pa and pb and pa == pb
    )


def _has_canonical_terminal_signature(
    G: nx.MultiGraph, a: str, b: str,
) -> bool:
    """Does this pair look like a canonical analog symmetry topology?

    Accepts exactly the four layout-friendly signatures we want to
    preserve:

    * current-mirror / ratioed-mirror family (same G + S + B, any D)
    * push-pull / inverter family           (same G + D + B, any S)
    * differential-pair family              (same S + B, any G, any D)
    * drain-tied diff pair                  (same D + B, any G, any S)

    Rejects pairs that share only G + B (common failure on clock / bias
    rails where many devices share a gate but are otherwise unrelated)
    and pairs with 0-1 matches (which are only legitimate in a cross-
    coupled topology; those are handled separately via ``exempt_pairs``).
    """
    if a not in G.nodes or b not in G.nodes:
        return False
    pins_a = _get_pin_connection_vector(G, a)
    pins_b = _get_pin_connection_vector(G, b)
    if len(pins_a) < 4 or len(pins_b) < 4:
        return False
    d_eq = pins_a[0] and pins_a[0] == pins_b[0]
    g_eq = pins_a[1] and pins_a[1] == pins_b[1]
    s_eq = pins_a[2] and pins_a[2] == pins_b[2]
    b_eq = pins_a[3] and pins_a[3] == pins_b[3]
    shared = int(bool(d_eq)) + int(bool(g_eq)) + int(bool(s_eq)) + int(bool(b_eq))
    if shared >= 3:
        # Current-mirror (G+S+B) or push-pull (G+D+B) or full-4 (dummy).
        return True
    if shared == 2 and b_eq:
        # Bulk-plus-one-non-bulk. Only diff-pair (S+B) and drain-tied
        # diff (D+B) are canonical. G+B alone is NOT (that is the bias /
        # clock-rail failure mode we want to reject).
        if s_eq or d_eq:
            return True
    return False


def _canonical_pair_ok(
    a: str, b: str,
    G: "nx.MultiGraph",
    type_map: Dict[str, str],
    exempt_pairs: Optional[Set[frozenset]] = None,
) -> bool:
    """Canonical-pair-quality check for ``SymmetricBlocks`` pairs.

    Returns ``True`` iff the pair (a, b) satisfies every one of:

    * same MOS type (pmos-pmos or nmos-nmos),
    * either the pair is tagged as a cross-coupled motif (in
      ``exempt_pairs`` as a ``frozenset``), OR BOTH parameters match
      (W/L/nf/m) AND the pair shares at least 2 of 4 terminal nets at the
      same pin index.

    The ``exempt_pairs`` set lets us keep legitimate cross-coupled latches
    (e.g. StrongArm back-to-back pairs) that can have identical or slightly
    different parameters in practice and share fewer terminals than a
    differential pair.
    """
    if not _same_mos_type(a, b, type_map):
        return False
    key = frozenset({str(a).lower(), str(b).lower()})
    if exempt_pairs and key in exempt_pairs:
        return True
    # Compare params and terminal sharing on the netlist graph.
    # The graph may carry upper-case node names while constraints use
    # lowercase; resolve to the real graph node name by case-insensitive
    # lookup when needed.
    def _resolve(name: str) -> Optional[str]:
        if name in G.nodes:
            return name
        for n in G.nodes:
            if str(n).lower() == str(name).lower():
                return n
        return None

    a_node = _resolve(a)
    b_node = _resolve(b)
    if a_node is None or b_node is None:
        # Cannot evaluate -> fall back to conservative reject so unrelated
        # pairs don't slip through, but keep cross-coupled exempts above.
        return False
    if not _params_match(G, a_node, b_node):
        return False
    # Tightened from ">=2 shared terminals" to one of the four canonical
    # analog symmetry signatures (see `_has_canonical_terminal_signature`).
    # The previous "any 2 shared" rule admitted G+B-only bias / clock-net
    # pairs which were the dominant remaining precision leak.
    return _has_canonical_terminal_signature(G, a_node, b_node)


def _filter_bad_sym_pairs(
    constraints: List[Dict[str, Any]],
    G: "nx.MultiGraph",
    type_map: Dict[str, str],
    exempt_pairs: Optional[Set[frozenset]] = None,
) -> List[Dict[str, Any]]:
    """Drop ``SymmetricBlocks`` pairs that fail ``_canonical_pair_ok``.

    Singleton pairs (self-symmetric axis devices) are preserved.  Empty
    ``SymmetricBlocks`` entries are dropped.  Non-``SymmetricBlocks``
    constraints are passed through untouched.  This subsumes
    ``_filter_cross_type_pairs`` but also catches pairs with mismatched
    parameters / insufficient terminal overlap that the type-only filter
    let through.
    """
    out: List[Dict[str, Any]] = []
    for c in constraints:
        if not isinstance(c, dict) or c.get("constraint") != "SymmetricBlocks":
            out.append(c)
            continue
        clean_pairs: List[List[str]] = []
        for pr in c.get("pairs", []) or []:
            if not isinstance(pr, (list, tuple)):
                continue
            if len(pr) == 1:
                clean_pairs.append([str(pr[0])])
                continue
            if len(pr) != 2:
                continue
            a, b = str(pr[0]), str(pr[1])
            if _canonical_pair_ok(a, b, G, type_map, exempt_pairs):
                clean_pairs.append([a, b])
        if clean_pairs:
            new_c = dict(c)
            new_c["pairs"] = clean_pairs
            out.append(new_c)
    return out


def _filter_cross_type_pairs(
    constraints: List[Dict[str, Any]],
    type_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Strip cross-MOS-type pairs out of every SymmetricBlocks entry.

    Singleton pairs (``[dev]``) are left in place -- they encode a
    self-symmetric device sitting on the axis, not a cross-type pair.
    Empty SymmetricBlocks entries are dropped entirely.
    """
    out: List[Dict[str, Any]] = []
    for c in constraints:
        if not isinstance(c, dict) or c.get("constraint") != "SymmetricBlocks":
            out.append(c)
            continue
        clean_pairs: List[List[str]] = []
        for pr in c.get("pairs", []) or []:
            if not isinstance(pr, (list, tuple)):
                continue
            if len(pr) == 1:
                clean_pairs.append([str(pr[0])])
                continue
            if len(pr) != 2:
                continue
            a, b = str(pr[0]), str(pr[1])
            if _same_mos_type(a, b, type_map):
                clean_pairs.append([a, b])
        if clean_pairs:
            new_c = dict(c)
            new_c["pairs"] = clean_pairs
            out.append(new_c)
    return out


def _reconcile_supply_ports(
    constraints: List[Dict[str, Any]],
    power_valid: List[str],
    ground_valid: List[str],
) -> List[Dict[str, Any]]:
    """Cross-check every ``PowerPorts`` / ``GroundPorts`` constraint against
    the supplies actually found in this netlist by ``detect_power_ground``.

    KB templates often re-use boiler-plate supply names (``vdd`` / ``vss``)
    that don't necessarily exist in the target netlist, and the translator
    sometimes puts the matched circuit's ground net into a ``PowerPorts``
    slot (or vice-versa) because the template mapping is degenerate for
    subcircuits without a VDD rail. This pass:

    * replaces every ``PowerPorts.ports`` with its intersection against
      the netlist-validated power-port list,
    * does the same for ``GroundPorts``,
    * drops the constraint entirely when that intersection is empty.

    If multiple ``PowerPorts`` (or ``GroundPorts``) constraints survive,
    the downstream fingerprint-dedup will fold them into one.
    """
    power_set = {p.lower() for p in power_valid}
    ground_set = {g.lower() for g in ground_valid}

    out: List[Dict[str, Any]] = []
    for c in constraints:
        if not isinstance(c, dict):
            out.append(c)
            continue
        ctype = c.get("constraint")
        if ctype == "PowerPorts":
            kept = [p for p in c.get("ports", [])
                    if str(p).lower() in power_set]
            if kept:
                new_c = dict(c)
                new_c["ports"] = kept
                out.append(new_c)
        elif ctype == "GroundPorts":
            kept = [p for p in c.get("ports", [])
                    if str(p).lower() in ground_set]
            if kept:
                new_c = dict(c)
                new_c["ports"] = kept
                out.append(new_c)
        else:
            out.append(c)
    return out


def _clean_symmetric_blocks(
    constraints: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Normalise SymmetricBlocks entries for the F1 benchmark:

    * drop pairs whose length is not exactly 2 (singletons / stray lists),
    * dedupe pairs within a single SymmetricBlocks using ``frozenset``
      equality so ``[a, b]`` and ``[b, a]`` don't both get emitted,
    * drop SymmetricBlocks entries that become empty.

    List-level dedup across multiple SymmetricBlocks (same set of pairs,
    different order) is already handled downstream by
    ``deduplicate_constraints`` via ``constraint_fingerprint``.
    """
    out: List[Dict[str, Any]] = []
    for c in constraints:
        if not isinstance(c, dict) or c.get("constraint") != "SymmetricBlocks":
            out.append(c)
            continue
        seen_pairs: Set[frozenset] = set()
        clean_pairs: List[List[str]] = []
        for pr in c.get("pairs", []) or []:
            if not isinstance(pr, (list, tuple)) or len(pr) != 2:
                continue
            a, b = str(pr[0]), str(pr[1])
            key = frozenset({a.lower(), b.lower()})
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            clean_pairs.append([a, b])
        if clean_pairs:
            new_c = dict(c)
            new_c["pairs"] = clean_pairs
            out.append(new_c)
    return out


def _default_match_devices_from_symmetric_blocks(
    constraints: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Graph-default MatchDevices for the KB-only path: mirror every
    cleaned SymmetricBlocks into a parallel MatchDevices with identical
    pairs. LLM paths emit MatchDevices directly via the CONSTRAINT_SCHEMA
    entry instead."""
    out: List[Dict[str, Any]] = []
    for c in constraints:
        if not isinstance(c, dict) or c.get("constraint") != "SymmetricBlocks":
            continue
        clean_pairs = [list(p) for p in (c.get("pairs", []) or [])
                       if isinstance(p, (list, tuple)) and len(p) == 2]
        if not clean_pairs:
            continue
        out.append({
            "constraint": "MatchDevices",
            "direction": c.get("direction", "V"),
            "pairs": clean_pairs,
        })
    return out


def _graphwalk_symmetry_seeds(
    G: nx.MultiGraph,
    power_nets: Set[str],
) -> List[Dict[str, str]]:
    """Mine candidate symmetric device pairs from the bipartite device-net graph.

    These seeds are *graph-topological* — they look at what each device's
    terminals connect to in the already-built NetworkX graph, NOT at
    isolated device-attribute predicates (which would duplicate the
    heuristics in ``GroundTruth_Constraints/_generate_ground_truth.py``
    and cause circularity in the F1 evaluation).

    Three independent motifs are detected:

    1. **shared_gate** — any two same-type MOSFETs whose gate terminals
       both land on the same non-supply net (canonical current-mirror
       topology).
    2. **shared_source** — any two same-type MOSFETs whose source
       terminals share a non-supply net (canonical differential-pair
       tail-node topology). Emitted only when the device pair has
       different gates (otherwise they are already caught by the
       shared-gate motif).
    3. **cross_coupled** — two same-type MOSFETs such that
       ``M1.D == M2.G`` and ``M2.D == M1.G`` (canonical cross-coupled
       latch topology).

    The function returns a list of ``{"dev1", "dev2", "type", "motif"}``
    dicts. Pairs appearing in multiple motifs are reported once, tagged
    with the first motif they were found under.

    NOTE: no parameter (W/L/nf/m) equality is required here — this is a
    *seed* list for BFS expansion; downstream BFS + type-safety filters
    decide which seeds turn into emitted ``SymmetricBlocks``.
    """
    seeds: List[Dict[str, str]] = []
    seen: Set[frozenset] = set()

    def _mos_type(d: str) -> str:
        return G.nodes[d].get("dev_type", "")

    def _same_mos_type(d1: str, d2: str) -> bool:
        t1 = _mos_type(d1)
        t2 = _mos_type(d2)
        return t1 in ("nmos", "pmos") and t1 == t2

    def _emit(d1: str, d2: str, motif: str) -> None:
        if d1 == d2:
            return
        if not _same_mos_type(d1, d2):
            return
        # P1: parameter equality required for shared_gate / shared_source /
        # clock_complement motifs. cross_coupled is exempt -- the 4-cycle
        # topology is specific enough that matched sizing is implicit.
        if motif != "cross_coupled" and not _params_match(G, d1, d2):
            return
        key = frozenset({d1, d2})
        if key in seen:
            return
        seen.add(key)
        seeds.append({
            "dev1": d1, "dev2": d2,
            "type": _mos_type(d1),
            "motif": motif,
        })

    def _param_key(d: str) -> Tuple[str, str, str, str, str]:
        p = G.nodes[d].get("params", {}) or {}
        return (_mos_type(d), str(p.get("w", "")), str(p.get("l", "")),
                str(p.get("nf", "1")), str(p.get("m", "1")))

    # --- Build fast terminal lookup for every device ------------------
    term_nets: Dict[str, Dict[str, str]] = {}
    for u, v, edata in G.edges(data=True):
        du, dv = G.nodes[u].get("bipartite"), G.nodes[v].get("bipartite")
        if du == "device" and dv == "net":
            dev, net_n = u, v
        elif dv == "device" and du == "net":
            dev, net_n = v, u
        else:
            continue
        term_nets.setdefault(dev, {})[edata.get("terminal", "?")] = net_n

    def _emit_bucket_shared_gate(devs: List[str]) -> None:
        """P3 + extra sub-grouping for the shared-gate motif.

        Devices in ``devs`` all share a non-supply gate net. Within the
        same (type, W, L, nf, m) parameter bucket, we further sub-group
        by matching ``S`` terminal (current-mirror family: shared gate +
        shared source) OR matching ``D`` terminal (push-pull / drain-
        tied family: shared gate + shared drain). Only sub-buckets of
        size exactly 2 emit a seed; larger sub-buckets remain ambiguous
        and are skipped.

        This lets the sc_cmfb-style topologies (many switches on a clock
        net that differ only in their drain or source connection) be
        picked up while still killing the N-finger-mirror spurious pairs
        in bias generators.
        """
        by_params: Dict[Tuple[str, ...], List[str]] = defaultdict(list)
        for d in devs:
            by_params[_param_key(d)].append(d)
        emitted_here: Set[frozenset] = set()
        for bucket in by_params.values():
            if len(bucket) < 2:
                continue
            # Sub-bucket by shared source (current-mirror family)
            by_src: Dict[str, List[str]] = defaultdict(list)
            for d in bucket:
                by_src[term_nets.get(d, {}).get("S", "")].append(d)
            for sb in by_src.values():
                if len(sb) == 2:
                    k = frozenset({sb[0], sb[1]})
                    if k in emitted_here:
                        continue
                    emitted_here.add(k)
                    _emit(sb[0], sb[1], "shared_gate")
            # Sub-bucket by shared drain (push-pull / inverter family)
            by_drn: Dict[str, List[str]] = defaultdict(list)
            for d in bucket:
                by_drn[term_nets.get(d, {}).get("D", "")].append(d)
            for db in by_drn.values():
                if len(db) == 2:
                    k = frozenset({db[0], db[1]})
                    if k in emitted_here:
                        continue
                    emitted_here.add(k)
                    _emit(db[0], db[1], "shared_gate")

    # --- Motif 1 & 2: nets that receive multiple G or S terminals -----
    for net, ndata in G.nodes(data=True):
        if ndata.get("bipartite") != "net":
            continue
        if net.lower() in power_nets:
            continue
        if _is_power_net(G, net):
            continue

        gate_devs: List[str] = []
        src_devs: List[str] = []
        for _, nbr, edata in G.edges(net, data=True):
            dev = nbr if G.nodes[nbr].get("bipartite") == "device" else None
            if dev is None:
                continue
            t = edata.get("terminal")
            if t == "G":
                gate_devs.append(dev)
            elif t == "S":
                src_devs.append(dev)

        # Shared-gate family.  ``_emit_bucket_shared_gate`` sub-groups by
        # both matching source (current-mirror subfamily) and matching
        # drain (push-pull subfamily), and caps each sub-bucket at size 2
        # so N-finger mirrors don't explode into all-pairs.
        _emit_bucket_shared_gate(gate_devs)

        # Shared-source (diff-pair family). Group by parameter signature,
        # then within each bucket of size exactly 2 keep only pairs whose
        # gates differ (same-gate cascaded devices are already covered by
        # Motif 1).
        by_params_src: Dict[Tuple[str, ...], List[str]] = defaultdict(list)
        for d in src_devs:
            by_params_src[_param_key(d)].append(d)
        for bucket in by_params_src.values():
            if len(bucket) != 2:
                continue  # ambiguous (>=3) or trivial (<2) - skip
            d1, d2 = bucket
            g1 = term_nets.get(d1, {}).get("G")
            g2 = term_nets.get(d2, {}).get("G")
            if g1 and g2 and g1 == g2:
                continue
            _emit(d1, d2, "shared_source")

    # --- Motif 3: cross-coupled 4-cycle through D<->G ------------------
    # For each device, look at its drain-net; for every device on that
    # drain-net's gate side, check if the back-edge holds (D'==G).
    for d1, t1 in term_nets.items():
        d_net = t1.get("D")
        g_net = t1.get("G")
        if not d_net or not g_net:
            continue
        if d_net.lower() in power_nets or g_net.lower() in power_nets:
            continue
        # Devices using d_net as their GATE
        for _, nbr, edata in G.edges(d_net, data=True):
            if G.nodes[nbr].get("bipartite") != "device":
                continue
            if nbr == d1 or edata.get("terminal") != "G":
                continue
            d2 = nbr
            t2 = term_nets.get(d2, {})
            if t2.get("D") == g_net:
                _emit(d1, d2, "cross_coupled")

    # --- Motif 4: complementary-clock diff pair (P5) -------------------
    # In switched-capacitor / clocking networks, the symmetric layout
    # partner of a device gated by signal port ``CLK1`` is usually the
    # device gated by ``CLK1B`` (or ``CLK1_N``, ``CLK1_b``).  Enumerate
    # same-param pairs whose gates are pin-level name-complements.
    def _is_complement(name_a: str, name_b: str) -> bool:
        la, lb = name_a.lower(), name_b.lower()
        if la == lb:
            return False
        for suffix in ("b", "_b", "_n", "n", "_bar", "bar"):
            if la + suffix == lb or lb + suffix == la:
                return True
        return False

    signal_ports = [n for n, nd in G.nodes(data=True)
                    if nd.get("bipartite") == "net"
                    and nd.get("role") == "SIGNAL_PORT"]
    for i, p1 in enumerate(signal_ports):
        for p2 in signal_ports[i + 1:]:
            if not _is_complement(p1, p2):
                continue
            # Gather devices using p1 / p2 as their gate.
            g1_devs = [d for d, t in term_nets.items() if t.get("G") == p1]
            g2_devs = [d for d, t in term_nets.items() if t.get("G") == p2]
            if not g1_devs or not g2_devs:
                continue
            # For each pair (one gate=p1, one gate=p2) with matching param
            # keys, emit as candidate.  Apply the P3 cap indirectly by
            # building a param-indexed lookup on each side.
            by_param_a: Dict[Tuple[str, ...], List[str]] = defaultdict(list)
            by_param_b: Dict[Tuple[str, ...], List[str]] = defaultdict(list)
            for d in g1_devs:
                by_param_a[_param_key(d)].append(d)
            for d in g2_devs:
                by_param_b[_param_key(d)].append(d)
            for pk in by_param_a:
                if pk not in by_param_b:
                    continue
                a_list = by_param_a[pk]
                b_list = by_param_b[pk]
                # Only emit when both sides have exactly one candidate
                # (clean 1-for-1 complementary pair).
                if len(a_list) == 1 and len(b_list) == 1:
                    _emit(a_list[0], b_list[0], "clock_complement")

    return seeds


def _detect_same_template_groups(
    G: nx.MultiGraph,
    devices: List[Dict[str, Any]],
) -> List[List[str]]:
    """Find groups of 2+ devices with identical type and parameters."""
    groups: Dict[str, List[str]] = defaultdict(list)
    for dev in devices:
        dtype = dev["type"]
        p = dev.get("params", {})
        key = (dtype, p.get("w", ""), p.get("l", ""),
               p.get("nf", "1"), p.get("m", "1"))
        groups[str(key)].append(dev["name"])
    return [g for g in groups.values() if len(g) >= 2]


def _infer_port_locations(
    G: nx.MultiGraph,
    circuit_ports: List[str],
    power_ports: List[str],
    ground_ports: List[str],
) -> List[Dict[str, Any]]:
    """Heuristic port placement: supply top/bottom, signal ports left/right."""
    constraints = []
    supply_set = {p.lower() for p in power_ports + ground_ports}

    top_ports = [p for p in power_ports if p.lower() not in SUPPLY_RAILS_LOWER]
    bottom_ports = [p for p in ground_ports if p.lower() not in SUPPLY_RAILS_LOWER]
    signal_ports = [p for p in circuit_ports
                    if p.lower() not in supply_set and p.lower() not in SUPPLY_RAILS_LOWER]

    if top_ports:
        constraints.append({"constraint": "PortLocation", "ports": [p.lower() for p in top_ports], "location": "TC"})
    if bottom_ports:
        constraints.append({"constraint": "PortLocation", "ports": [p.lower() for p in bottom_ports], "location": "BC"})

    # Split signal ports into input-like (connected to gates) and output-like
    input_ports = []
    output_ports = []
    for p in signal_ports:
        is_gate_connected = False
        for nbr in G.neighbors(p):
            ndata = G.nodes.get(nbr, {})
            if ndata.get("bipartite") != "device":
                continue
            for _, _, edata in G.edges(nbr, data=True):
                if edata.get("terminal") == "G":
                    net_of_gate = None
                    for _, n2, ed2 in G.edges(nbr, data=True):
                        if ed2.get("terminal") == "G" and G.nodes.get(n2, {}).get("bipartite") == "net":
                            net_of_gate = n2
                    if net_of_gate and net_of_gate.lower() == p.lower():
                        is_gate_connected = True
                        break
            if is_gate_connected:
                break
        if is_gate_connected:
            input_ports.append(p)
        else:
            output_ports.append(p)

    if input_ports:
        constraints.append({"constraint": "PortLocation", "ports": [p.lower() for p in input_ports], "location": "LC"})
    if output_ports:
        constraints.append({"constraint": "PortLocation", "ports": [p.lower() for p in output_ports], "location": "RC"})

    return constraints


def generate_constraints_from_graph(
    G: nx.MultiGraph,
    devices: List[Dict[str, Any]],
    circuit_ports: List[str],
    initial_constraints: List[Dict[str, Any]],
    matches: List["MatchResult"],
    gf: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Generate a complete ALIGN constraint set purely from graph analysis.

    Uses:
      1. KB-translated constraints as the seed (already matched and translated)
      2. BFS symmetry expansion to discover additional symmetric pairs
      3. Graph-derived SymmetricNets, SameTemplate, PortLocation
      4. Power/ground detection (already in initial_constraints)

    Zero LLM calls. Runtime is dominated by graph matching (already done).
    """
    # Scrub KB-translated constraints up front.  We apply the STRONGER
    # ``_filter_bad_sym_pairs`` filter (not only cross-MOS-type), because
    # KB templates sometimes re-emit pairs between same-type but
    # differently-sized devices (e.g. a PMOS load and a PMOS tail with
    # different W/L). Those bogus pairs otherwise pollute
    # ``visited_for_bfs`` below and silently block the correct same-type
    # same-sized pair from being discovered by BFS expansion.
    type_map = _device_type_lookup(G, devices)
    all_constraints = _filter_bad_sym_pairs(list(initial_constraints), G, type_map)

    power_nets = set()
    for c in all_constraints:
        if c.get("constraint") == "PowerPorts":
            power_nets.update(p.lower() for p in c.get("ports", []))
        if c.get("constraint") == "GroundPorts":
            power_nets.update(p.lower() for p in c.get("ports", []))
    power_nets |= SUPPLY_RAILS_LOWER

    # Collect device names already covered by KB SymmetricBlocks (now only
    # containing canonical pairs, thanks to the scrub above).  We count a
    # device as "covered" only when it is part of a real 2-element pair.
    # Singleton entries (``[dev]`` = self-symmetric axis device) should
    # NOT block that device from being paired with a matching partner by
    # BFS -- they're not actually a symmetry claim, just an axis marker.
    existing_sym_devices = set()
    existing_sym_pairs = []
    for c in all_constraints:
        if c.get("constraint") == "SymmetricBlocks":
            for pair in c.get("pairs", []):
                if len(pair) == 2:
                    for d in pair:
                        existing_sym_devices.add(d.lower())
                    existing_sym_pairs.append([p.lower() for p in pair])

    # --- BFS symmetry expansion from parameter-matched seed pairs ---
    # We combine two seed families here:
    #   1. ``parameter_matched_pairs`` - devices of same type with identical
    #      W/L/nf/m (device-attribute-based, from graph_features_summary).
    #   2. Graph-walk motif seeds (``_graphwalk_symmetry_seeds``): purely
    #      topological evidence from the bipartite device-net NetworkX graph
    #      (shared_gate / shared_source / cross_coupled / clock_complement).
    #      Seeds from shared_gate / shared_source / clock_complement are
    #      already parameter-matched (enforced inside the helper); seeds
    #      from cross_coupled are emitted even for differently-sized pairs
    #      because the 4-cycle topology is itself a strong signature.
    graphwalk_seeds = _graphwalk_symmetry_seeds(G, power_nets)
    # IMPORTANT: put graph-walk seeds FIRST in the BFS processing order.
    # Graph-walk seeds come from specific topological motifs
    # (shared_gate+shared_D/S, shared_source+different_G, cross_coupled,
    # clock_complement) and are already known-canonical.  The raw
    # ``parameter_matched_pairs`` list is a Cartesian product over same-
    # param devices (e.g. for 8 same-size switches on one clock line you
    # get 28 pairs, most of which are wrong).  If we process param_matched
    # first, BFS can mark the devices as visited via a noisy "first seen"
    # pair and block the correct graph-walk seed from firing.  Ordering by
    # motif quality fixes that.
    param_matched: List[Dict[str, Any]] = []
    _seen_seed_keys: Set[frozenset] = set()
    for s in graphwalk_seeds:
        key = frozenset({s["dev1"], s["dev2"]})
        if key in _seen_seed_keys:
            continue
        _seen_seed_keys.add(key)
        param_matched.append({"dev1": s["dev1"], "dev2": s["dev2"],
                               "type": s["type"], "motif": s.get("motif")})
    for pm in gf.get("parameter_matched_pairs", []):
        key = frozenset({pm["dev1"], pm["dev2"]})
        if key in _seen_seed_keys:
            continue
        _seen_seed_keys.add(key)
        param_matched.append({**pm, "motif": pm.get("motif", "param_match")})
    # Remember which pairs carry a cross_coupled motif tag -- those are
    # exempt from the param-equality / shared-terminal requirements in
    # P2's canonical filter (a cross-coupled pair has swapped D/G and only
    # shares the bulk, so it would otherwise fail the >=2 shared-pin check).
    # Lowercase the device names because ``_canonical_pair_ok`` lowercases
    # both sides of the lookup.
    _cross_coupled_pairs: Set[frozenset] = {
        frozenset({str(s["dev1"]).lower(), str(s["dev2"]).lower()})
        for s in graphwalk_seeds if s.get("motif") == "cross_coupled"
    }

    dev_nodes = [n for n, d in G.nodes(data=True) if d.get("bipartite") == "device"]
    visited_for_bfs = set(existing_sym_devices)

    new_sym_groups = []
    for pm in param_matched:
        d1 = pm["dev1"]
        d2 = pm["dev2"]
        if d1.lower() in visited_for_bfs or d2.lower() in visited_for_bfs:
            continue
        if d1 == d2:
            continue

        # Canonical-pair-quality gate. A seed pair must either be tagged
        # as a cross_coupled motif (exempt from param / terminal checks)
        # or pass ``_canonical_pair_ok``: same MOS type + matching W/L/nf/m
        # + one of the four canonical analog symmetry signatures
        # (current-mirror, push-pull, diff-pair, drain-tied-diff).  This
        # prevents the Cartesian ``parameter_matched_pairs`` cross product
        # from sending noisy (G+B only) shared-bias pairs into BFS and
        # locking out the correct graph-walk seed.
        if not _canonical_pair_ok(d1, d2, G, type_map,
                                   exempt_pairs=_cross_coupled_pairs):
            continue

        # Validate structural symmetry: must share a signal net at the same pin role,
        # or be connected to parallel signal paths
        pins1 = _get_pin_connection_vector(G, d1)
        pins2 = _get_pin_connection_vector(G, d2)

        has_structural_link = False
        # Check if they share a net at the same pin (e.g., shared source = diff pair)
        for idx in range(min(len(pins1), len(pins2))):
            if pins1[idx] and pins2[idx] and pins1[idx] == pins2[idx]:
                if not _is_power_net(G, pins1[idx]):
                    has_structural_link = True
                    break
        # Or check if their gate nets are symmetric signal ports
        if not has_structural_link:
            tnets1 = _get_terminal_nets(G, d1)
            tnets2 = _get_terminal_nets(G, d2)
            g1 = tnets1.get("G", "")
            g2 = tnets2.get("G", "")
            if (g1 and g2 and g1 != g2
                    and G.nodes.get(g1, {}).get("role") == "SIGNAL_PORT"
                    and G.nodes.get(g2, {}).get("role") == "SIGNAL_PORT"):
                has_structural_link = True

        if not has_structural_link:
            continue

        pairs, self_sym = expand_symmetry_bfs(G, (d1, d2), power_nets, visited_for_bfs)
        if pairs:
            new_sym_groups.append({"pairs": pairs, "self_sym": self_sym})
            for p in pairs:
                visited_for_bfs.update(x.lower() for x in p)
            for s in self_sym:
                visited_for_bfs.add(s.lower())

    # Add new SymmetricBlocks from BFS expansion
    for group in new_sym_groups:
        sym_block_pairs = []
        for pair in group["pairs"]:
            sym_block_pairs.append([p.lower() for p in pair])
        for s in group["self_sym"]:
            sym_block_pairs.append([s.lower()])
        if sym_block_pairs:
            all_constraints.append({
                "constraint": "SymmetricBlocks",
                "direction": "V",
                "pairs": sym_block_pairs,
            })

    # --- SymmetricNets: derive from all symmetric device pairs ---
    all_sym_pairs = list(existing_sym_pairs)
    for group in new_sym_groups:
        all_sym_pairs.extend(group["pairs"])

    existing_sym_nets = set()
    for c in all_constraints:
        if c.get("constraint") == "SymmetricNets":
            key = tuple(sorted([c.get("net1", "").lower(), c.get("net2", "").lower()]))
            existing_sym_nets.add(key)

    net_pairs = _find_symmetric_net_pairs(G, all_sym_pairs, power_nets)
    for n1, n2 in net_pairs:
        key = tuple(sorted([n1, n2]))
        if key not in existing_sym_nets:
            # Only add if at least one net is a signal port (externally visible symmetry)
            role1 = G.nodes.get(n1, G.nodes.get(key[0], {})).get("role", "")
            role2 = G.nodes.get(n2, G.nodes.get(key[1], {})).get("role", "")
            if role1 == "SIGNAL_PORT" or role2 == "SIGNAL_PORT":
                all_constraints.append({
                    "constraint": "SymmetricNets",
                    "net1": key[0],
                    "net2": key[1],
                    "direction": "V",
                })
                existing_sym_nets.add(key)

    # --- SameTemplate: parameter-matched groups not yet covered ---
    existing_same_template = set()
    for c in all_constraints:
        if c.get("constraint") == "SameTemplate":
            existing_same_template.add(frozenset(i.lower() for i in c.get("instances", [])))

    template_groups = _detect_same_template_groups(G, devices)
    for tg in template_groups:
        key = frozenset(d.lower() for d in tg)
        if key not in existing_same_template and len(tg) <= 4:
            all_constraints.append({
                "constraint": "SameTemplate",
                "instances": [d.lower() for d in tg],
            })

    # --- PortLocation: heuristic placement ---
    has_port_location = any(c.get("constraint") == "PortLocation" for c in all_constraints)
    if not has_port_location:
        power_ports_list = []
        ground_ports_list = []
        for c in all_constraints:
            if c.get("constraint") == "PowerPorts":
                power_ports_list = c.get("ports", [])
            if c.get("constraint") == "GroundPorts":
                ground_ports_list = c.get("ports", [])
        port_locs = _infer_port_locations(G, circuit_ports, power_ports_list, ground_ports_list)
        all_constraints.extend(port_locs)

    # --- CompactPlacement: always add if not present ---
    has_compact = any(c.get("constraint") == "CompactPlacement" for c in all_constraints)
    if not has_compact:
        all_constraints.append({"constraint": "CompactPlacement", "style": "center"})

    # Defense-in-depth: re-apply the canonical-pair-quality guard before
    # dedup so any pair leaked in by downstream passes (SameTemplate /
    # BFS secondary walks / etc.) is also filtered.  ``_cross_coupled_pairs``
    # is the set of pairs the graph-walk motif 3 identified as a valid
    # 4-cycle; they are exempt from the stricter param-match check inside
    # ``_canonical_pair_ok`` so legitimate cross-coupled latches survive.
    all_constraints = _filter_bad_sym_pairs(
        all_constraints, G, type_map,
        exempt_pairs=_cross_coupled_pairs,
    )
    all_constraints = _clean_symmetric_blocks(all_constraints)

    # KB-only default: mirror cleaned SymmetricBlocks into MatchDevices.
    # LLM paths produce MatchDevices via the CONSTRAINT_SCHEMA entry instead.
    all_constraints.extend(_default_match_devices_from_symmetric_blocks(all_constraints))

    # Reconcile KB-translated PowerPorts / GroundPorts with what
    # ``detect_power_ground`` finds in the current netlist: KB templates
    # frequently emit their own boilerplate supply names (vdd/vss) that
    # may not exist in the target, and sometimes swap power/ground roles
    # for subcircuits without a full VDD rail.
    valid_power, valid_ground = detect_power_ground(devices, circuit_ports)
    all_constraints = _reconcile_supply_ports(all_constraints, valid_power, valid_ground)

    return deduplicate_constraints(all_constraints)


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
#
#  VARIATION 1: Confidence-Gated Single-Shot Refinement
#
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

V1_SYSTEM_PROMPT = """You are an expert analog IC layout constraint engineer. You are reviewing
a constraint set that was automatically generated by matching the input circuit against
a knowledge base of known analog substructure patterns.

{schema}

YOUR TASK:
You are given:
1. The input SPICE netlist
2. Graph features (device connectivity, parameter-matched pairs, shared nets)
3. An INITIAL CONSTRAINT SET from graph matching with confidence scores
4. The matched KB patterns and their similarity scores

YOUR APPROACH depends on the confidence level:

HIGH CONFIDENCE (>0.85): The graph match is strong.
- Keep all existing constraints.
- Only ADD missing constraints that the KB templates could not cover
  (e.g., ordering between groups, net shielding, port locations).
- Do NOT remove or significantly modify existing constraints.

MEDIUM CONFIDENCE (0.6-0.85): Partial match.
- Review each constraint for correctness given the actual netlist.
- Modify instance names or parameters if the mapping seems off.
- Add any missing constraints.

LOW CONFIDENCE (<0.6): Weak match.
- Treat the initial set as suggestions only.
- Regenerate constraints primarily from the netlist and graph features.
- You may keep well-formed constraints that look correct.

Output ONLY a valid JSON array of the final constraint objects."""


def _run_variation_1(
    llm: LLMHelper,
    netlist_text: str,
    circuit_name: str,
    devices: List[Dict[str, Any]],
    circuit_ports: List[str],
    initial_constraints: List[Dict[str, Any]],
    matches: List[MatchResult],
    gf: Dict[str, Any],
    with_reasoning: bool = False,
) -> List[Dict[str, Any]]:
    """Variation 1: single LLM call to refine graph-matched constraints."""
    avg_score = np.mean([m.similarity_score for m in matches]) if matches else 0.0

    if avg_score > 0.85:
        confidence_label = "HIGH"
    elif avg_score > 0.6:
        confidence_label = "MEDIUM"
    else:
        confidence_label = "LOW"

    match_info = [{"pattern": m.pattern_name, "score": round(m.similarity_score, 3),
                   "device_mapping": m.device_mapping} for m in matches]

    system = V1_SYSTEM_PROMPT.format(schema=CONSTRAINT_SCHEMA)
    if with_reasoning:
        system += """

IMPORTANT: Before generating the final constraints, show your reasoning:
## STEP 1: Review each existing constraint — accept/reject/modify with justification
## STEP 2: Identify missing constraints from graph features and circuit physics
## STEP 3: Output the final constraint JSON array after the marker FINAL_CONSTRAINTS_JSON
"""

    user = f"""Circuit: {circuit_name}
Netlist:
{netlist_text}

Graph Features:
{json.dumps(gf, indent=2)}

Matched KB Patterns (confidence = {confidence_label}, avg_score = {avg_score:.3f}):
{json.dumps(match_info, indent=2)}

Initial Constraint Set ({len(initial_constraints)} constraints):
{json.dumps(initial_constraints, indent=2)}

Review and output the final constraint set as a JSON array."""

    result = llm.call(system, user)

    if with_reasoning and "FINAL_CONSTRAINTS_JSON" in result.content:
        parse_text = result.content.split("FINAL_CONSTRAINTS_JSON", 1)[1]
    else:
        parse_text = result.content

    try:
        raw = llm.extract_json(parse_text)
        return llm.normalize_constraints(raw), result.content
    except Exception:
        return initial_constraints, result.content


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
#
#  VARIATION 2: Iterative Constraint-by-Constraint Review (Surgical Audit)
#
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

V2_REVIEW_SYSTEM = """You are an expert analog IC layout constraint auditor.
You are reviewing ONE constraint that was auto-generated by graph matching.

Given:
- The constraint JSON
- The relevant devices and their graph context (shared nets, parameters)
- The KB pattern this constraint came from

Decide: accept, reject, or modify this constraint.

Output STRICTLY as JSON:
{{"verdict": "accept" | "reject" | "modify",
  "modified": {{...}} or null,
  "reasoning": "brief explanation"}}"""

V2_GAPFILL_SYSTEM = """You are an expert analog IC layout constraint engineer.

{schema}

You have already audited and accepted the constraints listed below.
Now identify any MISSING constraints that should be added for this circuit.
Consider: symmetry pairs not yet covered, ordering constraints, net routing,
grouping, alignment, port locations, etc.

Output ONLY a JSON array of ADDITIONAL constraints to add (may be empty [])."""


def _run_variation_2(
    llm: LLMHelper,
    netlist_text: str,
    circuit_name: str,
    devices: List[Dict[str, Any]],
    circuit_ports: List[str],
    initial_constraints: List[Dict[str, Any]],
    matches: List[MatchResult],
    gf: Dict[str, Any],
    with_reasoning: bool = False,
) -> Tuple[List[Dict[str, Any]], str]:
    """Variation 2: per-constraint LLM audit + gap-fill."""
    audit_log = []
    accepted: List[Dict[str, Any]] = []

    # Batch constraints by type to reduce LLM calls
    type_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in initial_constraints:
        type_groups[c.get("constraint", "UNKNOWN")].append(c)

    for ctype, group in type_groups.items():
        # Get relevant device context for this group
        involved_devices = set()
        for c in group:
            for key in ("instances", "ports"):
                if key in c:
                    involved_devices.update(str(i).lower() for i in c[key])
            if "pairs" in c:
                for pair in c["pairs"]:
                    involved_devices.update(str(i).lower() for i in pair)

        relevant_context = {
            "constraint_type": ctype,
            "involved_devices": list(involved_devices),
            "relevant_shared_nets": [
                a for a in gf.get("shared_net_adjacencies", [])
                if a["dev1"].lower() in involved_devices or a["dev2"].lower() in involved_devices
            ],
            "relevant_param_matches": [
                p for p in gf.get("parameter_matched_pairs", [])
                if p["dev1"].lower() in involved_devices or p["dev2"].lower() in involved_devices
            ],
        }

        source_pattern = "unknown"
        for m in matches:
            for c in m.translated_constraints:
                if c.get("constraint") == ctype:
                    source_pattern = m.pattern_name
                    break

        user = f"""Circuit: {circuit_name}
Netlist (excerpt — focus on the relevant devices):
{netlist_text}

Constraints to review ({len(group)} of type {ctype}, from KB pattern '{source_pattern}'):
{json.dumps(group, indent=2)}

Graph context for involved devices:
{json.dumps(relevant_context, indent=2)}

Review ALL {len(group)} constraints of this type. For each, provide verdict.
Output as JSON array of verdict objects."""

        result = llm.call(V2_REVIEW_SYSTEM, user)
        audit_log.append(f"[{ctype}] LLM response:\n{result.content}")

        try:
            verdicts = llm.extract_json(result.content)
            if isinstance(verdicts, dict):
                verdicts = [verdicts]
            for i, v in enumerate(verdicts):
                verdict = v.get("verdict", "accept")
                if verdict == "accept":
                    if i < len(group):
                        accepted.append(group[i])
                elif verdict == "modify" and v.get("modified"):
                    mod = v["modified"]
                    if isinstance(mod, dict) and "constraint" in mod:
                        accepted.append(mod)
                # reject: skip
        except Exception:
            accepted.extend(group)

    # Gap-fill pass
    gapfill_system = V2_GAPFILL_SYSTEM.format(schema=CONSTRAINT_SCHEMA)
    gapfill_user = f"""Circuit: {circuit_name}
Netlist:
{netlist_text}

Graph Features:
{json.dumps(gf, indent=2)}

Already accepted constraints ({len(accepted)}):
{json.dumps(accepted, indent=2)}

Identify any MISSING constraints to add."""

    gapfill_result = llm.call(gapfill_system, gapfill_user)
    audit_log.append(f"[GAP-FILL] LLM response:\n{gapfill_result.content}")

    try:
        additions = llm.extract_json(gapfill_result.content)
        additions = llm.normalize_constraints(additions)
    except Exception:
        additions = []

    final = deduplicate_constraints(accepted + additions)
    raw_text = "\n\n---\n\n".join(audit_log)
    return final, raw_text


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
#
#  VARIATION 3: Multi-Agent Debate with Graph Verifier (Propose-Verify-Merge)
#
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

V3_LLM_AGENT_SYSTEM = """You are an expert analog IC layout constraint engineer.
Analyze the circuit netlist and graph features to generate ALIGN-compatible
layout constraints.

{schema}

Use BOTH circuit physics knowledge AND graph connectivity features:
- Identify differential pairs, current mirrors, cascodes from topology
- Use parameter matching to find symmetric device pairs
- Determine placement ordering from signal flow
- Declare power/ground ports

Output ONLY a valid JSON array of constraint objects."""


V3_ARBITRATION_SYSTEM = """You are a judge resolving disagreements between two constraint
generation methods for an analog IC layout.

{schema}

You are given:
1. AGREED constraints (both methods produced equivalent constraints) — auto-accepted
2. CONFLICTS (both methods produced constraints of the same type but different details)
3. UNIQUE proposals (only one method suggested this constraint)
4. The input netlist and graph features for verification

For each CONFLICT: pick the better version or create a merged version.
For each UNIQUE proposal: accept or reject based on the netlist evidence.

Output ONLY a valid JSON array containing:
- All AGREED constraints (copy them as-is)
- Your resolved versions of CONFLICTS
- Accepted UNIQUE proposals"""


def _classify_constraints(
    graph_constraints: List[Dict[str, Any]],
    llm_constraints: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Classify constraints into agreed, graph-only, llm-only, conflicts."""
    g_fps = {constraint_fingerprint(c): c for c in graph_constraints}
    l_fps = {constraint_fingerprint(c): c for c in llm_constraints}

    agreed = []
    conflicts = []
    graph_only = []
    llm_only = []

    g_matched = set()
    l_matched = set()

    # Exact matches
    for gfp, gc in g_fps.items():
        if gfp in l_fps:
            agreed.append(gc)
            g_matched.add(gfp)
            l_matched.add(gfp)

    # Type-overlap conflicts (same constraint type, overlapping instances, but different)
    for gfp, gc in g_fps.items():
        if gfp in g_matched:
            continue
        gc_type = gc.get("constraint", "")
        gc_insts = set()
        for key in ("instances", "ports"):
            if key in gc:
                gc_insts.update(str(i).lower() for i in gc[key])
        if "pairs" in gc:
            for pair in gc["pairs"]:
                gc_insts.update(str(i).lower() for i in pair)

        found_conflict = False
        for lfp, lc in l_fps.items():
            if lfp in l_matched:
                continue
            if lc.get("constraint", "") != gc_type:
                continue
            lc_insts = set()
            for key in ("instances", "ports"):
                if key in lc:
                    lc_insts.update(str(i).lower() for i in lc[key])
            if "pairs" in lc:
                for pair in lc["pairs"]:
                    lc_insts.update(str(i).lower() for i in pair)

            if gc_insts & lc_insts:
                conflicts.append({"graph_version": gc, "llm_version": lc})
                g_matched.add(gfp)
                l_matched.add(lfp)
                found_conflict = True
                break

        if not found_conflict and gfp not in g_matched:
            graph_only.append(gc)
            g_matched.add(gfp)

    for lfp, lc in l_fps.items():
        if lfp not in l_matched:
            llm_only.append(lc)

    return agreed, conflicts, graph_only, llm_only


def _run_variation_3(
    llm: LLMHelper,
    netlist_text: str,
    circuit_name: str,
    devices: List[Dict[str, Any]],
    circuit_ports: List[str],
    initial_constraints: List[Dict[str, Any]],
    matches: List[MatchResult],
    gf: Dict[str, Any],
    with_reasoning: bool = False,
) -> Tuple[List[Dict[str, Any]], str]:
    """Variation 3: parallel graph + LLM generation -> deterministic merge -> arbitration."""
    # Agent A: graph constraints (already computed)
    graph_constraints = list(initial_constraints)

    # Agent B: independent LLM constraint generation (simplified: 1 call)
    llm_system = V3_LLM_AGENT_SYSTEM.format(schema=CONSTRAINT_SCHEMA)
    llm_user = f"""Circuit: {circuit_name}
Netlist:
{netlist_text}

Devices: {json.dumps([{{"name": d["name"], "type": d["type"], "params": d.get("params", {{}})}} for d in devices], indent=2)}
Ports: {circuit_ports}

Graph Features:
{json.dumps(gf, indent=2)}

Generate the complete ALIGN constraint set as a JSON array."""

    llm_result = llm.call(llm_system, llm_user)

    try:
        llm_raw = llm.extract_json(llm_result.content)
        llm_constraints = llm.normalize_constraints(llm_raw)
    except Exception:
        llm_constraints = []

    # Deterministic merge
    agreed, conflicts, graph_only, llm_only = _classify_constraints(graph_constraints, llm_constraints)

    debate_log = [
        f"Graph agent: {len(graph_constraints)} constraints",
        f"LLM agent: {len(llm_constraints)} constraints",
        f"Agreed: {len(agreed)}, Conflicts: {len(conflicts)}, "
        f"Graph-only: {len(graph_only)}, LLM-only: {len(llm_only)}",
        f"\nLLM Agent raw:\n{llm_result.content}",
    ]

    # If no conflicts or unique proposals, skip arbitration
    if not conflicts and not graph_only and not llm_only:
        return agreed, "\n".join(debate_log)

    # Arbitration call
    arb_system = V3_ARBITRATION_SYSTEM.format(schema=CONSTRAINT_SCHEMA)
    if with_reasoning:
        arb_system += """

Show your reasoning for each decision before the final JSON.
Mark the final output with FINAL_CONSTRAINTS_JSON then a JSON code block."""

    arb_user = f"""Circuit: {circuit_name}
Netlist:
{netlist_text}

Graph Features:
{json.dumps(gf, indent=2)}

AGREED constraints (auto-accepted, include these in output):
{json.dumps(agreed, indent=2)}

CONFLICTS (same type, different details — pick or merge):
{json.dumps([c for c in conflicts], indent=2)}

UNIQUE from Graph agent (accept or reject):
{json.dumps(graph_only, indent=2)}

UNIQUE from LLM agent (accept or reject):
{json.dumps(llm_only, indent=2)}

Output the complete final constraint set as a JSON array."""

    arb_result = llm.call(arb_system, arb_user)
    debate_log.append(f"\nArbitration:\n{arb_result.content}")

    parse_text = arb_result.content
    if with_reasoning and "FINAL_CONSTRAINTS_JSON" in parse_text:
        parse_text = parse_text.split("FINAL_CONSTRAINTS_JSON", 1)[1]

    try:
        final_raw = llm.extract_json(parse_text)
        final = llm.normalize_constraints(final_raw)
    except Exception:
        final = agreed + graph_only + llm_only
        for cf in conflicts:
            final.append(cf.get("graph_version", cf.get("llm_version", {})))

    return deduplicate_constraints(final), "\n".join(debate_log)


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
#
#  HybridConstraintEngine — main interface
#
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

class HybridConstraintEngine:
    """Orchestrates KB-only and LLM hybrid variations.

    Usage:
        engine = HybridConstraintEngine(model=DEFAULT_MODEL_ENDPOINT)
        # KB-only path (zero LLM calls when match is strong + circuit is small)
        result = engine.generate_constraints(netlist_text, variation=0)
        # LLM-assisted path
        result = engine.generate_constraints(netlist_text, variation=1)
    """

    def __init__(self, model: str = DEFAULT_MODEL_ENDPOINT, kb_dir: Optional[str] = None,
                top_k: int = 3, threshold: float = 0.45,
                kb_only_threshold: float = 0.50, complexity_cap: int = 15):
        """
        Args:
            kb_only_threshold: minimum best-match similarity score to allow
                the KB-only path (no LLM calls). Default 0.70.
            complexity_cap: maximum number of devices for KB-only path.
                Circuits with more devices fall back to LLM. Default 15.
        """
        self.kb_index = KnowledgeBaseIndex(kb_dir)
        self.matcher = SubstructureMatcher(self.kb_index, top_k=top_k, threshold=threshold)
        self.model = resolve_model_endpoint(model)
        self.kb_only_threshold = kb_only_threshold
        self.complexity_cap = complexity_cap
        print(f"HybridConstraintEngine initialized: {len(self.kb_index)} KB templates, "
              f"model={model}, kb_only_threshold={kb_only_threshold}, "
              f"complexity_cap={complexity_cap}")

    def generate_constraints(
        self,
        netlist_text: str,
        variation: int = 1,
        with_reasoning: bool = False,
    ) -> Dict[str, Any]:
        """Generate ALIGN constraints using the specified variation.

        Args:
            netlist_text: SPICE netlist string with .subckt
            variation: 0 (KB-only auto-gate), 1, 2, or 3.
                0 = KB-only when match is strong AND circuit is small,
                    otherwise falls back to variation 1.
            with_reasoning: whether to include LLM reasoning chain (ignored for KB-only)
        """
        assert variation in (0, 1, 2, 3), "variation must be 0, 1, 2, or 3"

        t_total_start = time.time()

        # Phase 1: Parse + graph match (shared across all variations)
        circuit_name, circuit_ports, devices = parse_netlist_general(netlist_text)

        t_match_start = time.time()
        matches, G_input, embs_input = self.matcher.match(devices, circuit_ports)
        initial_constraints = self.matcher.build_initial_constraints(matches, devices, circuit_ports)
        graph_match_time = time.time() - t_match_start

        gf = graph_features_summary(G_input, devices, circuit_ports)
        gm = GraphMatchMetrics(
            graph_match_time_seconds=graph_match_time,
            num_kb_templates_matched=len(matches),
            top_matches=[{"pattern": m.pattern_name, "score": round(m.similarity_score, 3)}
                         for m in matches],
            total_initial_constraints=len(initial_constraints),
        )

        # Decision gate: KB-only path or LLM path
        best_score = max((m.similarity_score for m in matches), default=0.0)
        num_devices = len(devices)
        use_kb_only = False

        if variation == 0:
            if best_score >= self.kb_only_threshold and num_devices <= self.complexity_cap:
                use_kb_only = True
            else:
                variation = 1  # fallback to V1

        # One type-map reused by the hygiene pass on both KB-only and LLM
        # paths so that LLM-generated cross-type pairs are scrubbed too.
        _type_map = _device_type_lookup(G_input, devices)

        if use_kb_only:
            # KB-Only path: pure graph-based constraint generation, zero LLM calls
            constraints = generate_constraints_from_graph(
                G_input, devices, circuit_ports,
                initial_constraints, matches, gf,
            )
            total_time = time.time() - t_total_start
            return {
                "constraints": constraints,
                "raw_response": "",
                "with_reasoning": False,
                "variation": 0,
                "kb_only_path": True,
                "initial_constraints": initial_constraints,
                "metrics": {
                    "model": self.model,
                    "num_llm_calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "llm_runtime_seconds": 0.0,
                    "runtime_seconds": total_time,
                    "graph_match_time_seconds": gm.graph_match_time_seconds,
                    "num_kb_templates_matched": gm.num_kb_templates_matched,
                    "top_kb_matches": gm.top_matches,
                    "total_initial_constraints": gm.total_initial_constraints,
                    "best_match_score": round(best_score, 3),
                    "num_devices": num_devices,
                    "kb_only_eligible": True,
                },
            }

        # Phase 2: LLM-assisted path
        llm = LLMHelper(model=self.model)
        raw_response = ""
        if variation == 1:
            constraints, raw_response = _run_variation_1(
                llm, netlist_text, circuit_name, devices, circuit_ports,
                initial_constraints, matches, gf, with_reasoning,
            )
        elif variation == 2:
            constraints, raw_response = _run_variation_2(
                llm, netlist_text, circuit_name, devices, circuit_ports,
                initial_constraints, matches, gf, with_reasoning,
            )
        elif variation == 3:
            constraints, raw_response = _run_variation_3(
                llm, netlist_text, circuit_name, devices, circuit_ports,
                initial_constraints, matches, gf, with_reasoning,
            )

        # Apply the same hygiene pipeline to LLM-assisted output: strip
        # SymmetricBlocks pairs that fail the canonical-pair-quality check
        # (same MOS type + matching W/L/nf/m + >=2 shared-pin terminals,
        # or cross-coupled motif), drop singletons, dedupe within a
        # SymmetricBlocks, reconcile supply-port names, and
        # re-fingerprint-dedupe.  We compute the cross-coupled exempt set
        # from the same graph-walk motif so the LLM can still propose
        # valid cross-coupled latches.
        _vp, _vg = detect_power_ground(devices, circuit_ports)
        _cc_pairs_llm: Set[frozenset] = {
            frozenset({s["dev1"].lower(), s["dev2"].lower()})
            for s in _graphwalk_symmetry_seeds(G_input, SUPPLY_RAILS_LOWER)
            if s.get("motif") == "cross_coupled"
        }
        constraints = _filter_bad_sym_pairs(
            constraints, G_input, _type_map,
            exempt_pairs=_cc_pairs_llm,
        )
        constraints = _clean_symmetric_blocks(constraints)
        constraints = _reconcile_supply_ports(constraints, _vp, _vg)
        constraints = deduplicate_constraints(constraints)

        total_time = time.time() - t_total_start
        llm_metrics = llm.aggregate_metrics()

        return {
            "constraints": constraints,
            "raw_response": raw_response,
            "with_reasoning": with_reasoning,
            "variation": variation,
            "kb_only_path": False,
            "initial_constraints": initial_constraints,
            "metrics": {
                **llm_metrics,
                "runtime_seconds": total_time,
                "graph_match_time_seconds": gm.graph_match_time_seconds,
                "num_kb_templates_matched": gm.num_kb_templates_matched,
                "top_kb_matches": gm.top_matches,
                "total_initial_constraints": gm.total_initial_constraints,
                "best_match_score": round(best_score, 3),
                "num_devices": num_devices,
                "kb_only_eligible": (best_score >= self.kb_only_threshold
                                     and num_devices <= self.complexity_cap),
            },
        }
