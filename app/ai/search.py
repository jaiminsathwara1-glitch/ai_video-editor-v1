"""
Semantic Search for Clips using sentence-transformers.
Computes embeddings for clip content and performs cosine similarity matching.
"""
from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.clip import Clip
import structlog

log = structlog.get_logger(__name__)

# Lazy load model
_model = None

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        log.info("loading_sentence_transformer_model", model_name="all-MiniLM-L6-v2")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    dot = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))

async def semantic_search_clips(db: AsyncSession, query: str, top_k: int = 12) -> list[dict]:
    """Search clips across all projects using semantic vector matching."""
    if not query.strip():
        return []

    model = get_embedding_model()
    query_embedding = model.encode([query])[0]
    
    # Load all clips that have analysis
    result = await db.execute(
        select(Clip)
        .options(joinedload(Clip.analysis))
        .where(Clip.status == "analysed")
    )
    clips = result.unique().scalars().all()
    
    scored_clips = []
    for clip in clips:
        if not clip.analysis:
            continue
            
        tags = " ".join(clip.analysis.tags) if clip.analysis.tags else ""
        summary = clip.analysis.summary or ""
        transcript = clip.analysis.transcript or ""
        
        # Combine the rich metadata into a single text representation
        text_content = f"{summary} {tags} {transcript}".strip()
        if not text_content:
            continue
            
        clip_embedding = model.encode([text_content])[0]
        score = cosine_similarity(query_embedding, clip_embedding)
        
        # Only include relevant matches with a similarity > 0.35
        if score > 0.35:
            scored_clips.append((score, clip))
            
    # Sort descending by similarity score
    scored_clips.sort(key=lambda x: x[0], reverse=True)
    
    return [{"score": score, "clip": clip} for score, clip in scored_clips[:top_k]]
