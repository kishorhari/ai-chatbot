"""Knowledge infrastructure — embedding, vector-store, and repository adapters.

Concrete implementations of the ``domain/knowledge`` ports (ADR-0011). Each is
selected at the composition root by configuration; domain and application import
nothing here.
"""
