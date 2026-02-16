"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "tmp_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# File upload limits
# ---------------------------------------------------------------------------
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_MIME_TYPES: set[str] = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}

# ---------------------------------------------------------------------------
# LLM extraction provider
# ---------------------------------------------------------------------------
# Supported: "mock", "claude", "openai"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# ---------------------------------------------------------------------------
# Rate limiting (requests per minute per IP)
# ---------------------------------------------------------------------------
RATE_LIMIT_RPM: int = int(os.getenv("RATE_LIMIT_RPM", "20"))

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ORIGINS: list[str] = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
).split(",")

# ---------------------------------------------------------------------------
# Tesseract
# ---------------------------------------------------------------------------
TESSERACT_LANG: str = os.getenv("TESSERACT_LANG", "heb+eng")

# ---------------------------------------------------------------------------
# Privacy
# ---------------------------------------------------------------------------
DELETE_FILE_AFTER_PROCESSING: bool = (
    os.getenv("DELETE_FILE_AFTER_PROCESSING", "true").lower() == "true"
)
