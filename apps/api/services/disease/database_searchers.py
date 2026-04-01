import requests
import time
import json
import re
from typing import List, Dict, Set
from bs4 import BeautifulSoup

DIGINET_API_KEY = "84e60a3a-59c5-4808-816a-92d92063541e"

# Junk patterns to filter out non-gene entries
JUNK_PATTERNS = {
    'html_words': {'YOUR', 'ADDRESS', 'JSON', 'THIS', 'DOMAINS', 'YOU', 'ALSO', 
                   'DOCTYPE', 'ORG', 'WARNING', 'WILL', 'AND', 'SITE', 'CRAWLER', 
                   'CRAWL', 'BLOCK', 'API', 'XML', 'MIM', 'RANGES', 'OMIM', 'SUB', 
                   'CRAWLS', 'IMPLICATED'},
    'numeric_only': r'^\d+$',  # Pure numbers
    'short_noise': r'^[A-Z]{1,2}$',  # Single/double letters like 'A', 'OR'
    'html_tags': r'^[<>].*|.*[<>]$',  # HTML tag remnants
    'random_codes': r'^[A-Z0-9]{6,}$'  # Random alphanumeric codes like 'HMPSQC23JJ'
}

def filter_gene_symbols(genes: List[str]) -> List[str]:
    """Filter out junk gene symbols that are not real genes"""
    filtered = []
    
    for gene in genes:
        gene = gene.strip().upper()
        
        # Skip empty or very short genes
        if len(gene) < 2:
            continue
            
        # Skip HTML/XML artifacts
        if gene in JUNK_PATTERNS['html_words']:
            continue
            
        # Skip pure numbers
        if re.match(JUNK_PATTERNS['numeric_only'], gene):
            continue
            
        # Skip single/double letter noise
        if re.match(JUNK_PATTERNS['short_noise'], gene) and gene not in {'A', 'B', 'C'}:
            continue
            
        # Skip HTML tag remnants
        if re.match(JUNK_PATTERNS['html_tags'], gene):
            continue
            
        # Skip random alphanumeric codes
        if re.match(JUNK_PATTERNS['random_codes'], gene):
            continue
            
        # Keep genes that look legitimate (3-15 chars, mostly letters)
        if 2 <= len(gene) <= 15 and gene.isalnum():
            filtered.append(gene)
    
    return filtered

def search_all_databases(disease_info: Dict) -> List[Dict]:
    """Search all available databases for disease-gene associations"""
    results = []
    
    print("  📊 Searching GeneCards...")
    results.append(search_genecards(disease_info))
    
    print("  🧬 Searching Diginet...")
    results.append(search_diginet(disease_info))
    
    print("  🎯 Searching OpenTargets...")
    results.append(search_opentargets(disease_info))
    
    print("  🧪 Searching OMIM (filtered)...")
    results.append(search_omim_filtered(disease_info))
    
    print("  🔬 Searching CTD...")
    results.append(search_ctd(disease_info))
    
    print("  📈 Searching KEGG (converted)...")
    results.append(search_kegg_converted(disease_info))
    
    print("  🧬 Searching STRING-DB...")
    results.append(search_string_db(disease_info))
    
    print("  🏥 Searching ClinVar...")
    results.append(search_clinvar(disease_info))
    
    return [r for r in results if r.get('genes')]

def search_genecards(disease_info: Dict) -> Dict:
    """Search GeneCards database"""
    try:
        disease_name = disease_info['preferred_name']
        url = f"https://www.genecards.org/cgi-bin/listdiseasecards.pl?querytype=3&diseaseterm={disease_name}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        genes = set()
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract gene symbols from GeneCards disease page
            for link in soup.find_all('a', href=True):
                if '/cgi-bin/carddisp.pl?gene=' in link['href']:
                    gene = link.get_text().strip()
                    if gene and len(gene) < 20:
                        genes.add(gene)
        
        # Filter out junk genes
        filtered_genes = filter_gene_symbols(list(genes))
        
        return {
            'database': 'GeneCards',
            'genes': filtered_genes,
            'url': url,
            'status': 'success' if filtered_genes else 'no_results'
        }
    except Exception as e:
        return {'database': 'GeneCards', 'genes': [], 'error': str(e), 'status': 'error'}

def search_diginet(disease_info: Dict) -> Dict:
    """Search Diginet API"""
    try:
        url = "https://diginet.biomedcentral.com/api/disease_genes"
        headers = {
            'Authorization': f'Bearer {DIGINET_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'disease': disease_info['preferred_name'],
            'limit': 100
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=15)
        genes = set()
        
        if response.status_code == 200:
            result = response.json()
            for item in result.get('data', []):
                gene = item.get('gene_symbol', '').strip()
                if gene:
                    genes.add(gene)
        
        filtered_genes = filter_gene_symbols(list(genes))
        
        return {
            'database': 'Diginet',
            'genes': filtered_genes,
            'status': 'success' if filtered_genes else 'no_results'
        }
    except Exception as e:
        return {'database': 'Diginet', 'genes': [], 'error': str(e), 'status': 'error'}

def search_opentargets(disease_info: Dict) -> Dict:
    """Search OpenTargets - FREE alternative to DisGeNET"""
    try:
        search_url = "https://api.platform.opentargets.org/api/v4/graphql"
        
        disease_query = {
            "query": """
            query searchDisease($queryString: String!) {
                search(queryString: $queryString, entityNames: ["disease"]) {
                    hits {
                        id
                        name
                        description
                        entity
                    }
                }
            }
            """,
            "variables": {
                "queryString": disease_info['preferred_name']
            }
        }
        
        response = requests.post(search_url, json=disease_query, timeout=20)
        genes = set()
        
        if response.status_code == 200:
            data = response.json()
            disease_hits = data.get('data', {}).get('search', {}).get('hits', [])
            
            if disease_hits:
                disease_id = disease_hits[0]['id']
                
                association_query = {
                    "query": """
                    query associationsForDisease($efoId: String!) {
                        disease(efoId: $efoId) {
                            id
                            name
                            associatedTargets(page: {index: 0, size: 200}) {
                                rows {
                                    target {
                                        id
                                        approvedSymbol
                                        approvedName
                                    }
                                    score
                                }
                            }
                        }
                    }
                    """,
                    "variables": {
                        "efoId": disease_id
                    }
                }
                
                assoc_response = requests.post(search_url, json=association_query, timeout=20)
                if assoc_response.status_code == 200:
                    assoc_data = assoc_response.json()
                    targets = assoc_data.get('data', {}).get('disease', {}).get('associatedTargets', {}).get('rows', [])
                    
                    for target in targets:
                        gene_symbol = target.get('target', {}).get('approvedSymbol', '').strip()
                        if gene_symbol:
                            genes.add(gene_symbol)
        
        filtered_genes = filter_gene_symbols(list(genes))
        
        return {
            'database': 'OpenTargets',
            'genes': filtered_genes,
            'status': 'success' if filtered_genes else 'no_results'
        }
    except Exception as e:
        return {'database': 'OpenTargets', 'genes': [], 'error': str(e), 'status': 'error'}

def search_omim_filtered(disease_info: Dict) -> Dict:
    """Search OMIM with heavy filtering to remove HTML artifacts"""
    try:
        disease_name = disease_info['preferred_name']
        url = f"https://omim.org/search?index=entry&start=1&limit=10&sort=score+desc%2C+prefix_sort+desc&search={disease_name}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        genes = set()
        
        if response.status_code == 200:
            # Use more restrictive gene pattern - must start with letter, 3-10 chars
            gene_pattern = r'\b[A-Z][A-Z0-9]{2,9}\b'
            matches = re.findall(gene_pattern, response.text)
            
            # Known gene prefixes to prioritize
            gene_prefixes = {'INS', 'GCK', 'HNF', 'TCF', 'PPP', 'SLC', 'KCNJ', 'ABCC', 
                           'NEUROD', 'PAX', 'PDX', 'GLIS', 'WFS', 'MTNR', 'DPP'}
            
            for match in matches[:100]:  # Limit matches
                # Prioritize genes with known diabetes-related prefixes
                if any(match.startswith(prefix) for prefix in gene_prefixes):
                    genes.add(match)
                elif 3 <= len(match) <= 8 and not match.isdigit():
                    genes.add(match)
        
        # Apply comprehensive filtering
        filtered_genes = filter_gene_symbols(list(genes))
        
        # Additional OMIM-specific filtering
        final_genes = []
        for gene in filtered_genes:
            # Skip common OMIM artifacts we know are not genes
            if gene not in {'HTML', 'HTTP', 'HTTPS', 'GENE', 'DISEASE', 'PHENO'}:
                final_genes.append(gene)
        
        return {
            'database': 'OMIM',
            'genes': final_genes,
            'url': url,
            'status': 'success' if final_genes else 'no_results'
        }
    except Exception as e:
        return {'database': 'OMIM', 'genes': [], 'error': str(e), 'status': 'error'}

def search_kegg_converted(disease_info: Dict) -> Dict:
    """Search KEGG and convert gene IDs to symbols using KEGG API"""
    try:
        disease_name = disease_info['preferred_name']
        
        # Search KEGG disease
        search_url = f"https://rest.kegg.jp/find/disease/{disease_name}"
        response = requests.get(search_url, timeout=10)
        genes = set()
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            disease_ids = []
            for line in lines[:3]:  # Take first 3 disease matches
                if line.strip():
                    disease_id = line.split('\t')[0].split(':')[1]
                    disease_ids.append(disease_id)
            
            # Get genes for each disease and convert to symbols
            for disease_id in disease_ids:
                gene_url = f"https://rest.kegg.jp/link/hsa/{disease_id}"
                gene_response = requests.get(gene_url, timeout=10)
                if gene_response.status_code == 200:
                    for gene_line in gene_response.text.strip().split('\n'):
                        if gene_line.strip():
                            gene_id = gene_line.split('\t')[1].replace('hsa:', '')
                            
                            # Convert KEGG gene ID to gene symbol
                            if gene_id.isdigit():
                                symbol_url = f"https://rest.kegg.jp/get/hsa:{gene_id}"
                                symbol_response = requests.get(symbol_url, timeout=5)
                                if symbol_response.status_code == 200:
                                    # Extract gene symbol from KEGG response
                                    for sym_line in symbol_response.text.split('\n'):
                                        if sym_line.startswith('SYMBOL'):
                                            symbol = sym_line.split()[1] if len(sym_line.split()) > 1 else None
                                            if symbol:
                                                genes.add(symbol)
                                            break
                                time.sleep(0.1)  # Rate limit
                            else:
                                genes.add(gene_id)
        
        filtered_genes = filter_gene_symbols(list(genes))
        
        return {
            'database': 'KEGG',
            'genes': filtered_genes,
            'status': 'success' if filtered_genes else 'no_results'
        }
    except Exception as e:
        return {'database': 'KEGG', 'genes': [], 'error': str(e), 'status': 'error'}

def search_ctd(disease_info: Dict) -> Dict:
    """Search Comparative Toxicogenomics Database"""
    try:
        disease_name = disease_info['preferred_name'].replace(' ', '%20')
        url = f"http://ctdbase.org/tools/batchQuery.go?inputType=disease&inputTerms={disease_name}&report=genes_curated&format=json"
        
        response = requests.get(url, timeout=15)
        genes = set()
        
        if response.status_code == 200:
            try:
                data = response.json()
                for item in data:
                    gene = item.get('GeneSymbol', '').strip()
                    if gene:
                        genes.add(gene)
            except json.JSONDecodeError:
                # CTD might return non-JSON sometimes, try to parse as text
                pass
        
        filtered_genes = filter_gene_symbols(list(genes))
        
        return {
            'database': 'CTD',
            'genes': filtered_genes,
            'status': 'success' if filtered_genes else 'no_results'
        }
    except Exception as e:
        return {'database': 'CTD', 'genes': [], 'error': str(e), 'status': 'error'}

def search_string_db(disease_info: Dict) -> Dict:
    """Search STRING-DB for disease-associated proteins"""
    try:
        disease_name = disease_info['preferred_name']
        genes = set()
        
        # Try direct search approach
        search_url = f"https://string-db.org/api/json/resolve?identifier={disease_name}&species=9606"
        search_response = requests.get(search_url, timeout=15)
        if search_response.status_code == 200:
            search_data = search_response.json()
            for item in search_data:
                gene = item.get('preferredName', '').strip()
                if gene and 2 < len(gene) < 20:
                    genes.add(gene)
        
        filtered_genes = filter_gene_symbols(list(genes))
        
        return {
            'database': 'STRING-DB',
            'genes': filtered_genes,
            'status': 'success' if filtered_genes else 'no_results'
        }
    except Exception as e:
        return {'database': 'STRING-DB', 'genes': [], 'error': str(e), 'status': 'error'}

def search_clinvar(disease_info: Dict) -> Dict:
    """Search NCBI ClinVar for genetic variants associated with disease"""
    try:
        disease_name = disease_info['preferred_name']
        
        # Search ClinVar using E-utilities
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            'db': 'clinvar',
            'term': f'{disease_name}[dis]',
            'retmax': 50,
            'retmode': 'json'
        }
        
        response = requests.get(search_url, params=params, timeout=15)
        genes = set()
        
        if response.status_code == 200:
            data = response.json()
            ids = data.get('esearchresult', {}).get('idlist', [])
            
            if ids:
                # Get details for the variants
                fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                fetch_params = {
                    'db': 'clinvar',
                    'id': ','.join(ids[:25]),  # Limit to first 25
                    'retmode': 'json'
                }
                
                fetch_response = requests.get(fetch_url, params=fetch_params, timeout=20)
                if fetch_response.status_code == 200:
                    fetch_data = fetch_response.json()
                    
                    for uid, info in fetch_data.get('result', {}).items():
                        if uid != 'uids' and isinstance(info, dict):
                            # Extract gene symbols from various fields
                            if 'genes' in info and info['genes']:
                                for gene_info in info['genes']:
                                    if isinstance(gene_info, dict):
                                        symbol = gene_info.get('symbol', '')
                                        if symbol:
                                            genes.add(symbol)
        
        filtered_genes = filter_gene_symbols(list(genes))
        
        return {
            'database': 'ClinVar',
            'genes': filtered_genes,
            'status': 'success' if filtered_genes else 'no_results'
        }
    except Exception as e:
        return {'database': 'ClinVar', 'genes': [], 'error': str(e), 'status': 'error'}