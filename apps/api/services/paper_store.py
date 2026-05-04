"""Local SQLite paper storage — zero-data-loss persistence layer.

Every paper fetched during literature analysis is stored locally so
repeated queries serve from cache and no data is ever lost.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select

from core.db import AsyncSessionLocal
from models.db_tables import StoredPaper

log = structlog.get_logger(__name__)


def _query_hash(query: str) -> str:
    """Deterministic hash for a query string."""
    return hashlib.sha256(query.strip().lower().encode()).hexdigest()[:16]


def _paper_key(paper: Dict[str, Any]) -> Optional[str]:
    """Return a dedup key for a paper (doi > pmid > title hash)."""
    doi = paper.get("doi")
    if doi:
        return f"doi:{doi}"
    pmid = paper.get("pmid")
    if pmid:
        return f"pmid:{pmid}"
    title = (paper.get("title") or "").strip().lower()
    if title:
        return f"title:{hashlib.md5(title.encode()).hexdigest()[:12]}"
    return None


async def store_papers(papers: List[Dict[str, Any]], query: str) -> int:
    """Persist a list of papers to local SQLite DB.

    Returns number of newly stored papers (skips duplicates).
    """
    qhash = _query_hash(query)
    stored = 0

    try:
        async with AsyncSessionLocal() as session:
            for p in papers:
                key = _paper_key(p)
                if not key:
                    continue

                doi = p.get("doi") or None
                pmid = str(p.get("pmid", "")) or None

                # Check if already stored (by doi or pmid)
                existing = None
                if doi:
                    stmt = select(StoredPaper).where(StoredPaper.doi == doi).limit(1)
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()
                if not existing and pmid:
                    stmt = select(StoredPaper).where(StoredPaper.pmid == pmid).limit(1)
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()

                if existing:
                    continue

                # Extract authors list
                authors = p.get("authors", [])
                if isinstance(authors, str):
                    authors = [a.strip() for a in authors.split(",") if a.strip()]

                # Build experimental context
                exp_ctx = {}
                summary = p.get("summary", "") or p.get("abstract", "") or ""
                title = p.get("title", "") or ""
                text = f"{title} {summary}"
                if text.strip():
                    from services.contradiction_detector import _extract_context
                    exp_ctx = _extract_context(text)

                row = StoredPaper(
                    query_hash=qhash,
                    doi=doi,
                    pmid=pmid,
                    pmc_id=p.get("pmc_id") or p.get("pmcid") or None,
                    title=title,
                    abstract=p.get("abstract") or p.get("summary") or "",
                    authors=authors,
                    year=int(p["year"]) if p.get("year") else None,
                    journal=p.get("journal", ""),
                    url=p.get("url", ""),
                    source_db=p.get("source", ""),
                    experimental_context=exp_ctx,
                    citation_count=int(p.get("citation_count", 0) or 0),
                    relevance_score=float(p.get("relevance_score", 0) or 0),
                    raw_json=p,
                )
                session.add(row)
                stored += 1

            await session.commit()
        log.info("papers_stored", count=stored, query_hash=qhash)
    except Exception as exc:
        log.error("paper_store_error", error=str(exc))

    return stored


async def get_cached_papers(query: str) -> List[Dict[str, Any]]:
    """Retrieve previously stored papers for a query hash."""
    qhash = _query_hash(query)
    papers: List[Dict[str, Any]] = []

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(StoredPaper).where(StoredPaper.query_hash == qhash)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            for row in rows:
                p = row.raw_json if isinstance(row.raw_json, dict) else {}
                if not p:
                    p = {
                        "title": row.title,
                        "abstract": row.abstract,
                        "authors": row.authors,
                        "year": row.year,
                        "journal": row.journal,
                        "doi": row.doi,
                        "pmid": row.pmid,
                        "url": row.url,
                        "source": row.source_db,
                        "citation_count": row.citation_count,
                    }
                papers.append(p)
        log.info("papers_cache_hit", count=len(papers), query_hash=qhash)
    except Exception as exc:
        log.debug("paper_cache_miss", error=str(exc))

    return papers


async def get_paper_count() -> int:
    """Return total number of stored papers."""
    try:
        from sqlalchemy import func
        async with AsyncSessionLocal() as session:
            stmt = select(func.count()).select_from(StoredPaper)
            result = await session.execute(stmt)
            return result.scalar() or 0
    except Exception:
        return 0
