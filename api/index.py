"""Vercel serverless entry point — re-exports the FastAPI app.

Vercel auto-detects `api/index.py` as a Python ASGI application.
The FastAPI app lives in backend/app/main.py.
"""
from backend.app.main import app
