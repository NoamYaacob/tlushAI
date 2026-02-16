"""
LLM-based structured extraction from raw payslip text.

Abstraction layer supporting multiple LLM providers:
- mock: returns realistic fixture data for local development
- claude: Anthropic Claude API
- openai: OpenAI GPT-4o API

The LLM receives raw OCR/PDF text and maps it to the Payslip schema,
handling RTL Hebrew text and Israeli numeric formats.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

from ..config.settings import ANTHROPIC_API_KEY, LLM_PROVIDER, OPENAI_API_KEY
from ..models.payslip import Payslip

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt shared across providers
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """\
You are an expert Israeli payroll data extraction system.

TASK: Parse the following raw text (extracted from an Israeli payslip / תלוש שכר) \
into a structured JSON object matching the provided schema.

CRITICAL RULES:
1. The text may be Hebrew (RTL) and the reading order may be scrambled due to OCR. \
   Use semantic understanding, not positional parsing.
2. Israeli numeric formats: comma for thousands separator (e.g., 12,345.67), \
   dot for decimal, ₪ symbol, negative amounts in parentheses (1,234.56).
3. Map each line item to the correct category: earning, deduction, or employer contribution.
4. Common Hebrew payslip terms:
   - שכר יסוד / בסיס = base salary
   - שעות נוספות = overtime hours (125%, 150%)
   - נסיעות / החזר נסיעות = travel allowance
   - הבראה = recuperation pay
   - תגמולים עובד = employee pension contribution
   - תגמולים מעביד = employer pension contribution
   - פיצויים = severance (pitzuyim)
   - קרן השתלמות = training fund (keren hishtalmut)
   - מס הכנסה = income tax
   - ביטוח לאומי = National Insurance (Bituach Leumi)
   - מס בריאות = health tax
   - חופשה = vacation leave
   - מחלה = sick leave
   - ברוטו = gross
   - נטו = net
5. If a field cannot be confidently determined, set it to null and add the field \
   name to meta.needs_user_confirmation_fields.
6. If multiple interpretations exist, pick the most common one and add a warning \
   to meta.parse_warnings.
7. Populate ALL fields you can find. Leave as null only when truly absent.

OUTPUT: Return ONLY valid JSON matching the schema. No markdown, no explanation.\
"""

EXTRACTION_SCHEMA_HINT = """\
Expected JSON schema (abbreviated):
{
  "employer": {"name": str|null, "id": str|null, "address": str|null},
  "employee": {"name": str|null, "id": str|null, "job_title": str|null},
  "period": {"month": int|null, "year": int|null},
  "payment_date": str|null,
  "employment": {
    "salary_type": "monthly"|"hourly"|null,
    "base_rate": float|null,
    "job_percent": float|null,
    "hours_regular": float|null,
    "hours_overtime_125": float|null,
    "hours_overtime_150": float|null,
    "weekend_hours": float|null,
    "holiday_hours": float|null
  },
  "earnings_lines": [{"label": str, "label_he": str|null, "qty": float|null, "rate": float|null, "amount": float}],
  "deductions_lines": [{"label": str, "label_he": str|null, "amount": float}],
  "employer_contrib_lines": [{"label": str, "label_he": str|null, "amount": float}],
  "pension": {
    "employee_tagmulim": float|null,
    "employer_tagmulim": float|null,
    "employer_pitzuyim": float|null,
    "training_fund_employee": float|null,
    "training_fund_employer": float|null
  },
  "leave": {
    "vacation_open": float|null, "vacation_accrued": float|null,
    "vacation_used": float|null, "vacation_close": float|null,
    "sick_open": float|null, "sick_accrued": float|null,
    "sick_used": float|null, "sick_close": float|null
  },
  "totals": {"gross": float|null, "taxable_gross": float|null, "net": float|null, "total_deductions": float|null},
  "meta": {"parse_warnings": [str], "needs_user_confirmation_fields": [str]}
}\
"""


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class LLMExtractor(ABC):
    """Base class for LLM-based payslip extraction."""

    @abstractmethod
    async def extract(
        self,
        raw_text: str,
        page_images: list[bytes] | None = None,
    ) -> Payslip:
        """Extract structured payslip data from raw text (and optionally images)."""

    def _parse_llm_json(self, raw_json: str) -> Payslip:
        """Parse LLM output JSON into a Payslip, handling common issues."""
        # Strip markdown fences if present
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last fence lines
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("LLM returned invalid JSON: %s", exc)
            payslip = Payslip()
            payslip.meta.parse_warnings.append(
                f"LLM extraction returned invalid JSON: {exc}"
            )
            return payslip

        try:
            return Payslip.model_validate(data)
        except Exception as exc:
            logger.error("LLM JSON failed schema validation: %s", exc)
            payslip = Payslip()
            payslip.meta.parse_warnings.append(
                f"LLM output failed schema validation: {exc}"
            )
            return payslip


# ---------------------------------------------------------------------------
# Mock extractor (local dev)
# ---------------------------------------------------------------------------

class MockExtractor(LLMExtractor):
    """Returns a realistic fixture payslip for development/testing."""

    async def extract(
        self,
        raw_text: str,
        page_images: list[bytes] | None = None,
    ) -> Payslip:
        logger.info("MockExtractor: returning fixture payslip (text length=%d)", len(raw_text))
        return Payslip.model_validate(_MOCK_PAYSLIP_DATA)


_MOCK_PAYSLIP_DATA = {
    "employer": {"name": "חברה לדוגמה בע\"מ", "id": "510000000", "address": "תל אביב"},
    "employee": {"name": "ישראל ישראלי", "id": "012345678", "job_title": "מפתח תוכנה"},
    "period": {"month": 1, "year": 2026},
    "payment_date": "2026-02-10",
    "employment": {
        "salary_type": "monthly",
        "base_rate": 15000.0,
        "job_percent": 100.0,
        "hours_regular": 182.0,
        "hours_overtime_125": 10.0,
        "hours_overtime_150": 5.0,
        "weekend_hours": None,
        "holiday_hours": None,
    },
    "earnings_lines": [
        {"label": "base_salary", "label_he": "שכר יסוד", "qty": 1, "rate": 15000.0, "amount": 15000.0},
        {"label": "overtime_125", "label_he": "שעות נוספות 125%", "qty": 10, "rate": 103.02, "amount": 1030.22},
        {"label": "overtime_150", "label_he": "שעות נוספות 150%", "qty": 5, "rate": 123.63, "amount": 618.13},
        {"label": "travel_allowance", "label_he": "החזר נסיעות", "qty": 22, "rate": 22.60, "amount": 497.20},
    ],
    "deductions_lines": [
        {"label": "income_tax", "label_he": "מס הכנסה", "amount": 1523.0},
        {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 608.50},
        {"label": "health_tax", "label_he": "מס בריאות", "amount": 428.75},
        {"label": "pension_employee", "label_he": "תגמולים עובד", "amount": 900.0},
        {"label": "training_fund_employee", "label_he": "קרן השתלמות עובד", "amount": 375.0},
    ],
    "employer_contrib_lines": [
        {"label": "pension_employer", "label_he": "תגמולים מעביד", "amount": 975.0},
        {"label": "severance_employer", "label_he": "פיצויים מעביד", "amount": 900.0},
        {"label": "training_fund_employer", "label_he": "קרן השתלמות מעביד", "amount": 1125.0},
    ],
    "pension": {
        "employee_tagmulim": 900.0,
        "employer_tagmulim": 975.0,
        "employer_pitzuyim": 900.0,
        "training_fund_employee": 375.0,
        "training_fund_employer": 1125.0,
    },
    "leave": {
        "vacation_open": 10.0,
        "vacation_accrued": 1.17,
        "vacation_used": 0.0,
        "vacation_close": 11.17,
        "sick_open": 18.0,
        "sick_accrued": 1.5,
        "sick_used": 0.0,
        "sick_close": 19.5,
    },
    "totals": {
        "gross": 17145.55,
        "taxable_gross": 16648.35,
        "net": 13311.30,
        "total_deductions": 3835.25,
    },
    "meta": {
        "parse_warnings": [],
        "needs_user_confirmation_fields": [],
    },
}


# ---------------------------------------------------------------------------
# Claude extractor
# ---------------------------------------------------------------------------

class ClaudeExtractor(LLMExtractor):
    """Extract payslip data using Anthropic Claude API."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self._api_key = api_key
        self._model = model

    async def extract(
        self,
        raw_text: str,
        page_images: list[bytes] | None = None,
    ) -> Payslip:
        import httpx

        messages_content: list[dict] = []

        # Add images if available (vision)
        if page_images:
            import base64
            for img_bytes in page_images[:3]:  # limit to first 3 pages
                messages_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.b64encode(img_bytes).decode(),
                    },
                })

        messages_content.append({
            "type": "text",
            "text": f"Raw extracted text:\n\n{raw_text}\n\n{EXTRACTION_SCHEMA_HINT}",
        })

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": 4096,
                    "system": EXTRACTION_SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": messages_content}],
                },
            )
            resp.raise_for_status()
            data = resp.json()

        raw_json = data["content"][0]["text"]
        return self._parse_llm_json(raw_json)


# ---------------------------------------------------------------------------
# OpenAI extractor
# ---------------------------------------------------------------------------

class OpenAIExtractor(LLMExtractor):
    """Extract payslip data using OpenAI API."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._api_key = api_key
        self._model = model

    async def extract(
        self,
        raw_text: str,
        page_images: list[bytes] | None = None,
    ) -> Payslip:
        import httpx

        messages_content: list[dict] = []

        if page_images:
            import base64
            for img_bytes in page_images[:3]:
                b64 = base64.b64encode(img_bytes).decode()
                messages_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                })

        messages_content.append({
            "type": "text",
            "text": f"Raw extracted text:\n\n{raw_text}\n\n{EXTRACTION_SCHEMA_HINT}",
        })

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": 4096,
                    "messages": [
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": messages_content},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()

        raw_json = data["choices"][0]["message"]["content"]
        return self._parse_llm_json(raw_json)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_extractor() -> LLMExtractor:
    """Return the configured LLM extractor instance."""
    if LLM_PROVIDER == "claude":
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY not set but LLM_PROVIDER=claude")
        return ClaudeExtractor(api_key=ANTHROPIC_API_KEY)
    elif LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not set but LLM_PROVIDER=openai")
        return OpenAIExtractor(api_key=OPENAI_API_KEY)
    else:
        return MockExtractor()
