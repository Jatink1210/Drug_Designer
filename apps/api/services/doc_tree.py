"""Document Intelligence service for hierarchical PageIndex doc trees with FTS5."""

import sqlite3
import os
import uuid
from typing import Dict, Any, List, Optional
import time
import pymupdf  # fits PyMuPDF==1.25.3

from config import settings


def _make_summary(text: str, max_len: int = 200) -> str:
    """Create a sentence-boundary-aware summary truncation."""
    if len(text) <= max_len:
        return text
    # Find the last sentence-ending punctuation before max_len
    for i in range(max_len - 1, max(max_len // 2, 0), -1):
        if text[i] in '.!?':
            return text[:i + 1]
    # Fall back to last space
    last_space = text.rfind(' ', 0, max_len)
    if last_space > max_len // 2:
        return text[:last_space] + "..."
    return text[:max_len] + "..."

class DocTreeService:
    """Manages ingestion of PDFs into a node tree with fast SQLite FTS5 search."""
    
    _db_path = os.path.join(settings.local_store_path, "doctree_index.db")
    
    @classmethod
    def setup_db(cls):
        """Initialize SQLite with FTS5 virtual tables."""
        with sqlite3.connect(cls._db_path) as conn:
            # Main hierarchy mapping table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS doc_nodes (
                    node_id TEXT PRIMARY KEY,
                    doc_id TEXT,
                    parent_id TEXT,
                    title TEXT,
                    page_start INTEGER,
                    page_end INTEGER,
                    summary TEXT,
                    created_at TEXT
                )
            ''')
            # FTS5 Extension Table for fast full-text keyword search
            conn.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS doc_fts USING fts5(
                    node_id, 
                    title, 
                    text_content, 
                    content='doc_nodes'
                )
            ''')
            conn.commit()

    @classmethod
    def ingest_pdf(cls, file_path: str, doc_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Extracts chunks from a PDF. Simulates TOC hierarchy by chunking
        per page and mapping it into the DocTree nodes.
        """
        cls.setup_db()
        doc_gen_id = doc_id or f"doc_{uuid.uuid4().hex[:8]}"
        t0 = time.monotonic()
        
        doc = pymupdf.open(file_path)
        title = doc.metadata.get("title") or os.path.basename(file_path)
        
        nodes_created = 0
        node_inserts = []
        fts_inserts = []
        
        # Simple PageIndex simulation: 1 node per page for rapid search mapping
        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text("text").strip()
            
            if not text:
                continue
                
            node_id = f"node_{uuid.uuid4().hex[:12]}"
            section_title = f"{title} - Page {page_num + 1}"
            
            # Simulated node hierarchy (flat for PageIndex mode)
            node_inserts.append((
                node_id, doc_gen_id, None, section_title, page_num + 1, page_num + 1, 
                _make_summary(text),  # Sentence-boundary-aware summary
                str(time.time())
            ))
            
            fts_inserts.append((node_id, section_title, text))
            nodes_created += 1

        doc.close()

        # Batch insert
        with sqlite3.connect(cls._db_path) as conn:
            conn.executemany(
                "INSERT INTO doc_nodes (node_id, doc_id, parent_id, title, page_start, page_end, summary, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                node_inserts
            )
            # Insert into 'doc_fts' table matching the columns: node_id, title, text_content
            # Note: We must insert into the virtual table directly to populate the FTS index
            conn.executemany(
                "INSERT INTO doc_fts (node_id, title, text_content) VALUES (?, ?, ?)",
                fts_inserts
            )
            conn.commit()
            
        return {
            "doc_id": doc_gen_id,
            "title": title,
            "nodes_indexed": nodes_created,
            "duration_ms": int((time.monotonic() - t0) * 1000)
        }

    @classmethod
    def search_nodes(cls, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Fast full-text search against the FTS5 table, joining back to get page anchors.
        Returns ranked nodes with explicit section paths and page references.
        """
        cls.setup_db()
        results = []
        
        # SQLite FTS5 Match syntax wrapper snippet 
        # (escaping quotes for safety in simple simulation)
        safe_query = query.replace('"', '').replace("'", "")
        
        with sqlite3.connect(cls._db_path) as conn:
            conn.row_factory = sqlite3.Row
            # FTS5 ranks implicitly by bm25() score function
            sql = '''
                SELECT 
                    dn.node_id, dn.doc_id, dn.title as section_path, 
                    dn.page_start, dn.page_end, dn.summary,
                    fts.text_content as snippet,
                    bm25(doc_fts) as rank
                FROM doc_fts fts
                JOIN doc_nodes dn ON fts.node_id = dn.node_id
                WHERE doc_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            '''
            # By default FTS MATCH treats separated words as AND terms. 
            # E.g. "type 2 diabetes" needs to be quoted or treated specially for phrase search in production.
            # Here we wrap the safe query in quotes to simulate a phrase search for the test snippet.
            phrase_query = f'"{safe_query}"'
            
            # Fallback to pure token match if phrase fails
            try:
                rows = conn.execute(sql, (phrase_query, limit)).fetchall()
                if not rows:
                     rows = conn.execute(sql, (safe_query, limit)).fetchall()
            except sqlite3.OperationalError:
                # Fallback if the FTS query parsing fails on special characters
                return []
                
            for row in rows:
                results.append(dict(row))
                
        return results

    @classmethod
    def clear_index(cls):
        """Wipes the entire document tree index."""
        cls.setup_db()
        with sqlite3.connect(cls._db_path) as conn:
            conn.execute("DELETE FROM doc_nodes")
            conn.execute("DELETE FROM doc_fts")
            conn.commit()
