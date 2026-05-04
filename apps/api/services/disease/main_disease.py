import sys
import asyncio
import time
from disease_normalizer import normalize_disease_name
from database_searchers import search_all_databases
from uniprot_mapper import map_genes_to_uniprot
from excel_writer_disease import write_disease_results

def main():
    if len(sys.argv) < 2:
        disease_name = input("Enter disease name: ").strip()
    else:
        disease_name = " ".join(sys.argv[1:])
    
    if not disease_name:
        print("❌ Please provide a disease name")
        return
    
    print(f"🔍 Processing disease: {disease_name}")
    start_time = time.time()
    
    # Step 1: Normalize disease name
    print("📋 Normalizing disease name...")
    normalized_disease = normalize_disease_name(disease_name)
    print(f"✓ Normalized: {normalized_disease['preferred_name']}")
    
    # Step 2: Search multiple databases with enhanced filtering
    print("🔍 Searching databases with enhanced gene filtering...")
    print("   ℹ️  Filtering out HTML artifacts, numeric IDs, and junk gene symbols")
    gene_results = search_all_databases(normalized_disease)
    
    # Count filtered results
    total_genes_found = sum(len(result.get('genes', [])) for result in gene_results)
    databases_with_results = len([r for r in gene_results if r.get('genes')])
    
    print(f"   ✓ Found {total_genes_found} high-quality genes from {databases_with_results} databases")
    
    # Step 3: Enhanced UniProt mapping with secondary names
    print("🧬 Enhanced UniProt mapping with retry logic and secondary names...")
    all_genes = set()
    for db_result in gene_results:
        all_genes.update(db_result.get('genes', []))
    
    uniprot_mapping = asyncio.run(map_genes_to_uniprot(list(all_genes)))
    
    # Step 4: Generate Excel output
    print("📊 Generating enhanced Excel report...")
    output_file = write_disease_results(
        disease_name=disease_name,
        normalized_disease=normalized_disease,
        gene_results=gene_results,
        uniprot_mapping=uniprot_mapping
    )
    
    total_genes = len(all_genes)
    total_uniprot = len(uniprot_mapping)
    elapsed = time.time() - start_time
    
    print(f"✓ {total_genes} genes → {total_uniprot} UniProt IDs ({elapsed:.1f}s) ➜ {output_file}")
    
    # Enhanced summary with mapping success rate
    success_rate = (total_uniprot / total_genes * 100) if total_genes > 0 else 0
    print(f"📈 UniProt mapping success rate: {success_rate:.1f}%")
    
    if total_uniprot > 15:
        print("🎉 Excellent! High-quality gene mapping achieved.")
    elif total_uniprot > 8:
        print("✓ Good gene mapping results.")
    else:
        print("⚠️  Consider trying alternative disease names for better results.")
    
    # Show detailed database results
    print("\n📊 Enhanced Database Results Summary:")
    for result in gene_results:
        db_name = result.get('database', 'Unknown')
        gene_count = len(result.get('genes', []))
        status = result.get('status', 'unknown')
        
        # Show quality indicators
        if gene_count == 0:
            quality = "❌"
        elif gene_count < 5:
            quality = "⚠️"
        elif gene_count < 20:
            quality = "✓"
        else:
            quality = "🎯"
            
        print(f"   {quality} {db_name}: {gene_count} genes ({status})")
    
    # Show top mapped genes
    if uniprot_mapping:
        print(f"\n🧬 Sample of mapped genes:")
        sample_genes = list(uniprot_mapping.items())[:5]
        for gene, uniprot_id in sample_genes:
            print(f"   {gene} → {uniprot_id}")
        if len(uniprot_mapping) > 5:
            print(f"   ... and {len(uniprot_mapping) - 5} more")

if __name__ == "__main__":
    main()