"""File upload validation: MIME type, size, and antivirus hook."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from fastapi import UploadFile

from ..config.settings import ALLOWED_MIME_TYPES, MAX_FILE_SIZE_BYTES

logger = logging.getLogger(__name__)

# Magic bytes for supported file types
_MAGIC_BYTES = {
    b"%PDF": "application/pdf",
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG": "image/png",
}


class FileValidationError(Exception):
    """Raised when a file fails validation."""

    def __init__(self, message: str, code: str = "invalid_file"):
        self.message = message
        self.code = code
        super().__init__(message)


async def validate_upload(file: UploadFile) -> bytes:
    """
    Read the file, validate MIME type and size, return raw bytes.
    Raises FileValidationError on failure.
    """
    content = await file.read()

    # Size check
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise FileValidationError(
            f"File too large: {len(content)} bytes (max {MAX_FILE_SIZE_BYTES})",
            code="file_too_large",
        )

    if len(content) == 0:
        raise FileValidationError("File is empty", code="empty_file")

    # MIME type check (declared)
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise FileValidationError(
            f"Unsupported file type: {file.content_type}",
            code="unsupported_type",
        )

    # Magic bytes check
    detected_type = _detect_mime_from_magic(content)
    if detected_type and detected_type not in ALLOWED_MIME_TYPES:
        raise FileValidationError(
            f"File content doesn't match an allowed type (detected: {detected_type})",
            code="mime_mismatch",
        )

    # If declared type doesn't match detected type, warn but allow
    if (
        file.content_type
        and detected_type
        and file.content_type != detected_type
    ):
        logger.warning(
            "MIME mismatch: declared=%s detected=%s (allowing)",
            file.content_type,
            detected_type,
        )

    return content


def compute_file_hash(content: bytes) -> str:
    """Return SHA-256 hex digest of file content."""
    return hashlib.sha256(content).hexdigest()


def _detect_mime_from_magic(content: bytes) -> str | None:
    """Best-effort MIME type detection from magic bytes."""
    for magic, mime in _MAGIC_BYTES.items():
        if content[: len(magic)].startswith(magic):
            return mime
    return None


def antivirus_scan_hook(file_path: Path) -> bool:
    """
    Placeholder for antivirus scanning integration.
    Returns True if file is clean (always True in MVP).

    To integrate a real scanner:
    - ClamAV: subprocess.run(["clamdscan", "--no-summary", str(file_path)])
    - VirusTotal API: upload hash and check results
    """
    logger.info("Antivirus scan placeholder — file: %s (skipped in MVP)", file_path.name)
    return True
