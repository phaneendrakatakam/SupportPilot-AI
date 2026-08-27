from google import genai
from google.genai import types

from app.config import settings


def _get_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    return genai.Client(
        api_key=settings.gemini_api_key
    )


def prepare_retrieval_query(
    query: str,
) -> str:
    """
    Format a customer support question for
    Gemini Embedding 2 question-answering
    retrieval.

    SupportPilot's knowledge-base queries are
    normally questions that should retrieve
    passages capable of answering them, rather
    than generic search-result matching.
    """

    return (
        "task: question answering | "
        f"query: {query}"
    )


def prepare_retrieval_document(
    title: str | None,
    content: str,
) -> str:
    """
    Format CloudDesk knowledge content for
    asymmetric semantic retrieval.
    """

    safe_title = (
        title
        if title
        else "none"
    )

    return (
        f"title: {safe_title} | "
        f"text: {content}"
    )


def _extract_embedding(
    response,
) -> list[float]:
    embeddings = (
        response.embeddings
        or []
    )

    if not embeddings:
        raise RuntimeError(
            "Gemini returned no embedding."
        )

    values = (
        embeddings[0].values
        or []
    )

    if (
        len(values)
        != settings.embedding_dimensions
    ):
        raise RuntimeError(
            "Unexpected embedding dimension. "
            f"Expected "
            f"{settings.embedding_dimensions}, "
            f"received {len(values)}."
        )

    return [
        float(value)
        for value in values
    ]


def embed_query(
    query: str,
) -> list[float]:
    """
    Generate one semantic question-answering
    query vector.
    """

    client = _get_client()

    prepared_query = (
        prepare_retrieval_query(
            query
        )
    )

    response = (
        client.models.embed_content(
            model=(
                settings
                .gemini_embedding_model
            ),
            contents=prepared_query,
            config=(
                types.EmbedContentConfig(
                    output_dimensionality=(
                        settings
                        .embedding_dimensions
                    )
                )
            ),
        )
    )

    return _extract_embedding(
        response
    )


def embed_documents(
    documents: list[
        tuple[
            str | None,
            str,
        ]
    ],
) -> list[
    list[float]
]:
    """
    Generate separate embeddings for multiple
    knowledge-base documents in one API request.

    Documents use Gemini Embedding 2's
    asymmetric retrieval document format.
    """

    if not documents:
        return []

    client = _get_client()

    contents = [
        types.Content(
            parts=[
                types.Part.from_text(
                    text=(
                        prepare_retrieval_document(
                            title,
                            content,
                        )
                    )
                )
            ]
        )
        for title, content
        in documents
    ]

    response = (
        client.models.embed_content(
            model=(
                settings
                .gemini_embedding_model
            ),
            contents=contents,
            config=(
                types.EmbedContentConfig(
                    output_dimensionality=(
                        settings
                        .embedding_dimensions
                    )
                )
            ),
        )
    )

    embeddings = (
        response.embeddings
        or []
    )

    if (
        len(embeddings)
        != len(documents)
    ):
        raise RuntimeError(
            "Gemini returned an unexpected "
            "number of document embeddings. "
            f"Expected {len(documents)}, "
            f"received {len(embeddings)}."
        )

    result: list[
        list[float]
    ] = []

    for embedding in embeddings:
        values = (
            embedding.values
            or []
        )

        if (
            len(values)
            != settings.embedding_dimensions
        ):
            raise RuntimeError(
                "Unexpected embedding dimension. "
                f"Expected "
                f"{settings.embedding_dimensions}, "
                f"received {len(values)}."
            )

        result.append(
            [
                float(value)
                for value in values
            ]
        )

    return result