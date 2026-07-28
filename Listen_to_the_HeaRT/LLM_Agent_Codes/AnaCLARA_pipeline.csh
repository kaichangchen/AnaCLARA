#!/bin/csh -f
# AnaCLARA full-pipeline driver — sourceable from csh.
#
# Usage (from csh) — CASE is REQUIRED. Must match whichever block is
# uncommented in each agent's main(), otherwise the scoreboard aggregates the
# wrong circuit:
#   source AnaCLARA_pipeline.csh <N_RUNS> <CASE>
#   source AnaCLARA_pipeline.csh 4 StrongArm_Latch_Comparator
#   source AnaCLARA_pipeline.csh 10 Hysteritic_Comp
#
# For each iteration: splitter -> hierarchy -> system_level.
# After all iterations: scoreboard aggregates every run under <case>/Runs/.
#
# On failure, the loop breaks (does NOT call `exit`, so your shell stays alive
# when sourced). Variables are unset at the end so they don't pollute your env.

# ---- arg parsing ----------------------------------------------------------
if ($#argv < 2) then
    echo "ERROR: missing arguments."
    echo "Usage: source AnaCLARA_pipeline.csh <N_RUNS> <CASE>"
    echo "  e.g.: source AnaCLARA_pipeline.csh 4 StrongArm_Latch_Comparator"
    # Don't exit when sourced; just unset vars and bail out.
    goto cleanup
endif

set N_RUNS = $1
set CASE = "$2"

# Hardcoded absolute path so source works regardless of cwd.
set AGENTS_DIR = /home/scratch.souradipp_vlsi/MLCAD/AnaCLARA_Framework/Listen_to_the_HeaRT/LLM_Agent_Codes

# ---- pipeline -------------------------------------------------------------
echo "================================================================"
echo "AnaCLARA pipeline:  case=$CASE   iterations=$N_RUNS"
echo "================================================================"

set ANACLARA_FAILED = 0
@ i = 1
while ($i <= $N_RUNS)
    echo ""
    echo "######## Iteration $i / $N_RUNS ########"

    echo "==> [1/3] Splitter"
    python $AGENTS_DIR/agents/analytical_splitter_agent.py
    if ($status != 0) then
        echo "Splitter failed (status $status); stopping pipeline."
        set ANACLARA_FAILED = 1
        break
    endif

    echo "==> [2/3] Hierarchy"
    python $AGENTS_DIR/agents/hierarchy_agent.py
    if ($status != 0) then
        echo "Hierarchy failed (status $status); stopping pipeline."
        set ANACLARA_FAILED = 1
        break
    endif

    echo "==> [3/3] System-level"
    python $AGENTS_DIR/agents/system_level_structural_analysis_agent_Ablation.py
    if ($status != 0) then
        echo "System-level failed (status $status); stopping pipeline."
        set ANACLARA_FAILED = 1
        break
    endif

    @ i++
end

if ($ANACLARA_FAILED == 0) then
    echo ""
    echo "================================================================"
    echo "All $N_RUNS iterations complete. Aggregating scoreboard..."
    echo "================================================================"
    python $AGENTS_DIR/agents/scoreboard.py --case "$CASE" --all-runs
    echo ""
    echo "Done."
endif

# ---- clean up vars so sourcing doesn't pollute your shell ----------------
cleanup:
unset N_RUNS CASE AGENTS_DIR ANACLARA_FAILED i
