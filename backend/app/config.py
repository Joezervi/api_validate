"""Application configuration loaded from environment variables.

Priority (highest to lowest):
  1. Environment variables already set in the process (e.g. Docker's `environment:` block)
  2. Values from the `.env` file in the backend directory
  3. Hardcoded fallback defaults
"""

import os
from pathlib import Path

# ── Load .env file (does NOT override already-set env vars) ────────────

_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path, override=False)
    except ImportError:
        pass  # dotenv not installed — use os.environ directly

# ── Runtime detection ──────────────────────────────────────────────────

IS_VERCEL = bool(os.getenv("VERCEL")) or os.getenv("VERCEL_ENV") is not None
"""True when running on Vercel's serverless platform."""

# ── Database ───────────────────────────────────────────────────────────

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/pochecker",
)

# ── Uploads / outputs — use /tmp on Vercel (only writable path) ────────

UPLOAD_DIR = "/tmp/uploads" if IS_VERCEL else "uploads"
OUTPUT_DIR = "/tmp/outputs" if IS_VERCEL else "outputs"

# Ensure directories exist (only meaningful for Docker / local)
if not IS_VERCEL:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
