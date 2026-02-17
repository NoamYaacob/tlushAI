"""
Text extraction pipeline.

Strategy:
1. PDF with selectable text → pdfplumber (RTL-aware, table + word-level)
2. PDF with images / image files → Tesseract OCR (Hebrew + English)
3. Return raw text + page images for optional LLM vision extraction
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from itertools import groupby
from pathlib import Path

logger = logging.getLogger(__name__)

# Known Hebrew payslip words used for reversal detection
_KNOWN_HEBREW_WORDS = {
    "שכר", "יסוד", "בסיס", "ברוטו", "נטו", "ניכויים", "הפרשות",
    "עובד", "מעביד", "חופשה", "מחלה", "הבראה", "נסיעות", "פנסיה",
    "תגמולים", "פיצויים", "השתלמות", "ביטוח", "לאומי", "בריאות",
    "הכנסה", "שעות", "נוספות", "תלוש", "משכורת", "סהכ", "סה״כ",
}

# Pattern matching Hebrew-heavy segments (4+ chars containing Hebrew)
_HEBREW_SEGMENT_RE = re.compile(r"[\u0590-\u05FF\s.,\-:]{4,}")


@dataclass
class ExtractionResult:
    raw_text: str
    method: str  # "pdf_text" | "ocr" | "pdf_text_partial_ocr"
    page_images: list[bytes] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_text(file_path: Path, content_type: str) -> ExtractionResult:
    """
    Main entry point: extract text from a PDF or image file.
    For images (JPG/PNG): bypasses OCR entirely and loads the raw image
    for direct LLM Vision extraction — far more accurate for Hebrew tables.
    For PDFs: uses pdfplumber with RTL-aware strategies, falls back to OCR.
    """
    logger.info("Starting text extraction: file=%s content_type=%s", file_path.name, content_type)
    if content_type == "application/pdf":
        return _extract_from_pdf(file_path)
    else:
        # Images bypass OCR — send directly to LLM Vision
        return _load_image_for_vision(file_path)


# ---------------------------------------------------------------------------
# Image → LLM Vision (bypass OCR)
# ---------------------------------------------------------------------------

def _load_image_for_vision(file_path: Path) -> ExtractionResult:
    """
    Load an image file and return its bytes for LLM Vision extraction.
    Does NOT run OCR — the LLM's Vision capability handles Hebrew tables
    far better than pytesseract.
    """
    warnings: list[str] = []
    page_image_bytes: list[bytes] = []

    try:
        from PIL import Image

        img = Image.open(file_path)
        buf = io.BytesIO()
        # Convert to PNG for consistent LLM Vision input
        img.save(buf, format="PNG")
        page_image_bytes.append(buf.getvalue())
        logger.info(
            "Image loaded for Vision: %s size=%dx%d",
            file_path.name, img.width, img.height,
        )
    except Exception as exc:
        msg = f"Cannot open image: {exc}"
        logger.error(msg)
        warnings.append(msg)

    return ExtractionResult(
        raw_text="[Image uploaded — text extraction delegated to LLM Vision]",
        method="vision",
        page_images=page_image_bytes,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# PDF extraction (pdfplumber, RTL-aware)
# ---------------------------------------------------------------------------

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
            logger.info("PDF opened: %d page(s)", len(pdf.pages))
            for i, page in enumerate(pdf.pages):
                text = _extract_page_text(page, i)
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

    # Fix reversed Hebrew segments
    original_len = len(combined)
    combined = _fix_reversed_hebrew(combined)
    if combined != combined:  # pragma: no cover – log only
        logger.info("Hebrew reversal fix applied to extracted text")

    hebrew_ratio = _hebrew_char_ratio(combined)
    logger.info(
        "PDF text extraction: pages=%d total_chars=%d hebrew_ratio=%.2f method=pdfplumber",
        len(all_text_parts), len(combined), hebrew_ratio,
    )

    # Heuristic: if extracted text is very short, it's likely a scanned PDF
    if len(combined) < 50:
        logger.info("Text below threshold (%d chars < 50), falling back to OCR", len(combined))
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


def _extract_page_text(page, page_num: int) -> str:
    """Extract text from a single pdfplumber page using RTL-aware strategies."""

    # Strategy 1: Try table extraction first (Israeli payslips are heavily tabular)
    try:
        tables = page.extract_tables()
        if tables:
            table_text_parts: list[str] = []
            for table in tables:
                for row in table:
                    cells = [str(c).strip() for c in row if c is not None]
                    table_text_parts.append(" | ".join(cells))
            table_text = "\n".join(table_text_parts)

            if len(table_text.strip()) > 20:
                # Also extract non-table text (headers, footers)
                non_table_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                combined = f"{non_table_text}\n\n{table_text}"
                logger.debug(
                    "Page %d: table extraction succeeded (%d table chars, %d non-table chars)",
                    page_num + 1, len(table_text), len(non_table_text),
                )
                return combined
    except Exception as exc:
        logger.debug("Page %d: table extraction failed: %s", page_num + 1, exc)

    # Strategy 2: Extract with custom layout tolerances for Hebrew
    text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""

    # Strategy 3: If text lacks Hebrew chars, try word-level RTL reconstruction
    if text and not _has_sufficient_hebrew(text):
        logger.debug("Page %d: low Hebrew ratio, trying word-level RTL reconstruction", page_num + 1)
        try:
            words = page.extract_words(x_tolerance=3, y_tolerance=3, keep_blank_chars=True)
            if words:
                text = _reconstruct_rtl_lines(words)
        except Exception as exc:
            logger.debug("Page %d: word extraction failed: %s", page_num + 1, exc)

    logger.debug("Page %d: extracted %d chars", page_num + 1, len(text))
    return text


# ---------------------------------------------------------------------------
# OCR extraction (Tesseract)
# ---------------------------------------------------------------------------

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
            processed = _preprocess_for_ocr(img)
            text = pytesseract.image_to_string(processed, lang=TESSERACT_LANG)
            text_parts.append(text)
            logger.debug("OCR page %d: %d chars extracted", i + 1, len(text))
        except Exception as e:
            warnings.append(f"OCR failed on page/image {i + 1}: {e}")

    combined = "\n\n".join(text_parts).strip()
    logger.info(
        "OCR extraction: images=%d total_chars=%d lang=%s",
        len(images), len(combined), TESSERACT_LANG,
    )

    return ExtractionResult(
        raw_text=combined,
        method="ocr",
        page_images=page_image_bytes,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Helper: OCR image pre-processing
# ---------------------------------------------------------------------------

def _preprocess_for_ocr(img: "Image.Image") -> "Image.Image":
    """Enhance image for better Hebrew OCR results."""
    from PIL import ImageFilter, ImageOps

    # Convert to grayscale
    if img.mode != "L":
        img = img.convert("L")
    # Increase contrast
    img = ImageOps.autocontrast(img, cutoff=2)
    # Sharpen slightly
    img = img.filter(ImageFilter.SHARPEN)
    # Binarize using a simple threshold
    img = img.point(lambda p: 255 if p > 128 else 0, mode="1")
    # Convert back to L for Tesseract
    img = img.convert("L")
    return img


# ---------------------------------------------------------------------------
# Helper: Hebrew character detection
# ---------------------------------------------------------------------------

def _has_sufficient_hebrew(text: str) -> bool:
    """Check if text contains a reasonable proportion of Hebrew characters."""
    if not text:
        return False
    hebrew_count = sum(1 for c in text if "\u0590" <= c <= "\u05FF")
    alpha_count = sum(1 for c in text if c.isalpha())
    if alpha_count == 0:
        return False
    return (hebrew_count / alpha_count) > 0.1  # at least 10% Hebrew


def _hebrew_char_ratio(text: str) -> float:
    """Return fraction of characters that are Hebrew."""
    if not text:
        return 0.0
    hebrew_count = sum(1 for c in text if "\u0590" <= c <= "\u05FF")
    return hebrew_count / len(text)


# ---------------------------------------------------------------------------
# Helper: RTL line reconstruction from word-level extraction
# ---------------------------------------------------------------------------

def _reconstruct_rtl_lines(words: list[dict]) -> str:
    """Reconstruct text lines from pdfplumber words, handling RTL order."""
    # Sort by top coordinate (group into lines), then by x0 descending (RTL)
    sorted_words = sorted(words, key=lambda w: (round(w["top"], 1), -w["x0"]))
    lines: list[str] = []
    for _, group in groupby(sorted_words, key=lambda w: round(w["top"], 1)):
        line_words = [w["text"] for w in group]
        lines.append(" ".join(line_words))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper: Fix reversed Hebrew text from pdfplumber
# ---------------------------------------------------------------------------

def _fix_reversed_hebrew(text: str) -> str:
    """Detect and fix reversed Hebrew segments in extracted text."""

    def _maybe_reverse_segment(match: re.Match) -> str:
        segment = match.group(0)
        reversed_seg = segment[::-1]
        fwd_hits = sum(1 for w in _KNOWN_HEBREW_WORDS if w in segment)
        rev_hits = sum(1 for w in _KNOWN_HEBREW_WORDS if w in reversed_seg)
        if rev_hits > fwd_hits:
            logger.debug("Reversed Hebrew segment: %r -> %r", segment.strip(), reversed_seg.strip())
            return reversed_seg
        return segment

    return _HEBREW_SEGMENT_RE.sub(_maybe_reverse_segment, text)
