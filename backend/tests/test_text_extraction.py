"""Unit tests for text extraction helpers (Hebrew detection, RTL, OCR preprocessing, Vision)."""

import pytest

from app.services.llm_extraction import _VISION_PLACEHOLDER
from app.services.text_extraction import (
    _fix_reversed_hebrew,
    _has_sufficient_hebrew,
    _hebrew_char_ratio,
    _load_image_for_vision,
    _reconstruct_rtl_lines,
    extract_text,
)


# ---------------------------------------------------------------------------
# Hebrew character detection
# ---------------------------------------------------------------------------

class TestHassufficientHebrew:
    def test_all_hebrew(self):
        assert _has_sufficient_hebrew("שכר יסוד") is True

    def test_no_hebrew(self):
        assert _has_sufficient_hebrew("base salary 15000") is False

    def test_mixed_above_threshold(self):
        # "שכר" (3 Hebrew) + "salary" (6 latin) = 3/9 > 10%
        assert _has_sufficient_hebrew("שכר salary 15000") is True

    def test_empty_string(self):
        assert _has_sufficient_hebrew("") is False

    def test_only_digits(self):
        assert _has_sufficient_hebrew("12345") is False

    def test_single_hebrew_char(self):
        # 1 Hebrew + many ASCII → below 10%
        assert _has_sufficient_hebrew("א and many english words here plus more text") is False


class TestHebrewCharRatio:
    def test_all_hebrew(self):
        ratio = _hebrew_char_ratio("שכר")
        assert ratio == 1.0

    def test_no_hebrew(self):
        assert _hebrew_char_ratio("abc") == 0.0

    def test_empty(self):
        assert _hebrew_char_ratio("") == 0.0

    def test_mixed(self):
        ratio = _hebrew_char_ratio("שכר abc")
        assert 0.3 < ratio < 0.6  # 3 Hebrew out of 7 chars (incl space)


# ---------------------------------------------------------------------------
# Hebrew reversal detection
# ---------------------------------------------------------------------------

class TestFixReversedHebrew:
    def test_reversed_bruto(self):
        # "וטורב" reversed = "ברוטו"
        result = _fix_reversed_hebrew("וטורב")
        assert "ברוטו" in result

    def test_reversed_neto(self):
        # "וטנ " reversed contains "נטו"
        result = _fix_reversed_hebrew("  וטנ  ")
        assert "נטו" in result

    def test_already_correct(self):
        result = _fix_reversed_hebrew("שכר יסוד")
        assert "שכר" in result
        assert "יסוד" in result

    def test_no_hebrew(self):
        text = "15,000.00 NIS"
        assert _fix_reversed_hebrew(text) == text

    def test_preserves_numbers(self):
        text = "15000 וטורב"
        result = _fix_reversed_hebrew(text)
        assert "15000" in result
        assert "ברוטו" in result


# ---------------------------------------------------------------------------
# RTL line reconstruction
# ---------------------------------------------------------------------------

class TestReconstructRtlLines:
    def test_groups_by_y_position(self):
        words = [
            {"text": "15,000", "top": 100.0, "x0": 50},
            {"text": "יסוד", "top": 100.0, "x0": 200},
            {"text": "שכר", "top": 100.0, "x0": 300},
            {"text": "נטו", "top": 150.0, "x0": 200},
            {"text": "12,000", "top": 150.0, "x0": 50},
        ]
        result = _reconstruct_rtl_lines(words)
        lines = result.split("\n")
        assert len(lines) == 2
        # RTL: higher x0 first
        assert "שכר" in lines[0]
        assert lines[0].index("שכר") < lines[0].index("15,000")
        assert "נטו" in lines[1]

    def test_single_line(self):
        words = [
            {"text": "hello", "top": 50.0, "x0": 100},
            {"text": "world", "top": 50.0, "x0": 200},
        ]
        result = _reconstruct_rtl_lines(words)
        assert "world" in result
        assert "hello" in result

    def test_empty_words(self):
        result = _reconstruct_rtl_lines([])
        assert result == ""


# ---------------------------------------------------------------------------
# OCR pre-processing (requires Pillow)
# ---------------------------------------------------------------------------

class TestPreprocessForOcr:
    def test_returns_grayscale_image(self):
        from PIL import Image

        from app.services.text_extraction import _preprocess_for_ocr

        img = Image.new("RGB", (100, 100), color="white")
        result = _preprocess_for_ocr(img)
        assert result.mode == "L"
        assert result.size == (100, 100)

    def test_already_grayscale(self):
        from PIL import Image

        from app.services.text_extraction import _preprocess_for_ocr

        img = Image.new("L", (50, 50), color=128)
        result = _preprocess_for_ocr(img)
        assert result.mode == "L"


# ---------------------------------------------------------------------------
# Vision bypass (image → LLM Vision, no OCR)
# ---------------------------------------------------------------------------

class TestLoadImageForVision:
    def test_loads_png_image(self, tmp_path):
        from PIL import Image

        img = Image.new("RGB", (200, 300), color="white")
        path = tmp_path / "payslip.png"
        img.save(path, format="PNG")

        result = _load_image_for_vision(path)
        assert result.method == "vision"
        assert len(result.page_images) == 1
        assert len(result.page_images[0]) > 0
        assert result.raw_text == _VISION_PLACEHOLDER
        assert len(result.warnings) == 0

    def test_loads_jpeg_image(self, tmp_path):
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        path = tmp_path / "payslip.jpg"
        img.save(path, format="JPEG")

        result = _load_image_for_vision(path)
        assert result.method == "vision"
        assert len(result.page_images) == 1

    def test_invalid_file_warns(self, tmp_path):
        path = tmp_path / "bad.png"
        path.write_bytes(b"not an image")

        result = _load_image_for_vision(path)
        assert result.method == "vision"
        assert len(result.page_images) == 0
        assert len(result.warnings) == 1
        assert "Cannot open image" in result.warnings[0]


class TestExtractTextVision:
    def test_image_content_type_uses_vision(self, tmp_path):
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="blue")
        path = tmp_path / "test.jpg"
        img.save(path, format="JPEG")

        result = extract_text(path, "image/jpeg")
        assert result.method == "vision"
        assert len(result.page_images) == 1

    def test_png_content_type_uses_vision(self, tmp_path):
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="green")
        path = tmp_path / "test.png"
        img.save(path, format="PNG")

        result = extract_text(path, "image/png")
        assert result.method == "vision"
