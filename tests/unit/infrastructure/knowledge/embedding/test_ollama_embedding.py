"""Unit tests for OllamaEmbeddingProvider transport & error mapping (M3.1)."""

from __future__ import annotations

import json

import httpx
import pytest

from aiplatform.domain.knowledge.errors import DimensionMismatchError, EmbeddingError
from aiplatform.infrastructure.knowledge.embedding.ollama.adapter import (
    OllamaEmbeddingProvider,
)

_BASE_URL = "http://ollama.test"
_URL = f"{_BASE_URL}/api/embed"


def _provider(dimension: int = 3) -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(base_url=_BASE_URL, model="embed-model", dimension=dimension)


async def test_embed_documents_maps_response_and_sends_model_and_input(respx_mock) -> None:
    route = respx_mock.post(_URL).mock(
        return_value=httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]})
    )
    provider = _provider()
    try:
        vectors = await provider.embed_documents(["a", "b"])
        assert [v.values for v in vectors] == [(0.1, 0.2, 0.3), (0.4, 0.5, 0.6)]
        sent = json.loads(route.calls.last.request.content)
        assert sent == {"model": "embed-model", "input": ["a", "b"]}
    finally:
        await provider.aclose()


async def test_embed_query_returns_single_vector(respx_mock) -> None:
    respx_mock.post(_URL).mock(
        return_value=httpx.Response(200, json={"embeddings": [[1.0, 0.0, 0.0]]})
    )
    provider = _provider()
    try:
        vector = await provider.embed_query("hello")
        assert vector.values == (1.0, 0.0, 0.0)
    finally:
        await provider.aclose()


async def test_empty_documents_makes_no_request(respx_mock) -> None:
    route = respx_mock.post(_URL).mock(return_value=httpx.Response(200, json={"embeddings": []}))
    provider = _provider()
    try:
        assert await provider.embed_documents([]) == []
        assert route.call_count == 0
    finally:
        await provider.aclose()


async def test_http_error_maps_to_embedding_error(respx_mock) -> None:
    respx_mock.post(_URL).mock(return_value=httpx.Response(500, json={"error": "boom"}))
    provider = _provider()
    try:
        with pytest.raises(EmbeddingError):
            await provider.embed_query("x")
    finally:
        await provider.aclose()


async def test_transport_error_maps_to_embedding_error(respx_mock) -> None:
    respx_mock.post(_URL).mock(side_effect=httpx.ConnectError("refused"))
    provider = _provider()
    try:
        with pytest.raises(EmbeddingError):
            await provider.embed_query("x")
    finally:
        await provider.aclose()


async def test_malformed_json_maps_to_embedding_error(respx_mock) -> None:
    respx_mock.post(_URL).mock(return_value=httpx.Response(200, content=b"{ not json"))
    provider = _provider()
    try:
        with pytest.raises(EmbeddingError):
            await provider.embed_query("x")
    finally:
        await provider.aclose()


async def test_missing_embeddings_key_maps_to_embedding_error(respx_mock) -> None:
    respx_mock.post(_URL).mock(return_value=httpx.Response(200, json={"unexpected": []}))
    provider = _provider()
    try:
        with pytest.raises(EmbeddingError):
            await provider.embed_query("x")
    finally:
        await provider.aclose()


async def test_dimension_mismatch_is_detected(respx_mock) -> None:
    respx_mock.post(_URL).mock(
        return_value=httpx.Response(200, json={"embeddings": [[0.1, 0.2]]})  # 2, expected 3
    )
    provider = _provider(dimension=3)
    try:
        with pytest.raises(DimensionMismatchError):
            await provider.embed_query("x")
    finally:
        await provider.aclose()
