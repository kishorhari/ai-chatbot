"""Infrastructure layer — adapters that touch the outside world.

Implements domain ports (LLM providers) and hosts cross-cutting concerns
(configuration, logging). The only layer permitted to import vendor SDKs or
``httpx``. Never imports application, interface, or composition.
"""
