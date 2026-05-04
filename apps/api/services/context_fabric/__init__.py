"""Context Fabric — Subsystem 1 (Drug Designer §21, §39).

Provides the 3-tier memory system that spans all 44 modules:
  L1 — Session (Redis): Ephemeral context within a user session
  L2 — Semantic (Qdrant): Evidence embeddings, run results, graph snapshots
  L3 — Archive (S3/MinIO): Bulk outputs (PDFs, ZIP exports, large dossiers)

Origin: Absorbs patterns from OpenViking (context DB) adapted for
scientific projects and evidence bundles.
"""
