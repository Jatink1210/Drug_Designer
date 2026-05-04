"""Drug Designer — Connector Registry.

All external data source connectors organized by family.
Each connector extends BaseConnector with: search(), fetch_by_id(),
normalize(), count(), extract_evidence().

Source Family Coverage:
  Literature:      PubMed, Europe PMC, Semantic Scholar, OpenAlex, CrossRef
  Disease/Ontology: DisGeNET, Disease Ontology, HPO
  Target/Protein:  UniProt, AlphaFold, InterPro, Ensembl
  Compounds/Drugs: ChEMBL, PubChem, DrugBank, ChEBI
  Pathways:        KEGG, Reactome, STRING, WikiPathways
  Genetics:        GWAS Catalog, ClinVar, gnomAD
  Interactions:    IntAct, BioGRID
  Clinical:        ClinicalTrials.gov
  Structural:      RCSB PDB
  Other:           OpenTargets, Patents, IndiGen, GenomeAsia, IGVDB
"""
