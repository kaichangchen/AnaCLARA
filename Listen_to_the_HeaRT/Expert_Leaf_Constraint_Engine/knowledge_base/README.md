# Constraint Knowledge Base for Bulk45nm_Mock_PDK

A collection of paired `.sp` + `.const.json` files demonstrating correct ALIGN constraints
for 16 common analog substructures. Each netlist uses generic device types from
[models.sp](../models.sp) -- constraint patterns are type-agnostic (same rules for NMOS/PMOS,
any threshold variant).

---

## Quick Start

Each `.sp` file is a minimal self-contained SPICE subcircuit. The matching `.const.json`
file contains the constraint array that ALIGN reads during compilation. To use as a
reference for your own design:

1. Identify the substructure in your netlist (see [Inference Rules](#inference-rules))
2. Find the matching example pair below
3. Copy and adapt the `.const.json` entries, replacing instance names

---

## Constraint Type Reference

All 36 supported constraint types defined in
[align/schema/constraint.py](../../../align/schema/constraint.py) (`ConstraintType` union).
Loaded by [align/compiler/user_const.py](../../../align/compiler/user_const.py).
Mapped to PnR names by [align/pnr/write_constraint.py](../../../align/pnr/write_constraint.py).

### Placement Constraints

| Constraint | Key Parameters | PnR Name | When to Use |
|---|---|---|---|
| `SymmetricBlocks` | `pairs` (list of 1-or-2-element lists), `direction` (`H`/`V`) | `SymmBlock` | Matched device pairs (diff pairs, mirrors, loads) |
| `Order` | `instances`, `direction` (`left_to_right`/`top_to_bottom`/...), `abut` | `Ordering` | Force placement order (cascode stacking, signal flow) |
| `Align` | `instances`, `line` (`h_bottom`/`h_top`/`h_center`/`v_left`/`v_right`/`v_center`) | `AlignBlock` | Align instances along a line |
| `AlignInOrder` | `instances`, `line` (`top`/`bottom`/`left`/`right`/`center`), `direction`, `abut` | Expands to `Order` + `Align` | Convenience: order + align in one |
| `Floorplan` | `regions` (list of rows), `order`, `symmetrize` | Expands to `Order` + `SymmetricBlocks` | Grid-based floorplan |
| `Spread` | `instances`, `direction`, `distance` (nm) | (direct) | Minimum spacing between overlapping blocks |
| `GroupBlocks` | `instance_name`, `instances`, `template_name` (opt), `generator` (opt) | (consumed at compile time) | Merge instances into one placement block |
| `GroupCaps` | `name`, `instances`, `unit_cap` (fF), `num_units`, `dummy` | `CC` | Common-centroid capacitor placement |
| `CompactPlacement` | `style` (`left`/`right`/`center`) | `CompactPlacement` | Compact overall layout |
| `PlaceCloser` | `instances` | `MatchBlock` | Place instances near each other |
| `PlaceOnBoundary` | `north`/`south`/`east`/`west`/corners | (consumed at compile time) | Pin instances to edges |
| `PlaceOnGrid` | `direction`, `pitch`, `ored_terms` | `PlaceOnGrid` | Snap to grid |
| `AspectRatio` | `ratio_low`, `ratio_high`, `weight` | `Aspect_Ratio` | Bound width/height ratio |
| `Boundary` | `max_width`, `max_height`, `halo_horizontal`, `halo_vertical` (um) | `Boundary` | Max dimensions |
| `BlockDistance` | `abs_distance` | `bias_graph` | Min distance between any two blocks |
| `HorizontalDistance` | `abs_distance` | `bias_Hgraph` | Min horizontal distance |
| `VerticalDistance` | `abs_distance` | `bias_Vgraph` | Min vertical distance |
| `GuardRing` | `guard_ring_primitives`, `global_pin`, `block_name` | `GuardRing` | Wrap block in guard ring |

### Routing Constraints

| Constraint | Key Parameters | PnR Name | When to Use |
|---|---|---|---|
| `SymmetricNets` | `net1`, `net2`, `direction` (`H`/`V`) | `SymmNet` | Route two nets symmetrically |
| `NetConst` | `nets`, `shield` (net name), `criticality` (int) | `ShieldNet` / `CritNet` | Shield or prioritize nets |
| `NetPriority` | `nets`, `weight` | `CritNet` | Set routing priority |
| `MultiConnection` | `nets`, `multiplier` | `Multi_Connection` | Multiple wire connections |
| `DoNotRoute` | `nets` | `DoNotRoute` | Skip routing for specific nets |
| `Route` | `min_layer`, `max_layer`, `customize` (list) | `Route` | Layer constraints for routing |
| `PortLocation` | `ports`, `location` (`TL`/`TC`/`TR`/`LC`/`RC`/`BL`/`BC`/`BR`/...) | per-port `PortLocation` | Pin placement on boundary |

### Identity / Template Constraints

| Constraint | Key Parameters | PnR Name | When to Use |
|---|---|---|---|
| `SameTemplate` | `instances` | `SameTemplate` | Force identical layout cells |
| `DoNotIdentify` | `instances` | (consumed at compile time) | Prevent auto-grouping |
| `Generator` | `name`, `parameters` (pattern, etc.) | (consumed at primitive gen) | Override layout generator |

### Setup / Compiler Constraints

| Constraint | Key Parameters | PnR Name | When to Use |
|---|---|---|---|
| `PowerPorts` | `ports`, `propagate` | (consumed at compile time) | Declare power supplies |
| `GroundPorts` | `ports`, `propagate` | (consumed at compile time) | Declare ground supplies |
| `ClockPorts` | `ports`, `propagate` | (consumed at compile time) | Declare clocks (stops symmetry search) |
| `DoNotUseLib` | `libraries`, `propagate` | (consumed at compile time) | Blacklist template libraries |
| `ConfigureCompiler` | `is_digital`, `auto_constraint`, `identify_array`, `fix_source_drain`, `remove_dummy_hierarchies`, `remove_dummy_devices`, `merge_series_devices`, `merge_parallel_devices`, `same_template`, `propagate` | (consumed at compile time) | Tune compiler behavior |

### Other

| Constraint | Key Parameters | PnR Name | When to Use |
|---|---|---|---|
| `ChargeFlow` | `dist_type`, `time`, `pin_current` | `scaled_rms_charge_flow` | EM-aware placement |
| `AssignBboxVariables` | `bbox_name`, `llx`, `lly`, `urx`, `ury` | (internal) | Fix bounding box coordinates |

---

## Substructure Pattern Recipes

### 1. Differential Pair (`differential_pair`)

```
Schematic:       INP --[M1]-- OUTP
                              |  (shared source = TAIL_S)
                 INN --[M2]-- OUTN
                         |
                  VB --[M0]-- (tail bias)
```

**Recognition:** 2 FETs, same model, same W/L, shared source, different gates.
**Template:** `DP_NMOS` / `DP_PMOS` ([basic_template.sp](../../../align/config/basic_template.sp))
**Constraints:** `SymmetricBlocks` (V-axis, M1/M2 pair + M0 self-sym) + `SymmetricNets` (input pair, output pair)

### 2. Simple Current Mirror (`current_mirror`)

```
Schematic:  IREF --[M0 diode]-- S
            IOUT --[M1]-------- S
                    (gate tied to IREF)
```

**Recognition:** 2+ FETs, same model, same W/L, one gate=drain (diode), shared source.
**Template:** `SCM_NMOS` / `SCM_PMOS`
**Constraints:** `GroupBlocks` + `SameTemplate` + `Align` (h_bottom)

### 3. Cascode Current Mirror (`current_mirror_cascode`)

```
Schematic:  IREF --[M2 cascode]-- [M0 diode]-- S
            IOUT --[M3 cascode]-- [M1]-------- S
```

**Recognition:** Two pairs of matched FETs stacked (drain of bottom = source of top).
**Template:** `CASCODED_SCM_NMOS` / `CASCODED_SCM_PMOS` ([user_template.sp](../../../align/config/user_template.sp))
**Constraints:** `SymmetricBlocks` (both pairs) + `Order` (top_to_bottom) + `SameTemplate` (per pair) + `GroupBlocks`

### 4. Scaled Current Mirror (`current_mirror_ratio`)

```
Schematic:  IREF --[M0 nf=2 diode]-- S
            IOUT --[M1 nf=8]-------- S     (4:1 ratio)
```

**Recognition:** 2+ FETs, same model, same W and L, different `nf` or `m`, one diode-connected.
**Layout pattern:** `ratio_devices` (pattern 3 in [align/primitive/main.py](../../../align/primitive/main.py))
**Constraints:** `GroupBlocks` + `Align` (h_bottom) + `Generator` (pattern: ratio_devices)

### 5. Cross-Coupled Pair (`cross_coupled_pair`)

```
Schematic:  OUTP --[M1]-- S      M1.G = OUTN (= M2.D)
            OUTN --[M2]-- S      M2.G = OUTP (= M1.D)
```

**Recognition:** 2 FETs, same model, same W/L, gate_A=drain_B and gate_B=drain_A.
**Template:** `CCP_NMOS` / `CCP_PMOS`
**Constraints:** `SymmetricBlocks` (V-axis) + `SymmetricNets`

### 6. Diode-Connected Load Pair (`diode_connected_load`)

```
Schematic:  VDD --[M1 G=D]-- OUTP
            VDD --[M2 G=D]-- OUTN
```

**Recognition:** 2+ FETs, same model, same W/L, each gate=drain, symmetric loads.
**Template:** `DCL_NMOS` / `DCL_PMOS`
**Constraints:** `SymmetricBlocks` (V-axis) + `SameTemplate`

### 7. Level Shifter (`level_shifter`)

```
Schematic:  DA --[M1]-- SA      (split sources SA/SB)
            DB --[M2]-- SB
```

**Recognition:** 2 FETs, same model, same W/L, separate sources, symmetric gate-drain paths.
**Template:** `LS_S_NMOS_B` / `LS_S_PMOS_B`
**Constraints:** `SymmetricBlocks` (V-axis) + `SymmetricNets` (outputs, sources)

### 8. CMOS Inverter (`inverter`)

```
Schematic:  VDD --[MP]-- OUT --[MN]-- VSS
                   (shared gate = IN)
```

**Recognition:** 1 NMOS + 1 PMOS, gate(N)=gate(P), drain(N)=drain(P).
**Template:** `INV` / `INV_B` ([user_template.sp](../../../align/config/user_template.sp))
**Constraints:** `GroupBlocks` + `Order` (top_to_bottom, PMOS above NMOS) + `Align` (v_center)

### 9. Transmission Gate (`transmission_gate`)

```
Schematic:  IN --[MN CLK]-- OUT
            IN --[MP CLKB]-- OUT    (parallel NMOS+PMOS)
```

**Recognition:** 1 NMOS + 1 PMOS, drain(N)=drain(P), source(N)=source(P), complementary gates.
**Template:** `tgate` ([user_template.sp](../../../align/config/user_template.sp))
**Constraints:** `GroupBlocks` + `Align` (h_center)

### 10. Matched Series Resistors (`res_series_matched`)

```
Schematic:  INP --[R0]--[R1]--[R2]-- OUTN
```

**Recognition:** 2+ resistors, same model, same R value, chained in series.
**Constraints:** `GroupBlocks` + `AlignInOrder` (horizontal) + `SameTemplate`

### 11. Resistive Voltage Divider (`res_divider`)

```
Schematic:  VIN --[R0]-- VMID --[R1]-- VOUT
```

**Recognition:** 2 resistors sharing a midpoint node, other terminals to distinct nets.
**Constraints:** `GroupBlocks` + `AlignInOrder` (vertical) + `SameTemplate` (if equal values)

### 12. Matched Capacitor Pair (`cap_matched_pair`)

```
Schematic:  INP --[C0]-- BOT
            INN --[C1]-- BOT
```

**Recognition:** 2 caps, same model, same C value, symmetric signal paths.
**Constraints:** `SymmetricBlocks` (V-axis) + `SymmetricNets`

### 13. Common-Centroid Cap Array (`cap_array_cc`)

```
Schematic:  B0 --[C0]-- BOT    (1 unit)
            B1 --[C1,C2]-- BOT (2 units)
            B2 --[C3..C6]-- BOT (4 units)
            VREF --[C7]-- BOT  (dummy/ref)
```

**Recognition:** 3+ caps with integer-ratio values, shared bottom plate.
**Constraints:** `GroupCaps` (with unit_cap, num_units, dummy flag)
**Placement engine:** [align/pnr/cap_placer.py](../../../align/pnr/cap_placer.py) + C++ [PlaceRouteHierFlow/cap_placer/](../../../PlaceRouteHierFlow/cap_placer/)

### 14. Switched Capacitor Cell (`switched_cap`)

```
Schematic:  IN --[M1 switch]--[C0]--[M2 switch]-- OUT
                  (CLK)               (CLKB)
```

**Recognition:** Cap with switching FETs on terminals, clock-driven gates.
**Template:** `switched_capacitor_combination` ([user_template.sp](../../../align/config/user_template.sp))
**Constraints:** `GroupBlocks` + `SymmetricBlocks` (switches + self-sym cap) + `ClockPorts`

### 15. Guard Ring (`guard_ring`)

**Recognition:** User-specified (no auto-detection). Applied to noise-sensitive blocks.
**Constraints:** `GuardRing` (guard_ring_primitives, global_pin, block_name)
**Generation:** [align/primitive/main.py](../../../align/primitive/main.py) `generate_Ring` + C++ [PlaceRouteHierFlow/guard_ring/](../../../PlaceRouteHierFlow/guard_ring/)

### 16. Dummy & Decap (`dummy_and_decap`)

**Recognition (automatic):** FET with G=S=D, or gate tied to supply. Detected by `remove_dummy_devices` in [align/compiler/preprocess.py](../../../align/compiler/preprocess.py).
**Constraints:** `DoNotIdentify` (prevent grouping) + `ConfigureCompiler` (`remove_dummy_devices: false` to preserve)
**Template:** `DUMMY_NMOS`, `DCAP_NMOS` etc.

---

## Inference Rules

Machine-readable rules mapping netlist features to constraint types.
Use these to auto-detect substructures and apply the correct constraints.

```json
[
    {
        "pattern": "differential_pair",
        "conditions": [
            "2 FETs",
            "same model (any MOS type)",
            "same W/L",
            "shared source node",
            "different gate nets"
        ],
        "constraints": ["SymmetricBlocks", "SymmetricNets"],
        "files": ["differential_pair.sp", "differential_pair.const.json"]
    },
    {
        "pattern": "current_mirror_simple",
        "conditions": [
            "2+ FETs",
            "same model",
            "same W/L",
            "one device has gate=drain (diode-connected)",
            "shared source/body"
        ],
        "constraints": ["GroupBlocks", "SameTemplate", "Align"],
        "files": ["current_mirror.sp", "current_mirror.const.json"]
    },
    {
        "pattern": "current_mirror_cascode",
        "conditions": [
            "4 FETs in 2 stacked pairs",
            "bottom pair: same model/W/L, one diode-connected",
            "top pair: same model/W/L, drain(bottom)=source(top)",
            "shared body"
        ],
        "constraints": ["GroupBlocks", "SymmetricBlocks", "Order", "SameTemplate"],
        "files": ["current_mirror_cascode.sp", "current_mirror_cascode.const.json"]
    },
    {
        "pattern": "current_mirror_ratio",
        "conditions": [
            "2+ FETs",
            "same model",
            "same W and L per finger",
            "different nf or m (integer ratio)",
            "one device diode-connected"
        ],
        "constraints": ["GroupBlocks", "Align", "Generator(pattern=ratio_devices)"],
        "files": ["current_mirror_ratio.sp", "current_mirror_ratio.const.json"]
    },
    {
        "pattern": "cross_coupled_pair",
        "conditions": [
            "2 FETs",
            "same model",
            "same W/L",
            "gate_A = drain_B",
            "gate_B = drain_A"
        ],
        "constraints": ["SymmetricBlocks", "SymmetricNets"],
        "files": ["cross_coupled_pair.sp", "cross_coupled_pair.const.json"]
    },
    {
        "pattern": "diode_connected_load",
        "conditions": [
            "2+ FETs",
            "same model",
            "same W/L",
            "each has gate=drain",
            "used as symmetric loads"
        ],
        "constraints": ["SymmetricBlocks", "SameTemplate"],
        "files": ["diode_connected_load.sp", "diode_connected_load.const.json"]
    },
    {
        "pattern": "level_shifter",
        "conditions": [
            "2 FETs",
            "same model",
            "same W/L",
            "separate source nodes (SA/SB)",
            "symmetric gate-drain connectivity"
        ],
        "constraints": ["SymmetricBlocks", "SymmetricNets"],
        "files": ["level_shifter.sp", "level_shifter.const.json"]
    },
    {
        "pattern": "cmos_inverter",
        "conditions": [
            "1 NMOS + 1 PMOS",
            "gate(N) = gate(P)",
            "drain(N) = drain(P)"
        ],
        "constraints": ["GroupBlocks", "Order", "Align"],
        "files": ["inverter.sp", "inverter.const.json"]
    },
    {
        "pattern": "transmission_gate",
        "conditions": [
            "1 NMOS + 1 PMOS",
            "drain(N) = drain(P)",
            "source(N) = source(P)",
            "complementary gate signals"
        ],
        "constraints": ["GroupBlocks", "Align"],
        "files": ["transmission_gate.sp", "transmission_gate.const.json"]
    },
    {
        "pattern": "matched_series_resistors",
        "conditions": [
            "2+ resistors",
            "same model",
            "same R value",
            "chained in series"
        ],
        "constraints": ["GroupBlocks", "AlignInOrder", "SameTemplate"],
        "files": ["res_series_matched.sp", "res_series_matched.const.json"]
    },
    {
        "pattern": "resistive_divider",
        "conditions": [
            "2 resistors",
            "sharing one node (midpoint)",
            "other terminals to distinct supply/signal nets"
        ],
        "constraints": ["GroupBlocks", "AlignInOrder", "SameTemplate"],
        "files": ["res_divider.sp", "res_divider.const.json"]
    },
    {
        "pattern": "matched_cap_pair",
        "conditions": [
            "2 capacitors",
            "same model",
            "same C value",
            "connected to symmetric signal paths"
        ],
        "constraints": ["SymmetricBlocks", "SymmetricNets"],
        "files": ["cap_matched_pair.sp", "cap_matched_pair.const.json"]
    },
    {
        "pattern": "common_centroid_cap_array",
        "conditions": [
            "3+ capacitors",
            "integer-ratio values",
            "shared bottom plate (common node)"
        ],
        "constraints": ["GroupCaps"],
        "files": ["cap_array_cc.sp", "cap_array_cc.const.json"]
    },
    {
        "pattern": "switched_capacitor",
        "conditions": [
            "capacitor flanked by FET switches",
            "switch gates driven by clock signals"
        ],
        "constraints": ["GroupBlocks", "SymmetricBlocks", "ClockPorts"],
        "files": ["switched_cap.sp", "switched_cap.const.json"]
    },
    {
        "pattern": "guard_ring",
        "conditions": [
            "user-specified (no auto-detection)",
            "noise-sensitive block requiring isolation"
        ],
        "constraints": ["GuardRing"],
        "files": ["guard_ring.sp", "guard_ring.const.json"]
    },
    {
        "pattern": "dummy_decap",
        "conditions": [
            "FET with G=S=D (all terminals tied)",
            "or gate tied to supply rail",
            "auto-detected by compiler"
        ],
        "constraints": ["DoNotIdentify", "ConfigureCompiler(remove_dummy_devices=false)"],
        "files": ["dummy_and_decap.sp", "dummy_and_decap.const.json"]
    }
]
```

---

## Python-to-PnR Constraint Name Mapping

User JSON `"constraint"` values are Python class names. The PnR engine uses different
names via [align/pnr/write_constraint.py](../../../align/pnr/write_constraint.py):

| Python (user JSON) | PnR (`const_name`) | Notes |
|---|---|---|
| `SymmetricBlocks` | `SymmBlock` | `pairs` restructured to `selfsym`/`sympair` objects |
| `Order` | `Ordering` | `direction` mapped: `left_to_right`->`H`, `top_to_bottom`->`V` |
| `Align` | `AlignBlock` | `h_any`/`v_any` not supported in PnR path |
| `GroupCaps` | `CC` | `name`->`cap_name`, `unit_cap`->`unit_capacitor`, `num_units`->`size` |
| `SymmetricNets` | `SymmNet` | Nets become structured objects with pin lists |
| `BlockDistance` | `bias_graph` | `abs_distance`->`distance` |
| `HorizontalDistance` | `bias_Hgraph` | |
| `VerticalDistance` | `bias_Vgraph` | |
| `AspectRatio` | `Aspect_Ratio` | |
| `PlaceCloser` | `MatchBlock` | All pairs of listed instances |
| `MultiConnection` | `Multi_Connection` | Per-net: `multi_number`, `net_name` |
| `NetConst` | `ShieldNet` / `CritNet` | Split per net based on `shield`/`criticality` |
| `NetPriority` | `CritNet` | `weight`->`priority` |
| `PortLocation` | `PortLocation` | One entry per port |

Constraints consumed at compile time (not forwarded to PnR):
`GroupBlocks`, `DoNotIdentify`, `DoNotUseLib`, `ConfigureCompiler`, `SameTemplate` (merged separately), `PlaceOnBoundary`.

---

## MOS Layout Pattern Reference

From [align/primitive/main.py](../../../align/primitive/main.py) `pattern_map` and
implemented in [pdks/Bulk45nm_Mock_PDK/mos.py](../mos.py):

| Pattern Name | ID | Use Case |
|---|---|---|
| `single_device` | 0 | One device / one column |
| `cc` | 1 | Common-centroid interleaving of two matched devices |
| `id` | 2 | Interdigitated (checkerboard A/B) |
| `ratio_devices` | 3 | Current mirror / ratio layout tiling |
| `ncc` | 4 | Non-common-centroid (two groups side by side) |

Default: identical params -> `cc`; different params -> `ratio_devices`.

---

## Code Pointers

| Component | Path | Role |
|---|---|---|
| Constraint schema (all 36 types) | `align/schema/constraint.py` | Pydantic models, `ConstraintType` union |
| User constraint loading | `align/compiler/user_const.py` | Reads `*.const.json`, dispatches by `"constraint"` key |
| Auto-constraint discovery | `align/compiler/find_constraint.py` | Symmetry search from port pairs, array detection |
| Subgraph matching | `align/compiler/match_graph.py` | NetworkX `GraphMatcher` against template library |
| Template library (core) | `align/config/basic_template.sp` | DP, SCM, CMC, CCP, LS, DCL, dummies, passives |
| Template library (extended) | `align/config/user_template.sp` | Cascoded mirrors, inverters, tgate, switched-cap |
| Python-to-PnR mapping | `align/pnr/write_constraint.py` | `PnRConstraintWriter.map_valid_const` |
| C++ constraint reader | `PlaceRouteHierFlow/PnRDB/ReadConstraint.cpp` | Parses `*.pnr.const.json` with `const_name` |
| C++ placer (SymmBlock) | `PlaceRouteHierFlow/placer/Pdatatype.h` | `placerDB::SymmBlock` struct |
| MOS pattern enum | `align/primitive/main.py` | `pattern_map`: single/cc/id/ratio/ncc |
| MOS layout generator | `pdks/Bulk45nm_Mock_PDK/mos.py` | `_addMOSArray`, pattern dispatch |
| Cap placer (Python) | `align/pnr/cap_placer.py` | Common-centroid cap placement |
| Cap placer (C++) | `PlaceRouteHierFlow/cap_placer/` | C++ CC placement engine |
| Guard ring (C++) | `PlaceRouteHierFlow/guard_ring/` | Guard ring generation |
| Dummy removal | `align/compiler/preprocess.py` | `remove_dummy_devices` heuristic |
| End-to-end flow | `align/main.py` | `1_topology` -> `2_primitives` -> `3_pnr` |

---

## File Index

| # | Substructure | Files | Key Constraints |
|---|---|---|---|
| 1 | Differential Pair | `differential_pair.sp` / `.const.json` | `SymmetricBlocks`, `SymmetricNets` |
| 2 | Simple Current Mirror | `current_mirror.sp` / `.const.json` | `GroupBlocks`, `SameTemplate`, `Align` |
| 3 | Cascode Current Mirror | `current_mirror_cascode.sp` / `.const.json` | `SymmetricBlocks`, `Order`, `SameTemplate`, `GroupBlocks` |
| 4 | Scaled Mirror (W*N/L) | `current_mirror_ratio.sp` / `.const.json` | `GroupBlocks`, `Align`, `Generator` |
| 5 | Cross-Coupled Pair | `cross_coupled_pair.sp` / `.const.json` | `SymmetricBlocks`, `SymmetricNets` |
| 6 | Diode-Connected Load | `diode_connected_load.sp` / `.const.json` | `SymmetricBlocks`, `SameTemplate` |
| 7 | Level Shifter | `level_shifter.sp` / `.const.json` | `SymmetricBlocks`, `SymmetricNets` |
| 8 | CMOS Inverter | `inverter.sp` / `.const.json` | `GroupBlocks`, `Order`, `Align` |
| 9 | Transmission Gate | `transmission_gate.sp` / `.const.json` | `GroupBlocks`, `Align` |
| 10 | Matched Series Resistors | `res_series_matched.sp` / `.const.json` | `GroupBlocks`, `AlignInOrder`, `SameTemplate` |
| 11 | Resistive Divider | `res_divider.sp` / `.const.json` | `GroupBlocks`, `AlignInOrder`, `SameTemplate` |
| 12 | Matched Capacitor Pair | `cap_matched_pair.sp` / `.const.json` | `SymmetricBlocks`, `SymmetricNets` |
| 13 | CC Cap Array (DAC) | `cap_array_cc.sp` / `.const.json` | `GroupCaps` |
| 14 | Switched Capacitor | `switched_cap.sp` / `.const.json` | `GroupBlocks`, `SymmetricBlocks`, `ClockPorts` |
| 15 | Guard Ring | `guard_ring.sp` / `.const.json` | `GuardRing`, `SymmetricBlocks` |
| 16 | Dummy & Decap | `dummy_and_decap.sp` / `.const.json` | `DoNotIdentify`, `ConfigureCompiler` |
