from __future__ import annotations

from typing import Sequence

from app.core.config import get_settings


class EmbeddingServiceError(RuntimeError):
    pass


class EmbeddingServiceUnavailableError(EmbeddingServiceError):
    pass


class EmbeddingServiceUpstreamError(EmbeddingServiceError):
    pass


def _estimate_token_count(text: str) -> int:
    # Rough but safe enough for batching embeddings requests.
    return max(1, len(text) // 4)


def _chunk_texts_for_embeddings(
    *,
    texts: Sequence[str],
    max_items_per_batch: int = 128,
    max_estimated_tokens_per_batch: int = 200_000,
) -> list[list[str]]:
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_tokens = 0

    for text in texts:
        estimated_tokens = _estimate_token_count(text)
        would_exceed_item_limit = len(current_batch) >= max_items_per_batch
        would_exceed_token_limit = current_batch and (
            current_tokens + estimated_tokens > max_estimated_tokens_per_batch
        )

        if would_exceed_item_limit or would_exceed_token_limit:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(text)
        current_tokens += estimated_tokens

    if current_batch:
        batches.append(current_batch)

    return batches


def embed_texts(*, texts: Sequence[str]) -> list[list[float]]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise EmbeddingServiceUnavailableError("OpenAI embeddings are not configured yet.")

    try:
        from openai import APIError, APITimeoutError, OpenAI
    except ImportError as exc:
        raise EmbeddingServiceUnavailableError(
            "The OpenAI client is not installed in this environment."
        ) from exc

    cleaned_texts = [text.strip() for text in texts if text and text.strip()]
    if not cleaned_texts:
        return []

    batches = _chunk_texts_for_embeddings(texts=cleaned_texts)

    client = OpenAI(
        api_key=settings.openai_api_key,
        timeout=max(settings.openai_rag_timeout_seconds, 1),
    )

    all_embeddings: list[list[float]] = []
    for batch in batches:
        try:
            response = client.embeddings.create(
                model=settings.openai_embedding_model,
                input=batch,
            )
        except APITimeoutError as exc:
            raise EmbeddingServiceUpstreamError("Embedding generation timed out.") from exc
        except APIError as exc:
            raise EmbeddingServiceUpstreamError("Embedding generation failed.") from exc
        except Exception as exc:
            raise EmbeddingServiceUpstreamError("Embedding generation is temporarily unavailable.") from exc

        all_embeddings.extend(list(item.embedding) for item in response.data)

    return all_embeddings


def embed_text(*, text: str) -> list[float]:
    embeddings = embed_texts(texts=[text])
    if not embeddings:
        raise EmbeddingServiceUpstreamError("Embedding generation returned no data.")
    return embeddings[0]
