"""
Baseline scorer — pairwise F1 of every baseline .json in a testbench folder
against that circuit's Golden_ALIGN_Constraints.json, plus a cross-circuit
average per category.

Reuses the *exact* scoring logic from the golden scoreboard
(Listen_to_the_HeaRT/LLM_Agent_Codes/agents/scoreboard.py) — that file is
imported, never modified. Same union-find pooling, same direction-agnostic
pairwise TP/FP/FN, same Precision / Recall / F1 definitions.

Three categories are tracked, matching the scoreboard:
    SymmetricBlocks, MatchDevices, SymmetricNets

Per-cell status (one baseline x category x circuit)
---------------------------------------------------
    N/A   golden is EMPTY for this category -> not applicable to this circuit.
    0     golden non-empty, baseline DID emit this constraint type but every
          predicted pair is wrong (a real, scored miss).
    Fail  golden non-empty, baseline emits NO constraints of this type at all
          (it cannot support the category) — distinct from a scored 0.

Average across circuits (per baseline x category)
-------------------------------------------------
    * N/A circuits are dropped (category does not apply there).
    * If every remaining circuit is N/A      -> N/A.
    * If every remaining circuit is Fail      -> Fail   ("consistently fails").
    * Otherwise -> numeric mean, where each Fail circuit counts as 0.0 (the
      baseline produced nothing the golden expected, i.e. a total miss).

Usage
-----
    # One circuit:
    python3 scorer_baseline.py --case LDO_Simple_Testbench
    python3 scorer_baseline.py --case OTA_TOPOLOGY_1_Testbench
    python3 scorer_baseline.py --case StrongArm_Latch_Comparator

    # Cross-circuit average per category (defaults to the 3 cases above):
    python3 scorer_baseline.py --average
    python3 scorer_baseline.py --average --cases LDO_Simple_Testbench,OTA_TOPOLOGY_1_Testbench

    # Override / add a golden, or suppress the JSON report:
    python3 scorer_baseline.py --case StrongArmComp_Testbench --gold /abs/Golden_ALIGN_Constraints.json
    python3 scorer_baseline.py --case LDO_Simple_Testbench --no-save
"""

import argparse
import glob
import json
import os
import sys
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Locate and import the golden scoreboard (read-only reuse — DO NOT EDIT it).
# ---------------------------------------------------------------------------
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
# Baselines/constraints4theTestbenches/ -> AnaCLARA_Framework/
PROJECT_ROOT = os.path.dirname(os.path.dirname(THIS_DIR))
SCOREBOARD_DIR = os.path.join(
    PROJECT_ROOT, "Listen_to_the_HeaRT", "LLM_Agent_Codes", "agents"
)
if SCOREBOARD_DIR not in sys.path:
    sys.path.insert(0, SCOREBOARD_DIR)

import scoreboard as sb  # noqa: E402  (golden module — used, never mutated)

TRACKED = sb.TRACKED_CONSTRAINTS  # ("SymmetricBlocks", "MatchDevices", "SymmetricNets")

# ---------------------------------------------------------------------------
# Case folder -> golden constraints file (under the repo's netlists tree).
# Add new circuits here, or pass --gold to override.
# ---------------------------------------------------------------------------
NETLISTS = os.path.join(PROJECT_ROOT, "Listen_to_the_HeaRT", "LLM_Agent_Codes", "netlists")
CASE_TO_GOLD = {
    "LDO_Simple_Testbench":        os.path.join(NETLISTS, "LDO_Simple", "Input_Netlist", "Golden_ALIGN_Constraints.json"),
    # ota4 is OTA Topology 1.
    "OTA_TOPOLOGY_1_Testbench":    os.path.join(NETLISTS, "OTAs", "ota4", "Input_Netlist", "Golden_ALIGN_Constraints.json"),
    # Both StrongArm testbenches score against the same StrongArm golden.
    "StrongArm_Latch_Comparator":  os.path.join(NETLISTS, "StrongArm_Latch_Comparator", "Input_Netlist", "Golden_ALIGN_Constraints.json"),
    "StrongArmComp_Testbench":     os.path.join(NETLISTS, "StrongArm_Latch_Comparator", "Input_Netlist", "Golden_ALIGN_Constraints.json"),
}

# Default circuit set for cross-circuit averaging (the 3 real cases).
DEFAULT_AVERAGE_CASES = [
    "LDO_Simple_Testbench",
    "OTA_TOPOLOGY_1_Testbench",
    "StrongArm_Latch_Comparator",
]

# Sentinel status strings (distinct from a numeric float f1).
NA = "N/A"
FAIL = "Fail"


def _baseline_name(filename: str) -> str:
    """Strip the constraint-file suffix to get a clean baseline label."""
    for suffix in (".const.json", "_constraints.json", ".json"):
        if filename.endswith(suffix):
            return filename[: -len(suffix)]
    return filename


def _has_constraint(constraints: List[Dict[str, Any]], ctype: str) -> bool:
    return any(
        isinstance(c, dict) and c.get("constraint") == ctype for c in constraints
    )


def _cell_status(ctype: str, pred_constraints: List[Dict[str, Any]], cat_report: Dict[str, Any]):
    """Classify one (baseline, category, circuit) cell.

    Returns a float F1 (numeric, including a scored 0.0), or NA, or FAIL.
      * support == 0            -> NA   (golden empty: not applicable here)
      * baseline emits nothing  -> FAIL (cannot support the category)
      * else                    -> numeric F1 from the scoreboard
    """
    support = cat_report["support"]  # = tp + fn = number of golden pairs
    if support == 0:
        return NA
    if not _has_constraint(pred_constraints, ctype):
        return FAIL
    return cat_report["f1"]


def score_baseline_file(
    pred_constraints: List[Dict[str, Any]],
    gold_constraints: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Score one baseline against golden using the scoreboard's own logic,
    then tag each category with its N/A / Fail / numeric status."""
    report = sb.score_final_align(pred_constraints, gold_constraints)
    out: Dict[str, Any] = {}
    for ctype in TRACKED:
        r = report[ctype]
        out[ctype] = {
            k: r[k] for k in ("tp", "fp", "fn", "support", "precision", "recall", "f1")
        }
        out[ctype]["status"] = _cell_status(ctype, pred_constraints, r)
    return out


def resolve_gold(case: str, gold_override: Optional[str]) -> str:
    if gold_override:
        return gold_override
    gold = CASE_TO_GOLD.get(case)
    if gold is None:
        raise SystemExit(
            f"ERROR: no built-in golden mapping for case '{case}'.\n"
            f"  Known cases: {', '.join(sorted(CASE_TO_GOLD))}\n"
            f"  Pass --gold /abs/path/to/Golden_ALIGN_Constraints.json to score it."
        )
    if not os.path.isfile(gold):
        raise SystemExit(f"ERROR: golden file for case '{case}' not found: {gold}")
    return gold


def score_case(case: str, gold_override: Optional[str] = None) -> Dict[str, Any]:
    """Score every baseline .json in a case folder. Returns a structured dict."""
    case_dir = os.path.join(THIS_DIR, case)
    if not os.path.isdir(case_dir):
        raise SystemExit(f"ERROR: case folder not found: {case_dir}")

    gold_path = resolve_gold(case, gold_override)
    gold = sb._load_json(gold_path)
    if not isinstance(gold, list):
        raise SystemExit(f"ERROR: golden file is not a top-level list: {gold_path}")

    json_files = sorted(glob.glob(os.path.join(case_dir, "*.json")))
    json_files = [f for f in json_files if os.path.basename(f) != "Baseline_Scoreboard.json"]
    if not json_files:
        raise SystemExit(f"ERROR: no .json baselines found in {case_dir}")

    results: List[Dict[str, Any]] = []
    for path in json_files:
        name = _baseline_name(os.path.basename(path))
        try:
            pred = sb._load_json(path)
        except json.JSONDecodeError as e:
            print(f"  [skip] {name}: invalid JSON ({e})", file=sys.stderr)
            continue
        if not isinstance(pred, list):
            print(f"  [skip] {name}: not a top-level list of constraints", file=sys.stderr)
            continue
        results.append({
            "baseline": name,
            "file": os.path.basename(path),
            "scores": score_baseline_file(pred, gold),
        })

    return {
        "case": case,
        "golden_path": os.path.abspath(gold_path),
        "n_baselines": len(results),
        "results": results,
    }


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------

def _fmt_status(s: Any) -> str:
    """Format a cell status: float -> 0.4f, else the sentinel string."""
    if isinstance(s, float):
        return f"{s:.4f}"
    if s is None:
        return NA
    return str(s)


def pretty_print_case(report: Dict[str, Any]) -> None:
    print("=" * 86)
    print(f"Baseline scoreboard — case: {report['case']}  (pair-level, direction-agnostic)")
    print(f"  golden: {report['golden_path']}")
    print("=" * 86)
    header = f"{'baseline':<22}" + "".join(f"{c:>20}" for c in TRACKED)
    print(header)
    print("-" * len(header))
    for r in report["results"]:
        row = f"{r['baseline']:<22}"
        for c in TRACKED:
            row += f"{_fmt_status(r['scores'][c]['status']):>20}"
        print(row)
    print("=" * 86)
    print("Legend: numeric F1 | 0 = emitted-but-wrong | Fail = category not emitted | N/A = golden empty")


def _average_category(cell_statuses: List[Any]) -> Dict[str, Any]:
    """Apply the cross-circuit averaging rule to a list of per-circuit statuses."""
    applicable = [s for s in cell_statuses if s != NA]  # drop N/A circuits
    n_na = len(cell_statuses) - len(applicable)
    n_fail = sum(1 for s in applicable if s == FAIL)
    numeric = [float(s) for s in applicable if isinstance(s, (int, float))]

    if not applicable:
        avg: Any = NA
    elif not numeric:               # every applicable circuit is a Fail
        avg = FAIL
    else:                           # mean over numeric circuits + Fails as 0.0
        total = sum(numeric) + 0.0 * n_fail  # Fail contributes 0.0
        avg = round(total / (len(numeric) + n_fail), 4)

    return {
        "average": avg,
        "n_circuits": len(cell_statuses),
        "n_applicable": len(applicable),
        "n_na": n_na,
        "n_fail": n_fail,
        "n_scored": len(numeric),
        "per_circuit": cell_statuses,
    }


def aggregate_average(cases: List[str]) -> Dict[str, Any]:
    """Score each case, then average each category across circuits per baseline."""
    case_reports = {case: score_case(case) for case in cases}

    # baseline -> ctype -> [status per case]
    per_baseline: Dict[str, Dict[str, List[Any]]] = {}
    for case in cases:
        for r in case_reports[case]["results"]:
            slot = per_baseline.setdefault(r["baseline"], {c: [] for c in TRACKED})
            for c in TRACKED:
                slot[c].append(r["scores"][c]["status"])

    averages: Dict[str, Dict[str, Any]] = {}
    for baseline, by_ctype in per_baseline.items():
        averages[baseline] = {c: _average_category(by_ctype[c]) for c in TRACKED}

    return {
        "cases": cases,
        "golden_paths": {case: case_reports[case]["golden_path"] for case in cases},
        "averages": averages,
        "per_case": case_reports,
    }


def pretty_print_average(agg: Dict[str, Any]) -> None:
    cases = agg["cases"]
    print("=" * 100)
    print(f"Cross-circuit average per category — {len(cases)} circuits: {', '.join(cases)}")
    print("=" * 100)
    header = f"{'baseline':<22}" + "".join(f"{c:>26}" for c in TRACKED)
    print(header)
    print("-" * len(header))
    for baseline in sorted(agg["averages"]):
        row = f"{baseline:<22}"
        for c in TRACKED:
            a = agg["averages"][baseline][c]
            cell = _fmt_status(a["average"])
            # annotate when some circuits were dropped (N/A) or failed
            notes = []
            if a["n_fail"]:
                notes.append(f"{a['n_fail']}F")
            if a["n_na"]:
                notes.append(f"{a['n_na']}NA")
            if notes and isinstance(a["average"], float):
                cell += f" ({','.join(notes)})"
            row += f"{cell:>26}"
        print(row)
    print("=" * 100)
    print("cell = mean F1 across applicable circuits (Fail counts as 0).")
    print("  suffix nF = n circuits the baseline could not support (counted 0);")
    print("  suffix mNA = m circuits dropped as N/A (golden empty).")
    print("  Fail = baseline failed the category in every applicable circuit.")
    print("  N/A  = category had empty golden in every circuit.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--case", default=None, help="Score one testbench folder (e.g. LDO_Simple_Testbench).")
    parser.add_argument("--gold", default=None, help="Override path to Golden_ALIGN_Constraints.json.")
    parser.add_argument("--out", default=None, help="Override path for the JSON report.")
    parser.add_argument("--no-save", action="store_true", help="Print only; write no JSON.")
    parser.add_argument(
        "--average",
        action="store_true",
        help="Average each category's F1 across circuits (per baseline).",
    )
    parser.add_argument(
        "--cases",
        default=None,
        help="With --average: comma-separated case folders (default: the 3 real cases).",
    )
    args = parser.parse_args()

    # Cross-circuit average mode.
    if args.average:
        cases = (
            [c.strip() for c in args.cases.split(",") if c.strip()]
            if args.cases else DEFAULT_AVERAGE_CASES
        )
        agg = aggregate_average(cases)
        pretty_print_average(agg)
        if not args.no_save:
            out_path = args.out or os.path.join(THIS_DIR, "Average_Scoreboard.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(agg, f, indent=2)
            print(f"\nReport saved: {out_path}")
        return

    # Single-case mode.
    if not args.case:
        parser.error("Provide --case <FOLDER> or --average.")
    report = score_case(args.case, args.gold)
    pretty_print_case(report)
    if not args.no_save:
        out_path = args.out or os.path.join(THIS_DIR, args.case, "Baseline_Scoreboard.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved: {out_path}")


if __name__ == "__main__":
    main()
