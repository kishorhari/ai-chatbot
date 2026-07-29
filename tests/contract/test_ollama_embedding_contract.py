"""Run the shared embedding contract suite against OllamaEmbeddingProvider (M3.1).

Over respx-mocked transport (offline, every push): the mock is a deterministic,
input-dependent embedding "server", so the adapter satisfies the same contract the
fake does. A live run against a real Ollama is available under the opt-in ``live``
marker but is not required for CI.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
import respx
from embedding_contract import EmbeddingProviderContract

from aiplatform.infrastructure.knowledge.embedding.ollama.adapter import (
    OllamaEmbeddingProvider,
)

_BASE_URL = "http://ollama.test"
_DIMENSION = 64


def _deterministic_vector(text: str) -> list[float]:
    """A stable, input-dependent vector standing in for a real embedding."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [(digest[i % len(digest)] / 255.0) * 2.0 - 1.0 for i in range(_DIMENSION)]


def _embed_response(request: httpx.Request) -> httpx.Response:
    inputs = json.loads(request.content)["input"]
    return httpx.Response(200, json={"embeddings": [_deterministic_vector(t) for t in inputs]})


class TestOllamaEmbeddingContract(EmbeddingProviderContract):
    """OllamaEmbeddingProvider must satisfy every EmbeddingProvider invariant."""

    @pytest_asyncio.fixture
    async def provider(
        self, respx_mock: respx.MockRouter
    ) -> AsyncIterator[OllamaEmbeddingProvider]:
        respx_mock.post(f"{_BASE_URL}/api/embed").mock(side_effect=_embed_response)
        instance = OllamaEmbeddingProvider(
            base_url=_BASE_URL, model="nomic-embed-text", dimension=_DIMENSION
        )
        yield instance
        await instance.aclose()
