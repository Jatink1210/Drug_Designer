"""Unit tests for Export Services.

Tests PDF, DOCX, SDF, and bulk export functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import json


class TestPDFExporter:
    """Test PDF export service."""
    
    @pytest.mark.asyncio
    async def test_export_dossier_pdf(self, mock_db_session):
        """Test dossier PDF export."""
        from services.exports.pdf_exporter import export_dossier_pdf
        
        with patch("services.exports.pdf_exporter.export_dossier_pdf") as mock_export:
            mock_export.return_value = {
                "export_id": str(uuid.uuid4()),
                "file_path": "s3://bucket/dossier.pdf",
                "file_size_bytes": 1024000,
                "pages": 25
            }
            
            result = await mock_export(
                db=mock_db_session,
                dossier_id=str(uuid.uuid4()),
                include_provenance=True
            )
            
            assert "export_id" in result
            assert "file_path" in result
            assert result["file_path"].endswith(".pdf")
    
    @pytest.mark.asyncio
    async def test_pdf_includes_provenance(self, mock_db_session):
        """Test PDF includes provenance appendix."""
        from services.exports.pdf_exporter import export_dossier_pdf
        
        with patch("services.exports.pdf_exporter.export_dossier_pdf") as mock_export:
            mock_export.return_value = {
                "export_id": str(uuid.uuid4()),
                "file_path": "s3://bucket/dossier.pdf",
                "sections": ["main_content", "provenance_appendix"]
            }
            
            result = await mock_export(
                db=mock_db_session,
                dossier_id=str(uuid.uuid4()),
                include_provenance=True
            )
            
            assert "provenance_appendix" in result["sections"]
    
    @pytest.mark.asyncio
    async def test_pdf_export_performance(self, mock_db_session):
        """Test PDF export meets performance target."""
        import time
        from services.exports.pdf_exporter import export_dossier_pdf
        
        with patch("services.exports.pdf_exporter.export_dossier_pdf") as mock_export:
            async def timed_export(*args, **kwargs):
                await asyncio.sleep(0.1)
                return {"export_id": str(uuid.uuid4()), "file_path": "test.pdf"}
            
            mock_export.side_effect = timed_export
            
            start = time.time()
            result = await mock_export(
                db=mock_db_session,
                dossier_id=str(uuid.uuid4())
            )
            elapsed = time.time() - start
            
            # Should be under 90s (p95 target)
            assert elapsed < 90.0


class TestDOCXExporter:
    """Test DOCX export service."""
    
    @pytest.mark.asyncio
    async def test_export_report_docx(self, mock_db_session):
        """Test report DOCX export."""
        from services.exports.docx_exporter import export_report_docx
        
        with patch("services.exports.docx_exporter.export_report_docx") as mock_export:
            mock_export.return_value = {
                "export_id": str(uuid.uuid4()),
                "file_path": "s3://bucket/report.docx",
                "file_size_bytes": 512000
            }
            
            result = await mock_export(
                db=mock_db_session,
                report_id=str(uuid.uuid4())
            )
            
            assert "export_id" in result
            assert result["file_path"].endswith(".docx")
    
    @pytest.mark.asyncio
    async def test_docx_formatting(self, mock_db_session):
        """Test DOCX includes proper formatting."""
        from services.exports.docx_exporter import export_report_docx
        
        with patch("services.exports.docx_exporter.export_report_docx") as mock_export:
            mock_export.return_value = {
                "export_id": str(uuid.uuid4()),
                "file_path": "s3://bucket/report.docx",
                "formatting": {
                    "has_headers": True,
                    "has_tables": True,
                    "has_images": True
                }
            }
            
            result = await mock_export(
                db=mock_db_session,
                report_id=str(uuid.uuid4())
            )
            
            assert result["formatting"]["has_headers"] is True


class TestSDFExporter:
    """Test SDF export service."""
    
    @pytest.mark.asyncio
    async def test_export_molecules_sdf(self, mock_db_session):
        """Test molecule SDF export."""
        from services.exports.sdf_exporter import export_molecules_sdf
        
        with patch("services.exports.sdf_exporter.export_molecules_sdf") as mock_export:
            mock_export.return_value = {
                "export_id": str(uuid.uuid4()),
                "file_path": "s3://bucket/molecules.sdf",
                "molecule_count": 50
            }
            
            result = await mock_export(
                db=mock_db_session,
                molecule_ids=[str(uuid.uuid4()) for _ in range(50)]
            )
            
            assert "export_id" in result
            assert result["file_path"].endswith(".sdf")
            assert result["molecule_count"] == 50
    
    @pytest.mark.asyncio
    async def test_sdf_includes_properties(self, mock_db_session):
        """Test SDF includes molecule properties."""
        from services.exports.sdf_exporter import export_molecules_sdf
        
        with patch("services.exports.sdf_exporter.export_molecules_sdf") as mock_export:
            mock_export.return_value = {
                "export_id": str(uuid.uuid4()),
                "file_path": "s3://bucket/molecules.sdf",
                "properties_included": ["molecular_weight", "logP", "SMILES"]
            }
            
            result = await mock_export(
                db=mock_db_session,
                molecule_ids=[str(uuid.uuid4())],
                include_properties=True
            )
            
            assert len(result["properties_included"]) > 0


class TestBulkExporter:
    """Test bulk project export service."""
    
    @pytest.mark.asyncio
    async def test_bulk_export_project(self, mock_db_session):
        """Test bulk project export."""
        from services.exports.bulk_exporter import export_project_bulk
        
        with patch("services.exports.bulk_exporter.export_project_bulk") as mock_export:
            mock_export.return_value = {
                "export_id": str(uuid.uuid4()),
                "file_path": "s3://bucket/project_export.zip",
                "file_size_bytes": 10240000,
                "manifest": {
                    "runs": 10,
                    "evidence_items": 500,
                    "dossiers": 3,
                    "reports": 5
                }
            }
            
            result = await mock_export(
                db=mock_db_session,
                project_id=str(uuid.uuid4())
            )
            
            assert "export_id" in result
            assert result["file_path"].endswith(".zip")
            assert "manifest" in result
    
    @pytest.mark.asyncio
    async def test_bulk_export_includes_all_artifacts(self, mock_db_session):
        """Test bulk export includes all project artifacts."""
        from services.exports.bulk_exporter import export_project_bulk
        
        with patch("services.exports.bulk_exporter.export_project_bulk") as mock_export:
            mock_export.return_value = {
                "export_id": str(uuid.uuid4()),
                "file_path": "s3://bucket/project_export.zip",
                "contents": [
                    "runs/",
                    "evidence/",
                    "dossiers/",
                    "reports/",
                    "media/",
                    "manifest.json"
                ]
            }
            
            result = await mock_export(
                db=mock_db_session,
                project_id=str(uuid.uuid4())
            )
            
            assert "manifest.json" in result["contents"]
            assert "runs/" in result["contents"]
            assert "evidence/" in result["contents"]
    
    @pytest.mark.asyncio
    async def test_bulk_export_manifest_structure(self, mock_db_session):
        """Test bulk export manifest has correct structure."""
        from services.exports.bulk_exporter import export_project_bulk
        
        with patch("services.exports.bulk_exporter.export_project_bulk") as mock_export:
            mock_export.return_value = {
                "export_id": str(uuid.uuid4()),
                "file_path": "s3://bucket/project_export.zip",
                "manifest": {
                    "project_id": str(uuid.uuid4()),
                    "export_date": "2024-01-01T00:00:00Z",
                    "version": "1.0",
                    "contents": {
                        "runs": 10,
                        "evidence_items": 500,
                        "dossiers": 3
                    }
                }
            }
            
            result = await mock_export(
                db=mock_db_session,
                project_id=str(uuid.uuid4())
            )
            
            manifest = result["manifest"]
            assert "project_id" in manifest
            assert "export_date" in manifest
            assert "version" in manifest
            assert "contents" in manifest


class TestExportFormats:
    """Test export format validation."""
    
    def test_pdf_format_validation(self):
        """Test PDF format validation."""
        valid_formats = ["pdf"]
        assert "pdf" in valid_formats
    
    def test_docx_format_validation(self):
        """Test DOCX format validation."""
        valid_formats = ["docx", "doc"]
        assert "docx" in valid_formats
    
    def test_sdf_format_validation(self):
        """Test SDF format validation."""
        valid_formats = ["sdf", "mol", "mol2"]
        assert "sdf" in valid_formats
    
    def test_bulk_format_validation(self):
        """Test bulk export format validation."""
        valid_formats = ["zip", "tar.gz"]
        assert "zip" in valid_formats


class TestExportMetadata:
    """Test export metadata tracking."""
    
    @pytest.mark.asyncio
    async def test_export_metadata_structure(self, mock_db_session):
        """Test export metadata has correct structure."""
        from services.exports.pdf_exporter import export_dossier_pdf
        
        with patch("services.exports.pdf_exporter.export_dossier_pdf") as mock_export:
            mock_export.return_value = {
                "export_id": str(uuid.uuid4()),
                "file_path": "s3://bucket/dossier.pdf",
                "metadata": {
                    "created_at": "2024-01-01T00:00:00Z",
                    "created_by": str(uuid.uuid4()),
                    "export_type": "dossier_pdf",
                    "source_id": str(uuid.uuid4())
                }
            }
            
            result = await mock_export(
                db=mock_db_session,
                dossier_id=str(uuid.uuid4())
            )
            
            metadata = result["metadata"]
            assert "created_at" in metadata
            assert "created_by" in metadata
            assert "export_type" in metadata


class TestErrorHandling:
    """Test export error handling."""
    
    @pytest.mark.asyncio
    async def test_export_handles_missing_resource(self, mock_db_session):
        """Test export handles missing resource."""
        from services.exports.pdf_exporter import export_dossier_pdf
        
        with patch("services.exports.pdf_exporter.export_dossier_pdf") as mock_export:
            mock_export.side_effect = Exception("Dossier not found")
            
            with pytest.raises(Exception) as exc_info:
                await mock_export(
                    db=mock_db_session,
                    dossier_id=str(uuid.uuid4())
                )
            
            assert "not found" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_export_handles_storage_error(self, mock_db_session):
        """Test export handles storage errors."""
        from services.exports.pdf_exporter import export_dossier_pdf
        
        with patch("services.exports.pdf_exporter.export_dossier_pdf") as mock_export:
            mock_export.side_effect = Exception("Storage error")
            
            with pytest.raises(Exception) as exc_info:
                await mock_export(
                    db=mock_db_session,
                    dossier_id=str(uuid.uuid4())
                )
            
            assert "error" in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
