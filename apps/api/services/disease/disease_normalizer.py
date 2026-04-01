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
        'diabetes': 'Diabetes Mellitus',
        'cancer': 'Neoplasms',
        'alzheimer': "Alzheimer's Disease",
        'parkinson': "Parkinson's Disease",
        'heart disease': 'Cardiovascular Diseases',
        'hypertension': 'Hypertension',
        'depression': 'Depressive Disorder',
        'asthma': 'Asthma',
        'copd': 'Pulmonary Disease, Chronic Obstructive',
        'covid': 'COVID-19',
        'breast cancer': 'Breast Neoplasms',
        'lung cancer': 'Lung Neoplasms',
        'stroke': 'Stroke'
    }
    
    disease_lower = disease_name.lower().strip()
    for key, standard in standardization_map.items():
        if key in disease_lower:
            return standard
    
    # Capitalize first letter of each word
    return ' '.join(word.capitalize() for word in disease_name.split())