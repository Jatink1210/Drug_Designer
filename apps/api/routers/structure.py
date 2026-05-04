"""Structure workbench API routes — RCSB-grade depth."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request
from routers.auth import get_current_user
from pydantic import BaseModel

from models.envelope import build_envelope as _shared_envelope
from connectors.uniprot import UniProtConnector
from services.structure_service import StructureService

router = APIRouter(prefix="/api/v1/structure", tags=["structure"], dependencies=[Depends(get_current_user)])

_svc = StructureService()

_THREE_TO_ONE = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLN": "Q",
    "GLU": "E",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
    "SEC": "U",
    "PYL": "O",
    "ASX": "B",
    "GLX": "Z",
    "UNK": "X",
}


class StructureCompareRequest(BaseModel):
    left_pdb_id: Optional[str] = None
    right_pdb_id: Optional[str] = None
    left_pdb_text: Optional[str] = None
    right_pdb_text: Optional[str] = None
    left_structure_url: Optional[str] = None
    right_structure_url: Optional[str] = None
    left_chain: Optional[str] = None
    right_chain: Optional[str] = None


def _normalize_chain(chain_id: Optional[str]) -> Optional[str]:
    if chain_id is None:
        return None
    normalized = chain_id.strip()
    return normalized or None


async def _load_structure_text(
    *,
    pdb_id: Optional[str] = None,
    pdb_text: Optional[str] = None,
    structure_url: Optional[str] = None,
) -> Tuple[str, str]:
    if pdb_text and pdb_text.strip():
        return pdb_text, "inline-model"

    if structure_url and structure_url.strip():
        body = await _svc._get(structure_url.strip())
        if isinstance(body, str) and body.strip():
            return body, structure_url.strip()
        raise HTTPException(status_code=400, detail=f"Unable to load structure text from '{structure_url}'")

    if pdb_id and pdb_id.strip():
        normalized = pdb_id.strip().upper()
        body = await _svc._get(f"https://files.rcsb.org/download/{normalized}.pdb")
        if isinstance(body, str) and body.strip():
            return body, normalized
        raise HTTPException(status_code=404, detail=f"Unable to fetch PDB structure '{normalized}'")

    raise HTTPException(
        status_code=400,
        detail="Each comparison side needs a PDB ID, structure URL, or inline PDB text",
    )


def _parse_ca_trace(pdb_text: str) -> Dict[str, List[Dict[str, Any]]]:
    chains: Dict[str, List[Dict[str, Any]]] = {}
    seen_residues: set[Tuple[str, str, str]] = set()

    for line in pdb_text.splitlines():
        if not line.startswith("ATOM") or len(line) < 54:
            continue
        if line[12:16].strip() != "CA":
            continue

        alt_loc = line[16].strip()
        if alt_loc not in ("", "A"):
            continue

        chain_id = line[21].strip() or "A"
        residue_number = line[22:26].strip()
        insertion_code = line[26].strip()
        residue_key = (chain_id, residue_number, insertion_code)
        if residue_key in seen_residues:
            continue
        seen_residues.add(residue_key)

        try:
            x_coord = float(line[30:38].strip())
            y_coord = float(line[38:46].strip())
            z_coord = float(line[46:54].strip())
        except ValueError:
            continue

        residue_name = line[17:20].strip().upper()
        chains.setdefault(chain_id, []).append(
            {
                "chain_id": chain_id,
                "residue_number": residue_number,
                "insertion_code": insertion_code,
                "residue_name": residue_name,
                "one_letter": _THREE_TO_ONE.get(residue_name, "X"),
                "coord": np.array([x_coord, y_coord, z_coord], dtype=float),
            }
        )

    return chains


def _align_sequences(seq1: str, seq2: str) -> Dict[str, Any]:
    if not seq1 or not seq2:
        return {
            "pairs": [],
            "matches": 0,
            "aligned_pairs": 0,
            "score": 0,
        }

    match_score = 2
    mismatch_penalty = -1
    gap_penalty = -1

    rows = len(seq1) + 1
    cols = len(seq2) + 1
    scores = [[0] * cols for _ in range(rows)]
    trace = [[0] * cols for _ in range(rows)]

    for row in range(1, rows):
        scores[row][0] = row * gap_penalty
        trace[row][0] = 1
    for col in range(1, cols):
        scores[0][col] = col * gap_penalty
        trace[0][col] = 2

    for row in range(1, rows):
        left_residue = seq1[row - 1]
        for col in range(1, cols):
            right_residue = seq2[col - 1]
            diag = scores[row - 1][col - 1] + (
                match_score if left_residue == right_residue else mismatch_penalty
            )
            up = scores[row - 1][col] + gap_penalty
            left = scores[row][col - 1] + gap_penalty
            best = max(diag, up, left)
            scores[row][col] = best
            trace[row][col] = 0 if best == diag else 1 if best == up else 2

    row = len(seq1)
    col = len(seq2)
    pairs: List[Tuple[int, int]] = []
    matches = 0
    while row > 0 or col > 0:
        move = trace[row][col] if row > 0 and col > 0 else 1 if row > 0 else 2
        if move == 0:
            row -= 1
            col -= 1
            pairs.append((row, col))
            if seq1[row] == seq2[col]:
                matches += 1
        elif move == 1:
            row -= 1
        else:
            col -= 1

    pairs.reverse()
    return {
        "pairs": pairs,
        "matches": matches,
        "aligned_pairs": len(pairs),
        "score": scores[-1][-1],
    }


def _select_chain_alignment(
    left_trace: Dict[str, List[Dict[str, Any]]],
    right_trace: Dict[str, List[Dict[str, Any]]],
    left_chain: Optional[str],
    right_chain: Optional[str],
) -> Dict[str, Any]:
    normalized_left_chain = _normalize_chain(left_chain)
    normalized_right_chain = _normalize_chain(right_chain)

    if normalized_left_chain and normalized_left_chain not in left_trace:
        raise HTTPException(status_code=400, detail=f"Left chain '{normalized_left_chain}' not found")
    if normalized_right_chain and normalized_right_chain not in right_trace:
        raise HTTPException(status_code=400, detail=f"Right chain '{normalized_right_chain}' not found")

    left_candidates = (
        [(normalized_left_chain, left_trace[normalized_left_chain])]
        if normalized_left_chain
        else list(left_trace.items())
    )
    right_candidates = (
        [(normalized_right_chain, right_trace[normalized_right_chain])]
        if normalized_right_chain
        else list(right_trace.items())
    )

    best: Optional[Dict[str, Any]] = None
    for left_id, left_residues in left_candidates:
        left_sequence = "".join(residue["one_letter"] for residue in left_residues)
        for right_id, right_residues in right_candidates:
            right_sequence = "".join(residue["one_letter"] for residue in right_residues)
            alignment = _align_sequences(left_sequence, right_sequence)
            aligned_pairs = alignment["aligned_pairs"]
            if aligned_pairs == 0:
                continue

            sequence_identity = alignment["matches"] / aligned_pairs
            candidate = {
                "left_chain": left_id,
                "right_chain": right_id,
                "left_residues": left_residues,
                "right_residues": right_residues,
                "pairs": alignment["pairs"],
                "matches": alignment["matches"],
                "aligned_pairs": aligned_pairs,
                "score": alignment["score"],
                "sequence_identity": sequence_identity,
            }

            if best is None:
                best = candidate
                continue

            if (
                candidate["matches"],
                candidate["aligned_pairs"],
                candidate["score"],
                candidate["sequence_identity"],
            ) > (
                best["matches"],
                best["aligned_pairs"],
                best["score"],
                best["sequence_identity"],
            ):
                best = candidate

    if best is None:
        raise HTTPException(status_code=400, detail="No comparable polymer chains with CA trace were found")
    if best["aligned_pairs"] < 3:
        raise HTTPException(status_code=400, detail="Need at least 3 aligned residues to compute RMSD")
    return best


def _compute_kabsch_rmsd(coords1: np.ndarray, coords2: np.ndarray) -> Dict[str, Any]:
    if coords1.shape != coords2.shape or coords1.shape[0] < 3:
        raise HTTPException(
            status_code=400,
            detail="Aligned coordinate sets must have the same length and at least 3 residues",
        )

    center1 = coords1.mean(axis=0)
    center2 = coords2.mean(axis=0)
    centered1 = coords1 - center1
    centered2 = coords2 - center2

    covariance = centered1.T @ centered2
    left_vectors, _, right_vectors_t = np.linalg.svd(covariance)
    correction = np.eye(3)
    if np.linalg.det(right_vectors_t.T @ left_vectors.T) < 0:
        correction[2, 2] = -1.0

    rotation = right_vectors_t.T @ correction @ left_vectors.T
    transformed = centered1 @ rotation
    diff = transformed - centered2
    rmsd = float(np.sqrt(np.mean(np.sum(diff * diff, axis=1))))
    translation = center2 - (center1 @ rotation)

    return {
        "rmsd": rmsd,
        "rotation": rotation.tolist(),
        "translation": translation.tolist(),
    }


async def _extract_alphafold_plddt(model_url: str) -> List[float]:
    """Parse per-residue pLDDT from AlphaFold PDB B-factor column."""
    if not model_url:
        return []

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(model_url)
        response.raise_for_status()

    residue_scores: List[float] = []
    seen_residues: set[tuple[str, str]] = set()
    for line in response.text.splitlines():
        if not line.startswith("ATOM") or len(line) < 66:
            continue
        chain_id = line[21].strip() or "A"
        residue_id = line[22:26].strip()
        residue_key = (chain_id, residue_id)
        if residue_key in seen_residues:
            continue
        seen_residues.add(residue_key)
        try:
            residue_scores.append(float(line[60:66].strip()))
        except ValueError:
            continue

    return residue_scores


async def _resolve_uniprot_entry(target_id: str) -> Optional[Dict[str, Any]]:
    connector = UniProtConnector()
    candidates = [target_id.strip()]
    try:
        search_hits = await connector.search(target_id, limit=1)
        if search_hits:
            resolved = search_hits[0].get("uniprot_id") or search_hits[0].get("id")
            if resolved:
                candidates.append(str(resolved))
    except Exception:
        pass

    seen: set[str] = set()
    async with httpx.AsyncClient(timeout=20.0) as client:
        for candidate in candidates:
            if not candidate:
                continue
            accession = candidate.upper()
            if accession in seen:
                continue
            seen.add(accession)
            response = await client.get(
                f"https://rest.uniprot.org/uniprotkb/{accession}.json",
                params={"fields": "accession,gene_names,organism_name,protein_name,sequence,xref_pdb"},
            )
            if response.status_code == 200:
                return response.json()
    return None


@router.get("/search", response_model=Dict[str, Any])
async def search_structures(request: Request, q: str = Query(...), limit: int = Query(25, le=100)) -> Dict[str, Any]:
    """Search RCSB PDB by text (protein name, disease, ligand, PDB ID)."""
    result = await _svc.search_structures(q, limit)
    return _build_envelope(request, result)


@router.post("/compare", response_model=Dict[str, Any])
async def compare_structures(req: StructureCompareRequest, request: Request) -> Dict[str, Any]:
    """Compute a sequence-guided CA alignment and backbone RMSD for two structures."""
    left_text, left_label = await _load_structure_text(
        pdb_id=req.left_pdb_id,
        pdb_text=req.left_pdb_text,
        structure_url=req.left_structure_url,
    )
    right_text, right_label = await _load_structure_text(
        pdb_id=req.right_pdb_id,
        pdb_text=req.right_pdb_text,
        structure_url=req.right_structure_url,
    )

    left_trace = _parse_ca_trace(left_text)
    right_trace = _parse_ca_trace(right_text)
    if not left_trace:
        raise HTTPException(status_code=400, detail="Left structure has no protein CA trace in PDB format")
    if not right_trace:
        raise HTTPException(status_code=400, detail="Right structure has no protein CA trace in PDB format")

    alignment = _select_chain_alignment(left_trace, right_trace, req.left_chain, req.right_chain)
    left_residues = alignment["left_residues"]
    right_residues = alignment["right_residues"]
    aligned_pairs = alignment["pairs"]

    left_coords = np.array([left_residues[left_index]["coord"] for left_index, _ in aligned_pairs], dtype=float)
    right_coords = np.array([right_residues[right_index]["coord"] for _, right_index in aligned_pairs], dtype=float)
    fit = _compute_kabsch_rmsd(left_coords, right_coords)

    left_aligned = [left_residues[left_index] for left_index, _ in aligned_pairs]
    right_aligned = [right_residues[right_index] for _, right_index in aligned_pairs]
    warnings = [
        "RMSD uses CA backbone atoms from the best-matching chain pair after global sequence alignment",
    ]
    return _build_envelope(
        request,
        {
            "left_label": left_label,
            "right_label": right_label,
            "left_chain": alignment["left_chain"],
            "right_chain": alignment["right_chain"],
            "left_selection": f":{alignment['left_chain']}",
            "right_selection": f":{alignment['right_chain']}",
            "aligned_residues": alignment["aligned_pairs"],
            "matching_residues": alignment["matches"],
            "sequence_identity": alignment["sequence_identity"],
            "coverage_left": alignment["aligned_pairs"] / max(len(left_residues), 1),
            "coverage_right": alignment["aligned_pairs"] / max(len(right_residues), 1),
            "left_chain_length": len(left_residues),
            "right_chain_length": len(right_residues),
            "left_residue_range": f"{left_aligned[0]['residue_number']}-{left_aligned[-1]['residue_number']}",
            "right_residue_range": f"{right_aligned[0]['residue_number']}-{right_aligned[-1]['residue_number']}",
            "rmsd": fit["rmsd"],
            "rotation": fit["rotation"],
            "translation": fit["translation"],
        },
        warnings=warnings,
    )


@router.get("/{pdb_id}", response_model=Dict[str, Any])
async def get_structure(pdb_id: str, request: Request) -> Dict[str, Any]:
    """Full structure summary: classification, organism, method, R-factors, assemblies, chains, ligands, downloads."""
    summary = await _svc.get_structure_summary(pdb_id)
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    return _build_envelope(request, summary)


@router.get("/{pdb_id}/annotations", response_model=Dict[str, Any])
async def get_annotations(pdb_id: str, request: Request) -> Dict[str, Any]:
    """Annotations: Pfam, InterPro, GO terms, EC numbers, PTMs."""
    data = await _svc.get_annotations(pdb_id)
    return _build_envelope(request, data)


@router.get("/{pdb_id}/experiment", response_model=Dict[str, Any])
async def get_experiment(pdb_id: str, request: Request) -> Dict[str, Any]:
    """Experiment details: data collection, refinement, crystal parameters, software."""
    data = await _svc.get_experiment(pdb_id)
    return _build_envelope(request, data)


@router.get("/{pdb_id}/sequence", response_model=Dict[str, Any])
async def get_sequences(pdb_id: str, request: Request) -> Dict[str, Any]:
    """Per-chain sequences with feature tracks."""
    data = await _svc.get_sequences(pdb_id)
    return _build_envelope(request, data)


@router.get("/alphafold/{uniprot_id}", response_model=Dict[str, Any])
async def get_alphafold(uniprot_id: str, request: Request) -> Dict[str, Any]:
    """AlphaFold predicted structure by UniProt ID."""
    result = await _svc.get_alphafold(uniprot_id)
    if not result:
        raise HTTPException(status_code=404, detail="AlphaFold prediction not found for %s" % uniprot_id)
    return _build_envelope(request, result)


@router.get("/predict/{target_id}", response_model=Dict[str, Any])
async def get_predicted_structure(target_id: str, request: Request) -> Dict[str, Any]:
    """Resolve predicted structure using ESM first, then AlphaFold, then RCSB."""
    warnings: List[str] = []
    uniprot_entry = await _resolve_uniprot_entry(target_id)
    uniprot_id = target_id.strip().upper()
    sequence = ""
    title = target_id
    organism = ""
    gene_symbol = ""

    if uniprot_entry:
        uniprot_id = str(uniprot_entry.get("primaryAccession") or uniprot_id)
        sequence = str((uniprot_entry.get("sequence") or {}).get("value") or "")
        title = (
            uniprot_entry.get("proteinDescription", {})
            .get("recommendedName", {})
            .get("fullName", {})
            .get("value", title)
        )
        organism = str((uniprot_entry.get("organism") or {}).get("scientificName") or "")
        genes = uniprot_entry.get("genes") or []
        gene_symbol = str(genes[0].get("geneName", {}).get("value") or "") if genes else ""
    else:
        warnings.append(f"No UniProt sequence resolved for {target_id}; skipping ESM fold")

    if sequence:
        try:
            from services.ml.esm3_client import get_esm3_client

            folded = await get_esm3_client().fold_sequence(sequence=sequence, protein_id=uniprot_id)
            return _build_envelope(
                request,
                {
                    "source": "esm3",
                    "fallback_chain": ["esm3", "alphafold", "rcsb"],
                    "target_id": target_id,
                    "uniprot_id": uniprot_id,
                    "title": title,
                    "organism": organism,
                    "gene_symbol": gene_symbol,
                    "sequence": sequence,
                    "sequence_length": len(sequence),
                    **folded,
                    "downloads": {},
                    "url": f"https://www.uniprot.org/uniprotkb/{uniprot_id}",
                },
                warnings=warnings or None,
            )
        except Exception as exc:
            warnings.append(f"ESM prediction unavailable: {str(exc)[:120]}")

    if uniprot_id:
        try:
            alphafold = await _svc.get_alphafold(uniprot_id)
            if alphafold:
                plddt: List[float] = []
                model_url = str(alphafold.get("model_url") or "")
                if model_url:
                    try:
                        plddt = await _extract_alphafold_plddt(model_url)
                    except Exception as exc:
                        warnings.append(f"AlphaFold pLDDT parsing unavailable: {str(exc)[:120]}")
                return _build_envelope(
                    request,
                    {
                        "source": "alphafold",
                        "fallback_chain": ["esm3", "alphafold", "rcsb"],
                        "target_id": target_id,
                        "title": title,
                        "organism": organism,
                        "gene_symbol": gene_symbol,
                        "sequence_length": len(sequence) or None,
                        "sequence": sequence,
                        "plddt": plddt,
                        **alphafold,
                    },
                    warnings=warnings or None,
                )
        except Exception as exc:
            warnings.append(f"AlphaFold prediction unavailable: {str(exc)[:120]}")

    try:
        rcsb_hits = await _svc.search_structures(target_id, limit=1)
        candidate_hits = []
        if isinstance(rcsb_hits, dict):
            candidate_hits = rcsb_hits.get("results") or rcsb_hits.get("result_set") or []
        resolved_pdb = ""
        if candidate_hits:
            first = candidate_hits[0]
            resolved_pdb = str(first.get("identifier") or first.get("id") or "")
        if resolved_pdb:
            summary = await _svc.get_structure_summary(resolved_pdb)
            if "error" not in summary:
                return _build_envelope(
                    request,
                    {
                        "source": "rcsb",
                        "fallback_chain": ["esm3", "alphafold", "rcsb"],
                        "resolved_pdb_id": resolved_pdb,
                        **summary,
                    },
                    warnings=warnings or None,
                )
    except Exception as exc:
        warnings.append(f"RCSB fallback unavailable: {str(exc)[:120]}")

    raise HTTPException(status_code=404, detail=f"No predicted or experimental structure found for '{target_id}'")

class DockingRequest(BaseModel):
    protein_pdb: str
    ligand_smiles: str

@router.post("/mirofish_dock", response_model=Dict[str, Any])
async def mirofish_docking(req: DockingRequest, request: Request) -> Dict[str, Any]:
    """Execute combinatorial docking strictly matching 666ghj/MiroFish logical mapping."""
    from services.structure.mirofish_pipeline import MiroFishDockingOrchestrator
    orchestrator = MiroFishDockingOrchestrator()
    mol = orchestrator.parse_smiles_to_mol(req.ligand_smiles)
    res = await orchestrator.execute_blind_docking(req.protein_pdb, mol)
    return _build_envelope(request, res)

class SequenceRequest(BaseModel):
    sequence: str

@router.post("/ssd_evaluate", response_model=Dict[str, Any])
async def evaluate_sequence_ssd(req: SequenceRequest, request: Request) -> Dict[str, Any]:
    """Execute state-space sequence modeling strictly matching tanishqkumar/ssd logic."""
    from services.models.ssd_state_space import StateSpaceSequenceModel
    ssd = StateSpaceSequenceModel()
    res = ssd.process_protein_sequence(req.sequence)
    return _build_envelope(request, res)

def _build_envelope(req: Request, data: Any, warnings: list = None) -> Dict[str, Any]:
    return _shared_envelope(req, data, warnings=warnings)


@router.get("/by-target/{target_id}", response_model=Dict[str, Any])
async def get_structure_by_target(target_id: str, request: Request) -> Dict[str, Any]:
    """§126: Resolve a target identifier (UniProt, gene symbol) → associated PDB structures.

    Returns a list of PDB IDs & summaries matching the target so the
    caller does not need to know the PDB ID upfront.
    """
    warnings: List[str] = []
    structures: List[Dict[str, Any]] = []

    # Try RCSB text search
    try:
        rcsb_hits = await _svc.search_structures(target_id, limit=10)
        if isinstance(rcsb_hits, dict):
            for item in rcsb_hits.get("results", []):
                structures.append(item)
    except Exception as exc:
        warnings.append(f"RCSB search failed: {str(exc)[:80]}")

    # Try AlphaFold (assumes UniProt ID)
    try:
        af_result = await _svc.get_alphafold(target_id)
        if af_result:
            structures.append({"source": "alphafold", "uniprot_id": target_id, **af_result})
    except Exception:
        pass  # AlphaFold may not have this target — not a warning

    if not structures:
        raise HTTPException(status_code=404, detail=f"No structures found for target '{target_id}'")

    return _build_envelope(request, {
        "target_id": target_id,
        "structures": structures,
        "total": len(structures),
    }, warnings=warnings if warnings else None)


@router.get("/{target_id}/pockets", response_model=Dict[str, Any])
async def get_target_pockets(target_id: str, request: Request) -> Dict[str, Any]:
    """§126: GET /api/v1/structure/{targetId}/pockets — Binding pocket predictions."""
    pockets = []
    warnings = []
    try:
        from connectors.alphafold import AlphaFoldConnector
        af = AlphaFoldConnector()
        af_results = await af.search(target_id, limit=1)
        if af_results:
            for entry in af_results:
                pockets.append({
                    "source": "alphafold",
                    "pdb_id": entry.get("id", ""),
                    "confidence": entry.get("confidence", 0),
                })
    except Exception as exc:
        warnings.append(f"AlphaFold lookup failed: {str(exc)[:80]}")
    try:
        from connectors.rcsb import RCSBConnector
        rcsb = RCSBConnector()
        rcsb_results = await rcsb.search(target_id, limit=3)
        for entry in rcsb_results:
            pockets.append({
                "source": "rcsb",
                "pdb_id": entry.get("id", ""),
                "title": entry.get("title", ""),
            })
    except Exception as exc:
        warnings.append(f"RCSB lookup failed: {str(exc)[:80]}")
    return _build_envelope(request, {
        "target_id": target_id,
        "pockets": pockets,
        "method": "alphafold+rcsb",
    }, warnings=warnings if warnings else None)
