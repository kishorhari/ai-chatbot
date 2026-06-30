"""Interface layer — delivery mechanisms (HTTP, CLI).

Depends on application and composition; never imports an adapter directly. It
receives wired providers from the composition root.
"""
