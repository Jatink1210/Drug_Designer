"""Bulk project export service for complete project archives."""

from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger()


class BulkProjectExporter:
    """
    Bulk project exporter for complete project archives.
    
    Creates ZIP archives containing all project data including:
    - Project metadata
    - Dossiers (PDF/DOCX)
    - Molecule candidates (SDF)
    - Raw data (JSON/CSV)
    - Analysis results
    - Provenance records
    """
    
    def __init__(
        self,
        output_path: str,
        project_id: str
    ):
        """
        Initialize bulk exporter.
        
        Args:
            output_path: Path to output ZIP file
            project_id: Project identifier
        """
        self.output_path = output_path
        self.project_id = project_id
        
        log.info("bulk_exporter_initialized", output_path=output_path, project_id=project_id)
    
    def export_project(
        self,
        project_data: Dict[str, Any],
        include_raw_data: bool = True,
        include_dossiers: bool = True,
        include_molecules: bool = True,
        include_provenance: bool = True
    ) -> str:
        """
        Export complete project to ZIP archive.
        
        Args:
            project_data: Complete project data
            include_raw_data: Include raw data files
            include_dossiers: Include generated dossiers
            include_molecules: Include molecule candidates
            include_provenance: Include provenance records
            
        Returns:
            Path to generated ZIP file
        """
        try:
            with zipfile.ZipFile(self.output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add project metadata
                self._add_project_metadata(zipf, project_data)
                
                # Add README
                self._add_readme(zipf, project_data)
                
                # Add dossiers
                if include_dossiers and 'dossiers' in project_data:
                    self._add_dossiers(zipf, project_data['dossiers'])
                
                # Add molecules
                if include_molecules and 'molecules' in project_data:
                    self._add_molecules(zipf, project_data['molecules'])
                
                # Add raw data
                if include_raw_data and 'raw_data' in project_data:
                    self._add_raw_data(zipf, project_data['raw_data'])
                
                # Add analysis results
                if 'analysis_results' in project_data:
                    self._add_analysis_results(zipf, project_data['analysis_results'])
                
                # Add provenance
                if include_provenance and 'provenance' in project_data:
                    self._add_provenance(zipf, project_data['provenance'])
            
            log.info("bulk_export_complete", output_path=self.output_path)
            return self.output_path
            
        except Exception as e:
            log.error("bulk_export_failed", error=str(e))
            raise
    
    def _add_project_metadata(
        self,
        zipf: zipfile.ZipFile,
        project_data: Dict[str, Any]
    ) -> None:
        """Add project metadata to archive."""
        metadata = {
            "project_id": self.project_id,
            "project_name": project_data.get('name', ''),
            "description": project_data.get('description', ''),
            "created_at": project_data.get('created_at', ''),
            "updated_at": project_data.get('updated_at', ''),
            "export_date": datetime.now().isoformat(),
            "version": "1.0"
        }
        
        zipf.writestr(
            "project_metadata.json",
            json.dumps(metadata, indent=2)
        )
    
    def _add_readme(
        self,
        zipf: zipfile.ZipFile,
        project_data: Dict[str, Any]
    ) -> None:
        """Add README file to archive."""
        readme_content = f"""# {project_data.get('name', 'Project')} Export

## Project Information
- **Project ID:** {self.project_id}
- **Export Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Description:** {project_data.get('description', 'N/A')}

## Archive Contents

### /dossiers/
Contains generated scientific dossiers in PDF and DOCX formats.

### /molecules/
Contains molecule candidates in SDF format for use with chemistry software.

### /raw_data/
Contains raw experimental and computational data in JSON and CSV formats.

### /analysis_results/
Contains analysis results including pathway analysis, target ranking, and predictions.

### /provenance/
Contains provenance records and MAV consensus traces for reproducibility.

## Usage

1. Extract the archive to your desired location
2. Review project_metadata.json for project details
3. Open dossiers with PDF/Word viewers
4. Import molecules into chemistry software (RDKit, ChemDraw, PyMOL)
5. Analyze raw data with your preferred tools

## Support

For questions or issues, please contact the Drug Designer support team.
"""
        
        zipf.writestr("README.md", readme_content)
    
    def _add_dossiers(
        self,
        zipf: zipfile.ZipFile,
        dossiers: List[Dict[str, Any]]
    ) -> None:
        """Add dossiers to archive."""
        for i, dossier in enumerate(dossiers):
            dossier_id = dossier.get('id', f'dossier_{i}')
            
            # Add PDF if available
            if 'pdf_path' in dossier and os.path.exists(dossier['pdf_path']):
                zipf.write(
                    dossier['pdf_path'],
                    f"dossiers/{dossier_id}.pdf"
                )
            
            # Add DOCX if available
            if 'docx_path' in dossier and os.path.exists(dossier['docx_path']):
                zipf.write(
                    dossier['docx_path'],
                    f"dossiers/{dossier_id}.docx"
                )
            
            # Add metadata
            zipf.writestr(
                f"dossiers/{dossier_id}_metadata.json",
                json.dumps(dossier.get('metadata', {}), indent=2)
            )
    
    def _add_molecules(
        self,
        zipf: zipfile.ZipFile,
        molecules: List[Dict[str, Any]]
    ) -> None:
        """Add molecules to archive."""
        # Add SDF file
        if molecules:
            from services.exports.sdf_exporter import SDFMoleculeExporter
            
            temp_sdf = f"/tmp/{self.project_id}_molecules.sdf"
            exporter = SDFMoleculeExporter(temp_sdf)
            
            try:
                exporter.export_molecules_simple(molecules)
                zipf.write(temp_sdf, "molecules/candidates.sdf")
                os.remove(temp_sdf)
            except Exception as e:
                log.warning("molecule_export_failed", error=str(e))
        
        # Add molecule list as JSON
        zipf.writestr(
            "molecules/molecule_list.json",
            json.dumps(molecules, indent=2)
        )
    
    def _add_raw_data(
        self,
        zipf: zipfile.ZipFile,
        raw_data: Dict[str, Any]
    ) -> None:
        """Add raw data to archive."""
        for data_type, data_content in raw_data.items():
            filename = f"raw_data/{data_type}.json"
            zipf.writestr(
                filename,
                json.dumps(data_content, indent=2)
            )
    
    def _add_analysis_results(
        self,
        zipf: zipfile.ZipFile,
        analysis_results: Dict[str, Any]
    ) -> None:
        """Add analysis results to archive."""
        zipf.writestr(
            "analysis_results/results.json",
            json.dumps(analysis_results, indent=2)
        )
    
    def _add_provenance(
        self,
        zipf: zipfile.ZipFile,
        provenance: Dict[str, Any]
    ) -> None:
        """Add provenance records to archive."""
        # Add consensus traces
        if 'consensus_traces' in provenance:
            zipf.writestr(
                "provenance/consensus_traces.json",
                json.dumps(provenance['consensus_traces'], indent=2)
            )
        
        # Add evidence records
        if 'evidence_records' in provenance:
            zipf.writestr(
                "provenance/evidence_records.json",
                json.dumps(provenance['evidence_records'], indent=2)
            )
        
        # Add audit trail
        if 'audit_trail' in provenance:
            zipf.writestr(
                "provenance/audit_trail.json",
                json.dumps(provenance['audit_trail'], indent=2)
            )
