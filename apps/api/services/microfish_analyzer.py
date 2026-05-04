import math
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MicrofishAnalyzer:
    """
    Microfish Integration: A fast, lightweight sequence and molecular property analyzer.
    Used to bypass heavy LLM calls for deterministic biological properties.
    """
    def __init__(self):
        self.version = "1.0.0-micro"
        logger.info(f"Initialized MicrofishAnalyzer v{self.version}")

    def analyze_sequence(self, fasta_sequence: str) -> Dict[str, Any]:
        """
        Computes basic properties of a protein sequence using Microfish heuristics.
        """
        # Basic amino acid counts
        length = len(fasta_sequence)
        aromatics = sum(fasta_sequence.count(aa) for aa in "FWY")
        aliphatics = sum(fasta_sequence.count(aa) for aa in "AILV")
        
        # Simple molecular weight approximation (avg ~110 Da per AA)
        mw_kda = (length * 110) / 1000.0

        return {
            "length": length,
            "aromatic_content": round(aromatics / length, 3) if length else 0,
            "aliphatic_index": round((aliphatics / length) * 100, 2) if length else 0,
            "approx_mw_kda": round(mw_kda, 2),
            "microfish_confidence": 0.95
        }

    def analyze_smiles(self, smiles: str) -> Dict[str, Any]:
        """
        Computes small molecule properties using RDKit for real Lipinski Rule of Five.
        """
        try:
            from rdkit import Chem
            from rdkit.Chem import Descriptors

            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return {
                    "smiles": smiles,
                    "error": "invalid_smiles",
                    "rule_of_five_pass": False,
                    "microfish_confidence": 0.0,
                }

            mw = Descriptors.MolWt(mol)
            logp = Descriptors.MolLogP(mol)
            hbd = Descriptors.NumHDonors(mol)
            hba = Descriptors.NumHAcceptors(mol)

            violations = sum([
                mw > 500,
                logp > 5,
                hbd > 5,
                hba > 10,
            ])

            return {
                "smiles": smiles,
                "molecular_weight": round(mw, 2),
                "logp": round(logp, 2),
                "h_bond_donors": hbd,
                "h_bond_acceptors": hba,
                "ro5_violations": violations,
                "rule_of_five_pass": violations <= 1,
                "heavy_atoms": mol.GetNumHeavyAtoms(),
                "microfish_confidence": 0.99,
            }
        except ImportError:
            logger.warning("RDKit not installed — falling back to heuristic SMILES analysis")
            return {
                "smiles": smiles,
                "rule_of_five_pass": False,
                "error": "rdkit_not_available",
                "heavy_atoms": len([c for c in smiles if c.isupper() and c not in 'H']),
                "microfish_confidence": 0.0,
            }

# Global instance
analyzer = MicrofishAnalyzer()
