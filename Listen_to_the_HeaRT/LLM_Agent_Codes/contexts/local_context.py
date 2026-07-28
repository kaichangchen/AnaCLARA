# contexts/local_context.py
import json
import datetime


class LocalContext:
    """
    Per-agent memory for compressed reasoning.
    Stores summaries across reasoning rounds (shallow + iterative refinement).
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.summaries = []  # list of structured dicts
        self.timestamps = []  # optional time tracking

    def add_summary(self, summary: dict):
        """
        Add a structured summary from a reasoning round.
        """
        timestamp = datetime.datetime.utcnow().isoformat()
        self.summaries.append(summary)
        self.timestamps.append(timestamp)

    def latest_summary(self) -> dict:
        """
        Return the most recent summary, or empty dict if none.
        """
        return self.summaries[-1] if self.summaries else {}

    def compress_for_global(self) -> dict:
        """
        Export a lightweight version of the latest summary for global use.
        Strips raw details but keeps important keys fromt the JSON.
        Also summarizes the role of the agent? (present system prompt)
        """
        if not self.summaries:
            return {}

        last = self.summaries[-1]

        return {
            "agent_name": self.agent_name,
            "agent_role_hint": self.system_prompt[
                :200
            ],  # More intelligent compression needed?
            "subcircuit_id": last.get("subcircuit_id", ""),
            "behavior": last.get("subcircuit_behavior", ""),
            "class": last.get("subcircuit_class", ""),
            "ports": last.get("ports", {}),
            "high_impedance_nodes_summary": last.get(
                "high_impedance_nodes_summary", {}
            ),
            "parasitic_effects_summary": last.get("parasitic_effects_summary", ""),
            "behavioral_parameters": last.get("behavioral_parameters", ""),
            "small_signal_analysis_summary": last.get(
                "small_signal_analysis_summary", ""
            ),
            "overall_component_level_behavior_summary": last.get(
                "overall_component_level_behavior_summary", ""
            ),
            "design_cautionary_notes": last.get("design_cautionary_notes", ""),
            "performance": last.get("performance_metric_impact", ""),
        }

    def export_history(self, as_json: bool = False):
        """
        Return all summaries (with timestamps).
        Useful for audit trail or debugging.
        """
        history = [
            {"timestamp": t, "summary": s}
            for t, s in zip(self.timestamps, self.summaries)
        ]
        return json.dumps(history, indent=2) if as_json else history

    def save_to_file(self, filepath: str) -> None:
        """
        Save all summaries with timestamps to a JSON file.
        """
        with open(filepath, "w") as f:
            f.write(self.export_history(as_json=True))

    def load_from_file(self, filepath: str) -> None:
        try:
            with open(filepath, "r") as f:
                history = json.load(f)

            # Clear existing data
            self.summaries = []
            self.timestamps = []

            # Load the data assuming the file contains a list of {"timestamp": ..., "summary": ...}
            for entry in history:
                self.timestamps.append(entry.get("timestamp", ""))
                self.summaries.append(entry.get("summary", {}))
        except Exception as e:
            raise RuntimeError(
                f"Failed to load local context from file {filepath}: {e}"
            )
