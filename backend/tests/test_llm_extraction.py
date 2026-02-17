"""Unit tests for LLM extraction JSON parsing and MockExtractor."""

import pytest

from app.services.llm_extraction import MockExtractor


# ---------------------------------------------------------------------------
# _parse_llm_json
# ---------------------------------------------------------------------------

class TestParseLlmJson:
    def setup_method(self):
        self.extractor = MockExtractor()

    def test_valid_json(self):
        json_str = '{"employer": {"name": "Test"}, "totals": {"gross": 10000}}'
        result = self.extractor._parse_llm_json(json_str)
        assert result.employer.name == "Test"
        assert result.totals.gross == 10000.0

    def test_markdown_fenced_json(self):
        json_str = '```json\n{"employer": {"name": "Test"}}\n```'
        result = self.extractor._parse_llm_json(json_str)
        assert result.employer.name == "Test"

    def test_prose_before_json(self):
        json_str = 'Here is the extracted data:\n{"employer": {"name": "Test"}}'
        result = self.extractor._parse_llm_json(json_str)
        assert result.employer.name == "Test"

    def test_prose_after_json(self):
        json_str = '{"employer": {"name": "Test"}}\nI hope this helps!'
        result = self.extractor._parse_llm_json(json_str)
        assert result.employer.name == "Test"

    def test_trailing_comma(self):
        json_str = '{"employer": {"name": "Test",}, "totals": {"gross": 10000,}}'
        result = self.extractor._parse_llm_json(json_str)
        assert result.employer.name == "Test"

    def test_nan_replaced_with_null(self):
        json_str = '{"totals": {"gross": NaN, "net": 5000}}'
        result = self.extractor._parse_llm_json(json_str)
        assert result.totals.gross is None
        assert result.totals.net == 5000.0

    def test_invalid_json_returns_empty_payslip(self):
        result = self.extractor._parse_llm_json("not json at all")
        assert len(result.meta.parse_warnings) > 0
        assert "invalid JSON" in result.meta.parse_warnings[0]

    def test_valid_json_with_hebrew(self):
        json_str = '{"employer": {"name": "חברה בע\\"מ"}, "period": {"month": 6, "year": 2025}}'
        result = self.extractor._parse_llm_json(json_str)
        assert result.employer.name == 'חברה בע"מ'
        assert result.period.month == 6


# ---------------------------------------------------------------------------
# MockExtractor
# ---------------------------------------------------------------------------

class TestMockExtractor:
    @pytest.mark.asyncio
    async def test_returns_valid_payslip(self):
        ext = MockExtractor()
        result = await ext.extract("שכר יסוד 15,000 ברוטו 17,000 נטו 13,000")
        assert result.employer.name is not None
        assert result.totals.gross is not None
        assert len(result.earnings_lines) > 0

    @pytest.mark.asyncio
    async def test_short_text_warning(self):
        ext = MockExtractor()
        result = await ext.extract("short")
        assert any("very short" in w for w in result.meta.parse_warnings)

    @pytest.mark.asyncio
    async def test_image_warning_tells_user_to_switch_provider(self):
        ext = MockExtractor()
        fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        result = await ext.extract("some text", page_images=[fake_image])
        assert any("LLM_PROVIDER=mock" in w for w in result.meta.parse_warnings)
        assert any("DEMO data" in w for w in result.meta.parse_warnings)

    @pytest.mark.asyncio
    async def test_image_warning_not_short_text_warning(self):
        """When images are provided, show the provider warning, not 'very short'."""
        ext = MockExtractor()
        from app.services.llm_extraction import _VISION_PLACEHOLDER
        fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        result = await ext.extract(_VISION_PLACEHOLDER, page_images=[fake_image])
        assert not any("very short" in w for w in result.meta.parse_warnings)
        assert any("LLM_PROVIDER=mock" in w for w in result.meta.parse_warnings)

    @pytest.mark.asyncio
    async def test_hourly_keyword_hebrew(self):
        ext = MockExtractor()
        result = await ext.extract("שכר שעתי 55 ₪ לשעה")
        assert result.employment.salary_type.value == "hourly"
        assert result.employment.base_rate == 55.0

    @pytest.mark.asyncio
    async def test_hourly_keyword_english(self):
        ext = MockExtractor()
        result = await ext.extract("hourly rate worker payslip for analysis test input")
        assert result.employment.salary_type.value == "hourly"

    @pytest.mark.asyncio
    async def test_default_is_monthly(self):
        ext = MockExtractor()
        result = await ext.extract("שכר יסוד 15,000 ברוטו 17,000 נטו 13,000 regular monthly pay")
        assert result.employment.salary_type.value == "monthly"
