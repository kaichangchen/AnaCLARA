import os
import requests
import re


def decide_simulation_targets_and_analyses(
    subcircuit, subcircuit_summary: dict
) -> dict:
    """
    Decide which nodes/branches/loops to probe.
    And for each analysis type determine the specific subcircuits,
    LLM based

    The returned dictionary format can be:
    {
        "nodes_to_check": ["INP", "INN", "OUT", "TAIL"],   # General nodes to probe
        "<analysis_type_1>": {                              # e.g. "dc_op"
            "subcircuits_to_check": ["subckt1", "subckt2"],
            "branches_to_check": ["branch1", "branch2"],
            "loops_to_check": ["loop1->loop2", "loop3->loop4"]
        },
        "<analysis_type_2>": {                              # e.g. "ac_gain"
            "subcircuits_to_check": [...],
            "branches_to_check": [...],
            "loops_to_check": [...]
        },
        ...
        example analyses in SPICE: "dc", "ac_gain" (small signal), "trans" meanign transient, "psrr", "cmrr", "noise" etc
    """

    return {"nodes_to_check": [], "analyses": {}}


def infer_nominal_device_sizes(
    subcircuit, subcircuit_summary: dict, pdk_info: dict
) -> dict:
    """
    Extract the List of all Design Variables in the Given netlist.
    Infer nominal W/L values or bias conditions based on context, in order to be able to run meaningful simulations
    Will need some PDK information or working examples for guidance.
    Example return:
    {"M1": {"W": "2u", "L": "120n"}, "M2": {"W": "2u", "L": "120n"}}
    """
    return {}


def create_testbench(
    subcircuit_summary: dict, analyses: list, device_sizes: dict
) -> str:
    """
    Generate a SPICE testbench netlist (or Verilog-A wrapper).
    Reuse base TB templates if available.
    Return: filename or netlist string.
    """
    # Feel free to use Verilog-A based simulations.
    return "generated_tb.sp"


def run_simulations(testbench_file: str) -> dict:
    """
    Call the simulator (e.g. Spectre, NgSpice, Xyce) and return waveforms and trends  and raw results.
    Example return:
    {"ac_gain": 72.5, "phase_margin": 58.2, "iq": 120e-6}
    """
    # Feel free to use Verilog-A based simulations.
    return {}


def iterative_refinement_infer_trends_and_simulation_grounding(
    subcircuit, subcircuit_reasoning_summary_compressed: dict, known_RAG_database: dict
) -> dict:
    """
    Compare simulation results and trends with the reasoning-based summary to validate consistency.
    """
    # Step 1: Intelligently plan targets and required analyses to justify the inferred reasoning summary:
    # decide_simulation_targets_and_analyses(subcircuit, subcircuit_reasoning_summary_compressed: dict) # LLM Based

    # Step 2: Use RAG knowledge database to reduce the number of required simulations and select most important few. Keep the small signal and transient sims. # LLM Based

    # Step 3: Infer nominal device sizes based on subcircuit and pdk info
    # Until all checklist of checks (like AnalogCoder) and operating points checks and headroom checks pass, keep repeating this step:
    ##### infer_nominal_device_sizes(subcircuit, subcircuit_reasoning_summary_compressed: dict, pdk_info: dict) # LLM Based

    # Step 4: Now create the corresponding test benches for the above targets and analyses and then run simulatiosn and give the output
    # create_testbench(subcircuit_reasoning_summary_compressed: dict, analyses: list, device_sizes: dict) # LLM Based: Using some templates
    # run_simulations and export waveforms and trends and results

    # Step 5: Use an LLM Agent to infer the simulation trends and verify if the reasoning aligns with the simulations. If not, debug and resolve, give preference to simulation-proven trends and RAG database stored.
    # During the debug, during conflicts, we can call the low level agents (branch level agents) and use them to resolve conflicts by detailed reasoning using bottom-up for the conflicts.
    return {}


def analytical_guided_LLM_reasoning_based_splitter(subcircuit):
    """
    Returns properly structured subcircuit.sp files which will also be the names of the blocks, like "cmfb", "core", "bias", "branch..." which we can pass to the subcircuit level agent
    """
    return {}


def extract_device_names(circuit_netlist):
    all_device_types = ["nmos", "pmos", "res", "cap"]
    device_vars = {}
    lines = circuit_netlist.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("*"):  # skip comments and blank lines
            continue

        # Start after the .subckt and end before the .ends

        # First token is device name if it starts with typical device prefix (example: m, r, c, d, q, x etc.)
        # Here, assume devices start with letter followed by digits (e.g., m0, r12)
        m = re.match(r"^([a-zA-Z]\w*)\s+(.+)", line)
        if m:
            device_name = m.group(1)
            rest = m.group(2)

            device_type = ""

            for dev_typ in all_device_types:
                if dev_typ in rest:
                    device_type = dev_typ
                    break

            # find parameter assignments of type var=value
            # This will capture all param names
            params = re.findall(r"(\b\w+)\s*=", rest)
            if device_name not in device_vars:
                device_vars[device_name] = {
                    "device_type": "",
                    "design_variables": set(),
                }
            device_vars[device_name]["design_variables"].update(params)
            device_vars[device_name]["device_type"] = device_type

    # Convert all sets to lists for JSON serialization or easier handling downstream
    device_vars_listified = {
        k: {
            "device_type": v["device_type"],
            "design_variables": list(v["design_variables"]),
        }
        for k, v in device_vars.items()
    }

    return device_vars_listified
