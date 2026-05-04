"""MeSH / Gene Ontology terminology mapper.

Maps user query terms to standardized ontology IDs:
- MeSH (Medical Subject Headings) for diseases, drugs, anatomy
- Gene Ontology (GO) for biological processes, molecular functions
- Provides synonym expansion for comprehensive search coverage.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ── Static MeSH mapping (common biomedical terms) ──────────
# In production, would query NLM MeSH API: https://id.nlm.nih.gov/mesh/
_MESH_MAP: Dict[str, Dict[str, Any]] = {
    "heart attack": {"mesh_id": "D009203", "preferred": "Myocardial Infarction", "synonyms": ["heart attack", "MI", "acute myocardial infarction", "AMI"]},
    "myocardial infarction": {"mesh_id": "D009203", "preferred": "Myocardial Infarction", "synonyms": ["heart attack", "MI", "acute myocardial infarction"]},
    "breast cancer": {"mesh_id": "D001943", "preferred": "Breast Neoplasms", "synonyms": ["breast cancer", "breast carcinoma", "mammary neoplasm", "breast tumor"]},
    "lung cancer": {"mesh_id": "D008175", "preferred": "Lung Neoplasms", "synonyms": ["lung cancer", "NSCLC", "SCLC", "pulmonary carcinoma", "lung carcinoma"]},
    "alzheimer": {"mesh_id": "D000544", "preferred": "Alzheimer Disease", "synonyms": ["alzheimer's disease", "alzheimer disease", "AD", "senile dementia"]},
    "alzheimer's disease": {"mesh_id": "D000544", "preferred": "Alzheimer Disease", "synonyms": ["alzheimer's", "alzheimer disease", "AD"]},
    "parkinson": {"mesh_id": "D010300", "preferred": "Parkinson Disease", "synonyms": ["parkinson's disease", "parkinson disease", "PD", "paralysis agitans"]},
    "diabetes": {"mesh_id": "D003920", "preferred": "Diabetes Mellitus", "synonyms": ["diabetes", "DM", "diabetes mellitus"]},
    "type 2 diabetes": {"mesh_id": "D003924", "preferred": "Diabetes Mellitus, Type 2", "synonyms": ["T2DM", "type 2 diabetes", "type II diabetes", "NIDDM"]},
    "type 1 diabetes": {"mesh_id": "D003922", "preferred": "Diabetes Mellitus, Type 1", "synonyms": ["T1DM", "type 1 diabetes", "juvenile diabetes", "IDDM"]},
    "hypertension": {"mesh_id": "D006973", "preferred": "Hypertension", "synonyms": ["high blood pressure", "HTN", "arterial hypertension"]},
    "asthma": {"mesh_id": "D001249", "preferred": "Asthma", "synonyms": ["asthma", "bronchial asthma", "reactive airway disease"]},
    "depression": {"mesh_id": "D003863", "preferred": "Depressive Disorder", "synonyms": ["depression", "MDD", "major depressive disorder", "clinical depression"]},
    "schizophrenia": {"mesh_id": "D012559", "preferred": "Schizophrenia", "synonyms": ["schizophrenia", "SCZ", "psychosis"]},
    "obesity": {"mesh_id": "D009765", "preferred": "Obesity", "synonyms": ["obesity", "overweight", "adiposity", "BMI >30"]},
    "rheumatoid arthritis": {"mesh_id": "D001172", "preferred": "Arthritis, Rheumatoid", "synonyms": ["RA", "rheumatoid arthritis", "rheumatoid disease"]},
    "leukemia": {"mesh_id": "D007938", "preferred": "Leukemia", "synonyms": ["leukemia", "leukaemia", "blood cancer"]},
    "lymphoma": {"mesh_id": "D008223", "preferred": "Lymphoma", "synonyms": ["lymphoma", "NHL", "non-Hodgkin lymphoma", "Hodgkin lymphoma"]},
    "melanoma": {"mesh_id": "D008545", "preferred": "Melanoma", "synonyms": ["melanoma", "malignant melanoma", "cutaneous melanoma"]},
    "glioblastoma": {"mesh_id": "D005909", "preferred": "Glioblastoma", "synonyms": ["GBM", "glioblastoma multiforme", "grade IV glioma"]},
    "covid": {"mesh_id": "D000086382", "preferred": "COVID-19", "synonyms": ["COVID-19", "SARS-CoV-2", "coronavirus disease 2019", "2019-nCoV"]},
    "malaria": {"mesh_id": "D008288", "preferred": "Malaria", "synonyms": ["malaria", "plasmodium", "falciparum malaria"]},
    "tuberculosis": {"mesh_id": "D014376", "preferred": "Tuberculosis", "synonyms": ["TB", "tuberculosis", "mycobacterium tuberculosis"]},
    "epilepsy": {"mesh_id": "D004827", "preferred": "Epilepsy", "synonyms": ["epilepsy", "seizure disorder", "convulsive disorder"]},
    "copd": {"mesh_id": "D029424", "preferred": "Pulmonary Disease, Chronic Obstructive", "synonyms": ["COPD", "chronic obstructive pulmonary disease", "chronic bronchitis", "emphysema"]},
    "hepatitis": {"mesh_id": "D006505", "preferred": "Hepatitis", "synonyms": ["hepatitis", "HBV", "HCV", "hepatitis B", "hepatitis C"]},
    "stroke": {"mesh_id": "D020521", "preferred": "Stroke", "synonyms": ["stroke", "cerebrovascular accident", "CVA", "ischemic stroke"]},
    "psoriasis": {"mesh_id": "D011565", "preferred": "Psoriasis", "synonyms": ["psoriasis", "plaque psoriasis", "psoriatic disease"]},
    "multiple sclerosis": {"mesh_id": "D009103", "preferred": "Multiple Sclerosis", "synonyms": ["MS", "multiple sclerosis", "demyelinating disease"]},
    "crohn's disease": {"mesh_id": "D003424", "preferred": "Crohn Disease", "synonyms": ["Crohn's disease", "Crohn disease", "regional enteritis", "IBD"]},
    "cystic fibrosis": {"mesh_id": "D003550", "preferred": "Cystic Fibrosis", "synonyms": ["CF", "cystic fibrosis", "mucoviscidosis"]},
    "sickle cell": {"mesh_id": "D000755", "preferred": "Anemia, Sickle Cell", "synonyms": ["sickle cell disease", "SCD", "sickle cell anemia"]},
    "pancreatic cancer": {"mesh_id": "D010190", "preferred": "Pancreatic Neoplasms", "synonyms": ["pancreatic cancer", "PDAC", "pancreatic adenocarcinoma"]},
    "triple-negative breast cancer": {"mesh_id": "D000071182", "preferred": "Triple Negative Breast Neoplasms", "synonyms": ["TNBC", "triple-negative breast cancer", "triple negative breast cancer", "basal-like breast cancer"]},
    "triple negative breast cancer": {"mesh_id": "D000071182", "preferred": "Triple Negative Breast Neoplasms", "synonyms": ["TNBC", "triple-negative breast cancer", "triple negative breast cancer", "basal-like breast cancer"]},
    "non-small cell lung cancer": {"mesh_id": "D002289", "preferred": "Carcinoma, Non-Small-Cell Lung", "synonyms": ["NSCLC", "non-small cell lung cancer", "non-small cell lung carcinoma", "adenocarcinoma of lung"]},
    "non small cell lung cancer": {"mesh_id": "D002289", "preferred": "Carcinoma, Non-Small-Cell Lung", "synonyms": ["NSCLC", "non-small cell lung cancer", "non-small cell lung carcinoma"]},
    "ulcerative colitis": {"mesh_id": "D003093", "preferred": "Colitis, Ulcerative", "synonyms": ["UC", "ulcerative colitis", "inflammatory bowel disease", "IBD"]},
    "hepatocellular carcinoma": {"mesh_id": "D006528", "preferred": "Carcinoma, Hepatocellular", "synonyms": ["HCC", "hepatocellular carcinoma", "liver cancer", "hepatoma"]},
    "liver cancer": {"mesh_id": "D006528", "preferred": "Carcinoma, Hepatocellular", "synonyms": ["HCC", "hepatocellular carcinoma", "liver cancer", "hepatoma"]},
    "type 2 diabetes mellitus": {"mesh_id": "D003924", "preferred": "Diabetes Mellitus, Type 2", "synonyms": ["T2DM", "type 2 diabetes mellitus", "type 2 diabetes", "NIDDM"]},
    "alzheimer's disease": {"mesh_id": "D000544", "preferred": "Alzheimer Disease", "synonyms": ["alzheimer's disease", "alzheimer disease", "AD", "senile dementia"]},
}

# ── Gene aliases ────────────────────────────────────────────
_GENE_ALIASES: Dict[str, List[str]] = {
    "BRCA1": ["BRCA1", "FANCS", "breast cancer type 1", "RING finger protein 53"],
    "BRCA2": ["BRCA2", "FANCD1", "breast cancer type 2"],
    "TP53": ["TP53", "p53", "tumor protein p53", "LFS1"],
    "EGFR": ["EGFR", "ErbB-1", "HER1", "epidermal growth factor receptor"],
    "KRAS": ["KRAS", "K-Ras", "KRAS4B", "K-Ras4B", "proto-oncogene c-K-ras"],
    "BRAF": ["BRAF", "B-Raf", "BRAF1", "proto-oncogene B-Raf"],
    "PIK3CA": ["PIK3CA", "PI3K", "p110alpha", "phosphatidylinositol-4,5-bisphosphate 3-kinase"],
    "ALK": ["ALK", "anaplastic lymphoma kinase", "CD246"],
    "HER2": ["HER2", "ERBB2", "NEU", "HER-2/neu"],
    "VEGF": ["VEGF", "VEGFA", "vascular endothelial growth factor"],
    "PD1": ["PD-1", "PDCD1", "CD279", "programmed cell death protein 1"],
    "PDL1": ["PD-L1", "CD274", "B7-H1", "programmed death-ligand 1"],
    "JAK2": ["JAK2", "Janus kinase 2", "JTK10"],
    "BCR-ABL": ["BCR-ABL", "BCR-ABL1", "Philadelphia chromosome"],
    "MTOR": ["mTOR", "FRAP", "mechanistic target of rapamycin"],
    "CDK4": ["CDK4", "cyclin-dependent kinase 4", "PSK-J3"],
    "CDK6": ["CDK6", "cyclin-dependent kinase 6", "PLSTIRE"],
    "AKT1": ["AKT1", "PKB", "protein kinase B", "RAC-alpha"],
    "MYC": ["MYC", "c-Myc", "bHLHe39"],
    "RB1": ["RB1", "retinoblastoma protein", "pRb"],
    "PTEN": ["PTEN", "MMAC1", "phosphatase and tensin homolog"],
    "IDH1": ["IDH1", "isocitrate dehydrogenase 1"],
    "IDH2": ["IDH2", "isocitrate dehydrogenase 2"],
    "FGFR": ["FGFR", "fibroblast growth factor receptor"],
    "ROS1": ["ROS1", "ROS proto-oncogene 1"],
    "MET": ["MET", "c-Met", "HGFR", "hepatocyte growth factor receptor"],
    "RET": ["RET", "ret proto-oncogene"],
    "NF1": ["NF1", "neurofibromin 1", "neurofibromatosis type 1"],
    "SMAD4": ["SMAD4", "DPC4", "MADH4"],
    "APC": ["APC", "adenomatous polyposis coli"],
}


def standardize_terms(query: str) -> Dict[str, Any]:
    """Map query terms to MeSH IDs & gene aliases, expand with synonyms.

    Returns:
        {
            "original_query": str,
            "mesh_mappings": [{term, mesh_id, preferred_name, synonyms}],
            "gene_mappings": [{gene, aliases}],
            "expanded_search_terms": [str],  # All synonyms + aliases for broader search
            "standardized_terms": [str],      # Preferred terms for display
        }
    """
    q_lower = query.lower()
    mesh_mappings = []
    gene_mappings = []
    expanded_terms = set()
    standardized = set()

    # MeSH lookup
    for term, info in _MESH_MAP.items():
        if term in q_lower:
            mesh_mappings.append({
                "term": term,
                "mesh_id": info["mesh_id"],
                "preferred_name": info["preferred"],
                "synonyms": info["synonyms"],
                "mesh_url": f"https://id.nlm.nih.gov/mesh/{info['mesh_id']}.html",
            })
            expanded_terms.update(info["synonyms"])
            standardized.add(info["preferred"])

    # Gene alias lookup
    for gene, aliases in _GENE_ALIASES.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", query, re.IGNORECASE):
                gene_mappings.append({
                    "gene": gene,
                    "matched_alias": alias,
                    "all_aliases": aliases,
                })
                expanded_terms.update(aliases)
                standardized.add(gene)
                break

    # Add original query words
    for word in query.split():
        if len(word) > 2:
            expanded_terms.add(word)

    return {
        "original_query": query,
        "mesh_mappings": mesh_mappings,
        "gene_mappings": gene_mappings,
        "expanded_search_terms": sorted(expanded_terms),
        "standardized_terms": sorted(standardized),
    }


def get_mesh_id(term: str) -> Optional[str]:
    """Quick MeSH ID lookup for a single term."""
    info = _MESH_MAP.get(term.lower())
    return info["mesh_id"] if info else None


def get_synonyms(term: str) -> List[str]:
    """Get all known synonyms for a term (disease or gene)."""
    t = term.lower()

    # Check MeSH
    info = _MESH_MAP.get(t)
    if info:
        return info["synonyms"]

    # Check gene aliases
    for gene, aliases in _GENE_ALIASES.items():
        for alias in aliases:
            if alias.lower() == t:
                return aliases

    return [term]
