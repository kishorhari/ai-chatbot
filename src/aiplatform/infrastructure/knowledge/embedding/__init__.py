"""Embedding adapters — concrete ``EmbeddingProvider`` implementations (ADR-0012).

Each maps text to domain ``EmbeddingVector``s and translates vendor/transport
failures into the domain ``EmbeddingError`` taxonomy. The deterministic
``FakeEmbeddingProvider`` is the offline reference (mirrors Echo); real adapters
(Ollama, later OpenAI/SentenceTransformers) are proven against the same contract
suite.
"""
