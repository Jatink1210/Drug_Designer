import requests
import time
from typing import Dict, List
import re

def map_genes_to_uniprot(genes: List[str]) -> Dict[str, str]:
    """Enhanced gene to UniProt mapping with retry logic and multiple query strategies"""
    mapping = {}

    if not genes:
        return mapping

    print(f"  🔗 Mapping {len(genes)} genes to UniProt IDs...")

    # Method 1: UniProt batch mapping (primary gene names)
    batch_mapping = _uniprot_batch_mapping_enhanced(genes)
    mapping.update(batch_mapping)
    
    print(f"  ✓ Batch mapping found {len(batch_mapping)} UniProt IDs")

    # Method 2: Individual lookups for unmapped genes with retry logic
    unmapped = [g for g in genes if g not in mapping]
    if unmapped:
        print(f"  🔄 Retrying individual mapping for {len(unmapped)} genes...")
        individual_mapping = _uniprot_individual_mapping_enhanced(unmapped[:100])
        mapping.update(individual_mapping)
        
        print(f"  ✓ Individual mapping found {len(individual_mapping)} additional UniProt IDs")

    # Method 3: Alternative query formats for still unmapped genes
    still_unmapped = [g for g in genes if g not in mapping]
    if still_unmapped:
        print(f"  🔍 Trying alternative query formats for {len(still_unmapped)} genes...")
        alternative_mapping = _uniprot_alternative_mapping(still_unmapped[:50])
        mapping.update(alternative_mapping)
        
        print(f"  ✓ Alternative mapping found {len(alternative_mapping)} additional UniProt IDs")

    return mapping


def _uniprot_batch_mapping_enhanced(genes: List[str]) -> Dict[str, str]:
    """Enhanced batch mapping with better error handling"""
    try:
        url = "https://rest.uniprot.org/idmapping/run"
        data = {
            'from': 'Gene_Name',
            'to': 'UniProtKB',
            'ids': ' '.join(genes[:400])  # Reduce batch size for reliability
        }
        
        response = requests.post(url, data=data, timeout=40)
        if response.status_code != 200:
            print(f"  Warning: Batch mapping failed with status {response.status_code}")
            return {}

        result = response.json()
        job_id = result.get('jobId')
        if not job_id:
            return {}

        # Wait for job completion with longer timeout
        status_url = f"https://rest.uniprot.org/idmapping/status/{job_id}"
        for attempt in range(15):  # Wait up to 45 seconds
            time.sleep(3)
            try:
                status_response = requests.get(status_url, timeout=15)
                if status_response.status_code != 200:
                    continue
                    
                status_json = status_response.json()
                job_status = status_json.get('jobStatus')
                
                if job_status == 'FINISHED':
                    break
                elif job_status == 'ERROR':
                    print("  Warning: UniProt batch job failed")
                    return {}
                elif job_status != 'RUNNING':
                    continue
                    
            except Exception as e:
                print(f"  Warning: Status check failed (attempt {attempt+1}): {e}")
                continue

        # Get results
        results_url = f"https://rest.uniprot.org/idmapping/uniprotkb/results/{job_id}"
        try:
            results_response = requests.get(results_url, timeout=40)
            mapping = {}
            
            if results_response.status_code == 200:
                data = results_response.json()
                for result in data.get('results', []):
                    gene = result.get('from')
                    uniprot_entry = result.get('to', {})
                    uniprot_id = uniprot_entry.get('primaryAccession')
                    
                    if gene and uniprot_id:
                        mapping[gene] = uniprot_id
            
            return mapping
            
        except Exception as e:
            print(f"  Warning: Failed to retrieve batch results: {e}")
            return {}

    except Exception as e:
        print(f"  Warning: UniProt batch mapping failed: {e}")
        return {}


def _uniprot_individual_mapping_enhanced(genes: List[str]) -> Dict[str, str]:
    """Enhanced individual mapping with multiple query strategies"""
    mapping = {}
    
    for gene in genes[:50]:  # Limit to prevent timeout
        for attempt in range(2):  # Reduce attempts but use better queries
            try:
                # Try multiple query formats
                queries = [
                    f'gene_exact:{gene} AND organism_id:9606',
                    f'gene:{gene} AND organism_id:9606',
                    f'(gene_exact:{gene} OR gene_synonym:{gene}) AND organism_id:9606'
                ]
                
                for query in queries:
                    url = "https://rest.uniprot.org/uniprotkb/search"
                    params = {
                        'query': query,
                        'fields': 'accession,gene_primary,gene_synonym',
                        'format': 'json',
                        'size': 1
                    }
                    
                    response = requests.get(url, params=params, timeout=25)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('results'):
                            uniprot_id = data['results'][0].get('primaryAccession')
                            if uniprot_id:
                                mapping[gene] = uniprot_id
                                break
                    
                    time.sleep(0.3)  # Rate limiting between queries
                
                if gene in mapping:
                    break
                    
            except Exception as e:
                if attempt == 0:  # Only print warning on first attempt
                    print(f"  Warning: Failed to map gene {gene} (attempt {attempt+1}): {e}")
                time.sleep(2 * (attempt + 1))
        
        time.sleep(0.5)  # Rate limit between genes
    
    return mapping


def _uniprot_alternative_mapping(genes: List[str]) -> Dict[str, str]:
    """Try mapping using alternative query formats and protein names"""
    mapping = {}
    
    for gene in genes[:30]:  # Further limit for alternative mapping
        try:
            # Try different search strategies
            queries = [
                f'(gene:{gene} OR protein_name:{gene}) AND organism_id:9606',
                f'gene_synonym:{gene} AND organism_id:9606',
                f'(gene_names:{gene} OR gene_oln:{gene}) AND organism_id:9606'
            ]
            
            for query in queries:
                url = "https://rest.uniprot.org/uniprotkb/search"
                params = {
                    'query': query,
                    'fields': 'accession,gene_primary,protein_name',
                    'format': 'json',
                    'size': 1
                }
                
                response = requests.get(url, params=params, timeout=20)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('results'):
                        uniprot_id = data['results'][0].get('primaryAccession')
                        if uniprot_id:
                            mapping[gene] = uniprot_id
                            break
                
                time.sleep(0.4)
            
            if gene in mapping:
                continue
                
        except Exception:
            continue
        
        time.sleep(0.2)
    
    return mapping
