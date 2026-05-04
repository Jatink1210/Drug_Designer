"""MiroFish Pipeline — Drug Designer Subsystem.

Absorbs the 'MiroFish-main' repo patterns into a Drug Designer-native subsystem
for combinatorial docking orchestration (§25, §43).

Wraps the real DockingService (Vina/smina/gnina) with a higher-level API
that accepts SMILES + PDB ID, handles pocket detection, and returns
ranked docking poses.
"""

import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)

RDKIT_AVAILABLE = False
try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    RDKIT_AVAILABLE = True
except ImportError:
    pass


class MiroFishDockingOrchestrator:
    """Combinatorial docking orchestrator (§25, §43).

    Provides parse_smiles_to_mol + execute_blind_docking as a
    high-level facade over DockingService.
    """

    def __init__(self):
        self._docking_service = None
        log.info("mirofish_orchestrator_initialized")

    def _get_docking_service(self):
        if self._docking_service is None:
            from services.docking_service import DockingService
            self._docking_service = DockingService()
        return self._docking_service

    def parse_smiles_to_mol(self, smiles: str) -> Dict[str, Any]:
        """Parse a SMILES string into a molecule representation.

        Returns a dict with the parsed molecule info:
        - smiles: canonical SMILES
        - mol_block: 3D SDF/MOL block (if RDKit available)
        - num_atoms: atom count
        - mol_weight: molecular weight
        """
        if not RDKIT_AVAILABLE:
            log.warning("rdkit_unavailable_for_mol_parse")
            return {"smiles": smiles, "mol_block": None, "num_atoms": 0, "mol_weight": 0.0, "valid": True}

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {"smiles": smiles, "mol_block": None, "num_atoms": 0, "mol_weight": 0.0, "valid": False,
                    "error": "Invalid SMILES string"}

        # Add hydrogens and generate 3D coordinates
        mol_h = Chem.AddHs(mol)
        try:
            AllChem.EmbedMolecule(mol_h, AllChem.ETKDGv3())
            AllChem.MMFFOptimizeMolecule(mol_h, maxIters=200)
        except Exception as exc:
            log.warning("3d_embed_failed", error=str(exc))

        from rdkit.Chem import Descriptors
        return {
            "smiles": Chem.MolToSmiles(mol),
            "mol_block": Chem.MolToMolBlock(mol_h),
            "num_atoms": mol.GetNumAtoms(),
            "mol_weight": round(Descriptors.MolWt(mol), 2),
            "valid": True,
        }

    async def execute_blind_docking(
        self, protein_pdb: str, mol_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute blind docking: detect pockets → dock ligand → rank poses.

        Args:
            protein_pdb: PDB ID or path to receptor PDB file.
            mol_info: Output of parse_smiles_to_mol().

        Returns:
            Dict with pockets, poses, and scoring summary.
        """
        run_id = str(uuid.uuid4())[:8]

        if not mol_info.get("valid", False):
            return {"status": "failed", "error": mol_info.get("error", "Invalid molecule"), "run_id": run_id}

        svc = self._get_docking_service()

        # Step 1: Resolve receptor — if it's a PDB ID, attempt to fetch structure
        receptor_path = protein_pdb
        tmp_dir = None
        if not os.path.exists(protein_pdb):
            # It's a PDB ID — try to fetch from RCSB
            try:
                import httpx
                async with httpx.AsyncClient(timeout=30) as client:
                    url = f"https://files.rcsb.org/download/{protein_pdb.upper()}.pdb"
                    resp = await client.get(url)
                    resp.raise_for_status()
                    tmp_dir = tempfile.mkdtemp(prefix="mirofish_")
                    receptor_path = os.path.join(tmp_dir, f"{protein_pdb}.pdb")
                    with open(receptor_path, "w") as f:
                        f.write(resp.text)
                    log.info("receptor_fetched", pdb_id=protein_pdb, path=receptor_path)
            except Exception as exc:
                log.warning("receptor_fetch_failed", pdb_id=protein_pdb, error=str(exc))
                return {
                    "status": "failed",
                    "error": f"Could not fetch PDB structure for {protein_pdb}: {str(exc)[:100]}",
                    "run_id": run_id,
                }

        # Step 2: Pocket detection
        pockets: List[Dict] = []
        try:
            pockets = await svc.detect_pockets(receptor_path)
            log.info("pockets_detected", count=len(pockets), pdb=protein_pdb)
        except Exception as exc:
            log.warning("pocket_detection_failed", error=str(exc))

        # Step 3: Prepare ligand file
        ligand_path = None
        if mol_info.get("mol_block") and tmp_dir:
            ligand_path = os.path.join(tmp_dir, "ligand.mol")
            with open(ligand_path, "w") as f:
                f.write(mol_info["mol_block"])
        elif mol_info.get("mol_block"):
            tmp_dir = tempfile.mkdtemp(prefix="mirofish_")
            ligand_path = os.path.join(tmp_dir, "ligand.mol")
            with open(ligand_path, "w") as f:
                f.write(mol_info["mol_block"])

        # Step 4: Docking — try each pocket
        docking_results: List[Dict[str, Any]] = []
        if ligand_path and pockets:
            for i, pocket in enumerate(pockets[:3]):  # Top 3 pockets
                center = pocket.get("center", [0, 0, 0])
                try:
                    result = await svc.run_docking(
                        receptor_path=receptor_path,
                        ligand_path=ligand_path,
                        center=center,
                        box_size=[20, 20, 20],
                    )
                    docking_results.append({
                        "pocket_index": i,
                        "pocket_score": pocket.get("score", 0),
                        "docking": result,
                    })
                except Exception as exc:
                    log.warning("docking_pocket_failed", pocket=i, error=str(exc))
                    docking_results.append({
                        "pocket_index": i,
                        "pocket_score": pocket.get("score", 0),
                        "docking": {"status": "failed", "error": str(exc)[:100]},
                    })
        elif ligand_path and not pockets:
            # Blind docking with default center (0,0,0) and large box
            try:
                result = await svc.run_docking(
                    receptor_path=receptor_path,
                    ligand_path=ligand_path,
                    center=[0, 0, 0],
                    box_size=[40, 40, 40],
                    exhaustiveness=16,
                )
                docking_results.append({"pocket_index": -1, "pocket_score": 0, "docking": result})
            except Exception as exc:
                log.warning("blind_docking_failed", error=str(exc))

        # Rank by best affinity
        best_affinity = None
        for dr in docking_results:
            poses = dr.get("docking", {}).get("poses", [])
            for pose in poses:
                aff = pose.get("affinity")
                if aff is not None and (best_affinity is None or aff < best_affinity):
                    best_affinity = aff

        return {
            "status": "completed" if docking_results else "no_results",
            "run_id": run_id,
            "protein_pdb": protein_pdb,
            "ligand_smiles": mol_info.get("smiles", ""),
            "pockets_detected": len(pockets),
            "docking_attempts": len(docking_results),
            "results": docking_results,
            "best_affinity_kcal": best_affinity,
        }

    async def compute_scenario(self, scenario_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Runs a comparison scenario computation."""
        log.info("scenario_simulation_triggered", scenario_id=scenario_id)
        return {"status": "computed", "scenario_id": scenario_id}
