import requests
import re
from typing import Dict, List

def normalize_disease_name(disease_name: str) -> Dict:
    """
    Normalize disease name using multiple sources
    Returns standardized disease information
    """
    disease_info = {
        'original_name': disease_name,
        'preferred_name': disease_name,
        'synonyms': [disease_name],
        'mesh_id': None,
        'omim_id': None,
        'icd_code': None,
        'mondo_id': None
    }
    
    # Try EBI OLS (Ontology Lookup Service) for disease normalization
    try:
        disease_info.update(_search_ebi_ols(disease_name))
    except Exception as e:
        print(f"Warning: EBI OLS search failed: {e}")
    
    # Try NCBI MeSH lookup
    try:
        mesh_info = _search_ncbi_mesh(disease_name)
        if mesh_info:
            disease_info.update(mesh_info)
    except Exception as e:
        print(f"Warning: NCBI MeSH search failed: {e}")
    
    # Try manual disease name standardization
    disease_info['preferred_name'] = _standardize_disease_name(disease_name)
    
    return disease_info

def _search_ebi_ols(disease_name: str) -> Dict:
    """Search EBI Ontology Lookup Service"""
    url = "https://www.ebi.ac.uk/ols/api/search"
    params = {
        'q': disease_name,
        'ontology': 'mondo,doid,hp',
        'type': 'class',
        'exact': 'false',
        'rows': 5
    }
    
    response = requests.get(url, params=params, timeout=10)
    if response.status_code == 200:
        data = response.json()
        if data.get('response', {}).get('docs'):
            doc = data['response']['docs'][0]
            return {
                'preferred_name': doc.get('label', disease_name),
                'synonyms': doc.get('synonym', [disease_name]),
                'mondo_id': doc.get('obo_id') if 'MONDO' in doc.get('obo_id', '') else None
            }
    return {}

def _search_ncbi_mesh(disease_name: str) -> Dict:
    """Search NCBI MeSH database"""
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        'db': 'mesh',
        'term': f"{disease_name}[MeSH Terms]",
        'retmode': 'json',
        'retmax': 1
    }
    
    response = requests.get(url, params=params, timeout=10)
    if response.status_code == 200:
        data = response.json()
        if data.get('esearchresult', {}).get('idlist'):
            mesh_id = data['esearchresult']['idlist'][0]
            return {'mesh_id': mesh_id}
    return {}

def _standardize_disease_name(disease_name: str) -> str:
    """Manual standardization of common disease names"""
    standardization_map = {
        'pancreatic ductal adenocarcinoma': 'Pancreatic Ductal Adenocarcinoma',
        'triple-negative breast cancer': 'Triple Negative Breast Neoplasms',
        'triple negative breast cancer': 'Triple Negative Breast Neoplasms',
        'hepatocellular carcinoma': 'Hepatocellular Carcinoma',
        'amyotrophic lateral sclerosis': 'Amyotrophic Lateral Sclerosis',
        'systemic lupus erythematosus': 'Systemic Lupus Erythematosus',
        'chronic myeloid leukemia': 'Leukemia, Myelogenous, Chronic, BCR-ABL Positive',
        'glioblastoma multiforme': 'Glioblastoma',
        'inflammatory bowel disease': 'Inflammatory Bowel Diseases',
        'multiple sclerosis': 'Multiple Sclerosis',
        'rheumatoid arthritis': 'Rheumatoid Arthritis',
        'lung adenocarcinoma': 'Lung Neoplasms',
        'cystic fibrosis': 'Cystic Fibrosis',
        'prostate cancer': 'Prostatic Neoplasms',
        'breast cancer': 'Breast Neoplasms',
        'lung cancer': 'Lung Neoplasms',
        'colon cancer': 'Colonic Neoplasms',
        'ovarian cancer': 'Ovarian Neoplasms',
        'heart disease': 'Cardiovascular Diseases',
        'type 2 diabetes': 'Type 2 Diabetes Mellitus',
        'type 1 diabetes': 'Type 1 Diabetes Mellitus',
        'parkinsons disease': "Parkinson Disease",
        'parkinson': "Parkinson Disease",
        'alzheimer': "Alzheimer Disease",
        'hypertension': 'Hypertension',
        'depression': 'Depressive Disorder',
        'asthma': 'Asthma',
        'copd': 'Pulmonary Disease, Chronic Obstructive',
        'covid': 'COVID-19',
        'stroke': 'Stroke',
        'diabetes': 'Diabetes Mellitus',
        'cancer': 'Neoplasms',
    }
    
    disease_lower = disease_name.lower().strip()
    # Sort by longest key first so specific terms match before generic ones
    for key in sorted(standardization_map.keys(), key=len, reverse=True):
        if key in disease_lower:
            return standardization_map[key]
    
    # Capitalize first letter of each word
    return ' '.join(word.capitalize() for word in disease_name.split())