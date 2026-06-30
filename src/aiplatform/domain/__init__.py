"""Domain layer — pure entities, value objects, ports, and errors.

The innermost layer. Imports nothing from outer layers and uses no framework,
I/O, or logging. Only ``pydantic`` is permitted here, for value-object modelling.
"""
