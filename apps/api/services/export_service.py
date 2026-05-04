"""Export service for scientific reference formats.

Generates RIS (Research Information Systems) and BibTeX exports
for import into Zotero, Mendeley, EndNote, etc.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List


def generate_ris(papers: List[Dict[str, Any]], query: str = "") -> str:
    """Generate RIS format string from paper list.

    RIS format: https://en.wikipedia.org/wiki/RIS_(file_format)
    Compatible with: Zotero, Mendeley, EndNote, Papers, RefWorks.
    """
    lines = []
    for paper in papers:
        lines.append("TY  - JOUR")  # Journal article

        title = paper.get("title", "")
        if title:
            lines.append(f"TI  - {title}")
            lines.append(f"T1  - {title}")

        # Authors
        authors = paper.get("authors", [])
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",")]
        for author in authors[:10]:
            if author:
                lines.append(f"AU  - {author}")

        # Year
        year = paper.get("year")
        if year:
            lines.append(f"PY  - {year}///")
            lines.append(f"DA  - {year}///")

        # Journal
        journal = paper.get("journal", "")
        if journal:
            lines.append(f"JO  - {journal}")
            lines.append(f"T2  - {journal}")

        # Abstract
        abstract = paper.get("abstract", paper.get("snippet", paper.get("summary", "")))
        if abstract:
            lines.append(f"AB  - {abstract[:2000]}")

        # DOI
        doi = paper.get("doi", "")
        if doi:
            clean_doi = doi.replace("https://doi.org/", "").strip()
            if clean_doi:
                lines.append(f"DO  - {clean_doi}")

        # PMID
        pmid = paper.get("pmid", "")
        if pmid:
            lines.append(f"AN  - PMID:{pmid}" if not str(pmid).startswith("PMID:") else f"AN  - {pmid}")

        # URL
        url = paper.get("url", "")
        if url:
            lines.append(f"UR  - {url}")

        # Keywords from query
        if query:
            for kw in query.split()[:5]:
                if len(kw) > 2:
                    lines.append(f"KW  - {kw}")

        # Database
        source = ""
        prov = paper.get("provenance", [])
        if prov and isinstance(prov, list) and prov:
            source = prov[0].get("source", "DrugDesigner")
        lines.append(f"DB  - {source or 'DrugDesigner'}")
        lines.append(f"N1  - Source: {source or 'DrugDesigner'}")

        lines.append("ER  - ")
        lines.append("")

    return "\n".join(lines)


def generate_bibtex(papers: List[Dict[str, Any]]) -> str:
    """Generate BibTeX format string from paper list.

    Compatible with: LaTeX, Zotero, Mendeley, JabRef, Overleaf.
    """
    entries = []

    for i, paper in enumerate(papers):
        # Build citation key
        authors = paper.get("authors", [])
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",")]

        first_author = ""
        if authors:
            # Extract last name
            parts = authors[0].split()
            first_author = parts[-1] if parts else "Unknown"
        else:
            first_author = "Unknown"

        year = paper.get("year", "0000")
        # Sanitize for BibTeX key
        key = re.sub(r"[^a-zA-Z0-9]", "", first_author) + str(year)
        if not key[0].isalpha():
            key = "ref" + key

        # Avoid duplicate keys
        key = f"{key}_{i}"

        title = paper.get("title", "")
        journal = paper.get("journal", "")
        doi = paper.get("doi", "").replace("https://doi.org/", "")
        pmid = paper.get("pmid", "")
        url = paper.get("url", "")
        abstract = paper.get("abstract", paper.get("snippet", paper.get("summary", "")))

        # Format authors for BibTeX: "Last1, First1 and Last2, First2"
        bibtex_authors = " and ".join(authors[:10]) if authors else "Unknown"

        entry = f"@article{{{key},\n"
        entry += f"  title = {{{_escape_bibtex(title)}}},\n"
        entry += f"  author = {{{_escape_bibtex(bibtex_authors)}}},\n"
        if year:
            entry += f"  year = {{{year}}},\n"
        if journal:
            entry += f"  journal = {{{_escape_bibtex(journal)}}},\n"
        if doi:
            entry += f"  doi = {{{doi}}},\n"
        if pmid:
            entry += f"  pmid = {{{pmid}}},\n"
        if url:
            entry += f"  url = {{{url}}},\n"
        if abstract:
            entry += f"  abstract = {{{_escape_bibtex(abstract[:1000])}}},\n"
        entry += "}"

        entries.append(entry)

    return "\n\n".join(entries)


def _escape_bibtex(text: str) -> str:
    """Escape special BibTeX characters."""
    if not text:
        return ""
    # Escape: & % $ # _ { } ~ ^
    for char in ("&", "%", "$", "#", "_", "{", "}", "~", "^"):
        text = text.replace(char, "\\" + char)
    return text


def papers_to_csv(papers: List[Dict[str, Any]]) -> str:
    """Generate CSV from papers with literature-specific columns."""
    cols = ["sno", "id", "doi", "title", "authors", "year", "journal",
            "summary", "citation_count", "pmid", "url", "methodology_context"]

    lines = [",".join(cols)]
    for i, p in enumerate(papers):
        row = []
        for col in cols:
            val = p.get(col, "")
            if col == "sno":
                val = str(i + 1)
            s = str(val) if val is not None else ""
            # Escape CSV
            if "," in s or '"' in s or "\n" in s:
                s = '"' + s.replace('"', '""') + '"'
            row.append(s)
        lines.append(",".join(row))

    return "\n".join(lines)
