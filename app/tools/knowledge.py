from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from app.agent.schemas import (
    KnowledgePassage,
    KnowledgeSearchInput,
    KnowledgeSearchResult,
)
from app.config import settings
from app.db.models import (
    Document,
    DocumentChunk,
)
from app.services.embeddings import (
    embed_query,
)


RETRIEVAL_MODE = (
    "semantic-pgvector-gemini-embedding-2"
)


def search_knowledge_base(
    db: Session,
    payload: KnowledgeSearchInput,
) -> KnowledgeSearchResult:
    """
    Search CloudDesk support documentation
    using Gemini embeddings + pgvector cosine
    similarity.

    The public tool contract remains unchanged
    from Day 1.
    """

    embedded_chunk_count = db.scalar(
        select(
            func.count(
                DocumentChunk.chunk_id
            )
        ).where(
            DocumentChunk.embedding.is_not(
                None
            )
        )
    )

    if not embedded_chunk_count:
        return KnowledgeSearchResult(
            status="NOT_READY",
            results=[],
            retrieval_mode=(
                RETRIEVAL_MODE
            ),
            error=(
                "Knowledge-base embeddings "
                "have not been prepared."
            ),
        )

    try:
        query_embedding = embed_query(
            payload.query
        )

    except Exception as exc:
        return KnowledgeSearchResult(
            status="ERROR",
            results=[],
            retrieval_mode=(
                RETRIEVAL_MODE
            ),
            error=(
                "Embedding generation failed: "
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        )

    distance_expression = (
        DocumentChunk.embedding
        .cosine_distance(
            query_embedding
        )
    )

    similarity_expression = (
        1.0
        - distance_expression
    ).label(
        "similarity"
    )

    rows = db.execute(
        select(
            DocumentChunk,
            Document,
            similarity_expression,
        )
        .join(
            Document,
            (
                Document.document_id
                == DocumentChunk.document_id
            ),
        )
        .where(
            DocumentChunk.embedding.is_not(
                None
            )
        )
        .order_by(
            distance_expression
        )
        .limit(
            payload.top_k
        )
    ).all()

    matches: list[
        KnowledgePassage
    ] = []

    for (
        chunk,
        document,
        raw_similarity,
    ) in rows:
        if raw_similarity is None:
            continue

        similarity = float(
            raw_similarity
        )

        if (
            similarity
            < settings
            .knowledge_similarity_threshold
        ):
            continue

        safe_score = max(
            0.0,
            min(
                1.0,
                similarity,
            ),
        )

        matches.append(
            KnowledgePassage(
                content=chunk.content,
                source=document.source,
                score=round(
                    safe_score,
                    4,
                ),
            )
        )

    if not matches:
        return KnowledgeSearchResult(
            status="NOT_FOUND",
            results=[],
            retrieval_mode=(
                RETRIEVAL_MODE
            ),
            error=(
                "No sufficiently relevant "
                "CloudDesk support content "
                "was found."
            ),
        )

    return KnowledgeSearchResult(
        status="SUCCESS",
        results=matches,
        retrieval_mode=(
            RETRIEVAL_MODE
        ),
        error=None,
    )