import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google import genai
from google.genai import types
from sqlalchemy import select

from app.config import settings
from app.db.models import DocumentChunk
from app.db.schema import ensure_schema
from app.db.session import SessionLocal


def _document_content(
    text: str,
) -> types.Content:
    """
    Wrap one knowledge-base document as one Gemini Content object.

    Gemini embedding models can aggregate a list of primitive parts into
    one embedding. Using one Content object per knowledge chunk makes the
    intended one-chunk-to-one-embedding relationship explicit.
    """
    return types.Content(
        role="user",
        parts=[
            types.Part.from_text(
                text=text,
            )
        ],
    )


def embed_knowledge(
    force: bool = False,
) -> int:
    ensure_schema()

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is required to create knowledge embeddings."
        )

    with SessionLocal() as db:
        chunks = list(
            db.scalars(
                select(
                    DocumentChunk
                ).order_by(
                    DocumentChunk.chunk_index,
                    DocumentChunk.chunk_id,
                )
            ).all()
        )

        if not force:
            chunks = [
                item
                for item in chunks
                if item.embedding is None
            ]

        if not chunks:
            print(
                "Knowledge embeddings are already up to date."
            )
            return 0

        client = genai.Client(
            api_key=settings.gemini_api_key
        )

        response = client.models.embed_content(
            model=settings.gemini_embedding_model,
            contents=[
                _document_content(
                    item.content
                )
                for item in chunks
            ],
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=(
                    settings.embedding_dimensions
                ),
            ),
        )

        embeddings = (
            response.embeddings
            or []
        )

        if len(
            embeddings
        ) != len(
            chunks
        ):
            raise RuntimeError(
                (
                    "Gemini returned an unexpected number of embeddings: "
                    f"expected {len(chunks)}, received {len(embeddings)}."
                )
            )

        for (
            chunk,
            embedding,
        ) in zip(
            chunks,
            embeddings,
            strict=True,
        ):
            if not embedding.values:
                raise RuntimeError(
                    (
                        "Gemini returned an empty embedding "
                        f"for knowledge chunk {chunk.chunk_id}."
                    )
                )

            values = list(
                embedding.values
            )

            if len(
                values
            ) != settings.embedding_dimensions:
                raise RuntimeError(
                    (
                        "Gemini returned an unexpected embedding dimension "
                        f"for knowledge chunk {chunk.chunk_id}: "
                        f"expected {settings.embedding_dimensions}, "
                        f"received {len(values)}."
                    )
                )

            chunk.embedding = (
                values
            )

        db.commit()

        count = len(
            chunks
        )

    print(
        f"Embedded {count} knowledge chunk(s)."
    )

    return count


if __name__ == "__main__":
    embed_knowledge()
