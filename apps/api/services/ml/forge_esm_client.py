"""EvolutionaryScale Forge API — Unified ESM-C / ESM-3 Async Client.

Two capabilities via the Forge REST gateway:
  1. ESM-C (esmc-6b-2024-12) — rapid sequence embeddings + variant effect
     prediction (VEP / log-likelihood scoring).
  2. ESM-3 (esm3-large-2024-08) — multimodal generation: accepts sequence
     and structure constraints to produce novel protein backbones.

Structural outputs (PDB files) are persisted to ``apps/api/data/files/``
and the client returns the absolute file path.

Auth: ESM_FORGE_API_KEY env var (Forge token from .env).
Requirements: httpx, pydantic>=2
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import structlog
from pydantic import BaseModel, Field, field_validator

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FORGE_BASE = "https://forge.evolutionaryscale.ai"
_ESMC_MODEL = "esmc-6b-2024-12"
_ESM3_MODEL = "esm3-large-2024-08"
_TIMEOUT = 180.0
_MAX_RETRIES = 3
_BACKOFF = 2.0

# Output directory for structure files
_DATA_FILES_DIR = Path(__file__).resolve().parents[2] / "data" / "files"

# ---------------------------------------------------------------------------
# Pydantic I/O — ESM-C
# ---------------------------------------------------------------------------

class ESMCEmbedIn(BaseModel):
    """Input for ESM-C sequence embedding."""
    sequence: str = Field(..., min_length=1, description="Amino acid sequence (1-letter).")
    protein_id: Optional[str] = Field(None, description="Tracking ID for provenance.")

    @field_validator("sequence")
    @classmethod
    def _sanitize(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("Sequence empty")
        invalid = set(v) - set("ACDEFGHIKLMNPQRSTVWY_X")
        if invalid:
            raise ValueError(f"Invalid amino acid chars: {invalid}")
        return v

class ESMCEmbedOut(BaseModel):
    """Output for ESM-C embedding."""
    embedding: List[float] = []
    embedding_dim: int = 0
    sequence_length: int = 0
    model: str = _ESMC_MODEL
    protein_id: Optional[str] = None

class ESMCVariantIn(BaseModel):
    """Input for ESM-C variant effect prediction (log-likelihood scoring)."""
    sequence: str = Field(..., min_length=1, description="Wild-type sequence.")
    variants: List[str] = Field(
        ...,
        min_length=1,
        description="Variants in 'A123G' notation (1-indexed).",
    )
    protein_id: Optional[str] = None

    @field_validator("sequence")
    @classmethod
    def _sanitize_seq(cls, v: str) -> str:
        return v.strip().upper()

class VariantScore(BaseModel):
    variant: str
    delta_ll: float = 0.0  # negative = deleterious
    wt_ll: float = 0.0
    mt_ll: float = 0.0

class ESMCVariantOut(BaseModel):
    scores: List[VariantScore] = []
    model: str = _ESMC_MODEL
    protein_id: Optional[str] = None

# ---------------------------------------------------------------------------
# Pydantic I/O — ESM-3
# ---------------------------------------------------------------------------

class ESM3GenerateIn(BaseModel):
    """Input for ESM-3 multimodal protein generation."""
    partial_sequence: Optional[str] = Field(
        None,
        description="Partial sequence with '_' mask tokens for positions to generate.",
    )
    structure_conditioning_pdb: Optional[str] = Field(
        None,
        description="Path to a PDB file whose backbone is used as structural constraint.",
    )
    num_steps: int = Field(8, ge=1, le=64)
    temperature: float = Field(0.7, ge=0.01, le=2.0)
    track: str = Field("sequence", description="Generation track: sequence | structure | both")
    project_id: Optional[str] = None
    run_id: Optional[str] = None

class ESM3GenerateOut(BaseModel):
    """Output for ESM-3 generation."""
    sequence: str = ""
    confidence: float = 0.0
    per_residue_confidence: List[float] = []
    pdb_file_path: Optional[str] = None  # absolute path if structure generated
    model: str = _ESM3_MODEL
    num_steps: int = 0
    temperature: float = 0.0
    provenance: Dict[str, Any] = {}

class ESM3FoldIn(BaseModel):
    """Input for ESM-3 structure prediction."""
    sequence: str = Field(..., min_length=1)
    protein_id: Optional[str] = None

class ESM3FoldOut(BaseModel):
    """Output for ESM-3 folding."""
    pdb_file_path: str = ""  # absolute path to saved PDB
    plddt: List[float] = []
    ptm: float = 0.0
    sequence_length: int = 0
    model: str = _ESM3_MODEL

# ---------------------------------------------------------------------------
# Key resolver
# ---------------------------------------------------------------------------

def _resolve_key() -> str:
    key = os.environ.get("ESM_FORGE_API_KEY", "")
    if not key:
        raise RuntimeError(
            "ESM_FORGE_API_KEY not set. Add to .env. "
            "Get from https://forge.evolutionaryscale.ai"
        )
    return key

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class ForgeESMClient:
    """Async client for EvolutionaryScale Forge (ESM-C + ESM-3).

    Example::
        client = ForgeESMClient()
        emb = await client.esmc_embed(ESMCEmbedIn(sequence="MKTAYIAKQR"))
        gen = await client.esm3_generate(ESM3GenerateIn(partial_sequence="MKTA____QR"))
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = _FORGE_BASE,
        timeout: float = _TIMEOUT,
        max_retries: int = _MAX_RETRIES,
        output_dir: Optional[Path] = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._output_dir = output_dir or _DATA_FILES_DIR
        self._client: Optional[httpx.AsyncClient] = None
        # Ensure output dir exists
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # -- lifecycle --------------------------------------------------------

    async def _ensure(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            key = self._api_key or _resolve_key()
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=httpx.Timeout(self._timeout, connect=30.0),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # -- retry wrapper ----------------------------------------------------

    async def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        client = await self._ensure()
        last: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                r = await client.post(path, json=body)
                if r.status_code >= 500:
                    log.warning("forge_5xx", path=path, code=r.status_code, attempt=attempt)
                    last = httpx.HTTPStatusError(
                        f"Server {r.status_code}", request=r.request, response=r,
                    )
                    await asyncio.sleep(_BACKOFF ** attempt)
                    continue
                r.raise_for_status()
                return r.json()
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                log.warning("forge_net_err", path=path, err=str(exc), attempt=attempt)
                last = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(_BACKOFF ** attempt)
        raise RuntimeError(
            f"Forge {path} failed after {self._max_retries} retries"
        ) from last

    # -- file persistence -------------------------------------------------

    def _save_pdb(self, content: str, prefix: str = "esm") -> str:
        """Write PDB string to data/files/ and return absolute path."""
        fname = f"{prefix}_{uuid.uuid4().hex[:12]}.pdb"
        out = self._output_dir / fname
        out.write_text(content, encoding="utf-8")
        abs_path = str(out.resolve())
        log.info("pdb_saved", path=abs_path, size=len(content))
        return abs_path

    # =====================================================================
    # ESM-C: Embeddings
    # =====================================================================

    async def esmc_embed(self, req: ESMCEmbedIn) -> ESMCEmbedOut:
        """Generate ESM-C sequence embedding (high-dim per-residue → mean-pooled)."""
        data = await self._post(
            f"/api/v1/models/{_ESMC_MODEL}/encode",
            {"sequence": req.sequence},
        )
        emb = data.get("embedding", data.get("embeddings", []))
        # API may return per-residue [L, D] or already pooled [D]
        if emb and isinstance(emb[0], list):
            # Mean-pool over residue dimension
            import numpy as np
            arr = np.array(emb, dtype=float)
            emb = arr.mean(axis=0).tolist()
        dim = len(emb) if emb else 0
        log.info("esmc_embed_done", pid=req.protein_id, dim=dim)
        return ESMCEmbedOut(
            embedding=emb,
            embedding_dim=dim,
            sequence_length=len(req.sequence),
            protein_id=req.protein_id,
        )

    # =====================================================================
    # ESM-C: Variant Effect Prediction
    # =====================================================================

    async def esmc_variant_effect(self, req: ESMCVariantIn) -> ESMCVariantOut:
        """Score variants via ESM-C log-likelihood ratio (delta_ll < 0 = deleterious)."""
        data = await self._post(
            f"/api/v1/models/{_ESMC_MODEL}/loglikelihood",
            {"sequence": req.sequence, "variants": req.variants},
        )
        scores = []
        for v in data.get("scores", data.get("results", [])):
            scores.append(
                VariantScore(
                    variant=v.get("variant", ""),
                    delta_ll=v.get("delta_ll", v.get("delta_log_likelihood", 0.0)),
                    wt_ll=v.get("wt_ll", 0.0),
                    mt_ll=v.get("mt_ll", 0.0),
                )
            )
        log.info("esmc_vep_done", pid=req.protein_id, n=len(scores))
        return ESMCVariantOut(scores=scores, protein_id=req.protein_id)

    # =====================================================================
    # ESM-3: Multimodal Generation
    # =====================================================================

    async def esm3_generate(self, req: ESM3GenerateIn) -> ESM3GenerateOut:
        """Generate novel protein via ESM-3 iterative decoding.

        Accepts partial sequence (with '_' masks) and optional structural
        conditioning.  Structure outputs saved to data/files/.
        """
        body: Dict[str, Any] = {
            "num_steps": req.num_steps,
            "temperature": req.temperature,
            "track": req.track,
        }
        if req.partial_sequence:
            body["sequence"] = req.partial_sequence
        if req.structure_conditioning_pdb:
            pdb_path = Path(req.structure_conditioning_pdb)
            if not pdb_path.exists():
                raise FileNotFoundError(f"Conditioning PDB not found: {pdb_path}")
            body["structure_pdb"] = pdb_path.read_text(encoding="utf-8")

        log.info(
            "esm3_gen_start",
            seq_len=len(req.partial_sequence or ""),
            steps=req.num_steps,
            track=req.track,
        )
        data = await self._post(
            f"/api/v1/models/{_ESM3_MODEL}/generate", body
        )

        sequence = data.get("sequence", "")
        confidence = data.get("confidence", data.get("ptm", 0.0))
        per_res = data.get("per_residue_confidence", data.get("plddt", []))

        # Persist structure if returned
        pdb_path_out: Optional[str] = None
        pdb_str = data.get("pdb", data.get("structure_pdb", ""))
        if pdb_str:
            pdb_path_out = self._save_pdb(pdb_str, prefix="esm3_gen")

        log.info(
            "esm3_gen_done",
            seq_len=len(sequence),
            conf=round(confidence, 4),
            has_structure=bool(pdb_path_out),
        )
        return ESM3GenerateOut(
            sequence=sequence,
            confidence=round(confidence, 4),
            per_residue_confidence=per_res,
            pdb_file_path=pdb_path_out,
            num_steps=req.num_steps,
            temperature=req.temperature,
            provenance={
                "source": "forge_esm3",
                "model": _ESM3_MODEL,
                "project_id": req.project_id,
                "run_id": req.run_id,
                "track": req.track,
            },
        )

    # =====================================================================
    # ESM-3: Structure Prediction (Fold)
    # =====================================================================

    async def esm3_fold(self, req: ESM3FoldIn) -> ESM3FoldOut:
        """Predict 3D structure from sequence via ESM-3. Saves PDB locally."""
        data = await self._post(
            f"/api/v1/models/{_ESM3_MODEL}/generate",
            {"sequence": req.sequence, "track": "structure", "num_steps": 8},
        )
        pdb_str = data.get("pdb", data.get("structure_pdb", ""))
        pdb_path = ""
        if pdb_str:
            pdb_path = self._save_pdb(pdb_str, prefix="esm3_fold")

        plddt = data.get("plddt", [])
        ptm = data.get("ptm", 0.0)

        log.info("esm3_fold_done", pid=req.protein_id, ptm=round(ptm, 4))
        return ESM3FoldOut(
            pdb_file_path=pdb_path,
            plddt=plddt,
            ptm=round(ptm, 4),
            sequence_length=len(req.sequence),
        )

    # =====================================================================
    # Health
    # =====================================================================

    async def health_check(self) -> Dict[str, Any]:
        try:
            c = await self._ensure()
            r = await c.get("/api/v1/health")
            return {"status": "ok" if r.is_success else "degraded", "code": r.status_code}
        except Exception as exc:
            log.warning("forge_health_fail", err=str(exc))
            return {"status": "unreachable", "error": str(exc)}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[ForgeESMClient] = None

def get_forge_esm_client(*, api_key: Optional[str] = None) -> ForgeESMClient:
    """Return (or create) module-level Forge ESM singleton."""
    global _instance
    if _instance is None:
        _instance = ForgeESMClient(api_key=api_key)
    return _instance
