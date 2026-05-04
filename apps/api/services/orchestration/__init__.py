"""Autonomous Run Orchestrator — Subsystem 3 (Drug Designer §23, §41).

Absorbs patterns from symphony. Manages the complete lifecycle of
scientific runs: CREATED → QUEUED → RUNNING → [SUCCESS | PARTIAL | FAILED].
Every run is persistent, evented, and replayable.
"""
