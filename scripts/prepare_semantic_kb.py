from sqlalchemy import (
    select,
    text,
)

from app.config import settings
from app.db.models import (
    Document,
    DocumentChunk,
)
from app.db.session import (
    SessionLocal,
    engine,
)
from app.services.embeddings import (
    embed_documents,
)


def ensure_pgvector_schema() -> None:
    """
    Make the Day-1 database ready for
    semantic retrieval.

    CREATE TABLE / create_all cannot add a
    column to an already-existing table, so
    this small local migration is explicit.
    """

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE EXTENSION "
                "IF NOT EXISTS vector"
            )
        )

        connection.execute(
            text(
                "ALTER TABLE "
                "document_chunks "
                "ADD COLUMN IF NOT EXISTS "
                "embedding vector(768)"
            )
        )


def prepare_embeddings() -> None:
    """
    Generate and store embeddings for all
    existing CloudDesk knowledge chunks.
    """

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    with SessionLocal() as db:
        rows = db.execute(
            select(
                DocumentChunk,
                Document,
            )
            .join(
                Document,
                (
                    Document.document_id
                    == DocumentChunk.document_id
                ),
            )
            .order_by(
                Document.source,
                DocumentChunk.chunk_index,
            )
        ).all()

        if not rows:
            raise RuntimeError(
                "No knowledge-base chunks "
                "were found. Run the seed "
                "script first."
            )

        embedding_inputs = [
            (
                document.title,
                chunk.content,
            )
            for chunk, document
            in rows
        ]

        print(
            "Generating semantic embeddings..."
        )

        embeddings = embed_documents(
            embedding_inputs
        )

        for (
            (chunk, _document),
            embedding,
        ) in zip(
            rows,
            embeddings,
            strict=True,
        ):
            chunk.embedding = (
                embedding
            )

        db.commit()

        print(
            f"Embedded chunks: {len(rows)}"
        )


def main() -> None:
    print()
    print(
        "========================================"
    )
    print(
        "SupportPilot Semantic KB Preparation"
    )
    print(
        "========================================"
    )

    print(
        "Embedding model: "
        f"{settings.gemini_embedding_model}"
    )

    print(
        "Embedding dimensions: "
        f"{settings.embedding_dimensions}"
    )

    print(
        "Ensuring pgvector schema..."
    )

    ensure_pgvector_schema()

    print(
        "pgvector schema ready."
    )

    prepare_embeddings()

    print()
    print(
        "Semantic knowledge base ready."
    )


if __name__ == "__main__":
    main()