"""AI Platform — Clean Architecture core for a provider-agnostic AI assistant.

Layers (dependencies point inward only; enforced by import-linter):

    domain < application < {infrastructure, interface} < composition (root)

See ``docs/`` for the ratified architecture package (ADRs, roadmap, dependency
matrix, testing strategy).
"""

__version__ = "0.1.0"
