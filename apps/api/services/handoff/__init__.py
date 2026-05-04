"""Workflow Handoff Layer — Subsystem 6 (Drug Designer §26).

Manages baton-passing between specialists and modules. When Disease
Intelligence completes, it hands off to Target Prioritization.
When a Target is selected, it hands off to Design Studio. Etc.

Every handoff preserves full provenance and run linkage.
"""
