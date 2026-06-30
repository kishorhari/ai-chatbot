"""Composition root — the single place permitted to wire concretes to ports.

Loads settings, configures logging, builds providers, and assembles the
registry. The only multi-layer importer; every other layer stays unaware of
concrete adapters (ADR-0001).
"""
