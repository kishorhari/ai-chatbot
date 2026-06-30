"""Run the shared provider contract suite against OllamaProvider (M1.4).

Ollama passes the *identical* suite that Echo passes (over respx-mocked
transport), which is the executable proof that the abstraction is real and not
Ollama-shaped (ADR-0004). A live run is available under the opt-in ``live``
marker but is not part of required CI.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
import respx
from provider_contract import LLMProviderContract

from aiplatform.infrastructure.config.settings import OllamaSettings
from aiplatform.infrastructure.llm.ollama.adapter import OllamaProvider

_BASE_URL = "http://ollama.test"

# A deterministic NDJSON stream: "Hel" + "lo" + terminal.
_STREAM = (
    b'{"model":"test-model","message":{"role":"assistant","content":"Hel"},"done":false}\n'
    b'{"model":"test-model","message":{"role":"assistant","content":"lo"},"done":false}\n'
    b'{"model":"test-model","message":{"role":"assistant","content":""},"done":true,'
    b'"done_reason":"stop","prompt_eval_count":5,"eval_count":2}\n'
)


class TestOllamaContract(LLMProviderContract):
    """OllamaProvider must satisfy every LLMProvider invariant."""

    @pytest_asyncio.fixture
    async def provider(self, respx_mock: respx.MockRouter) -> AsyncIterator[OllamaProvider]:
        respx_mock.post(f"{_BASE_URL}/api/chat").mock(
            side_effect=lambda _request: httpx.Response(200, content=_STREAM)
        )
        provider = OllamaProvider(OllamaSettings(base_url=_BASE_URL, model="test-model"))
        yield provider
        await provider.aclose()
