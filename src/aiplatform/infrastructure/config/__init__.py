"""Configuration — the single, validated, fail-fast Settings source.

All configuration is read through this module's Settings object; nothing else in
the codebase reads ``os.environ`` directly. Loads before logging is configured,
so it imports nothing from the logging package.
"""
