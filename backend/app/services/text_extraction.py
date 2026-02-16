"""
Text extraction pipeline.

Strategy:
1. PDF with selectable text → pdfplumber
2. PDF with images / image files → Tesseract OCR (Hebrew + English)
3. Return raw text + page images for optional LLM vision extraction
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    raw_text: str
    method: str  # "pdf_text" | "ocr" | "pdf_text_partial_ocr"
    page_images: list[bytes] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def extract_text(file_path: Path, content_type: str) -> ExtractionResult:
    """
    Main entry point: extract text from a PDF or image file.
    Falls back to OCR when PDF text is insufficient.
    """
    if content_type == "application/pdf":
        return _extract_from_pdf(file_path)
    else:
        return _extract_from_image(file_path)


def _extract_from_pdf(file_path: Path) -> ExtractionResult:
    """Try pdfplumber first; fall back to OCR if text is too short."""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed — falling back to OCR")
        return _extract_from_image(file_path)

    warnings: list[str] = []
    page_images: list[bytes] = []
    all_text_parts: list[str] = []

    try:
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                all_text_parts.append(text)

                # Render page to image for potential LLM vision fallback
                try:
                    img = page.to_image(resolution=200)
                    buf = io.BytesIO()
                    img.original.save(buf, format="PNG")
                    page_images.append(buf.getvalue())
                except Exception:
                    warnings.append(f"Could not render page {i + 1} to image")

    except Exception as exc:
        logger.error("pdfplumber failed: %s", exc)
        warnings.append(f"PDF text extraction failed: {exc}")
        return _extract_from_image(file_path)

    combined = "\n\n".join(all_text_parts).strip()

    # Heuristic: if extracted text is very short, it's likely a scanned PDF
    if len(combined) < 50:
        warnings.append("PDF appears scanned — using OCR fallback")
        ocr_result = _extract_from_image(file_path)
        ocr_result.page_images = page_images or ocr_result.page_images
        ocr_result.method = "pdf_text_partial_ocr"
        ocr_result.warnings.extend(warnings)
        return ocr_result

    return ExtractionResult(
        raw_text=combined,
        method="pdf_text",
        page_images=page_images,
        warnings=warnings,
    )


def _extract_from_image(file_path: Path) -> ExtractionResult:
    """OCR an image (or scanned PDF rendered to images) using Tesseract."""
    warnings: list[str] = []

    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        msg = f"OCR dependencies not installed: {exc}"
        logger.error(msg)
        return ExtractionResult(
            raw_text="",
            method="ocr",
            warnings=[msg],
        )

    from ..config.settings import TESSERACT_LANG

    suffix = file_path.suffix.lower()
    images: list[Image.Image] = []
    page_image_bytes: list[bytes] = []

    if suffix == ".pdf":
        # For scanned PDFs, try pdf2image or pdfplumber image rendering
        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    try:
                        img = page.to_image(resolution=300)
                        images.append(img.original)
                        buf = io.BytesIO()
                        img.original.save(buf, format="PNG")
                        page_image_bytes.append(buf.getvalue())
                    except Exception as e:
                        warnings.append(f"Page render failed: {e}")
        except Exception as e:
            warnings.append(f"Cannot render PDF pages for OCR: {e}")
    else:
        try:
            img = Image.open(file_path)
            images.append(img)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            page_image_bytes.append(buf.getvalue())
        except Exception as e:
            warnings.append(f"Cannot open image: {e}")

    if not images:
        return ExtractionResult(
            raw_text="",
            method="ocr",
            page_images=page_image_bytes,
            warnings=warnings + ["No images could be processed for OCR"],
        )

    text_parts: list[str] = []
    for i, img in enumerate(images):
        try:
            text = pytesseract.image_to_string(img, lang=TESSERACT_LANG)
            text_parts.append(text)
        except Exception as e:
            warnings.append(f"OCR failed on page/image {i + 1}: {e}")

    return ExtractionResult(
        raw_text="\n\n".join(text_parts).strip(),
        method="ocr",
        page_images=page_image_bytes,
        warnings=warnings,
    )
