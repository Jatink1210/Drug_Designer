"""PDF export service for scientific dossiers with provenance."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)
from reportlab.platypus.tableofcontents import TableOfContents

log = structlog.get_logger()


class PDFDossierExporter:
    """
    Professional PDF exporter for scientific dossiers.
    
    Generates publication-quality PDF documents with:
    - Automatic table of contents
    - Professional formatting
    - Provenance appendix with MAV consensus traces
    - Citations and references
    """
    
    def __init__(
        self,
        output_path: str,
        title: str,
        author: str = "Drug Designer System"
    ):
        """
        Initialize PDF exporter.
        
        Args:
            output_path: Path to output PDF file
            title: Document title
            author: Document author
        """
        self.output_path = output_path
        self.title = title
        self.author = author
        
        # Create document
        self.doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Story (content elements)
        self.story: List[Any] = []
        
        # Styles
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
        log.info("pdf_exporter_initialized", output_path=output_path)
    
    def _setup_custom_styles(self) -> None:
        """Setup custom paragraph styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=1  # Center
        ))
        
        # Section heading
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            spaceBefore=12
        ))
        
        # Subsection heading
        self.styles.add(ParagraphStyle(
            name='SubsectionHeading',
            parent=self.styles['Heading3'],
            fontSize=14,
            textColor=colors.HexColor('#34495e'),
            spaceAfter=10,
            spaceBefore=10
        ))
        
        # Body text
        self.styles.add(ParagraphStyle(
            name='BodyText',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=14,
            spaceAfter=10
        ))
        
        # Caption
        self.styles.add(ParagraphStyle(
            name='Caption',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=1  # Center
        ))
    
    def add_title_page(
        self,
        subtitle: Optional[str] = None,
        date: Optional[str] = None
    ) -> None:
        """Add title page to document."""
        # Title
        self.story.append(Spacer(1, 2*inch))
        self.story.append(Paragraph(self.title, self.styles['CustomTitle']))
        
        # Subtitle
        if subtitle:
            self.story.append(Spacer(1, 0.2*inch))
            self.story.append(Paragraph(subtitle, self.styles['Heading3']))
        
        # Author and date
        self.story.append(Spacer(1, 0.5*inch))
        self.story.append(Paragraph(f"<b>Author:</b> {self.author}", self.styles['Normal']))
        
        date_str = date or datetime.now().strftime("%B %d, %Y")
        self.story.append(Paragraph(f"<b>Date:</b> {date_str}", self.styles['Normal']))
        
        self.story.append(PageBreak())
    
    def add_table_of_contents(self) -> None:
        """Add table of contents."""
        toc = TableOfContents()
        toc.levelStyles = [
            ParagraphStyle(name='TOCHeading1', fontSize=14, leftIndent=20, spaceBefore=10, spaceAfter=10),
            ParagraphStyle(name='TOCHeading2', fontSize=12, leftIndent=40, spaceBefore=5, spaceAfter=5),
            ParagraphStyle(name='TOCHeading3', fontSize=10, leftIndent=60, spaceBefore=3, spaceAfter=3),
        ]
        
        self.story.append(Paragraph("Table of Contents", self.styles['Heading1']))
        self.story.append(Spacer(1, 0.2*inch))
        self.story.append(toc)
        self.story.append(PageBreak())
    
    def add_section(
        self,
        title: str,
        content: str,
        level: int = 1
    ) -> None:
        """
        Add a section to the document.
        
        Args:
            title: Section title
            content: Section content (HTML supported)
            level: Heading level (1-3)
        """
        # Add heading
        style_name = {
            1: 'SectionHeading',
            2: 'SubsectionHeading',
            3: 'Heading4'
        }.get(level, 'SectionHeading')
        
        self.story.append(Paragraph(title, self.styles[style_name]))
        
        # Add content
        paragraphs = content.split('\n\n')
        for para in paragraphs:
            if para.strip():
                self.story.append(Paragraph(para, self.styles['BodyText']))
                self.story.append(Spacer(1, 0.1*inch))
    
    def add_table(
        self,
        data: List[List[str]],
        caption: Optional[str] = None,
        col_widths: Optional[List[float]] = None
    ) -> None:
        """
        Add a table to the document.
        
        Args:
            data: Table data (list of rows)
            caption: Optional table caption
            col_widths: Optional column widths
        """
        # Create table
        table = Table(data, colWidths=col_widths)
        
        # Style table
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')])
        ]))
        
        self.story.append(table)
        
        # Add caption
        if caption:
            self.story.append(Spacer(1, 0.1*inch))
            self.story.append(Paragraph(caption, self.styles['Caption']))
        
        self.story.append(Spacer(1, 0.2*inch))
    
    def add_provenance_appendix(
        self,
        consensus_traces: List[Dict[str, Any]],
        evidence_records: List[Dict[str, Any]]
    ) -> None:
        """
        Add provenance appendix with MAV consensus traces.
        
        Args:
            consensus_traces: List of MAV consensus voting records
            evidence_records: List of evidence provenance records
        """
        self.story.append(PageBreak())
        self.story.append(Paragraph("Appendix: Provenance and Consensus Traces", self.styles['Heading1']))
        self.story.append(Spacer(1, 0.2*inch))
        
        # MAV Consensus section
        self.story.append(Paragraph("MAV Consensus Voting Records", self.styles['SectionHeading']))
        
        for i, trace in enumerate(consensus_traces, 1):
            self.story.append(Paragraph(f"<b>Consensus {i}:</b> {trace.get('claim', '')}", self.styles['BodyText']))
            
            # Voting results table
            votes = trace.get('votes', [])
            if votes:
                vote_data = [['Agent', 'Vote', 'Reasoning']]
                for vote in votes:
                    vote_data.append([
                        vote.get('agent', ''),
                        vote.get('vote', ''),
                        vote.get('reasoning', '')[:100] + '...' if len(vote.get('reasoning', '')) > 100 else vote.get('reasoning', '')
                    ])
                
                self.add_table(vote_data, caption=f"Voting record for consensus {i}")
            
            self.story.append(Spacer(1, 0.2*inch))
        
        # Evidence provenance section
        self.story.append(PageBreak())
        self.story.append(Paragraph("Evidence Provenance Records", self.styles['SectionHeading']))
        
        for i, evidence in enumerate(evidence_records, 1):
            self.story.append(Paragraph(
                f"<b>Evidence {i}:</b> {evidence.get('source', '')} - {evidence.get('evidence_type', '')}",
                self.styles['BodyText']
            ))
            self.story.append(Paragraph(
                f"Confidence: {evidence.get('confidence', 0):.2f}",
                self.styles['Normal']
            ))
            self.story.append(Paragraph(
                f"URL: {evidence.get('url', '')}",
                self.styles['Normal']
            ))
            self.story.append(Spacer(1, 0.1*inch))
    
    def export_dossier(
        self,
        dossier_data: Dict[str, Any]
    ) -> str:
        """
        Export complete dossier to PDF.
        
        Args:
            dossier_data: Dossier data including sections, tables, and provenance
            
        Returns:
            Path to generated PDF file
        """
        # Add title page
        self.add_title_page(
            subtitle=dossier_data.get('subtitle'),
            date=dossier_data.get('date')
        )
        
        # Add table of contents
        self.add_table_of_contents()
        
        # Add sections
        for section in dossier_data.get('sections', []):
            self.add_section(
                title=section.get('title', ''),
                content=section.get('content', ''),
                level=section.get('level', 1)
            )
            
            # Add tables if present
            for table in section.get('tables', []):
                self.add_table(
                    data=table.get('data', []),
                    caption=table.get('caption'),
                    col_widths=table.get('col_widths')
                )
        
        # Add provenance appendix
        if 'consensus_traces' in dossier_data or 'evidence_records' in dossier_data:
            self.add_provenance_appendix(
                consensus_traces=dossier_data.get('consensus_traces', []),
                evidence_records=dossier_data.get('evidence_records', [])
            )
        
        # Build PDF
        try:
            self.doc.build(self.story)
            log.info("pdf_export_complete", output_path=self.output_path)
            return self.output_path
        except Exception as e:
            log.error("pdf_export_failed", error=str(e))
            raise
