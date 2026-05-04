"""G3: Unit test — dossier PDF generation.

Tests minimal dossier creation, PDF bytes output, and provenance appendix presence.
"""
from __future__ import annotations
import pytest
from typing import Any, Dict, List, Optional


# ─── Minimal dossier model (self-contained) ─────────────────────────────────

class ProvenanceRecord:
    def __init__(self, source: str, ext_id: str, confidence: float, url: str = ""):
        self.source = source
        self.ext_id = ext_id
        self.confidence = confidence
        self.url = url

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "ext_id": self.ext_id,
            "confidence": self.confidence,
            "url": self.url,
        }


class MinimalDossier:
    """Minimal dossier for PDF export tests."""

    def __init__(self, title: str, target: str, disease: str):
        self.title = title
        self.target = target
        self.disease = disease
        self.sections: List[Dict[str, Any]] = []
        self.provenance: List[ProvenanceRecord] = []

    def add_section(self, heading: str, content: str) -> None:
        self.sections.append({"heading": heading, "content": content})

    def add_provenance(self, prov: ProvenanceRecord) -> None:
        self.provenance.append(prov)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "target": self.target,
            "disease": self.disease,
            "sections": self.sections,
            "provenance": [p.to_dict() for p in self.provenance],
        }


def render_dossier_to_pdf_stub(dossier: MinimalDossier) -> bytes:
    """
    Stub renderer that creates a minimal valid-looking PDF bytes blob.
    In production this would call WeasyPrint or similar.
    """
    doc = dossier.to_dict()
    # Build a deterministic fake PDF for testing
    content_lines = [
        b"%PDF-1.4",
        f"1 0 obj << /Title ({doc['title']}) >>".encode(),
        f"% Target: {doc['target']}".encode(),
        f"% Disease: {doc['disease']}".encode(),
    ]
    for section in doc["sections"]:
        content_lines.append(f"% SECTION: {section['heading']}".encode())
    # Provenance appendix marker
    content_lines.append(b"% APPENDIX: PROVENANCE")
    for prov in doc["provenance"]:
        content_lines.append(f"% PROV: {prov['source']} {prov['ext_id']}".encode())
    content_lines.append(b"%%EOF")
    return b"\n".join(content_lines)


class TestDossierPDF:
    def _make_dossier(self) -> MinimalDossier:
        d = MinimalDossier(title="BRCA1 Target Dossier", target="BRCA1", disease="Breast Cancer")
        d.add_section("Summary", "BRCA1 is a tumor suppressor gene.")
        d.add_section("Evidence", "Multiple GWAS studies confirm association.")
        d.add_provenance(ProvenanceRecord("PubMed", "12345678", 0.95, "https://pubmed.ncbi.nlm.nih.gov/12345678"))
        d.add_provenance(ProvenanceRecord("UniProt", "P38398", 0.98, "https://www.uniprot.org/uniprot/P38398"))
        return d

    def test_render_returns_bytes(self):
        """PDF renderer returns bytes."""
        dossier = self._make_dossier()
        pdf = render_dossier_to_pdf_stub(dossier)
        assert isinstance(pdf, bytes)
        assert len(pdf) > 0

    def test_pdf_starts_with_valid_header(self):
        """PDF output begins with %PDF- header."""
        dossier = self._make_dossier()
        pdf = render_dossier_to_pdf_stub(dossier)
        assert pdf.startswith(b"%PDF-")

    def test_pdf_ends_with_eof(self):
        """PDF output ends with %%EOF marker."""
        dossier = self._make_dossier()
        pdf = render_dossier_to_pdf_stub(dossier)
        assert b"%%EOF" in pdf

    def test_provenance_appendix_present(self):
        """Provenance appendix marker included in PDF output."""
        dossier = self._make_dossier()
        pdf = render_dossier_to_pdf_stub(dossier)
        assert b"APPENDIX: PROVENANCE" in pdf

    def test_all_provenance_sources_in_pdf(self):
        """Each provenance source referenced in PDF appendix."""
        dossier = self._make_dossier()
        pdf = render_dossier_to_pdf_stub(dossier)
        assert b"PubMed" in pdf
        assert b"UniProt" in pdf

    def test_all_sections_referenced(self):
        """All section headings present in PDF."""
        dossier = self._make_dossier()
        pdf = render_dossier_to_pdf_stub(dossier)
        assert b"Summary" in pdf
        assert b"Evidence" in pdf

    def test_title_in_pdf(self):
        """Title included in PDF metadata."""
        dossier = self._make_dossier()
        pdf = render_dossier_to_pdf_stub(dossier)
        assert b"BRCA1 Target Dossier" in pdf

    def test_empty_dossier_still_renders(self):
        """Dossier with no sections/provenance still produces valid PDF bytes."""
        d = MinimalDossier(title="Empty", target="UNKNOWN", disease="UNKNOWN")
        pdf = render_dossier_to_pdf_stub(d)
        assert pdf.startswith(b"%PDF-")
        assert b"%%EOF" in pdf

    def test_dossier_to_dict_structure(self):
        """Dossier serializes to expected dict structure."""
        dossier = self._make_dossier()
        doc = dossier.to_dict()
        assert "title" in doc
        assert "target" in doc
        assert "disease" in doc
        assert "sections" in doc
        assert "provenance" in doc
        assert len(doc["sections"]) == 2
        assert len(doc["provenance"]) == 2
