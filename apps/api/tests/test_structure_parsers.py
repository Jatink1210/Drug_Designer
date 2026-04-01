"""Tests for structure_service.py — parser methods (no external API calls)."""
from __future__ import annotations

from services.structure_service import StructureService


def _svc():
    """Create a StructureService instance for accessing parser methods."""
    return StructureService()


def test_parse_polymer_entities():
    svc = _svc()
    data = [
        {
            "rcsb_id": "1ABC_1",
            "entity_poly": {
                "type": "polypeptide(L)",
                "pdbx_strand_id": "A,B",
                "rcsb_sample_sequence_length": 250,
                "pdbx_seq_one_letter_code_can": "MVLSPADKTNVKAAWG",
            },
            "rcsb_entity_source_organism": [{"ncbi_scientific_name": "Homo sapiens"}],
            "rcsb_polymer_entity_container_identifiers": {"uniprot_ids": ["P12345"]},
            "rcsb_gene_name": [{"value": "HBA1"}],
            "rcsb_polymer_entity": {"pdbx_description": "Hemoglobin subunit alpha"},
        }
    ]
    result = svc._parse_polymer_entities(data)
    assert len(result) == 1
    entity = result[0]
    assert entity["entity_id"] == "1ABC_1"
    assert entity["type"] == "polypeptide(L)"
    assert entity["chains"] == ["A", "B"]
    assert entity["length"] == 250
    assert entity["organism"] == "Homo sapiens"
    assert "P12345" in entity["uniprot_ids"]
    assert "HBA1" in entity["gene_names"]


def test_parse_nonpolymer_entities():
    svc = _svc()
    data = [
        {
            "rcsb_id": "1ABC_HEM",
            "rcsb_nonpolymer_entity": {
                "pdbx_description": "PROTOPORPHYRIN IX CONTAINING FE",
                "formula_weight": 616.5,
            },
        }
    ]
    result = svc._parse_nonpolymer_entities(data)
    assert len(result) == 1
    ligand = result[0]
    assert ligand["comp_id"] == "HEM"
    assert ligand["name"] == "PROTOPORPHYRIN IX CONTAINING FE"
    assert ligand["type"] == "ligand"


def test_parse_assemblies():
    svc = _svc()
    data = [
        {
            "rcsb_id": "1ABC-1",
            "rcsb_assembly_info": {"polymer_entity_count": 4},
            "rcsb_struct_symmetry": [{"oligomeric_state": "Homo 4-mer", "kind": "Global Symmetry"}],
        }
    ]
    result = svc._parse_assemblies(data)
    assert len(result) == 1
    asm = result[0]
    assert asm["assembly_id"] == "1"
    assert asm["polymer_entity_count"] == 4
    assert asm["oligomeric_state"] == "Homo 4-mer"


def test_extract_organism():
    svc = _svc()
    entry = {
        "rcsb_entry_info": {},
        "polymer_entities": [
            {"rcsb_entity_source_organism": [{"ncbi_scientific_name": "Homo sapiens"}]},
        ],
    }
    assert svc._extract_organism(entry) == "Homo sapiens"


def test_extract_expression_system():
    svc = _svc()
    entry = {
        "polymer_entities": [
            {"rcsb_entity_host_organism": [{"ncbi_scientific_name": "Escherichia coli"}]},
        ],
    }
    assert svc._extract_expression_system(entry) == "Escherichia coli"
