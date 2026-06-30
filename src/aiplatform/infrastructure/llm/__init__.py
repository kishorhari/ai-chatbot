"""LLM infrastructure — concrete ``LLMProvider`` adapters.

Each adapter maps domain value objects to/from a vendor API and translates all
transport/vendor failures into the domain ``LLMError`` taxonomy. No transport
exception escapes an adapter (ADR-0002).
"""
