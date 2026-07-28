#!/usr/bin/env bash
# AnaCLARA full-pipeline driver.
#
# For each iteration:
#   1) Splitter         (creates a fresh Runs/Run_NNN+1/splitter/)
#   2) Hierarchy        (fills  Runs/Run_NNN/hierarchy/  — picks oldest pending)
#   3) System-level     (fills  Runs/Run_NNN/constraints/ — picks oldest pending)
#
# After all iterations:
#   4) Scoreboard       (aggregates EVERY run under <case>/Runs/ into
#                        <case>/Aggregate_Scoreboard.json)
#
#
# Usage (CASE is REQUIRED — must match whichever block is uncommented in
# each agent's main(), otherwise the scoreboard aggregates the wrong circuit):
#   ./AnaCLARA_pipeline.sh <N_RUNS> <CASE>
#   ./AnaCLARA_pipeline.sh 4 StrongArm_Latch_Comparator
#   ./AnaCLARA_pipeline.sh 10 Hysteritic_Comp
#   MPLBACKEND=Agg ./AnaCLARA_pipeline.sh 5 LDO_Simple      # suppress matplotlib popups

set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "ERROR: missing arguments." >&2
    echo "Usage: $0 <N_RUNS> <CASE>" >&2
    echo "  e.g.: $0 4 StrongArm_Latch_Comparator" >&2
    exit 2
fi

N_RUNS="$1"
CASE="$2"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================================"
echo "AnaCLARA pipeline:  case=$CASE   iterations=$N_RUNS"
echo "================================================================"

for ((i = 1; i <= N_RUNS; i++)); do
    echo
    echo "######## Iteration $i / $N_RUNS ########"

    echo "==> [1/3] Splitter"
    python agents/analytical_splitter_agent.py

    echo "==> [2/3] Hierarchy"
    python agents/hierarchy_agent.py

    echo "==> [3/3] System-level"
    python agents/system_level_structural_analysis_agent_Ablation.py
done

echo
echo "================================================================"
echo "All $N_RUNS iterations complete. Aggregating scoreboard..."
echo "================================================================"
python agents/scoreboard.py --case "$CASE" --all-runs

echo
echo "✓ AnaCLARA pipeline complete for case: $CASE  ($N_RUNS runs)"
