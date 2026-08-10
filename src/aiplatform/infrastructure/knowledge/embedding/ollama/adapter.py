"""OllamaEmbeddingProvider — embeddings over Ollama's HTTP API (ADR-0012).

The first production ``EmbeddingProvider``, reusing the M1 Ollama/httpx adapter
style. It calls Ollama's batch ``/api/embed`` endpoint and maps the response to
domain ``EmbeddingVector``s, translating every transport/vendor failure into the
domain ``EmbeddingError`` taxonomy — **no httpx or json exception escapes** — and
validating the returned dimension against the configured one (``DimensionMismatchError``).

The vector dimension is configured (it is a fixed property of the chosen embedding
model, e.g. 768 for ``nomic-embed-text``) so ``capabilities()`` performs no I/O.
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx
from pydantic import SecretStr

from aiplatform.domain.knowledge.errors import DimensionMismatchError, EmbeddingError
from aiplatform.domain.knowledge.ports import EmbeddingCapabilities, EmbeddingProvider
from aiplatform.domain.knowledge.vectors import EmbeddingVector

_EMBED_PATH = "/api/embed"


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embeds text via a local (or remote) Ollama server.

    Args:
        base_url: The Ollama base URL.
        model: The embedding model name (e.g. ``nomic-embed-text``).
        dimension: The model's fixed output dimension.
        timeout_seconds: Request timeout budget.
        api_key: Optional bearer credential for an authenticated/proxied server.
        client: An optional pre-built httpx client (e.g. for tests); when omitted
            the provider builds and owns one, disposed via :meth:`aclose`.
    """

    NAME = "ollama"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        dimension: int,
        timeout_seconds: float = 30.0,
        api_key: SecretStr | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Store configuration and build an httpx client when none is given."""
        self._model = model
        self._dimension = dimension
        self._owns_client = client is None
        self._client = client or self._build_client(base_url, timeout_seconds, api_key)

    def capabilities(self) -> EmbeddingCapabilities:
        """Return the model id and configured dimension (no I/O)."""
        return EmbeddingCapabilities(model=self._model, dimension=self._dimension)

    async def embed_query(self, text: str) -> EmbeddingVector:
        """Embed a single query text."""
        vectors = await self._embed([text])
        return vectors[0]

    async def embed_documents(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        """Embed a batch of document texts (empty input returns empty)."""
        if not texts:
            return []
        return await self._embed(list(texts))

    async def aclose(self) -> None:
        """Dispose of the owned httpx client (no-op for an injected client)."""
        if self._owns_client:
            await self._client.aclose()

    async def _embed(self, inputs: list[str]) -> list[EmbeddingVector]:
        """Call ``/api/embed`` and map the response to domain vectors."""
        try:
            response = await self._client.post(
                _EMBED_PATH, json={"model": self._model, "input": inputs}
            )
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"Ollama embedding request failed: {exc}") from exc
        if response.status_code >= 400:
            raise EmbeddingError(f"Ollama embeddings returned HTTP {response.status_code}")
        return self._parse(response)

    def _parse(self, response: httpx.Response) -> list[EmbeddingVector]:
        """Parse the ``embeddings`` array, validating each vector's dimension."""
        try:
            data = response.json()
        except ValueError as exc:
            raise EmbeddingError("malformed JSON in Ollama embeddings response") from exc
        raw = data.get("embeddings") if isinstance(data, dict) else None
        if not isinstance(raw, list):
            raise EmbeddingError("Ollama embeddings response missing an 'embeddings' array")

        vectors: list[EmbeddingVector] = []
        for item in raw:
            if not isinstance(item, list) or not item:
                raise EmbeddingError("Ollama embedding is not a non-empty array")
            vector = EmbeddingVector(tuple(float(value) for value in item))
            if vector.dimension != self._dimension:
                raise DimensionMismatchError(expected=self._dimension, actual=vector.dimension)
            vectors.append(vector)
        return vectors

    @staticmethod
    def _build_client(
        base_url: str, timeout_seconds: float, api_key: SecretStr | None
    ) -> httpx.AsyncClient:
        """Build an httpx client with a timeout and optional bearer auth."""
        headers: dict[str, str] = {}
        if api_key is not None:
            headers["Authorization"] = f"Bearer {api_key.get_secret_value()}"
        return httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(timeout_seconds), headers=headers
        )
