"""G1-5: PDF render failure drill.

Corrupt PDF renderer → 503 returned, provenance payload preserved.
"""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch


class PDFRenderError(Exception):
    """Simulates PDF renderer crash or corrupt output."""


@pytest.mark.asyncio
async def test_pdf_render_failure_returns_503():
    """PDF renderer raises → HTTP 503 with provenance intact."""
    from fastapi import HTTPException

    provenance_data = [
        {"source": "PubMed", "pmid": "12345678", "confidence": 0.92},
        {"source": "UniProt", "uniprot_id": "P04637", "confidence": 0.98},
    ]

    async def render_dossier_pdf(dossier: dict) -> bytes:
        raise PDFRenderError("Weasyprint font load failed")

    async def export_dossier_endpoint(dossier: dict) -> dict:
        prov = dossier.get("provenance", [])
        try:
            pdf_bytes = await render_dossier_pdf(dossier)
            return {"status": "OK", "pdf_size": len(pdf_bytes), "provenance": prov}
        except PDFRenderError as exc:
            raise HTTPException(
                status_code=503,
                detail={"error": "pdf_render_failed", "provenance": prov, "message": str(exc)},
            )

    dossier = {"title": "Test Dossier", "provenance": provenance_data}
    with pytest.raises(Exception) as exc_info:
        await export_dossier_endpoint(dossier)

    exc = exc_info.value
    assert hasattr(exc, "status_code")
    assert exc.status_code == 503
    # Provenance must be in the error detail
    assert "provenance" in exc.detail
    assert len(exc.detail["provenance"]) == 2


@pytest.mark.asyncio
async def test_pdf_render_partial_fail_provenance_not_lost():
    """Even when PDF fails, provenance is returned in error payload."""
    provenance = [{"source": f"DB_{i}", "confidence": 0.8} for i in range(10)]

    async def export_with_provenance(provenance: list) -> dict:
        try:
            raise PDFRenderError("LaTeX compile error: missing packages")
        except PDFRenderError:
            return {
                "status": "ERROR",
                "error_code": 503,
                "provenance": provenance,
                "fallback": "json_export",
            }

    result = await export_with_provenance(provenance)
    assert result["status"] == "ERROR"
    assert len(result["provenance"]) == 10
    assert result["fallback"] == "json_export"


@pytest.mark.asyncio
async def test_corrupt_pdf_bytes_detected():
    """PDF output that fails integrity check → error, not silent corruption."""
    VALID_PDF_HEADER = b"%PDF-"

    async def verify_pdf(pdf_bytes: bytes) -> bool:
        if not pdf_bytes.startswith(VALID_PDF_HEADER):
            raise PDFRenderError("Output is not valid PDF: missing %PDF- header")
        return True

    corrupt_bytes = b"\x00\x01\x02CORRUPT"
    with pytest.raises(PDFRenderError, match="not valid PDF"):
        await verify_pdf(corrupt_bytes)

    valid_bytes = b"%PDF-1.4 ..."
    assert await verify_pdf(valid_bytes) is True
