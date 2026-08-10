"""Conversation domain — identity and durable message history (Milestone 2).

Pure domain (ADR-0001): value objects and the ``Conversation`` aggregate root,
with no I/O, framework (beyond pydantic types reused from ``domain.llm``), or
persistence concern. The aggregate is designed for clean relational mapping later
(ADR-0005) and keeps the frozen ``LLMProvider`` port untouched — a stored
:class:`~aiplatform.domain.conversation.message.Message` is deliberately distinct
from the transport ``ChatMessage`` (ADR-0007).
"""
