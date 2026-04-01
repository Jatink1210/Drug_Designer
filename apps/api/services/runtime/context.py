"""Hierarchical Context Database (Inspired by OpenViking).

Organizes an agent's context (private memories, public resources, skills) like
a virtual file system to enable Tiered Context Loading.
This prevents the need to load large amounts of irrelevant information into
the agent's context window, mimicking L0 (Abstract), L1 (Overview), and L2 (Details).
"""

import json
import os
import time
from typing import Dict, Any, List

from core.paths import get_data_dir

class ContextFileSystem:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.context_root = os.path.join(get_data_dir(), "viking_context", run_id)
        os.makedirs(self.context_root, exist_ok=True)
        # Initialize basic filesystem structure
        for d in ["L0_Abstract", "L1_Overview", "L2_Details"]:
            os.makedirs(os.path.join(self.context_root, d), exist_ok=True)

    def _path(self, layer: str, fname: str) -> str:
        return os.path.join(self.context_root, layer, fname)

    def save_memory(self, layer: str, filename: str, content: Dict[str, Any]):
        """Save an explicit memory dictionary to a specific context layer."""
        if layer not in ["L0_Abstract", "L1_Overview", "L2_Details"]:
            raise ValueError("Invalid layer. Must be L0_Abstract, L1_Overview, or L2_Details")
            
        with open(self._path(layer, filename), "w") as f:
            json.dump({"updated_at": time.time(), "data": content}, f, indent=2)

    def load_context_window(self, max_l2_items: int = 2) -> Dict[str, Any]:
        """Load context, prioritizing L0 and L1, and fetching limited L2 data.
        
        This mimics Tiered Context Loading to save token costs during long agent runs.
        """
        window = {
            "abstract": {},
            "overview": {},
            "details_sample": {}
        }
        
        # Load all L0
        for f in os.listdir(os.path.join(self.context_root, "L0_Abstract")):
            with open(self._path("L0_Abstract", f)) as p:
                window["abstract"][f] = json.load(p)["data"]
                
        # Load all L1
        for f in os.listdir(os.path.join(self.context_root, "L1_Overview")):
            with open(self._path("L1_Overview", f)) as p:
                window["overview"][f] = json.load(p)["data"]

        # Load limited L2
        l2_files = os.listdir(os.path.join(self.context_root, "L2_Details"))
        for f in l2_files[:max_l2_items]:
            with open(self._path("L2_Details", f)) as p:
                window["details_sample"][f] = json.load(p)["data"]
                
        return window

    def evolve_brain(self):
        """Analyze past interactions and summarize L1/L2 data into L0 abstract memory."""
        # Simulated self-evolution
        l1_summaries = []
        for f in os.listdir(os.path.join(self.context_root, "L1_Overview")):
            with open(self._path("L1_Overview", f)) as p:
                data = json.load(p)["data"]
                l1_summaries.append(f"Reviewed {f}: {len(str(data))} bytes of memory.")
                
        if l1_summaries:
            self.save_memory("L0_Abstract", "evolved_traits.json", {
                "insights": "Synthesized past interactions.",
                "details": l1_summaries
            })
