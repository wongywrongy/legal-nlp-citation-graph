"""
Local sentence-transformers embedding service.

Loaded lazily so the model (~420 MB for all-mpnet-base-v2) doesn't block
import or test collection. Runs on CPU only — no GPU code paths.

The embedding column on `documents` is a pgvector `vector(768)` in production
and a `LargeBinary` placeholder under sqlite (test only). All similarity
queries here therefore assume a Postgres backend; callers must guard with
`settings.feature_embeddings` and check for sqlite if they support both.

Long-document handling (Phase 1):
    Legal opinions routinely exceed mpnet's 384-token context window.
    `embed_text()` tokenizes the input once, slides a 384-token window with
    a 64-token overlap (320-token stride), embeds each window, mean-pools
    the resulting chunk vectors, and re-normalizes to unit length. Short
    documents (<= 384 tokens) take a single fast path. The output shape and
    callable signature are unchanged from the prior single-pass version.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import Document

logger = structlog.get_logger()


# mpnet's transformer block accepts up to 384 tokens (after [CLS]/[SEP]).
# Allow some headroom for special tokens added at encode time.
_MAX_TOKENS = 380
_STRIDE = 320  # 60-token overlap between successive windows
_MIN_TAIL_TOKENS = 32  # discard the trailing chunk if it's tiny

_model = None
_cross_encoder = None


def get_model():
    """Lazy-load the SentenceTransformer model. Cached for process lifetime."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model", model=settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def get_cross_encoder():
    """
    Lazy-load the cross-encoder used for /api/search re-ranking.

    The cross-encoder model is small (~85 MB for ms-marco-MiniLM-L-6-v2) but
    we still avoid loading it until the first re-rank call so workers that
    only need bi-encoder embeddings don't pay the overhead.
    """
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder

        logger.info("Loading cross-encoder", model=settings.cross_encoder_model)
        _cross_encoder = CrossEncoder(settings.cross_encoder_model)
    return _cross_encoder


def cross_encoder_score(query: str, passages: list[str]) -> list[float]:
    """
    Score (query, passage) pairs with the cross-encoder.

    Returns raw logits — higher is more relevant. The absolute scale isn't
    meaningful; only the ordering is. Callers should sort descending and
    take the top-K.
    """
    if not passages:
        return []
    ce = get_cross_encoder()
    pairs = [(query, p or "") for p in passages]
    scores = ce.predict(pairs, show_progress_bar=False)
    return [float(s) for s in scores]


def _chunk_token_ids(token_ids: list[int]) -> list[list[int]]:
    """
    Slide a `_MAX_TOKENS`-wide window with `_STRIDE` step over the token
    sequence. Drop any trailing chunk shorter than `_MIN_TAIL_TOKENS` so we
    don't bias the mean toward a near-empty fragment.
    """
    if len(token_ids) <= _MAX_TOKENS:
        return [token_ids]
    chunks: list[list[int]] = []
    start = 0
    while start < len(token_ids):
        chunk = token_ids[start : start + _MAX_TOKENS]
        if len(chunk) >= _MIN_TAIL_TOKENS or not chunks:
            chunks.append(chunk)
        if start + _MAX_TOKENS >= len(token_ids):
            break
        start += _STRIDE
    return chunks


def embed_text(text: str) -> List[float]:
    """
    Encode a single document/query string into a 768-d unit vector.

    For inputs longer than mpnet's context window, the text is split into
    overlapping token windows, each chunk is embedded independently, and the
    chunk vectors are mean-pooled and re-normalized. The return type and
    dimensionality are identical to the single-pass implementation, so
    callers don't need to change.

    Returns the vector. Logs `chunks=N elapsed=Xs` so worker output shows
    that the model is doing work for long docs (otherwise it sits silent
    for ~5s on a 30-page opinion and the user thinks it's stuck).
    """
    if not text:
        return []

    import time as _time

    import numpy as np

    started = _time.perf_counter()
    model = get_model()
    tokenizer = model.tokenizer

    # Tokenize once, without special tokens so we control window boundaries.
    token_ids = tokenizer.encode(text, add_special_tokens=False, truncation=False)
    if not token_ids:
        return []

    chunks = _chunk_token_ids(token_ids)

    # Single-chunk fast path — the original behaviour for short queries.
    if len(chunks) == 1:
        vec = model.encode(
            text if len(token_ids) <= _MAX_TOKENS else tokenizer.decode(
                chunks[0], skip_special_tokens=True
            ),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vec.tolist()

    chunk_texts = [tokenizer.decode(ids, skip_special_tokens=True) for ids in chunks]

    # Encode without per-chunk normalization, then mean-pool, then normalize
    # once at the end. Equivalent to averaging in cosine space.
    chunk_vecs = model.encode(
        chunk_texts,
        normalize_embeddings=False,
        show_progress_bar=False,
        batch_size=16,
        convert_to_numpy=True,
    )
    pooled = np.mean(chunk_vecs, axis=0)
    norm = float(np.linalg.norm(pooled))
    if norm > 0:
        pooled = pooled / norm

    elapsed = _time.perf_counter() - started
    if len(chunks) > 1:
        logger.info(
            "embed_text chunked",
            tokens=len(token_ids),
            chunks=len(chunks),
            elapsed_s=round(elapsed, 2),
        )
    return pooled.tolist()


def warmup_models() -> None:
    """Pre-load the bi-encoder (and cross-encoder if enabled) at startup.

    Called from the ARQ worker's `on_startup`. Without this, the first
    document to embed pays a ~5–10 second silent stall while the model
    weights load — which looks identical to "the worker is stuck" in the
    log output. Loading once on boot makes every subsequent job's
    elapsed time honest.
    """
    if not settings.feature_embeddings:
        return
    logger.info("warming embedding model", model=settings.embedding_model)
    get_model()
    if settings.feature_cross_encoder:
        logger.info("warming cross-encoder", model=settings.cross_encoder_model)
        get_cross_encoder()
    logger.info("models warm")


async def top_k_for_document(
    session: AsyncSession,
    doc_id: str,
    k: int = 10,
    min_score: float = 0.0,
) -> List[Tuple[str, float]]:
    """
    Return up to k (other_doc_id, similarity_score) tuples ranked by cosine
    similarity to `doc_id`. Excludes the source document and rows without
    embeddings.
    """
    src_row = await session.execute(
        select(Document.embedding).where(Document.id == doc_id)
    )
    src = src_row.scalar_one_or_none()
    if src is None:
        return []

    distance = Document.embedding.cosine_distance(src)
    rows = await session.execute(
        select(Document.id, distance.label("distance"))
        .where(Document.id != doc_id)
        .where(Document.embedding.isnot(None))
        .order_by("distance")
        .limit(k * 4)  # over-fetch then filter by min_score
    )
    out: List[Tuple[str, float]] = []
    for other_id, dist in rows.all():
        if dist is None:
            continue
        score = max(0.0, min(1.0, 1.0 - float(dist)))
        if score < min_score:
            continue
        out.append((other_id, score))
        if len(out) >= k:
            break
    return out


async def top_k_for_query(
    session: AsyncSession,
    query_vector: List[float],
    k: int = 10,
    min_score: float = 0.0,
) -> List[Tuple[Document, float]]:
    """
    Return up to k (Document, similarity_score) for documents nearest the
    query vector. Used by /api/search.
    """
    if not query_vector:
        return []

    distance = Document.embedding.cosine_distance(query_vector)
    rows = await session.execute(
        select(Document, distance.label("distance"))
        .where(Document.embedding.isnot(None))
        .order_by("distance")
        .limit(k * 4)
    )
    out: List[Tuple[Document, float]] = []
    for document, dist in rows.all():
        if dist is None:
            continue
        score = max(0.0, min(1.0, 1.0 - float(dist)))
        if score < min_score:
            continue
        out.append((document, score))
        if len(out) >= k:
            break
    return out


def is_postgres() -> bool:
    """True when the runtime database supports pgvector queries."""
    return settings.database_url_sync.startswith("postgresql")
