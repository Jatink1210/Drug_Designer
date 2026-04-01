import pandas as pd
import datetime as dt
from typing import Dict, List

def write_disease_results(disease_name: str, normalized_disease: Dict,
                          gene_results: List[Dict], uniprot_mapping: Dict[str, str]) -> str:
    """Write disease-gene analysis results to Excel file"""

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"disease_gene_analysis_{timestamp}.xlsx"

    with pd.ExcelWriter(filename, engine='openpyxl') as writer:

        # Sheet 1: Disease Information
        disease_data = pd.DataFrame([{
            'Original_Disease_Name': disease_name,
            'Preferred_Disease_Name': normalized_disease.get('preferred_name', ''),
            'Synonyms': '; '.join(normalized_disease.get('synonyms', [])),
            'MeSH_ID': normalized_disease.get('mesh_id', ''),
            'OMIM_ID': normalized_disease.get('omim_id', ''),
            'MONDO_ID': normalized_disease.get('mondo_id', ''),
            'Analysis_Date': dt.datetime.now()
        }])
        disease_data.to_excel(writer, sheet_name='Disease_Info', index=False)

        # Sheet 2: Database Results Summary
        summary_data = []
        for result in gene_results:
            summary_data.append({
                'Database': result.get('database', ''),
                'Status': result.get('status', ''),
                'Genes_Found': len(result.get('genes', [])),
                'Error': result.get('error', ''),
                'URL': result.get('url', '')
            })

        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Database_Summary', index=False)

        # Sheet 3: All Genes with Database Sources AND UniProt IDs
        gene_data = []
        for result in gene_results:
            database = result.get('database', '')
            for gene in result.get('genes', []):
                uniprot_id = uniprot_mapping.get(gene, '')
                gene_data.append({
                    'Gene_Symbol': gene,
                    'UniProt_ID': uniprot_id,
                    'Database_Source': database,
                    'Has_UniProt': 'Yes' if uniprot_id else 'No',
                    'UniProt_URL': f'https://www.uniprot.org/uniprot/{uniprot_id}' if uniprot_id else ''
                })

        if gene_data:
            genes_df = pd.DataFrame(gene_data)
            genes_df.to_excel(writer, sheet_name='Gene_Results', index=False)

        # Sheet 4: Unique Genes Summary
        unique_genes = set()
        for result in gene_results:
            unique_genes.update(result.get('genes', []))

        unique_data = []
        for gene in sorted(unique_genes):
            sources = []
            for result in gene_results:
                if gene in result.get('genes', []):
                    sources.append(result.get('database', ''))

            uniprot_id = uniprot_mapping.get(gene, '')
            unique_data.append({
                'Gene_Symbol': gene,
                'UniProt_ID': uniprot_id,
                'UniProt_URL': f'https://www.uniprot.org/uniprot/{uniprot_id}' if uniprot_id else '',
                'Source_Databases': '; '.join(sources),
                'Source_Count': len(sources)
            })

        if unique_data:
            unique_df = pd.DataFrame(unique_data)
            unique_df.to_excel(writer, sheet_name='Unique_Genes', index=False)

        # Sheet 5: UniProt Mapping
        uniprot_data = []
        for gene, uniprot_id in uniprot_mapping.items():
            uniprot_data.append({
                'Gene_Symbol': gene,
                'UniProt_ID': uniprot_id,
                'UniProt_URL': f'https://www.uniprot.org/uniprot/{uniprot_id}'
            })

        if uniprot_data:
            uniprot_df = pd.DataFrame(uniprot_data)
            uniprot_df.to_excel(writer, sheet_name='UniProt_Mapping', index=False)

        # Sheet 6: Analysis Summary
        total_genes = len(unique_genes)
        mapped_genes = len(uniprot_mapping)

        analysis_summary = pd.DataFrame([{
            'Disease_Name': disease_name,
            'Normalized_Name': normalized_disease.get('preferred_name', ''),
            'Total_Databases_Searched': len(gene_results),
            'Databases_With_Results': len([r for r in gene_results if r.get('genes')]),
            'Total_Unique_Genes': total_genes,
            'Genes_With_UniProt': mapped_genes,
            'Mapping_Success_Rate': f"{(mapped_genes/total_genes*100):.1f}%" if total_genes > 0 else "0%",
            'Analysis_Timestamp': dt.datetime.now()
        }])
        analysis_summary.to_excel(writer, sheet_name='Analysis_Summary', index=False)

    return filename