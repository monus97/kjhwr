"""Vercel entry point: exposes the Starlette app as a Python serverless function.

Vercel routes /api/* here (see vercel.json). The React build is served as static
files from the same project, so the browser talks to a single origin.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401
