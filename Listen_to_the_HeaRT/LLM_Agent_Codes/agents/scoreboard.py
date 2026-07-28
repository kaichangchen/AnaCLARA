"""
Scoreboard for Final_ALIGN_Constraints.json vs Golden_ALIGN_Constraints.json.

Validates three constraint types at the PAIR level:
    - SymmetricBlocks
    - MatchDevices
    - SymmetricNets

Scoring model
-------------
* For each constraint type, pool every (a, b) edge across all entries
  of that type (from both predicted and golden).
* Run union-find over the pooled edges to recover the implied groups
  (connected components). This way a chain like [a,b], [b,c] is
  collapsed into the group {a,b,c}.
* Each group of size n is then expanded to all C(n,2) member pairs.
  The resulting pooled pair set is what we score against.
* Direction is ignored.
* TP / FP / FN are computed on UNORDERED PAIRS:
      TP  = pairs present in both predicted-expanded and golden-expanded
      FP  = pairs in predicted only
      FN  = pairs in golden only
* Precision / Recall / F1 follow standard definitions. This is the
  "pairwise F1" used in clustering / coreference evaluation: it gives
  partial credit when predicted and golden groups overlap but aren't
  identical, which strict group-equality scoring does not.

Format quirks handled
---------------------
* Predicted SymmetricNets uses the legacy form
      {"constraint": "SymmetricNets", "net1": "...", "net2": "...", "direction": "..."}
  Golden SymmetricNets uses the pair-list form
      {"constraint": "SymmetricNets", "pairs": [["a","b"], ...]}
  Both are accepted.
* All names are lower-cased before comparison.

Usage
-----
    python3 scoreboard.py --case Hysteritic_Comp

    python3 scoreboard.py \
        --pred <abs path to Final_ALIGN_Constraints.json> \
        --gold <abs path to Golden_ALIGN_Constraints.json>

    python3 scoreboard.py --case Hysteritic_Comp --out scoreboard_report.json

Later this can be extended to walk Results/MultiRun/Run_XX/ or
Results/MultiModel/<MODEL>/ and aggregate scores across runs/models.
"""

import argparse
import itertools
import json
import os
import statistics
import sys
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))

TRACKED_CONSTRAINTS = ("SymmetricBlocks", "MatchDevices", "SymmetricNets")


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _lc(x: Any) -> str:
    return str(x).strip().lower()


def _extract_pairs(
    constraints: List[Dict[str, Any]],
    constraint_type: str,
) -> List[Tuple[str, str]]:
    """Pool every (a, b) edge across all entries of `constraint_type`.

    Accepted shapes:
      * {"constraint": ctype, "pairs": [[a,b], ...]}
      * {"constraint": "SymmetricNets", "net1": "...", "net2": "..."}  (legacy)
    """
    pairs: List[Tuple[str, str]] = []
    if not isinstance(constraints, list):
        return pairs

    for c in constraints:
        if not isinstance(c, dict):
            continue
        if c.get("constraint") != constraint_type:
            continue

        # Pair-list form (works for all three constraint types).
        for pr in c.get("pairs", []) or []:
            if not isinstance(pr, (list, tuple)) or len(pr) != 2:
                continue
            a, b = _lc(pr[0]), _lc(pr[1])
            if not a or not b or a == b:
                continue
            pairs.append((a, b))

        # Legacy SymmetricNets shape: single (net1, net2) per entry.
        if constraint_type == "SymmetricNets":
            n1, n2 = _lc(c.get("net1", "")), _lc(c.get("net2", ""))
            if n1 and n2 and n1 != n2:
                pairs.append((n1, n2))

    return pairs


def _union_find_groups(pairs: List[Tuple[str, str]]) -> List[FrozenSet[str]]:
    """Union-find on pair edges → list of connected components (size >= 2)."""
    parent: Dict[str, str] = {}
    rank: Dict[str, int] = {}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
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

    for a, b in pairs:
        for n in (a, b):
            if n not in parent:
                parent[n] = n
                rank[n] = 0

    for a, b in pairs:
        union(a, b)

    comps: Dict[str, Set[str]] = {}
    for n in parent:
        r = find(n)
        comps.setdefault(r, set()).add(n)

    return [frozenset(c) for c in comps.values() if len(c) >= 2]


def _expand_groups_to_pair_set(groups: List[FrozenSet[str]]) -> Set[FrozenSet[str]]:
    """For each group of size n, emit all C(n,2) unordered member pairs."""
    pair_set: Set[FrozenSet[str]] = set()
    for g in groups:
        for a, b in itertools.combinations(sorted(g), 2):
            pair_set.add(frozenset({a, b}))
    return pair_set


def _prf(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def _score_one_constraint(
    pred_groups: List[FrozenSet[str]],
    gold_groups: List[FrozenSet[str]],
) -> Dict[str, Any]:
    pred_pair_set = _expand_groups_to_pair_set(pred_groups)
    gold_pair_set = _expand_groups_to_pair_set(gold_groups)

    tp_set = pred_pair_set & gold_pair_set
    fp_set = pred_pair_set - gold_pair_set
    fn_set = gold_pair_set - pred_pair_set

    tp, fp, fn = len(tp_set), len(fp_set), len(fn_set)
    # support = number of golden positives for this category (tp + fn).
    # If support == 0 the category effectively does not exist in this
    # circuit, so precision / recall / F1 are NOT APPLICABLE (null) — we
    # don't want a contrived 0.0 polluting later cross-circuit aggregation.
    support = tp + fn
    if support == 0:
        precision = recall = f1 = None
    else:
        precision, recall, f1 = _prf(tp, fp, fn)
        precision, recall, f1 = round(precision, 4), round(recall, 4), round(f1, 4)

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "support": support,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "predicted_groups": sorted([sorted(g) for g in pred_groups]),
        "golden_groups": sorted([sorted(g) for g in gold_groups]),
        "n_predicted_pairs": len(pred_pair_set),
        "n_golden_pairs": len(gold_pair_set),
        "false_positives": sorted([sorted(p) for p in fp_set]),
        "false_negatives": sorted([sorted(p) for p in fn_set]),
    }


def score_final_align(
    pred_constraints: List[Dict[str, Any]],
    gold_constraints: List[Dict[str, Any]],
) -> Dict[str, Any]:
    report: Dict[str, Any] = {}

    for ctype in TRACKED_CONSTRAINTS:
        pred_pairs = _extract_pairs(pred_constraints, ctype)
        gold_pairs = _extract_pairs(gold_constraints, ctype)
        pred_groups = _union_find_groups(pred_pairs)
        gold_groups = _union_find_groups(gold_pairs)
        report[ctype] = _score_one_constraint(pred_groups, gold_groups)

    # NOTE: no per-circuit averaging across categories. Cross-circuit
    # aggregation per category (e.g., mean F1 of SymmetricBlocks across
    # all cases) is done by a separate aggregator script, not here.
    return report


def pretty_print_report(report: Dict[str, Any], pred_path: str, gold_path: str) -> None:
    print("=" * 84)
    print("Final ALIGN Constraints — Scoreboard  (pair-level, direction-agnostic)")
    print(f"  predicted: {pred_path}")
    print(f"  golden   : {gold_path}")
    print("=" * 84)

    def _fmt(v: Any) -> str:
        return "  N/A   " if v is None else f"{v:>8.4f}"

    header = f"{'Constraint':<20}{'TP':>6}{'FP':>6}{'FN':>6}{'Sup':>6}{'Prec':>10}{'Rec':>10}{'F1':>10}"
    print(header)
    print("-" * len(header))

    for ctype in TRACKED_CONSTRAINTS:
        r = report[ctype]
        print(
            f"{ctype:<20}{r['tp']:>6}{r['fp']:>6}{r['fn']:>6}{r['support']:>6}"
            f"  {_fmt(r['precision'])}  {_fmt(r['recall'])}  {_fmt(r['f1'])}"
        )
    print("=" * 84)

    for ctype in TRACKED_CONSTRAINTS:
        r = report[ctype]
        print(
            f"\n[{ctype}]  "
            f"predicted_groups={r['predicted_groups']}  "
            f"golden_groups={r['golden_groups']}  "
            f"(expanded pairs: pred={r['n_predicted_pairs']}, gold={r['n_golden_pairs']})"
        )
        if r["false_positives"] or r["false_negatives"]:
            if r["false_positives"]:
                print(f"  False positive pairs ({len(r['false_positives'])}): predicted but not in golden")
                for p in r["false_positives"]:
                    print(f"    + {p}")
            if r["false_negatives"]:
                print(f"  False negative pairs ({len(r['false_negatives'])}): in golden but missing from prediction")
                for p in r["false_negatives"]:
                    print(f"    - {p}")


def resolve_paths_from_case(case: str) -> Tuple[str, str]:
    base = os.path.join(
        PROJECT_ROOT,
        "LLM_Agent_Codes",
        "netlists",
        case,
        "Generated_Subcircuits",
    )
    pred = os.path.join(base, "Final_ALIGN_Constraints.json")
    gold = os.path.join(base, "Golden_ALIGN_Constraints.json")
    return pred, gold


# -----------------------------------------------------------------------------
# Multi-run aggregation: walk Runs/* under a circuit and score every run found.
# The folder name IS the run_id (Run_001, Claude, Gemini, ...) — no parsing.
# -----------------------------------------------------------------------------

def _load_optional_json(path: str) -> Optional[Any]:
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _strip_score_for_aggregate(report_for_ctype: Dict[str, Any]) -> Dict[str, Any]:
    """Drop heavy debug fields (predicted_groups / false_*) from per-run scores
    to keep the aggregate file small. tp/fp/fn/precision/recall/f1 are kept."""
    return {
        k: report_for_ctype[k]
        for k in ("tp", "fp", "fn", "support", "precision", "recall", "f1")
    }


def collect_llm_metrics_for_run(run_dir: str) -> Dict[str, Any]:
    """Read per-stage llm_metrics.json files dropped by each agent.

    Looks for:
      <run_dir>/splitter/llm_metrics.json
      <run_dir>/constraints/Leaf_Constraints/llm_metrics.json   (adaptive — may be 0 calls)
      <run_dir>/constraints/system_level/llm_metrics.json

    Returns {"splitter": ..., "leaf_engine": ..., "bottom_up": ..., "totals": {...}}.
    Missing files yield None for that stage; totals sum across whatever was found.
    """
    splitter_metrics = _load_optional_json(
        os.path.join(run_dir, "splitter", "llm_metrics.json")
    )
    leaf_metrics = _load_optional_json(
        os.path.join(run_dir, "constraints", "Leaf_Constraints", "llm_metrics.json")
    )
    bottom_up_metrics = _load_optional_json(
        os.path.join(run_dir, "constraints", "system_level", "llm_metrics.json")
    )
    total_tokens = 0
    input_tokens = 0
    output_tokens = 0
    num_calls = 0
    for m in (splitter_metrics, leaf_metrics, bottom_up_metrics):
        if not isinstance(m, dict):
            continue
        total_tokens += int(m.get("total_tokens", 0) or 0)
        input_tokens += int(m.get("input_tokens", 0) or 0)
        output_tokens += int(m.get("output_tokens", 0) or 0)
        num_calls += int(m.get("num_llm_calls", m.get("num_calls", 0)) or 0)
    return {
        "splitter":    splitter_metrics,
        "leaf_engine": leaf_metrics,
        "bottom_up":   bottom_up_metrics,
        "totals": {
            "num_llm_calls": num_calls,
            "input_tokens":  input_tokens,
            "output_tokens": output_tokens,
            "total_tokens":  total_tokens,
        },
    }


def find_runs(parent_netlist_path: str) -> List[str]:
    """Return absolute paths of every directory under <parent_netlist_path>/Runs/.

    Folder name == run_id; no format assumed (Run_NNN, Claude, Gemini, etc.).
    """
    runs_dir = os.path.join(parent_netlist_path, "Runs")
    if not os.path.isdir(runs_dir):
        return []
    return sorted(
        os.path.join(runs_dir, name)
        for name in os.listdir(runs_dir)
        if os.path.isdir(os.path.join(runs_dir, name))
    )


def score_one_run(run_dir: str, gold_constraints: List[Dict[str, Any]]) -> Dict[str, Any]:
    run_id = os.path.basename(os.path.normpath(run_dir))
    pred_path = os.path.join(
        run_dir, "constraints", "system_level", "Final_ALIGN_Constraints.json"
    )
    if not os.path.isfile(pred_path):
        return {
            "run_id": run_id,
            "error": f"Final_ALIGN_Constraints.json not found at {pred_path}",
            "scores": None,
            "llm_metrics": collect_llm_metrics_for_run(run_dir),
        }

    pred = _load_json(pred_path)
    if not isinstance(pred, list):
        return {
            "run_id": run_id,
            "error": "predicted JSON is not a top-level list of constraints",
            "scores": None,
            "llm_metrics": collect_llm_metrics_for_run(run_dir),
        }

    full = score_final_align(pred, gold_constraints)
    scores = {ctype: _strip_score_for_aggregate(full[ctype]) for ctype in TRACKED_CONSTRAINTS}
    return {
        "run_id": run_id,
        "predicted_path": os.path.abspath(pred_path),
        "scores": scores,
        "llm_metrics": collect_llm_metrics_for_run(run_dir),
    }


def aggregate_circuit_runs(
    case: str,
    gold_path: Optional[str] = None,
    out_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Score every run under <case>/Runs/ against the case's golden constraints.

    Returns aggregate dict and (unless out_path is "" ) writes it to JSON.
    """
    parent_netlist_path = os.path.join(PROJECT_ROOT, "LLM_Agent_Codes", "netlists", case)
    if not os.path.isdir(parent_netlist_path):
        raise FileNotFoundError(f"Circuit folder not found: {parent_netlist_path}")

    if gold_path is None:
        candidates = [
            os.path.join(parent_netlist_path, "Input_Netlist", "Golden_ALIGN_Constraints.json"),
            os.path.join(parent_netlist_path, "Generated_Subcircuits", "Golden_ALIGN_Constraints.json"),
        ]
        gold_path = next((p for p in candidates if os.path.isfile(p)), None)
        if gold_path is None:
            raise FileNotFoundError(
                f"No Golden_ALIGN_Constraints.json found for case {case}. "
                f"Looked in: {candidates}"
            )

    gold = _load_json(gold_path)
    if not isinstance(gold, list):
        raise ValueError(f"Golden file is not a top-level list of constraints: {gold_path}")

    run_dirs = find_runs(parent_netlist_path)
    if not run_dirs:
        raise FileNotFoundError(
            f"No Runs/ subdirectories under {parent_netlist_path}/Runs/."
        )

    per_run_entries = [score_one_run(rd, gold) for rd in run_dirs]

    # Per-category lists so user can compute mean/std with one numpy call.
    summary: Dict[str, Dict[str, List[Any]]] = {
        ctype: {"f1": [], "precision": [], "recall": []} for ctype in TRACKED_CONSTRAINTS
    }
    token_summary = {"total_tokens_per_run": [], "num_calls_per_run": []}
    for entry in per_run_entries:
        if entry.get("scores") is None:
            continue
        for ctype in TRACKED_CONSTRAINTS:
            s = entry["scores"][ctype]
            summary[ctype]["f1"].append(s["f1"])
            summary[ctype]["precision"].append(s["precision"])
            summary[ctype]["recall"].append(s["recall"])
        totals = entry["llm_metrics"]["totals"]
        token_summary["total_tokens_per_run"].append(totals["total_tokens"])
        token_summary["num_calls_per_run"].append(totals["num_llm_calls"])

    aggregate = {
        "circuit": case,
        "golden_path": os.path.abspath(gold_path),
        "n_runs": len(per_run_entries),
        "run_ids": [e["run_id"] for e in per_run_entries],
        "runs": per_run_entries,
        "summary": summary,
        "token_summary": token_summary,
        "statistics": _compute_per_circuit_statistics(summary, token_summary),
    }

    if out_path is None:
        out_path = os.path.join(parent_netlist_path, "Aggregate_Scoreboard.json")
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(aggregate, f, indent=2)
        print(f"Aggregate scoreboard saved: {out_path}")
    return aggregate


def _mean_std(values: List[Any]) -> Tuple[Optional[float], Optional[float]]:
    """Mean and sample std of a list, ignoring None entries.

    Returns (None, None) if no valid values, (mean, None) if exactly one.
    """
    valid = [float(v) for v in values if v is not None]
    if not valid:
        return (None, None)
    if len(valid) == 1:
        return (valid[0], None)
    return (statistics.mean(valid), statistics.stdev(valid))


def _round_pair(p: Tuple[Optional[float], Optional[float]], digits: int) -> Tuple[Optional[float], Optional[float]]:
    m, s = p
    return (
        round(m, digits) if m is not None else None,
        round(s, digits) if s is not None else None,
    )


def _compute_per_circuit_statistics(
    summary: Dict[str, Dict[str, List[Any]]],
    token_summary: Dict[str, List[int]],
) -> Dict[str, Dict[str, Optional[float]]]:
    """Mean and std dev per category F1, plus tokens and call counts.

    Token / call zeros are dropped from their mean/std — they represent runs
    produced *before* the per-stage llm_metrics.json wiring existed (no real
    "0 LLM calls" case can occur: splitter + bottom-up always fire >=2 calls).
    F1 zeros are kept; a legitimate 0 F1 is a real prediction failure.
    """
    stats: Dict[str, Dict[str, Optional[float]]] = {}
    for ctype in TRACKED_CONSTRAINTS:
        f1_mean, f1_std = _round_pair(_mean_std(summary[ctype]["f1"]), 4)
        stats[ctype] = {"f1_mean": f1_mean, "f1_std": f1_std}

    tok_nonzero  = [v for v in token_summary["total_tokens_per_run"] if v]
    call_nonzero = [v for v in token_summary["num_calls_per_run"]    if v]
    tok_mean,  tok_std  = _round_pair(_mean_std(tok_nonzero),  1)
    call_mean, call_std = _round_pair(_mean_std(call_nonzero), 2)
    stats["tokens"] = {
        "total_tokens_mean": tok_mean,
        "total_tokens_std":  tok_std,
        "n_runs_with_data":  len(tok_nonzero),
    }
    stats["calls"] = {
        "num_llm_calls_mean": call_mean,
        "num_llm_calls_std":  call_std,
        "n_runs_with_data":   len(call_nonzero),
    }
    return stats


# -----------------------------------------------------------------------------
# Cross-circuit aggregation: macro-average per-circuit means.
# -----------------------------------------------------------------------------

def aggregate_across_circuits(
    cases: List[str],
    out_path: Optional[str] = None,
    rebuild: bool = False,
) -> Dict[str, Any]:
    """Compute macro mean ± std across a list of cases.

    For each case, ensures the per-circuit Aggregate_Scoreboard.json exists
    (rebuilds it from Runs/ if missing OR `rebuild=True`), then takes the
    *per-circuit f1_mean / tokens_mean / calls_mean* and computes their mean
    and std dev across cases.

    Each case contributes equally (macro average) — circuits with more
    constraints don't dominate the result.
    """
    if not cases:
        raise ValueError("Need at least one case.")

    per_circuit: List[Dict[str, Any]] = []
    for case in cases:
        case_dir = os.path.join(PROJECT_ROOT, "LLM_Agent_Codes", "netlists", case)
        agg_path = os.path.join(case_dir, "Aggregate_Scoreboard.json")
        if rebuild or not os.path.isfile(agg_path):
            print(f"[across-circuits] Building per-circuit aggregate for {case} ...")
            aggregate = aggregate_circuit_runs(case=case)
        else:
            aggregate = _load_json(agg_path)
        per_circuit.append({
            "case": case,
            "n_runs": aggregate.get("n_runs", 0),
            "statistics": aggregate.get("statistics", {}),
        })

    # Macro: list of per-circuit f1_means, then mean+std across them.
    macro: Dict[str, Dict[str, Optional[float]]] = {}
    for ctype in TRACKED_CONSTRAINTS:
        means = [p["statistics"].get(ctype, {}).get("f1_mean") for p in per_circuit]
        m, s = _round_pair(_mean_std(means), 4)
        macro[ctype] = {"f1_mean_macro": m, "f1_std_macro": s}

    tok_means = [p["statistics"].get("tokens", {}).get("total_tokens_mean") for p in per_circuit]
    m, s = _round_pair(_mean_std(tok_means), 1)
    macro["tokens"] = {"total_tokens_mean_macro": m, "total_tokens_std_macro": s}

    call_means = [p["statistics"].get("calls", {}).get("num_llm_calls_mean") for p in per_circuit]
    m, s = _round_pair(_mean_std(call_means), 2)
    macro["calls"] = {"num_llm_calls_mean_macro": m, "num_llm_calls_std_macro": s}

    result = {
        "cases": cases,
        "n_cases": len(cases),
        "per_circuit": per_circuit,
        "macro": macro,
    }

    if out_path is None:
        out_path = os.path.join(PROJECT_ROOT, "LLM_Agent_Codes", "netlists", "Cross_Circuit_Scoreboard.json")
    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"Cross-circuit scoreboard saved: {out_path}")
    return result


def pretty_print_cross_circuit(result: Dict[str, Any]) -> None:
    cases = result["cases"]
    print("=" * 96)
    print(f"Cross-circuit scoreboard — {len(cases)} circuits  (macro = mean of per-circuit means)")
    print("=" * 96)
    header = f"{'circuit':<28}" + "".join(f"{c+' F1':>22}" for c in TRACKED_CONSTRAINTS) + f"{'tokens':>14}{'calls':>9}"
    print(header)
    print("-" * len(header))
    for entry in result["per_circuit"]:
        st = entry["statistics"]
        row = f"{entry['case']:<28}"
        for c in TRACKED_CONSTRAINTS:
            m = st.get(c, {}).get("f1_mean")
            s = st.get(c, {}).get("f1_std")
            cell = "    N/A" if m is None else (
                f"{m:.4f}" if s is None else f"{m:.4f}±{s:.4f}"
            )
            row += f"{cell:>22}"
        tok_m = st.get("tokens", {}).get("total_tokens_mean")
        tok_s = st.get("tokens", {}).get("total_tokens_std")
        cl_m  = st.get("calls",  {}).get("num_llm_calls_mean")
        row += f"{'N/A' if tok_m is None else (f'{tok_m:.0f}' if tok_s is None else f'{tok_m:.0f}±{tok_s:.0f}'):>14}"
        row += f"{'N/A' if cl_m is None else f'{cl_m:.1f}':>9}"
        print(row)
    print("-" * len(header))
    # Macro row
    macro_row = f"{'MACRO (mean ± std)':<28}"
    for c in TRACKED_CONSTRAINTS:
        m = result["macro"][c]["f1_mean_macro"]
        s = result["macro"][c]["f1_std_macro"]
        cell = "    N/A" if m is None else (
            f"{m:.4f}" if s is None else f"{m:.4f}±{s:.4f}"
        )
        macro_row += f"{cell:>22}"
    tm = result["macro"]["tokens"]["total_tokens_mean_macro"]
    ts = result["macro"]["tokens"]["total_tokens_std_macro"]
    cm = result["macro"]["calls"]["num_llm_calls_mean_macro"]
    macro_row += f"{'N/A' if tm is None else (f'{tm:.0f}' if ts is None else f'{tm:.0f}±{ts:.0f}'):>14}"
    macro_row += f"{'N/A' if cm is None else f'{cm:.1f}':>9}"
    print(macro_row)
    print("=" * 96)


def pretty_print_aggregate(aggregate: Dict[str, Any]) -> None:
    print("=" * 96)
    print(f"Aggregate scoreboard — circuit: {aggregate['circuit']}  ({aggregate['n_runs']} runs)")
    print(f"  golden: {aggregate['golden_path']}")
    print("=" * 96)
    header = f"{'run_id':<18}" + "".join(f"{c+' F1':>20}" for c in TRACKED_CONSTRAINTS) + f"{'tokens':>10}{'calls':>7}"
    print(header)
    print("-" * len(header))
    for entry in aggregate["runs"]:
        if entry.get("scores") is None:
            print(f"{entry['run_id']:<18}  [error: {entry.get('error', 'unknown')}]")
            continue
        row = f"{entry['run_id']:<18}"
        for c in TRACKED_CONSTRAINTS:
            f1 = entry["scores"][c]["f1"]
            row += f"{'   N/A' if f1 is None else f'{f1:>20.4f}':>20}"
        totals = entry["llm_metrics"]["totals"]
        row += f"{totals['total_tokens']:>10}{totals['num_llm_calls']:>7}"
        print(row)
    # Mean ± std across runs
    stats = aggregate.get("statistics", {})
    summary_row = f"{'MEAN ± STD':<18}"
    for c in TRACKED_CONSTRAINTS:
        m = stats.get(c, {}).get("f1_mean")
        s = stats.get(c, {}).get("f1_std")
        cell = "    N/A" if m is None else (
            f"{m:.4f}" if s is None else f"{m:.4f}±{s:.4f}"
        )
        summary_row += f"{cell:>20}"
    tm = stats.get("tokens", {}).get("total_tokens_mean")
    ts = stats.get("tokens", {}).get("total_tokens_std")
    cm = stats.get("calls", {}).get("num_llm_calls_mean")
    summary_row += f"{'N/A' if tm is None else (f'{tm:.0f}' if ts is None else f'{tm:.0f}±{ts:.0f}'):>10}"
    summary_row += f"{'N/A' if cm is None else f'{cm:.1f}':>7}"
    print("-" * 96)
    print(summary_row)
    print("=" * 96)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", default=None, help="Circuit case (looks under LLM_Agent_Codes/netlists/<CASE>/)")
    parser.add_argument("--pred", default=None, help="Path to predicted Final_ALIGN_Constraints.json (overrides --case)")
    parser.add_argument("--gold", default=None, help="Path to Golden_ALIGN_Constraints.json (overrides --case)")
    parser.add_argument("--out", default=None, help="Override path for the JSON report")
    parser.add_argument("--no-save", action="store_true", help="Print the report only; do not write any JSON file.")
    parser.add_argument(
        "--all-runs",
        action="store_true",
        help="Walk <CASE>/Runs/* (any folder name — Run_001, Claude, Gemini, ...) "
             "and emit a single aggregate report. Per-run scores + LLM token "
             "totals are collected. Requires --case.",
    )
    parser.add_argument(
        "--across-circuits",
        default=None,
        help="Comma-separated list of cases (e.g. 'LDO_Simple,StrongArm_Latch_Comparator,OTAs/ota4'). "
             "Computes a macro mean ± std across each case's per-circuit means. "
             "Builds per-circuit Aggregate_Scoreboard.json on demand if missing.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="With --across-circuits: ignore cached per-circuit aggregates and rebuild them.",
    )
    args = parser.parse_args()

    # Cross-circuit aggregation mode.
    if args.across_circuits:
        cases = [c.strip() for c in args.across_circuits.split(",") if c.strip()]
        result = aggregate_across_circuits(
            cases=cases,
            out_path="" if args.no_save else args.out,
            rebuild=args.rebuild,
        )
        pretty_print_cross_circuit(result)
        return

    # Aggregation mode: walk every run folder for the case, score, collect.
    if args.all_runs:
        if not args.case:
            parser.error("--all-runs requires --case <CASE>.")
        aggregate = aggregate_circuit_runs(
            case=args.case,
            gold_path=args.gold,
            out_path="" if args.no_save else args.out,
        )
        pretty_print_aggregate(aggregate)
        return

    if args.pred and args.gold:
        pred_path, gold_path = args.pred, args.gold
    elif args.case:
        pred_path, gold_path = resolve_paths_from_case(args.case)
    else:
        parser.error("Provide either --case <CASE> or both --pred and --gold paths.")

    for label, path in (("predicted", pred_path), ("golden", gold_path)):
        if not os.path.exists(path):
            print(f"ERROR: {label} file does not exist: {path}", file=sys.stderr)
            sys.exit(2)

    pred_constraints = _load_json(pred_path)
    gold_constraints = _load_json(gold_path)
    if not isinstance(pred_constraints, list) or not isinstance(gold_constraints, list):
        print("ERROR: both predicted and golden JSON must be top-level arrays of constraints.", file=sys.stderr)
        sys.exit(2)

    report = score_final_align(pred_constraints, gold_constraints)
    # Stamp provenance so collected reports can be diff'd / aggregated later.
    report["_meta"] = {
        "predicted_path": os.path.abspath(pred_path),
        "golden_path": os.path.abspath(gold_path),
    }

    pretty_print_report(report, pred_path, gold_path)

    if not args.no_save:
        out_path = args.out or os.path.join(os.path.dirname(os.path.abspath(pred_path)), "Scoreboard_Report.json")
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved: {out_path}")


if __name__ == "__main__":
    main()
