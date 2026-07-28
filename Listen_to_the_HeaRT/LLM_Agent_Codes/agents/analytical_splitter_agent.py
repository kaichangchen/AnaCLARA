import re
import json
import sys
import os
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict


# Add parent directory (Multi_Agent) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from base_agent import Agent, DEFAULT_MODEL_ENDPOINT
from contexts.global_context import GlobalContext
from agents.prompts import (
    GRAPH_BASED_SPLITTER_AGENT_SYSTEM_PROMPT_MODIF_PART_1,
    GRAPH_BASED_SPLITTER_AGENT_SYSTEM_PROMPT_MODIF_PART_2,
)

from tools.functions import extract_device_names

working_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUPPLY_RAILS = {"vdd", "vss", "VDD", "GND", "VSS", "gnd"}

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

def parse_spice_netlist(netlist_str: str):
    """
    Parse a SPICE netlist into a bipartite graph:
      - Device nodes (MOSFETs, Rs, Cs, etc.)
      - Net nodes
      - Edges with terminal annotations. These are the branches physcially and we will be cutting on these. Also we respect KCL through these (hence this representation is good).
      Other reasons?
    """
    # G = nx.Graph()
    G = nx.MultiGraph()

    # Define terminal conventions
    mosfet_terminals = ["D", "G", "S"]  # For simplicity: Removing "B"
    default_terms = []  # fallback if needed
    device_types = {"nmos", "pmos", "res", "cap"}  # And?

    SIGNAL_PORTS = {"vinn", "vinp", "d1", "vout"}

    # Parse each line
    for line in netlist_str:
        line = line.strip().lower()
        if not line or line.startswith(("*", ".", "+")):
            continue  # skip comments and directives

        tokens = line.split()
        dev_name = tokens[0]

        dev_type = None
        for canon_type, variants in device_map.items():
            if any(variant in tokens for variant in variants):
                dev_type = canon_type
                break

        if dev_type is None:
            raise ValueError(f"Unsupported [tsmcN40] device type: {dev_name}")

        # MOSFET device
        if "mos" in dev_type:
            nets = tokens[1:4]  # Removing B for simplicity # tokens[1:5]  # D G S B
            params = tokens[6:]

            # Add device node
            G.add_node(
                dev_name, bipartite="device", type=dev_type, params=" ".join(params)
            )  # Added the node to the device set

            # Add nets + edges
            for term, net in zip(mosfet_terminals, nets):
                if net in SUPPLY_RAILS:
                    role = "SUPPLY_PORT"  # Edges (i.e. branches) coming here are uncuttable
                elif net in SIGNAL_PORTS:
                    role = "SIGNAL_PORT"  # Edges (i.e. branches) coming here are uncuttable
                else:
                    role = "INTERNAL_NET"

                G.add_node(net, bipartite="net", role=role)

                edge_id = f"{dev_name}.{term}"

                G.add_edge(
                    dev_name,
                    net,
                    key=edge_id,  # unique key = edge_id
                    terminal=term,
                    edge_id=edge_id,
                )


        # SPECIFIC TO TSMCN40
        elif "res" in dev_type:
            nets = tokens[1:3]
            params = tokens[5:]
            G.add_node(dev_name, bipartite="device", type="resistor", params=" ".join(params))

            # Add nets + edges
            for i, net in enumerate(nets):
                if net in SUPPLY_RAILS:
                    role = "SUPPLY_PORT"  # Edges (i.e. branches) coming here are uncuttable
                elif net in SIGNAL_PORTS:
                    role = "SIGNAL_PORT"  # Edges (i.e. branches) coming here are uncuttable
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

            # Add nets + edges
            for i, net in enumerate(nets):
                if net in SUPPLY_RAILS:
                    role = "SUPPLY_PORT"  # Edges (i.e. branches) coming here are uncuttable
                elif net in SIGNAL_PORTS:
                    role = "SIGNAL_PORT"  # Edges (i.e. branches) coming here are uncuttable
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


def plot_bipartite(G):
    # Separate device vs net nodes
    devices = [n for n, d in G.nodes(data=True) if d["bipartite"] == "device"]
    nets = [n for n, d in G.nodes(data=True) if d["bipartite"] == "net"]

    # Place devices on left, nets on right
    pos = {}
    pos.update((n, (0, i)) for i, n in enumerate(devices))
    pos.update((n, (1, i)) for i, n in enumerate(nets))

    # Color code
    node_colors = []
    for n in G.nodes():
        if n in devices:
            node_colors.append("lightblue")  # devices
        else:
            role = G.nodes[n].get("role", "INTERNAL_NET")
            if role == "SUPPLY_PORT":
                node_colors.append("red")
            elif role == "SIGNAL_PORT":
                node_colors.append("green")
            else:
                node_colors.append("gray")

    # Edge labels, colors, widths
    edge_labels = {}
    for u, v, key, d in G.edges(keys=True, data=True):
        dev, net = (u, v) if u in devices else (v, u)
        edge_id = d.get("edge_id", key)
        edge_labels[(u, v, key)] = edge_id

        # Highlight edges to ports
        role = G.nodes[net].get("role")

        d["color"] = "red" if "PORT" in role else "black"
        d["width"] = 2.5 if "PORT" in role else 1.0

    edge_colors = [d["color"] for _, _, d in G.edges(data=True)]
    edge_widths = [d["width"] for _, _, d in G.edges(data=True)]

    # Draw
    plt.figure(figsize=(14, 10))
    nx.draw(
        G,
        pos,
        with_labels=True,
        node_color=node_colors,
        edge_color=edge_colors,
        width=edge_widths,
        node_size=1200,
        font_size=8,
    )

    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=6)
    plt.title("Bipartite Graph of Netlist")
    plt.show()


# -----------------------------
# DC Current-only pipeline (my strategy)
# -----------------------------


def make_dc_pruned_bipartite_copy(G: nx.MultiGraph) -> nx.MultiGraph:
    """
    Create a DC-pruned copy of the bipartite graph.

    Removes:
      - All MOSFET gate terminals (terminal == 'G')
      - All capacitor terminals (entire capacitor device has no DC path)

    Returns:
      G_dc: a pruned bipartite graph containing only DC-conduction "capable" edges.
    """
    G_dc = G.copy()

    for u, v, key, d in list(G_dc.edges(keys=True, data=True)):
        # Skip if either endpoint was removed earlier in this loop
        if u not in G_dc or v not in G_dc:
            continue
        # Identify the device endpoint
        dev = u if G_dc.nodes[u].get("bipartite") == "device" else v
        term = (d.get("terminal") or "").upper()
        dev_type = (G_dc.nodes[dev].get("type") or "").lower()

        # Rule 1: remove capacitor edges (no DC conduction)
        if dev_type in {"capacitor", "cap"}:
            G_dc.remove_node(dev)
            continue

        # Rule 2: remove MOS gate edges (high impedance at DC)
        elif dev_type in {"nmos", "pmos", "mos"} and term == "G":
            G_dc.remove_edge(u, v, key=key)

    # Remove any isolated nodes left behind
    iso_nodes = [n for n in G_dc.nodes if G_dc.degree(n) == 0]
    if iso_nodes:
        G_dc.remove_nodes_from(iso_nodes)

    return G_dc


# Once we’ve pruned away gates and capacitors, every remaining device is effectively a two-port (MOS: D–S, resistor: N1–N2).
# That means we can now collapse the bipartite into a net-only multigraph, with each device represented as an edge connecting its two nets.


def build_net_only_graph(G_dc: nx.MultiGraph) -> nx.MultiGraph:
    """
    Collapse DC-pruned bipartite (devices + nets) into a net-only multigraph H.
    - Each device that connects exactly two distinct nets -> one edge (u, v).
    - Parallel devices become parallel edges (multi-edges).
    - Devices with <2 nets are ignored (dangling after DC prune).
    - Devices with >2 nets should not exist in this flow (assert for safety).
    """
    H = nx.MultiGraph()

    # Copy net nodes with their attributes (role, etc.)
    for n, data in G_dc.nodes(data=True):
        if G_dc.nodes[n].get("bipartite") == "net":
            H.add_node(n, **data)

    # Map device -> nets it still touches
    dev_to_nets = {}
    for dev, data in G_dc.nodes(data=True):
        if data.get("bipartite") != "device":
            continue
        nets = [
            nbr
            for nbr in G_dc.neighbors(dev)
            if G_dc.nodes[nbr].get("bipartite") == "net"
        ]
        dev_to_nets[dev] = list(
            set(nets)
        )  # Unique nets only. So shorted devices like MOS source and drain shorted cases will be igored (not be added in the below net only multigraph)

    # Build edges for 2-port devices
    for dev, nets in dev_to_nets.items():
        if len(nets) < 2:
            # device is dangling at DC -> skip
            continue
        elif len(nets) > 2:
            # shouldn't happen for MOS (D,S) or R (2 terminals)
            raise ValueError(f"Device {dev} has >2 nets after DC prune: {nets}")

        u, v = nets
        key = f"{dev}__{u}__{v}"
        H.add_edge(u, v, key=key, device=dev)

    return H


def is_rail(n):
    return n.lower() in SUPPLY_RAILS


def peel_open_ends(H: nx.MultiGraph) -> nx.MultiGraph:
    """
    Iteratively remove non-rail degree-1 nets and their incident edges
    until no more such nets remain.

    Args:
        H: net-only multigraph (nets as nodes, devices as edges)
        rails_high: set of high-rail names (e.g. {"vdd"})
        rails_low: set of low-rail names (e.g. {"vss","gnd"})

    Returns:
        A pruned net-only graph (copy of H) with open branches peeled off.
    """
    Hp = H.copy()
    changed = True

    while changed:
        changed = False

        # collect all current non-rail leaves
        leaves = [n for n in Hp.nodes if Hp.degree(n) == 1 and not is_rail(n)]
        if not leaves:
            break

        changed = True
        for n in leaves:
            # remove all incident edges (devices attached to this dangling net)
            Hp.remove_node(n)

    return Hp


def mark_dc_alive_devices(H: nx.MultiGraph, rails_high: set, rails_low: set):
    """
    Identify devices (edges) that actually lie on some VDD→VSS conduction path.

    Args:
        H: net-only multigraph after peeling (nets as nodes, devices as edges).
        rails_high: set of names considered high rails (e.g., {"vdd"})
        rails_low: set of names considered low rails (e.g., {"vss","gnd"})

    Returns:
        alive_devices: set of device names that are DC-alive
        alive_edges: list of edge keys (u,v,key) that are DC-alive
    """
    # Multi-source BFS for reachability
    R_high = set()
    R_low = set()

    for src in rails_high:
        if src in H:
            R_high |= nx.node_connected_component(
                H, src
            )  # All net nodes reachable from any VDD-like (High) Rail
    for src in rails_low:
        if src in H:
            R_low |= nx.node_connected_component(
                H, src
            )  # All net nodes reachable from any VSS-like (Low) Rail

    # Now iterate over each device (edge) and see if both its ends are reachable from opposite rails:
    # Strategy: Mark the device DC-alive iff : (u ∈ R_high and v ∈ R_low) OR (v ∈ R_high and u ∈ R_low).

    alive_devices = set()
    alive_edges = []

    for u, v, key, data in H.edges(keys=True, data=True):
        if (u in R_high and v in R_low) or (v in R_high and u in R_low):
            alive_devices.add(data["device"])
            alive_edges.append((u, v, key))

    return alive_devices, alive_edges


def restricted_reachable_components_with_conduction_check(
    G_dc: nx.MultiGraph, alive_devices: set
):
    """
    DFS to find connected components in the DC-pruned bipartite graph through *alive* devices only
    Rules:
      - Traversal stops at supply rail nodes.
      - Only devices in `alive_devices` are allowed into a component.
      - MOS gate edges and capacitors are already removed in G_dc, so no need to check here.

    Args:
        G_dc: DC-pruned bipartite graph (from make_dc_pruned_bipartite_copy).
        alive_devices: set of device names previously marked as DC-alive. (existence of DC current path from VDD -> device -> VSS proved)

    Returns:
        subcircuits: list of lists, where each list is a group of connected alive devices.
    """

    visited = set()
    subcircuits = []
    # Only consider alive devices
    devices = [
        n
        for n, d in G_dc.nodes(data=True)
        if d.get("bipartite") == "device" and n in alive_devices
    ]
    for dev in devices:
        if dev in visited:
            continue

        comp = []
        stack = [dev]
        visited.add(dev)

        while stack:
            current = stack.pop()
            comp.append(current)

            # Explore neighbor nets
            for nbr_net in G_dc.neighbors(current):
                if nbr_net in SUPPLY_RAILS:
                    continue  # stop traversal at supplies

                # From this net → go to other devices
                for nbr_dev in G_dc.neighbors(nbr_net):
                    if (
                        G_dc.nodes[nbr_dev].get("bipartite") == "device"
                        and nbr_dev in alive_devices
                        and nbr_dev not in visited
                    ):
                        visited.add(nbr_dev)
                        stack.append(nbr_dev)

        subcircuits.append(comp)

    return subcircuits


def _build_full_subgraph_from_device_group(
    G_orig: nx.MultiGraph, dev_group: list | set, idx: int
) -> nx.MultiGraph:
    """
    Create a *full* bipartite subgraph for a single device group:
      - include ALL edges for those devices from the original graph (this reattaches gates automatically)
      - mark SUPPLY_PORT / SIGNAL_PORT by degree drop vs original
      - clone supplies so subcircuits are disjoint
    """

    # 1) collect nets touched by these devices in the original graph
    nets = set()
    for d in dev_group:
        if d not in G_orig:
            continue
        for nbr in G_orig.neighbors(d):
            if G_orig.nodes[nbr].get("bipartite") == "net":
                nets.add(nbr)

    # 2) build induced subgraph nodes
    keep_nodes = set(dev_group) | nets
    subG = nx.MultiGraph()
    subG.add_nodes_from((n, G_orig.nodes[n]) for n in keep_nodes)

    # 3) copy *only* edges whose device endpoint ∈ dev_group
    for d in dev_group:
        if d not in G_orig:
            continue
        for net in G_orig.neighbors(d):
            if net not in nets:
                continue
            for key, ed in G_orig[d][net].items():
                subG.add_edge(d, net, key=key, **ed)  # gates come back here

    # 4) mark ports by comparing degrees vs original
    for n in list(nets):
        if n in SUPPLY_RAILS:
            subG.nodes[n]["role"] = "SUPPLY_PORT"
        else:
            deg_sub = subG.degree(n)
            deg_full = G_orig.degree(n)
            subG.nodes[n]["role"] = (
                "SIGNAL_PORT"
                if deg_sub < deg_full
                else subG.nodes[n].get("role", "INTERNAL_NET")
            )

    """ # Commenting out since already supply ports have been included per subgraph using neighbours
    # 5) Add the supply nodes to the subgraphs with dijoint namings
    for sup in SUPPLY_RAILS:
        local_sup = f"{sup}_subckt_{idx}"
        for dev in dev_group:
            if G_orig.has_edge(dev, sup):
                if local_sup not in subG:
                    subG.add_node(local_sup, bipartite="net", role="SUPPLY_PORT")

                # Iterate over all parallel edges between dev and sup
                for key, d in list(G_orig[dev][sup].items()):
                    # Replicate the same edges in this subgraph
                    subG.add_edge(dev, local_sup, key=key, **d)
    """

    return subG


def split_graph_DC_Current_Zero(G):

    # 1) DC prune
    G_dc = make_dc_pruned_bipartite_copy(G)

    # 2) net-only → peel → alive
    H = build_net_only_graph(G_dc)
    H_clean = peel_open_ends(H)
    alive_devices, _ = mark_dc_alive_devices(
        H_clean,
        rails_high={"vdd"},
        rails_low={"vss", "gnd"},
    )

    # 3) group alive devices (on DC-pruned bipartite, stop at supplies)
    device_groups = restricted_reachable_components_with_conduction_check(
        G_dc, alive_devices
    )

    # 4) build full bipartite subgraphs for each device group
    subgraphs = []
    for idx, group in enumerate(device_groups, 1):
        subG = _build_full_subgraph_from_device_group(
            G_orig=G, dev_group=group, idx=idx
        )
        subgraphs.append(subG)

    return subgraphs


def print_device_connections(G: nx.MultiGraph):
    """
    Print all device nodes with their terminals, edge IDs, and connected nets.
    """
    for dev, data in G.nodes(data=True):
        if data.get("bipartite") != "device":
            continue

        print(f"\nDevice: {dev} (type={data.get('type')})")

        # Collect all edges from this device
        for net in G.neighbors(dev):
            if G.nodes[net].get("bipartite") != "net":
                continue

            # Iterate over all parallel edges between dev and net
            for key, ed in G[dev][net].items():
                term = ed.get("terminal", "?")
                edge_id = ed.get("edge_id", key)
                print(f"  Terminal {term:>2} -> Net {net} (edge_id={edge_id})")


def save_dc_subblocks(G: nx.MultiGraph, subgraphs: list):
    """
    Save off each DC subblock with its internal nets and ports.
    Return:
        subblocks: list of dicts with graph + metadata
        taken_devices: set of all device nodes assigned to DC subblocks
        all_signal_ports_set: set of all nets marked as signal ports in all the DC subblocks combined
    """

    subblocks = []
    taken_devices = set()
    all_signal_ports_set = set()

    for idx, subG in enumerate(subgraphs, 1):
        # Separate nets by role
        internal_nets = {
            n
            for n, d in subG.nodes(data=True)
            if d.get("bipartite") == "net" and d.get("role") == "INTERNAL_NET"
        }
        signal_ports = {
            n
            for n, d in subG.nodes(data=True)
            if d.get("bipartite") == "net" and d.get("role") in {"SIGNAL_PORT"}
        }

        # Do we need to save the supply ports also?? Why? THINKKKK
        # Residual Graph can be dervied by just removing the device nodes already taken by the conduction graph. Since removing nodes also mean their edges also get removed. Then upon removing the dangling, the remaining is the residual graph. In the residual graph the net nodes marked as signal ports in all subgraphs combined should also be considered as signal ports and supply ports if in the SUPPLY RAIL list

        # Track devices
        devices = {
            n for n, d in subG.nodes(data=True) if d.get("bipartite") == "device"
        }

        taken_devices |= devices
        all_signal_ports_set |= signal_ports

        subblocks.append(
            {
                "id": f"subblock_{idx}",
                "graph": subG,
                "internal_nets": sorted(list(internal_nets)),
                "signal_ports": sorted(list(signal_ports)),
                "devices": sorted(list(devices)),
            }
        )

    return subblocks, taken_devices, all_signal_ports_set


def build_residual_graph(
    G: nx.MultiGraph, taken_devices: set, all_signal_ports_set: set
):
    """
    Build the residual graph after removing used/taken device nodes.
    - Keep all net nodes unless dangling.
    - Mark net nodes that overlap with all_signal_ports_set as "SIGNAL_PORT".
    - Mark net nodes that overlap with SUPPLY_RAILS as "SUPPLY_PORT"
    - Mark rest net nodes as "INTERNAL_NET"
    Returns:
        residual_graph (nx.MultiGraph),
        connected_components
    """

    # Residual Graph can be dervied by just removing the device nodes already taken by the conduction graph.
    # Since removing nodes also mean their edges also get removed. Then upon removing the dangling net nodes, the remaining is the residual graph.
    # In the residual graph the net nodes marked as signal ports in all the DC subgraphs combined, should also be considered as signal ports, and supply ports if they are in the SUPPLY RAIL list

    residual = G.copy()

    # 1.) Remove all devices already assigned to subblocks
    residual.remove_nodes_from([d for d in taken_devices if d in residual])

    # 2.) Remove dangling net nodes (no edges left)
    dangling_nets = [n for n in residual.nodes if residual.degree(n) == 0]
    if dangling_nets:
        residual.remove_nodes_from(dangling_nets)

    # 3) Update net roles
    for n, data in residual.nodes(data=True):
        if data.get("bipartite") != "net":
            continue
        if n in all_signal_ports_set:
            residual.nodes[n]["role"] = "SIGNAL_PORT"
        elif n in SUPPLY_RAILS:
            residual.nodes[n]["role"] = "SUPPLY_PORT"
        else:
            residual.nodes[n]["role"] = "INTERNAL_NET"

    # 4) Extract connected components (as induced subgraphs)
    components = [
        residual.subgraph(c).copy() for c in nx.connected_components(residual)
    ]

    return residual, components


def map_residual_component_owners(residual_components, subblocks):
    # Build a quick lookup: net -> subblock_id(s)
    net_to_owner = {}
    for sub in subblocks:
        sid = sub["id"]
        for p in sub[
            "signal_ports"
        ]:  # Internal nets won't connect to residuals, so only signal ports matter
            net_to_owner.setdefault(p, set()).add(sid)

    results = []
    for idx, residual_comp in enumerate(residual_components, 1):
        # Collect all ports of this residual component (signal + supply)
        residual_component_ports = {
            n
            for n, d in residual_comp.nodes(data=True)
            if d.get("bipartite") == "net"
            and d.get("role") in {"SIGNAL_PORT", "SUPPLY_PORT"}
        }

        port_owner_map = {}
        supply_owners = set()
        subblock_owners_per_port = []

        for p in residual_component_ports:  # i.e. for every port in this component
            if p in SUPPLY_RAILS:
                owners = {p}  # treat supply rails as "owners" of themselves
                supply_owners |= owners
            else:
                owners = net_to_owner.get(p, set())
                subblock_owners_per_port.append(owners)

            port_owner_map[p] = sorted(list(owners))

        # Subblock must appear in every port’s owners to be a "true owner"
        if subblock_owners_per_port:
            common_subblocks = set.intersection(*subblock_owners_per_port)
        else:
            common_subblocks = set()

        component_owners = sorted(list(common_subblocks | supply_owners))

        results.append(
            {
                "component_id": f"residual_{idx}",
                "graph": residual_comp,
                "port_owners": port_owner_map,
                "component_owners": sorted(list(component_owners)),
            }
        )

    return results


# Now implement a function that deos the merger

# Present implementation of the hypothesis will be: (Later we will do the port-span /path-wise technique)
# > Ignoring supplies, use the DC subblock owner of all ports (component_owner) and put this together with the subblock (if multiple choose any 1).
# > Recompute the ports and save into a separate list of Final_Subcircuts

## Now let's see if LLM reasoning can automatically achieve this


# Per-run output layout:
#   <parent_netlist_path>/Runs/Run_NNN/splitter/
#       circuit_global_context.json
#       subcircuits/<id>.sp
def make_run_directory(parent_netlist_path: str) -> str:
    """Create the next Runs/Run_NNN/splitter/subcircuits/ folder and return Run_NNN path."""
    runs_dir = os.path.join(parent_netlist_path, "Runs")
    os.makedirs(runs_dir, exist_ok=True)

    existing_ids = [
        int(name[4:]) for name in os.listdir(runs_dir)
        if name.startswith("Run_") and name[4:].isdigit()
    ]
    next_n = (max(existing_ids) + 1) if existing_ids else 1
    run_dir = os.path.join(runs_dir, f"Run_{next_n:03d}")

    os.makedirs(os.path.join(run_dir, "splitter", "subcircuits"), exist_ok=True)
    return run_dir


class SplitterAgent(Agent):
    """
    A Splitter Agent that outputs the top-level external port names, all device names, and splits a provided circuit into subcircuits, containing their unique subcircuit names (IDs), port names, device names in each, approximtae reason for the spltting, self.subcircuits list....
    Plan and optimize more on the message passing between this and the other agents (subcircuit, integrator etc)
    """

    def __init__(
        self,
        name,
        system_prompt,
        tools,
        available_functions,
        toplevelcircuit: str,
        model: str = DEFAULT_MODEL_ENDPOINT,
    ):
        super().__init__(name, tools, available_functions, system_prompt, model)
        self.global_context = GlobalContext()
        self.subcircuits = []
        self.devices = set()
        self.toplevelcircuit = toplevelcircuit
        self.subcircuits = []

    def _safe_parse_json(self, text: str):
        # Match triple backticks optionally followed by 'json' and capture the content inside
        match = re.search(r"```(?:[a-zA-Z]+)?\s*([\s\S]*?)\s*```", text)
        if match:
            json_text = match.group(1)
            return json.loads(json_text)

        # Otherwise try extracting first {...} JSON block
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)

    def generate_subcircuits(self, filepath):

        # Presently hardcoded and pure LLM-based (placeholder)
        user_message = f"""
            Please analyze the circuit SPICE netlist provided below:
            Netlist:
            {self.toplevelcircuit} 
        """

        response = self.run(user_message=user_message)
        # print("///////////////////////////////////////////////////////////////////////////////////////////////////////////////////")
        # print(response)
        # print("///////////////////////////////////////////////////////////////////////////////////////////////////////////////////")

        top_level_port_names = self.parse_response_top_level_port_names(response)
        unique_subcircuit_IDs_with_port_names_dict = self.parse_response_unique_subcircuit_names_ports(
            response
        )  # dict output containing, subcircuit IDs, their port names and their subcircuit netlist

        # devices = extract_device_names(self.toplevelcircuit)

        # Update agent internal state
        self.subcircuits = unique_subcircuit_IDs_with_port_names_dict
        self.top_level_port_names = top_level_port_names

        # Stuff the global context that downstream agents will read
        self.global_context.set("model", self.model)
        self.global_context.set("top_level_port_names", top_level_port_names)
        self.global_context.set("subcircuits", self.subcircuits)

        # Print and export each subcircuit nicely
        for subckt in self.global_context.get("subcircuits", []):
            subckt_id = subckt["id"]
            netlist_str = subckt["netlist"].replace("\\n", "\n")

            # Export to file named <id>.sp
            subckt_filename = f"{subckt_id}.sp"
            complete_subcircuit_filepath = os.path.join(filepath, subckt_filename)
            with open(complete_subcircuit_filepath, "w") as f:
                f.write(netlist_str)

        return {
            "top_level_port_names": self.top_level_port_names,
            "subcircuits": self.subcircuits,
            "devices": list(self.devices),
        }

    def parse_response_top_level_port_names(self, LLM_response):
        """
        Parse top-level port names from the LLM response JSON.
        """

        # Convert response string to JSON object and extract field
        data = self._safe_parse_json(LLM_response)
        if data:
            return data.get("top_level_port_names", [])
        else:
            return []

    def parse_response_unique_subcircuit_names_ports(self, LLM_response):
        """
        Parse subcircuits dict from the LLM response JSON.
        """

        # Convert response string to JSON object and extract field
        data = self._safe_parse_json(LLM_response)
        if data:
            return data.get("subcircuits", [])
        else:
            return []


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

    netlist_filepath = os.path.join(parent_netlist_path, "Input_Netlist/unknown_circuit.sp")

    top_level_netlist_filename = os.path.basename(netlist_filepath)
    top_level_circuit_name = os.path.splitext(top_level_netlist_filename)[0]

    with open(netlist_filepath, "r") as file:
        full_netlist_content = file.readlines()

    G = parse_spice_netlist(full_netlist_content)
    print(G)

    # Check if graph is fully connected
    if nx.is_connected(G):
        print("Graph is 1 connected component")
    else:
        print("Graph has", nx.number_connected_components(G), "components")

    plot_bipartite(G)

    # For DEBUG purposes only
    """
    print_device_connections(G)
    # exit()
    """

    subgraphs = split_graph_DC_Current_Zero(G)
    print(len(subgraphs))
    for subgraph in subgraphs:
        plot_bipartite(subgraph)
        # For DEBUG purposes only
        """
        print_device_connections(subgraph)
        """

    # Now perform the Residual Graph computation

    subblocks, taken_devices, all_signal_ports_set = save_dc_subblocks(G, subgraphs)
    # print(subblocks)
    # print(taken_devices)
    # print(all_signal_ports_set)
    # exit()

    residual, components = build_residual_graph(G, taken_devices, all_signal_ports_set)

    """
    for component in components:
        plot_bipartite(component)
        print_device_connections(component)
    """

    device_groups = []

    for DC_subblock in subblocks:
        device_groups.append(DC_subblock["devices"])

    # Convert device_groups list to string representation for prompt injection
    device_groups_str = json.dumps(device_groups, indent=2)  # pretty JSON string

    splitter_agent_prompt = (
        GRAPH_BASED_SPLITTER_AGENT_SYSTEM_PROMPT_MODIF_PART_1.format(
            device_groups=device_groups_str
        )
        + GRAPH_BASED_SPLITTER_AGENT_SYSTEM_PROMPT_MODIF_PART_2
    )

    circuit_splitter_agent = SplitterAgent(
        name=top_level_circuit_name,
        system_prompt=splitter_agent_prompt,
        tools=[],
        available_functions={},
        toplevelcircuit=full_netlist_content,
    )

    run_dir = make_run_directory(parent_netlist_path)
    splitter_dir = os.path.join(run_dir, "splitter")
    print(f"[splitter] Writing artifacts to: {run_dir}")

    generated_response = circuit_splitter_agent.generate_subcircuits(
        os.path.join(splitter_dir, "subcircuits")
    )
    circuit_splitter_agent.global_context.visualize()
    circuit_splitter_agent.global_context.save(
        os.path.join(splitter_dir, "circuit_global_context.json")
    )

    # Persist token usage from the splitter LLM call (one chat completion).
    last_usage = getattr(circuit_splitter_agent, "last_usage", {}) or {}
    splitter_llm_metrics = {
        "model": circuit_splitter_agent.model,
        "num_llm_calls": 1,
        "input_tokens":  int(last_usage.get("prompt_tokens", 0) or 0),
        "output_tokens": int(last_usage.get("completion_tokens", 0) or 0),
        "total_tokens":  int(last_usage.get("total_tokens", 0) or 0),
    }
    with open(os.path.join(splitter_dir, "llm_metrics.json"), "w") as f:
        json.dump(splitter_llm_metrics, f, indent=2)


if __name__ == "__main__":
    main()


# self.subcircuits will be in the global context. SplitterAgent puts its information into it. Then SubcircuitAgent puts its information into it. Then integratorAgent uses this to collect the information and do its processing.
