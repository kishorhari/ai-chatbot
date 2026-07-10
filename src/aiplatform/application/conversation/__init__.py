"""Conversation application layer — memory assembly and the chat use case.

Pure application components that orchestrate the conversation domain and the
provider port (ADR-0009, ADR-0010): token estimation, context-window selection,
and prompt assembly (M2.2), and the chat application service (M2.3). Depends only
on domain and application ports — never on a concrete adapter, ``httpx``,
SQLAlchemy, or a framework.
"""
