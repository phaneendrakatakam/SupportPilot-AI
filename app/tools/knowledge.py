from google import genai
from google.genai import types
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.schemas import KnowledgePassage, KnowledgeSearchInput, KnowledgeSearchResult
from app.config import settings
from app.db.models import Document, DocumentChunk


def _embed_query(query: str) -> list[float]:
    if not settings.gemini_api_key:
        raise RuntimeError("Gemini API key is not configured.")

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=settings.embedding_dimensions,
        ),
    )

    if not response.embeddings or not response.embeddings[0].values:
        raise RuntimeError("Gemini returned no query embedding.")

    return list(response.embeddings[0].values)


def search_knowledge_base(
    db: Session,
    payload: KnowledgeSearchInput,
) -> KnowledgeSearchResult:
    embedded_count = db.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.embedding.is_not(None))
    )

    if not embedded_count:
        return KnowledgeSearchResult(
            status="NOT_READY",
            results=[],
            retrieval_mode=f"semantic-pgvector-{settings.gemini_embedding_model}",
            error="Knowledge embeddings are not ready. Run scripts/bootstrap.py --embed.",
        )

    try:
        query_embedding = _embed_query(payload.query)
    except Exception as exc:
        return KnowledgeSearchResult(
            status="ERROR",
            results=[],
            retrieval_mode=f"semantic-pgvector-{settings.gemini_embedding_model}",
            error=f"{type(exc).__name__}: {exc}",
        )

    distance = DocumentChunk.embedding.cosine_distance(query_embedding)

    rows = db.execute(
        select(DocumentChunk, Document, distance.label("distance"))
        .join(Document, Document.document_id == DocumentChunk.document_id)
        .where(DocumentChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(payload.top_k)
    ).all()

    results = []
    for chunk, document, raw_distance in rows:
        score = max(0.0, min(1.0, 1.0 - float(raw_distance)))
        if score < settings.knowledge_min_score:
            continue
        results.append(
            KnowledgePassage(
                content=chunk.content,
                source=document.source,
                score=round(score, 4),
            )
        )

    if not results:
        return KnowledgeSearchResult(
            status="NOT_FOUND",
            results=[],
            retrieval_mode=f"semantic-pgvector-{settings.gemini_embedding_model}",
            error="No sufficiently relevant documentation was found.",
        )

    return KnowledgeSearchResult(
        status="SUCCESS",
        results=results,
        retrieval_mode=f"semantic-pgvector-{settings.gemini_embedding_model}",
        error=None,
    )
