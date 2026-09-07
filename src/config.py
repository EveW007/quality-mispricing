"""Compatibility import. Runtime configuration now lives in settings.py/config.json."""

try:
    from .settings import Settings, load_settings
except ImportError:
    from settings import Settings, load_settings

__all__ = ["Settings", "load_settings"]
