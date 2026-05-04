"""Symphony re-export — bridges main.py import to core.py implementation."""

from services.agency.core import SymphonyOrchestrator

# Alias expected by main.py (§29 Integration Map)
UniversalSymphony = SymphonyOrchestrator

__all__ = ["UniversalSymphony", "SymphonyOrchestrator"]
