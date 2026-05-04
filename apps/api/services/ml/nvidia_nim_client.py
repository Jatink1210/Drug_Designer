"""NVIDIA NIM Biology — Async Client for Drug Design Endpoints.

Typed access to three NVIDIA cloud-hosted NIM microservices:
  1. MolMIM  — Latent-variable controlled molecule generation
  2. GenMol  — Masked-diffusion fragment-based de-novo design
  3. DiffDock — Blind molecular docking pose prediction

Cloud gateway: https://integrate.api.nvidia.com/v1
Auth: NVIDIA_NIM_API_KEY env var (nvapi-* token from .env)

Requirements: httpx, pydantic>=2
"""

from __future__ import annotations

import asyncio
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import structlog
from pydantic import BaseModel, Field, field_validator

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NIM_BASE = "https://integrate.api.nvidia.com/v1"
_TIMEOUT = 120.0
_MAX_RETRIES = 3
_BACKOFF = 2.0

_MOLMIM_MODEL = "nvidia/molmim"
_GENMOL_MODEL = "nvidia/genmol"
_DIFFDOCK_MODEL = "nvidia/diffdock"

# ---------------------------------------------------------------------------
# Pydantic I/O — MolMIM
# ---------------------------------------------------------------------------

class MolMIMScoring(str, Enum):
    QED = "QED"
    LOGP = "logP"
    TPSA = "tPSA"
    NONE = "None"

class MolMIMGenerateIn(BaseModel):
    smiles: str = Field(..., min_length=1)
    num_molecules: int = Field(10, ge=1, le=1000)
    algorithm: str = "CMA-ES"
    property_name: MolMIMScoring = MolMIMScoring.QED
    min_similarity: float = Field(0.3, ge=0.0, le=1.0)
    iterations: int = Field(10, ge=1, le=200)

    @field_validator("smiles")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("SMILES empty")
        return v

class MolMIMEmbedIn(BaseModel):
    smiles: str = Field(..., min_length=1)

class MolMIMDecodeIn(BaseModel):
    hidden: List[float] = Field(..., min_length=1)

class MolMIMHit(BaseModel):
    smiles: str
    score: Optional[float] = None
    similarity: Optional[float] = None

class MolMIMGenerateOut(BaseModel):
    molecules: List[MolMIMHit] = []
    seed_smiles: str = ""
    model: str = _MOLMIM_MODEL

class MolMIMEmbedOut(BaseModel):
    embedding: List[float] = []
    smiles: str = ""
    model: str = _MOLMIM_MODEL

# ---------------------------------------------------------------------------
# Pydantic I/O — GenMol
# ---------------------------------------------------------------------------

class GenMolGenerateIn(BaseModel):
    smiles: str = Field(..., min_length=1, description="SMILES/SAFE with [MASK] tokens")
    num_molecules: int = Field(10, ge=1, le=1000)
    temperature: float = Field(1.0, ge=0.01, le=5.0)
    noise: float = Field(0.0, ge=0.0, le=1.0)
    step_size: int = Field(1, ge=1, le=100)
    scoring: str = "QED"

class GenMolHit(BaseModel):
    smiles: str
    score: Optional[float] = None

class GenMolGenerateOut(BaseModel):
    molecules: List[GenMolHit] = []
    template_smiles: str = ""
    model: str = _GENMOL_MODEL

# ---------------------------------------------------------------------------
# Pydantic I/O — DiffDock
# ---------------------------------------------------------------------------

class DiffDockIn(BaseModel):
    ligand_smiles: str = Field(..., min_length=1)
    protein_pdb_path: Optional[str] = None
    protein_pdb_content: Optional[str] = None
    num_poses: int = Field(10, ge=1, le=100)
    time_divisor: int = Field(2, ge=1, le=10)
    steps: int = Field(18, ge=1, le=100)

    @field_validator("protein_pdb_path")
    @classmethod
    def _chk_path(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            p = Path(v)
            if not p.exists():
                raise ValueError(f"PDB not found: {v}")
            if p.suffix.lower() not in (".pdb", ".ent"):
                raise ValueError(f"Expected .pdb, got {p.suffix}")
        return v

class DiffDockPose(BaseModel):
    pose_id: int = 0
    confidence: float = 0.0
    ligand_sdf: str = ""

class DiffDockOut(BaseModel):
    poses: List[DiffDockPose] = []
    ligand_smiles: str = ""
    model: str = _DIFFDOCK_MODEL

# ---------------------------------------------------------------------------
# Key resolver
# ---------------------------------------------------------------------------

def _resolve_key() -> str:
    key = os.environ.get("NVIDIA_NIM_API_KEY", "")
    if not key:
        raise RuntimeError(
            "NVIDIA_NIM_API_KEY not set. Add to .env. "
            "Get from https://build.nvidia.com/"
        )
    return key

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class NvidiaNIMClient:
    """Async client for NVIDIA NIM Biology cloud endpoints.

    Example::
        client = NvidiaNIMClient()
        out = await client.molmim_generate(MolMIMGenerateIn(smiles="CCO"))
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = _NIM_BASE,
        timeout: float = _TIMEOUT,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

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
                    log.warning("nim_5xx", path=path, code=r.status_code, attempt=attempt)
                    last = httpx.HTTPStatusError(
                        f"Server {r.status_code}", request=r.request, response=r,
                    )
                    await asyncio.sleep(_BACKOFF ** attempt)
                    continue
                r.raise_for_status()
                return r.json()
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                log.warning("nim_net_err", path=path, err=str(exc), attempt=attempt)
                last = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(_BACKOFF ** attempt)
        raise RuntimeError(
            f"NIM {path} failed after {self._max_retries} retries"
        ) from last

    # == MolMIM ===========================================================

    async def molmim_generate(self, req: MolMIMGenerateIn) -> MolMIMGenerateOut:
        """Generate molecules via MolMIM latent-space optimisation."""
        payload = {
            "smiles": req.smiles,
            "num_molecules": req.num_molecules,
            "algorithm": req.algorithm,
            "property_name": req.property_name.value,
            "min_similarity": req.min_similarity,
            "iterations": req.iterations,
        }
        log.info("molmim_gen", seed=req.smiles[:40], n=req.num_molecules)
        data = await self._post("/biology/nvidia/molmim/generate", payload)
        hits = [
            MolMIMHit(smiles=m.get("smiles", ""), score=m.get("score"), similarity=m.get("similarity"))
            for m in data.get("molecules", data.get("results", []))
        ]
        return MolMIMGenerateOut(molecules=hits, seed_smiles=req.smiles)

    async def molmim_embed(self, req: MolMIMEmbedIn) -> MolMIMEmbedOut:
        """Get latent embedding for a molecule."""
        data = await self._post("/biology/nvidia/molmim/embedding", {"smiles": req.smiles})
        return MolMIMEmbedOut(embedding=data.get("embedding", []), smiles=req.smiles)

    async def molmim_decode(self, req: MolMIMDecodeIn) -> str:
        """Decode latent vector → SMILES."""
        data = await self._post("/biology/nvidia/molmim/decode", {"hidden": req.hidden})
        return data.get("smiles", "")

    # == GenMol ============================================================

    async def genmol_generate(self, req: GenMolGenerateIn) -> GenMolGenerateOut:
        """Fragment-based masked-diffusion molecule generation."""
        payload = {
            "smiles": req.smiles,
            "num_molecules": req.num_molecules,
            "temperature": req.temperature,
            "noise": req.noise,
            "step_size": req.step_size,
            "scoring": req.scoring,
        }
        log.info("genmol_gen", tpl=req.smiles[:40], n=req.num_molecules)
        data = await self._post("/biology/nvidia/genmol/generate", payload)
        hits = [
            GenMolHit(smiles=m.get("smiles", ""), score=m.get("score"))
            for m in data.get("molecules", data.get("results", []))
        ]
        return GenMolGenerateOut(molecules=hits, template_smiles=req.smiles)

    # == DiffDock ===========================================================

    async def diffdock_dock(self, req: DiffDockIn) -> DiffDockOut:
        """Blind molecular docking via DiffDock.

        Supply protein via ``protein_pdb_path`` or ``protein_pdb_content``.
        """
        pdb = req.protein_pdb_content
        if pdb is None and req.protein_pdb_path:
            pdb = Path(req.protein_pdb_path).read_text(encoding="utf-8")
        if not pdb:
            raise ValueError("Provide protein_pdb_path or protein_pdb_content")

        payload = {
            "ligand": req.ligand_smiles,
            "ligand_file_type": "smiles",
            "protein": pdb,
            "num_poses": req.num_poses,
            "time_divisor": req.time_divisor,
            "steps": req.steps,
        }
        log.info("diffdock_start", lig=req.ligand_smiles[:40], poses=req.num_poses)
        data = await self._post("/biology/nvidia/diffdock/generate", payload)
        poses = [
            DiffDockPose(
                pose_id=i,
                confidence=p.get("confidence", p.get("score", 0.0)),
                ligand_sdf=p.get("ligand", p.get("sdf", "")),
            )
            for i, p in enumerate(data.get("poses", data.get("results", [])))
        ]
        return DiffDockOut(poses=poses, ligand_smiles=req.ligand_smiles)

    # == health ============================================================

    async def health_check(self) -> Dict[str, Any]:
        try:
            c = await self._ensure()
            r = await c.get("/v1/health/ready")
            return {"status": "ok" if r.is_success else "degraded", "code": r.status_code}
        except Exception as exc:
            log.warning("nim_health_fail", err=str(exc))
            return {"status": "unreachable", "error": str(exc)}

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[NvidiaNIMClient] = None

def get_nvidia_nim_client(*, api_key: Optional[str] = None) -> NvidiaNIMClient:
    """Return (or create) module-level NIM singleton."""
    global _instance
    if _instance is None:
        _instance = NvidiaNIMClient(api_key=api_key)
    return _instance
