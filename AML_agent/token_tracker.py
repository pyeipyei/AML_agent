"""
Token usage tracker for the AML pipeline.

Accumulates token counts from extraction and screening events,
then serialises them into a structured JSON file.
"""

import json
import os


class TokenTracker:
    """Tracks token usage across files, agents, and the full pipeline."""

    def __init__(self):
        # {filename: {"extraction_agent": str,
        #             "extraction_input_tokens": int, ...
        #             "entities_screened": int,
        #             "screening_input_tokens": int, ...}}
        self._files: dict[str, dict] = {}

        # {agent_name: {"input_tokens": int, "output_tokens": int, "total_tokens": int}}
        self._agents: dict[str, dict] = {}

        # pipeline-level grand totals
        self._pipeline = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_file(self, filename: str) -> dict:
        if filename not in self._files:
            self._files[filename] = {
                "extraction_agent": "",
                "extraction_input_tokens": 0,
                "extraction_output_tokens": 0,
                "extraction_total_tokens": 0,
                "entities_screened": 0,
                "screening_input_tokens": 0,
                "screening_output_tokens": 0,
                "screening_total_tokens": 0,
            }
        return self._files[filename]

    def _ensure_agent(self, agent_name: str) -> dict:
        if agent_name not in self._agents:
            self._agents[agent_name] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }
        return self._agents[agent_name]

    # ------------------------------------------------------------------
    # Public recording methods
    # ------------------------------------------------------------------

    def record_extraction(
        self,
        filename: str,
        agent_name: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
    ) -> None:
        """Accumulate tokens produced by an extraction agent for *filename*."""
        entry = self._ensure_file(filename)
        entry["extraction_agent"] = agent_name
        entry["extraction_input_tokens"] += input_tokens
        entry["extraction_output_tokens"] += output_tokens
        entry["extraction_total_tokens"] += total_tokens

        agent = self._ensure_agent(agent_name)
        agent["input_tokens"] += input_tokens
        agent["output_tokens"] += output_tokens
        agent["total_tokens"] += total_tokens

        self._pipeline["input_tokens"] += input_tokens
        self._pipeline["output_tokens"] += output_tokens
        self._pipeline["total_tokens"] += total_tokens

    def record_screening(
        self,
        filename: str,
        agent_name: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        entities_screened: int = 0,
    ) -> None:
        """Accumulate tokens produced by a screening agent for *filename*."""
        entry = self._ensure_file(filename)
        entry["screening_input_tokens"] += input_tokens
        entry["screening_output_tokens"] += output_tokens
        entry["screening_total_tokens"] += total_tokens
        entry["entities_screened"] += entities_screened

        agent = self._ensure_agent(agent_name)
        agent["input_tokens"] += input_tokens
        agent["output_tokens"] += output_tokens
        agent["total_tokens"] += total_tokens

        self._pipeline["input_tokens"] += input_tokens
        self._pipeline["output_tokens"] += output_tokens
        self._pipeline["total_tokens"] += total_tokens

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return the tracker state in the target JSON shape."""
        files_list = []
        for fname, data in self._files.items():
            files_list.append({
                "file_name": fname,
                "extraction_agent": data["extraction_agent"],
                "extraction_input_tokens": data["extraction_input_tokens"],
                "extraction_output_tokens": data["extraction_output_tokens"],
                "extraction_total_tokens": data["extraction_total_tokens"],
                "entities_screened": data["entities_screened"],
                "screening_input_tokens": data["screening_input_tokens"],
                "screening_output_tokens": data["screening_output_tokens"],
                "screening_total_tokens": data["screening_total_tokens"],
                "combined_input_tokens": (
                    data["extraction_input_tokens"]
                    + data["screening_input_tokens"]
                ),
                "combined_output_tokens": (
                    data["extraction_output_tokens"]
                    + data["screening_output_tokens"]
                ),
                "combined_total_tokens": (
                    data["extraction_total_tokens"]
                    + data["screening_total_tokens"]
                ),
            })

        agents_list = [
            {"agent_name": name, **totals}
            for name, totals in self._agents.items()
        ]

        return {
            "files": files_list,
            "agents": agents_list,
            "pipeline": dict(self._pipeline),
        }

    def save(self, path: str) -> None:
        """Write the token-usage JSON to *path*."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"Token usage saved to {path}")
