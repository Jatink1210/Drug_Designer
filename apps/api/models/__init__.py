"""Drug Designer — Pydantic Data Models.

This package contains the shared data vocabulary used across all
modules, subsystems, routers, and services.

Core contracts:
  - envelope.py   — Universal Response Envelope (§78)
  - run.py        — Run & Job state machines (§41)
  - evidence.py   — Evidence Items & Bundles (§94.2)
  - target.py     — Target Ranking (§94.3)
  - disease.py    — Disease Intelligence pipeline (§B1)
  - project.py    — Project & Memory (§A7)
  - source.py     — Source & Connector Health (§62)
  - dossier.py    — Dossier, Report, Export (§A10)
  - runtime.py    — Runtime & Local Agent (§34)
  - graph.py      — Graph & Pathway (§82)
  - specialist.py — Specialist Roles & MAV Consensus (§22)
  - scenario.py   — SynthArena Scenarios & DAG Planner (§43)
  - entities.py   — Canonical biomedical entity schemas
  - user.py       — SQLAlchemy User & Project ORM models
"""
