"""Upload handler: validate, hash, save temporarily, and clean up."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from ..config.settings import DELETE_FILE_AFTER_PROCESSING, UPLOAD_DIR
from ..security.file_validator import (
    FileValidationError,
    antivirus_scan_hook,
    compute_file_hash,
    validate_upload,
)

logger = logging.getLogger(__name__)


class UploadResult:
    __slots__ = ("file_path", "file_hash", "content", "content_type")

    def __init__(
        self,
        file_path: Path,
        file_hash: str,
        content: bytes,
        content_type: str,
    ):
        self.file_path = file_path
        self.file_hash = file_hash
        self.content = content
        self.content_type = content_type


async def handle_upload(file: UploadFile) -> UploadResult:
    """
    Validate, save to tmp, compute hash, run AV placeholder.
    Caller is responsible for calling cleanup() when done.
    """
    content = await validate_upload(file)
    file_hash = compute_file_hash(content)

    ext = _extension_for(file.content_type or "")
    tmp_name = f"{uuid4().hex}{ext}"
    tmp_path = UPLOAD_DIR / tmp_name
    tmp_path.write_bytes(content)

    # AV placeholder
    if not antivirus_scan_hook(tmp_path):
        tmp_path.unlink(missing_ok=True)
        raise FileValidationError("File failed antivirus scan", code="av_failed")

    logger.info(
        "Upload accepted: hash=%s size=%d type=%s",
        file_hash[:12],
        len(content),
        file.content_type,
    )

    return UploadResult(
        file_path=tmp_path,
        file_hash=file_hash,
        content=content,
        content_type=file.content_type or "application/octet-stream",
    )


def cleanup_file(path: Path) -> None:
    """Delete the temporary file if configured to do so."""
    if DELETE_FILE_AFTER_PROCESSING:
        path.unlink(missing_ok=True)
        logger.info("Temporary file deleted: %s", path.name)


def _extension_for(content_type: str) -> str:
    return {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
    }.get(content_type, ".bin")
