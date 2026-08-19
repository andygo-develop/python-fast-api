"""ASGI entrypoint.

Run with: uv run fastapi dev main.py
"""

from app.main import app

__all__ = ["app"]
