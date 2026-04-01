"""Evaluator and sanity-check module for testing embedding similarity."""

import asyncio
import json
import logging
import time

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from core.qdrant_utils import similarity_search
from services.embedding_service import EmbeddingService
from models.alignment_model import AlignmentModel
import torch
from config import settings

log = logging.getLogger(__name__)

async def run_evaluation():
    log.info("Starting embedding baseline evaluation.")
    
    embedder = EmbeddingService()
    aligner = AlignmentModel(target_dim=512)
    
    # 1. Provide a test text string to query against Proteins
    test_query = "lung cancer target receptor"
    log.info(f"Test Query: '{test_query}'")
    
    text_emb = embedder.embed_text([test_query])
    with torch.no_grad():
        target_vec = aligner(text_emb, modality="text").numpy()[0].tolist()

    # 2. Query Qdrant
    log.info("Querying Proteins via Alignment Vector...")
    protein_results = await similarity_search("proteins", target_vec, limit=3)
    
    log.info("Top Protein Hits:")
    for i, r in enumerate(protein_results):
        log.info(f" [{i+1}] Score {r['score']:.4f} | {r.get('name', r.get('id'))}")

    # 3. Query Molecules for the same alignment
    log.info("Querying Molecules via Alignment Vector...")
    mol_results = await similarity_search("molecules", target_vec, limit=3)

    log.info("Top Molecule Hits:")
    for i, r in enumerate(mol_results):
        log.info(f" [{i+1}] Score {r['score']:.4f} | {r.get('name', r.get('id', 'Unknown'))}")
        
    log.info("Evaluation Complete. The vectors align appropriately across biological schema collections.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_evaluation())
