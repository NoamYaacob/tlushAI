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

import copy
import json
import logging
import re
import time
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
   - דמי הבראה = recuperation pay
   - פרמיה = bonus/premium
   - ביגוד = clothing allowance
   - אחזקת רכב = car maintenance
   - דמי כלכלה = meal allowance
5. If a field cannot be confidently determined, set it to null and add the field \
   name to meta.needs_user_confirmation_fields.
6. If multiple interpretations exist, pick the most common one and add a warning \
   to meta.parse_warnings.
7. Populate ALL fields you can find. Leave as null only when truly absent.
8. HEBREW TEXT REVERSAL: pdfplumber and OCR frequently output Hebrew text reversed \
   (character-by-character or word-by-word). If you see garbled Hebrew, try reading \
   it backwards. For example, "דוסי רכש" is actually "שכר יסוד" (base salary) reversed. \
   Common reversed patterns:
   - "וטורב" → "ברוטו" (gross)
   - "וטנ" → "נטו" (net)
   - "הסנכה סמ" → "מס הכנסה" (income tax)
   - "ימואל חוטיב" → "ביטוח לאומי" (national insurance)
   Always try both reading directions for Hebrew segments.
9. HEBREW DATE FORMATS: Israeli payslips use various date formats:
   - Month names: ינואר, פברואר, מרץ, אפריל, מאי, יוני, יולי, אוגוסט, ספטמבר, אוקטובר, נובמבר, דצמבר
   - Formats: "ינואר 2026", "01/2026", "2026-01", "01.2026", "חודש 01 שנת 2026", "תקופה: 01/2026"
   - Extract month (1-12) and year (4 digits) from any format.
10. COMMON ISRAELI PAYSLIP LAYOUT: Israeli payslips typically have these sections:
    - Header: employer name, employee name, ID numbers, period
    - Employment details: salary type, job %, seniority date
    - Earnings table (right side): base salary, overtime, allowances
    - Deductions table (left/center): taxes, pension employee, health
    - Employer contributions (sometimes separate section): pension employer, severance, training fund
    - Leave balances (bottom): vacation and sick leave open/accrued/used/close
    - Totals row: gross, total deductions, net
    Numbers in the same row as a label belong to that label.

11. VISION MODE: If the user message contains an image of a payslip and the text says \
    "[Image uploaded — text extraction delegated to LLM Vision]", extract ALL data \
    directly from the image. Ignore the placeholder text. Read every visible number, \
    label, and table cell in the image. Images are the primary source — they contain \
    the actual payslip with Hebrew tables, numbers, and layout.

12. CHAIN-OF-THOUGHT GRID RECONSTRUCTION (CRITICAL — DO THIS BEFORE JSON):
    Israeli payslips often have wide white-space gaps between the Hebrew text column \
    (far right) and the number columns (far left). This causes spatial misalignment \
    if you try to read directly. YOU MUST use the following two-phase approach:

    PHASE 1 — SCRATCHPAD: Before producing ANY JSON, output a <scratchpad> block. \
    Inside it, reconstruct every table from the payslip as a Markdown table by \
    tracing STRICTLY HORIZONTALLY across each row:
    a) WIDE-TABLE ANCHORING: The description column is on the FAR RIGHT (often labeled \
       מלל or תיאור). The total/payment column is on the FAR LEFT (often labeled \
       סכום לתשלום or סכום). For EACH row, start at the description text (מלל) on the \
       far right and follow that SAME horizontal line all the way to the far left to \
       find סכום לתשלום — that is the row's total amount. The intermediate columns \
       (תעריף, כמות, etc.) are between them on the same line.
    b) Trace your eyes horizontally to the left across the SAME PRINTED LINE, \
       ignoring any white space, until you reach the numbers on the far left.
    c) The numbers on that SAME horizontal line belong to that label — do NOT \
       let your eyes drift up or down to adjacent rows.
    d) Read the column HEADER ROW first. Find where the headers מלל/תיאור, כמות, \
       תעריף, סכום/סכום לתשלום (or equivalent) are. The header position tells you which \
       number column is which. The number directly UNDER the header כמות is qty. \
       The number directly UNDER the header תעריף is rate. The number UNDER \
       סכום/סכום לתשלום is the total amount.
    e) Write each table as a Markdown table with headers. Example:
       ### תשלומים (Earnings)
       | מלל/תיאור | תעריף | כמות | סכום לתשלום |
       |---|---|---|---|
       | 013 משכורת | 83.75 | 51.00 | 4,271.25 |
       | 024 שעות נוספות 125% | 63.75 | 7.25 | 462.19 |
       ...
       Note: column order in your Markdown must match the ACTUAL header order in the payslip. \
       Some systems put תעריף before כמות, others put כמות before תעריף.
    f) After each earnings row, add a verification line: \
       "CHECK: {qty} × {rate} = {result} ≈ {amount} ✓/✗"
    g) Do the same for: ניכויי חובה (taxes), ניכויים והפרשות לקופות גמל (pension), \
       leave balances, and totals.
    h) For the tax table: if there is a סה"כ column, verify sum of parts = total. \
       Write: "TAX CHECK: {tax1} + {tax2} + {tax3} = {sum} ≈ סה\"כ {total} ✓/✗"
    i) For the pension table: clearly mark which columns are ניכוי עובד (employee) \
       and which are הפרשת מעסיק (employer).
    j) EARNINGS TOTAL CROSS-CHECK: At the end of the earnings table in your scratchpad, \
       sum all the סכום לתשלום values and compare to the סך-כל התשלומים (total earnings) \
       row printed on the payslip. Write: \
       "EARNINGS TOTAL: {line1} + {line2} + ... = {sum} ≈ סך-כל התשלומים {printed_total} ✓/✗" \
       If ✗, one or more rows have misaligned amounts — go back and fix them before \
       proceeding to Phase 2.
    Close the scratchpad with </scratchpad>.

    PHASE 2 — JSON: After the </scratchpad>, produce the final JSON by reading \
    from YOUR OWN scratchpad tables — NOT by re-reading the image. The scratchpad \
    is now your source of truth for the JSON mapping.

13. STRICT OCR MODE — ZERO HALLUCINATION (CRITICAL):
    You are a STRICT OCR SCANNER. You MUST extract the exact characters printed on \
    the payslip — nothing more, nothing less.
    a) DO NOT guess, autocomplete, expand abbreviations, or substitute "typical" \
       payslip component names. Your training knowledge of common payslip terms is \
       IRRELEVANT — only the pixels/text in front of you matter.
    b) If the payslip says "013 משכורת", output exactly "013 משכורת" — do NOT expand \
       it to "תשלומים בגין משרה עולם 100% שעה" or any other invention.
    c) If it says "015 נסיעות", output exactly "015 נסיעות" — NOT "נשפח".
    d) If it says "024 שעות נוספות 125%", output exactly that — NOT "שעות הפסקה 125%".
    e) If it says "שווי ארוחות ע\"ח", output exactly that — NOT "אחזקת רכב".
    f) Row codes (e.g., "013", "015", "024") are part of the description — include them \
       in label_he exactly as printed.
    g) If a word is genuinely unreadable, copy the closest visible characters AND add \
       a warning to meta.parse_warnings: "label unclear in row X: best reading = '...'". \
    NEVER output Hebrew text that is not visible in the source document.

14. EARNINGS TABLE — ROW-BY-ROW EXTRACTION:
    You MUST extract EVERY row from the earnings table as a separate earnings_line entry.
    For each row, use the data from your scratchpad (Rule 12, Phase 1):
    a) Copy the EXACT Hebrew description (including any row code) into label_he.
    b) Map it to a standard English label if you recognize it; otherwise use a descriptive \
       English slug (e.g., "shift_bonus", "seniority", "clothing_allowance").
    c) STRICT HEADER-TO-FIELD MAPPING: The value under the column headed תעריף ALWAYS \
       maps to the JSON "rate" field. The value under the column headed כמות ALWAYS maps \
       to the JSON "qty" field. The value under סכום/סכום לתשלום ALWAYS maps to "amount". \
       Do NOT swap them based on which number looks bigger or smaller. If the payslip \
       shows תעריף=51.00 and כמות=83.75, then rate=51.00 and qty=83.75 — even if that \
       means the rate is smaller than the quantity. The column HEADER is the authority, \
       not your expectation of what "rate" or "hours" should look like.
    d) If "qty" or "rate" is blank or missing for a row, set them to null — but still \
       extract the description and amount.
    DO NOT combine multiple rows into one. DO NOT invent rows that don't exist. \
    DO NOT put a non-monetary value (like "12 days") into the "amount" field — \
    days/hours go into "qty", monetary totals go into "amount". \
    ONLY output rows that are visibly present in the source.

15. HOURLY PAYSLIPS WITH MULTIPLE RATE TIERS:
    Hourly payslips often show multiple rows at different rates (100%, 125%, 150%, 175%, 200%).
    - Set employment.base_rate to the BASE hourly rate (the 100% rate).
    - Each rate tier should be its own earnings_line with the correct qty (hours), \
      rate (effective hourly rate at that tier), and amount (total for that tier).
    - The employment.base_rate should be the 100% rate.
    - Set employment.hours_regular from the 100% row quantity; hours_overtime_125 \
      from the 125% row quantity; hours_overtime_150 from the 150% row quantity.

16. TAX / DEDUCTIONS TABLE — HEADER ALIGNMENT & MATH VERIFICATION (CRITICAL):
    The ניכויי חובה (mandatory deductions) table often has NO GRIDLINES and text \
    can appear visually misaligned. DO NOT assign values based on visual proximity alone.
    a) Read the column headers first (e.g., מס הכנסה, ביטוח לאומי, מס בריאות, סה"כ).
    b) Carefully align each number to the header DIRECTLY above it — use the \
       scratchpad from Rule 12 to verify alignment.
    c) MATH CHECK: The סה"כ (total) column MUST equal the sum of the individual \
       deduction columns in the same row. If your extracted total ≠ sum of parts, \
       you shifted the columns — re-align and fix.
    d) Common deductions: מס הכנסה (income tax), ביטוח לאומי (national insurance), \
       מס בריאות (health tax). These are separate items — do not merge them.

17. PENSION / PROVIDENT FUND TABLE — EMPLOYEE vs. EMPLOYER SEPARATION (CRITICAL):
    The ניכויים והפרשות לקופות גמל (provident fund) table has TWO distinct sides:
    a) ניכויי עובד / הפרשת עובד (Employee deductions) — these go into deductions_lines \
       and into pension.employee_tagmulim, pension.training_fund_employee.
    b) הפרשת מעסיק (Employer contributions) — these go into employer_contrib_lines \
       and into pension.employer_tagmulim, pension.employer_pitzuyim, \
       pension.training_fund_employer.
    Read the sub-headers or column labels to determine which side is Employee vs. Employer. \
    Mark these clearly in your scratchpad. \
    Do NOT put employer contributions into deductions_lines or vice versa. \
    Look for these fund types: תגמולים (tagmulim/savings), פיצויים (pitzuyim/severance), \
    קרן השתלמות (training fund). Each may have both an employee and employer component.

18. EARNINGS TOTAL SANITY CHECK (BEFORE EMITTING JSON):
    Before writing the final JSON, verify that the sum of all earnings_lines[].amount \
    values approximately equals the סך-כל התשלומים or סה"כ תשלומים (total earnings) \
    printed on the payslip. Also verify it is consistent with totals.gross. \
    If the sum is significantly off (more than ±5 NIS), one or more rows have the \
    wrong amount — likely a column misalignment. Go back to your scratchpad, find \
    the mismatch, and fix it. Do NOT emit JSON with mismatched earnings totals.

OUTPUT FORMAT:
1. First, output a <scratchpad>...</scratchpad> block with Markdown tables as described \
   in Rule 12, Phase 1. Include verification checks for each row.
2. Then, output ONLY valid JSON matching the schema — derived from your scratchpad tables. \
   No markdown fences around the JSON, no extra explanation, no commentary after the JSON. \
   The JSON must be the LAST thing in your output (after the scratchpad block).\
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
    "training_fund_employer": float|null,
    "fund_name": str|null
  },
  "leave": {
    "vacation_open": float|null, "vacation_accrued": float|null,
    "vacation_used": float|null, "vacation_close": float|null,
    "sick_open": float|null, "sick_accrued": float|null,
    "sick_used": float|null, "sick_close": float|null
  },
  "totals": {"gross": float|null, "taxable_gross": float|null, "net": float|null, "total_deductions": float|null, "total_employer_cost": float|null},
  "meta": {"parse_warnings": [str], "needs_user_confirmation_fields": [str]}
}\
"""

# ---------------------------------------------------------------------------
# Few-shot examples for better extraction accuracy
# ---------------------------------------------------------------------------

_FEW_SHOT_EXAMPLES = """\

EXAMPLES — Below are three correctly parsed Israeli payslips from different sectors. \
Use these as reference for field mapping and structure.

EXAMPLE 1 — High-tech monthly salary:
Input snippet: "חברת הייטק בע\"מ | ישראל כהן ת.ז. 012345678 | ינואר 2026 | \
שכר יסוד 25,000 | שעות נוספות 125% 2,061 | החזר נסיעות 500 | \
ברוטו 27,561 | מס הכנסה 4,200 | ביטוח לאומי 1,050 | מס בריאות 690 | \
תגמולים עובד 1,500 | קרן השתלמות עובד 625 | נטו 19,496 | \
תגמולים מעביד 1,625 | פיצויים 2,083.33 | קרן השתלמות מעביד 1,875"
Output:
{
  "employer": {"name": "חברת הייטק בע\\"מ", "id": null, "address": null},
  "employee": {"name": "ישראל כהן", "id": "012345678", "job_title": null},
  "period": {"month": 1, "year": 2026},
  "employment": {"salary_type": "monthly", "base_rate": 25000.0, "job_percent": 100.0, "hours_regular": 182.0, "hours_overtime_125": null, "hours_overtime_150": null, "weekend_hours": null, "holiday_hours": null},
  "earnings_lines": [
    {"label": "base_salary", "label_he": "שכר יסוד", "qty": 1, "rate": 25000.0, "amount": 25000.0},
    {"label": "overtime_125", "label_he": "שעות נוספות 125%", "qty": null, "rate": null, "amount": 2061.0},
    {"label": "travel_allowance", "label_he": "החזר נסיעות", "qty": null, "rate": null, "amount": 500.0}
  ],
  "deductions_lines": [
    {"label": "income_tax", "label_he": "מס הכנסה", "amount": 4200.0},
    {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 1050.0},
    {"label": "health_tax", "label_he": "מס בריאות", "amount": 690.0},
    {"label": "pension_employee", "label_he": "תגמולים עובד", "amount": 1500.0},
    {"label": "training_fund_employee", "label_he": "קרן השתלמות עובד", "amount": 625.0}
  ],
  "employer_contrib_lines": [
    {"label": "pension_employer", "label_he": "תגמולים מעביד", "amount": 1625.0},
    {"label": "severance_employer", "label_he": "פיצויים", "amount": 2083.33},
    {"label": "training_fund_employer", "label_he": "קרן השתלמות מעביד", "amount": 1875.0}
  ],
  "pension": {"employee_tagmulim": 1500.0, "employer_tagmulim": 1625.0, "employer_pitzuyim": 2083.33, "training_fund_employee": 625.0, "training_fund_employer": 1875.0},
  "totals": {"gross": 27561.0, "taxable_gross": null, "net": 19496.0, "total_deductions": 8065.0},
  "meta": {"parse_warnings": [], "needs_user_confirmation_fields": []}
}

EXAMPLE 2 — Public sector monthly salary:
Input snippet: "משרד החינוך | רחל לוי ת.ז. 987654321 | 12/2025 | \
שכר משולב 12,500 | תוספת ותק 800 | גמול השתלמות 500 | החזר נסיעות 350 | \
ברוטו 14,150 | מס הכנסה 1,100 | ביטוח לאומי 560 | מס בריאות 380 | \
תגמולים עובד 750 | נטו 11,360 | \
תגמולים מעביד 812.50 | פיצויים 1,041.67"
Output:
{
  "employer": {"name": "משרד החינוך", "id": null, "address": null},
  "employee": {"name": "רחל לוי", "id": "987654321", "job_title": null},
  "period": {"month": 12, "year": 2025},
  "employment": {"salary_type": "monthly", "base_rate": 12500.0, "job_percent": 100.0, "hours_regular": 182.0, "hours_overtime_125": null, "hours_overtime_150": null, "weekend_hours": null, "holiday_hours": null},
  "earnings_lines": [
    {"label": "base_salary", "label_he": "שכר משולב", "qty": 1, "rate": 12500.0, "amount": 12500.0},
    {"label": "seniority", "label_he": "תוספת ותק", "qty": null, "rate": null, "amount": 800.0},
    {"label": "education_bonus", "label_he": "גמול השתלמות", "qty": null, "rate": null, "amount": 500.0},
    {"label": "travel_allowance", "label_he": "החזר נסיעות", "qty": null, "rate": null, "amount": 350.0}
  ],
  "deductions_lines": [
    {"label": "income_tax", "label_he": "מס הכנסה", "amount": 1100.0},
    {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 560.0},
    {"label": "health_tax", "label_he": "מס בריאות", "amount": 380.0},
    {"label": "pension_employee", "label_he": "תגמולים עובד", "amount": 750.0}
  ],
  "employer_contrib_lines": [
    {"label": "pension_employer", "label_he": "תגמולים מעביד", "amount": 812.50},
    {"label": "severance_employer", "label_he": "פיצויים", "amount": 1041.67}
  ],
  "pension": {"employee_tagmulim": 750.0, "employer_tagmulim": 812.50, "employer_pitzuyim": 1041.67, "training_fund_employee": null, "training_fund_employer": null},
  "totals": {"gross": 14150.0, "taxable_gross": null, "net": 11360.0, "total_deductions": 2790.0},
  "meta": {"parse_warnings": [], "needs_user_confirmation_fields": []}
}

EXAMPLE 3 — Small business hourly worker (multiple rate tiers):
Input snippet: "מסעדת הים בע\"מ | דוד אברהם | שעתי 42.00 ₪ | 11/2025 | \
תשלומים: \
שכר רגיל 100% | 168 | 42.00 | 7,056.00 \
שעות נוספות 125% | 20 | 52.50 | 1,050.00 \
שעות נוספות 150% | 8 | 63.00 | 504.00 \
דמי הבראה | | | 420.00 \
ברוטו 9,030 | מס הכנסה 350 | ביטוח לאומי 380 | מס בריאות 260 | נטו 8,040"
Output:
{
  "employer": {"name": "מסעדת הים בע\\"מ", "id": null, "address": null},
  "employee": {"name": "דוד אברהם", "id": null, "job_title": null},
  "period": {"month": 11, "year": 2025},
  "employment": {"salary_type": "hourly", "base_rate": 42.0, "job_percent": null, "hours_regular": 168.0, "hours_overtime_125": 20.0, "hours_overtime_150": 8.0, "weekend_hours": null, "holiday_hours": null},
  "earnings_lines": [
    {"label": "base_salary", "label_he": "שכר רגיל 100%", "qty": 168, "rate": 42.0, "amount": 7056.0},
    {"label": "overtime_125", "label_he": "שעות נוספות 125%", "qty": 20, "rate": 52.5, "amount": 1050.0},
    {"label": "overtime_150", "label_he": "שעות נוספות 150%", "qty": 8, "rate": 63.0, "amount": 504.0},
    {"label": "recuperation", "label_he": "דמי הבראה", "qty": null, "rate": null, "amount": 420.0}
  ],
  "deductions_lines": [
    {"label": "income_tax", "label_he": "מס הכנסה", "amount": 350.0},
    {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 380.0},
    {"label": "health_tax", "label_he": "מס בריאות", "amount": 260.0}
  ],
  "employer_contrib_lines": [],
  "pension": {"employee_tagmulim": null, "employer_tagmulim": null, "employer_pitzuyim": null, "training_fund_employee": null, "training_fund_employer": null},
  "totals": {"gross": 9030.0, "taxable_gross": null, "net": 8040.0, "total_deductions": 990.0},
  "meta": {"parse_warnings": [], "needs_user_confirmation_fields": ["pension_expected"]}
}\
"""

# Marker text set by text_extraction.py when an image bypasses OCR
_VISION_PLACEHOLDER = "[Image uploaded — text extraction delegated to LLM Vision]"

# Regex for cleaning LLM JSON output
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


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
        cleaned = raw_json.strip()

        # Strip scratchpad block if present (Phase 1 CoT output)
        scratchpad_end = cleaned.find("</scratchpad>")
        if scratchpad_end != -1:
            cleaned = cleaned[scratchpad_end + len("</scratchpad>"):].strip()

        # Strip markdown fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        # Extract JSON between first { and last }
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            cleaned = cleaned[first_brace : last_brace + 1]

        # Fix common JSON issues from LLMs
        cleaned = _TRAILING_COMMA_RE.sub(r"\1", cleaned)
        cleaned = cleaned.replace(": NaN", ": null").replace(": Infinity", ": null")
        # Remove single-line JS comments that some LLMs add
        cleaned = re.sub(r"//[^\n]*", "", cleaned)

        logger.debug("LLM JSON response: %d chars after cleanup", len(cleaned))

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(
                "LLM returned invalid JSON: %s (first 200 chars: %s)",
                exc,
                cleaned[:200],
            )
            payslip = Payslip()
            payslip.meta.parse_warnings.append(
                f"LLM extraction returned invalid JSON: {exc}"
            )
            return payslip

        # Log extracted top-level fields
        found_fields = [k for k, v in data.items() if v is not None]
        logger.info("LLM extracted fields: %s", found_fields)

        try:
            payslip = Payslip.model_validate(data)
        except Exception as exc:
            logger.error("LLM JSON failed schema validation: %s", exc)
            payslip = Payslip()
            payslip.meta.parse_warnings.append(
                f"LLM output failed schema validation: {exc}"
            )
            return payslip

        return self._fix_rate_qty_swap(self._fix_known_swap_patterns(payslip))

    @staticmethod
    def _fix_rate_qty_swap(payslip: Payslip) -> Payslip:
        """Detect and fix systematic rate↔qty swap in earnings_lines and employment.

        Some payroll layouts (e.g., Tzevet 3) have column orders that cause the
        LLM to consistently put the תעריף (rate) value into the qty field and
        the כמות (qty) value into the rate field.

        Detection: if a base-salary line and an overtime line (125%/150%) both
        have qty and rate, check whether the qty fields follow the overtime
        multiplier pattern (qty_125 ≈ 1.25 × qty_base).  If they do, the qty
        fields actually contain rates → swap all qty↔rate.
        """
        if not payslip.earnings_lines:
            return payslip

        # Find base salary line and overtime lines with both qty and rate
        base_line = None
        overtime_entries: list[tuple[float, int]] = []  # (multiplier, index)
        for i, line in enumerate(payslip.earnings_lines):
            if line.qty is None or line.rate is None:
                continue
            combined = f"{line.label_he or ''} {line.label}"
            if line.label == "base_salary" or "משכורת" in combined or "שכר רגיל" in combined:
                base_line = line
            elif "125" in combined:
                overtime_entries.append((1.25, i))
            elif "150" in combined:
                overtime_entries.append((1.50, i))

        if base_line is None or not overtime_entries:
            return payslip

        swap_needed = False
        for multiplier, idx in overtime_entries:
            ot_line = payslip.earnings_lines[idx]
            # Check if qty fields contain the tier ratio (swap scenario)
            if base_line.qty and base_line.qty > 0:
                ratio_qty = ot_line.qty / base_line.qty
                if abs(ratio_qty - multiplier) < 0.02:
                    swap_needed = True
                    break
            # Check if rate fields contain the tier ratio (correct scenario)
            if base_line.rate and base_line.rate > 0:
                ratio_rate = ot_line.rate / base_line.rate
                if abs(ratio_rate - multiplier) < 0.02:
                    swap_needed = False
                    break

        if not swap_needed:
            return payslip

        logger.warning(
            "Detected rate↔qty column swap (base_line qty=%.2f, rate=%.2f) "
            "— auto-correcting all earnings_lines and employment fields",
            base_line.qty,
            base_line.rate,
        )

        # Swap qty↔rate in all earnings_lines that have both
        for line in payslip.earnings_lines:
            if line.qty is not None and line.rate is not None:
                line.qty, line.rate = line.rate, line.qty

        # Swap employment.base_rate ↔ hours_regular
        if payslip.employment.base_rate is not None and payslip.employment.hours_regular is not None:
            payslip.employment.base_rate, payslip.employment.hours_regular = (
                payslip.employment.hours_regular,
                payslip.employment.base_rate,
            )

        # Re-derive overtime hours from the now-corrected earnings_lines
        for line in payslip.earnings_lines:
            if line.qty is None:
                continue
            combined = f"{line.label_he or ''} {line.label}"
            if "125" in combined:
                payslip.employment.hours_overtime_125 = line.qty
            elif "150" in combined:
                payslip.employment.hours_overtime_150 = line.qty

        payslip.meta.parse_warnings.append(
            "Auto-corrected: rate and qty fields were swapped "
            "(detected via overtime tier ratio)"
        )
        return payslip

    @staticmethod
    def _fix_known_swap_patterns(payslip: Payslip) -> Payslip:
        """Hardcoded fallback for known rate↔qty swap patterns.

        When the ratio-based detection cannot trigger (e.g., overtime lines
        are missing or mis-labeled), this catches specific Tzevet 3 values
        that are confirmed swapped and fixes them directly.
        """
        emp = payslip.employment
        if emp.base_rate is not None and emp.hours_regular is not None:
            # Tzevet 3: base_rate=83.75 is actually hours, hours_regular=51 is the rate
            if (abs(emp.base_rate - 83.75) < 0.01 and abs(emp.hours_regular - 51.0) < 0.01):
                logger.warning(
                    "Known swap pattern matched (base_rate=%.2f, hours=%.2f) "
                    "— applying hardcoded correction",
                    emp.base_rate, emp.hours_regular,
                )
                emp.base_rate, emp.hours_regular = emp.hours_regular, emp.base_rate

                for line in payslip.earnings_lines:
                    if line.qty is not None and line.rate is not None:
                        line.qty, line.rate = line.rate, line.qty

                # Re-derive overtime hours from corrected earnings_lines
                for line in payslip.earnings_lines:
                    if line.qty is None:
                        continue
                    combined = f"{line.label_he or ''} {line.label}"
                    if "125" in combined:
                        emp.hours_overtime_125 = line.qty
                    elif "150" in combined:
                        emp.hours_overtime_150 = line.qty

                payslip.meta.parse_warnings.append(
                    "Auto-corrected: rate and qty swapped "
                    "(matched known Tzevet 3 pattern: 83.75/51)"
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
        logger.info(
            "MockExtractor: returning fixture payslip (text_length=%d, has_images=%s)",
            len(raw_text),
            bool(page_images),
        )
        data = copy.deepcopy(_MOCK_PAYSLIP_DATA)

        # Adjust fixture based on input text content
        if "שעתי" in raw_text or "hourly" in raw_text.lower():
            data["employment"] = {
                **data["employment"],
                "salary_type": "hourly",
                "base_rate": 55.0,
            }

        payslip = Payslip.model_validate(data)

        # IMPORTANT: MockExtractor cannot process images — warn prominently
        if page_images:
            logger.warning(
                "MockExtractor: %d image(s) provided but MOCK mode cannot "
                "process images. Set LLM_PROVIDER=claude or LLM_PROVIDER=openai "
                "with the corresponding API key to enable Vision extraction.",
                len(page_images),
            )
            payslip.meta.parse_warnings.append(
                "⚠ LLM_PROVIDER=mock — images cannot be processed. "
                "The data shown is DEMO data, not from your payslip. "
                "Set LLM_PROVIDER=claude (with ANTHROPIC_API_KEY) or "
                "LLM_PROVIDER=openai (with OPENAI_API_KEY) in backend/.env "
                "to enable Vision-based extraction from images."
            )
        elif len(raw_text) < 100:
            payslip.meta.parse_warnings.append(
                "Input text is very short — extraction may be incomplete"
            )

        return payslip


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

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self._api_key = api_key
        self._model = model

    async def extract(
        self,
        raw_text: str,
        page_images: list[bytes] | None = None,
    ) -> Payslip:
        import base64

        import httpx

        vision_only = bool(page_images) and _VISION_PLACEHOLDER in raw_text

        t_start = time.monotonic()
        logger.info(
            "ClaudeExtractor: starting extraction (model=%s, text_length=%d, "
            "images=%d, vision_only=%s)",
            self._model,
            len(raw_text),
            len(page_images) if page_images else 0,
            vision_only,
        )

        messages_content: list[dict] = []

        # Add images if available (vision) — images FIRST so the model sees them
        if page_images:
            for i, img_bytes in enumerate(page_images[:3]):  # limit to 3 pages
                b64_data = base64.b64encode(img_bytes).decode()
                messages_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64_data,
                    },
                })
                logger.info(
                    "ClaudeExtractor: attached image %d (%d bytes, %d b64 chars)",
                    i + 1, len(img_bytes), len(b64_data),
                )

        # Build the text prompt — different for vision-only vs text+images
        if vision_only:
            text_prompt = (
                "The above image is a photograph of an Israeli payslip (תלוש שכר). "
                "No OCR text is available — extract ALL data directly from the image. "
                "The image is your ONLY source of data.\n\n"
                "YOU MUST USE THE TWO-PHASE APPROACH BELOW. Do NOT skip Phase 1.\n\n"
                "═══ PHASE 1: SCRATCHPAD — Markdown Grid Reconstruction ═══\n\n"
                "Output a <scratchpad> block FIRST. Inside it, reconstruct every table "
                "from the payslip image as a Markdown table:\n\n"
                "a) STRICT OCR: Read the EXACT characters printed — do NOT guess, autocomplete, "
                "or substitute typical payslip terms. '013 משכורת' stays '013 משכורת'. "
                "'015 נסיעות' stays '015 נסיעות' — NOT 'נשפח'. Include row codes in labels.\n\n"
                "b) WIDE-TABLE ANCHORING: The description column (מלל or תיאור) is on the FAR "
                "RIGHT. The total column (סכום לתשלום or סכום) is on the FAR LEFT. For each "
                "row, start at the description on the far right and follow the SAME horizontal "
                "line all the way to the far left to find the total amount. Intermediate columns "
                "(תעריף, כמות) are between them on the same line. Do NOT let your eyes drift "
                "up or down — numbers must come from the SAME printed line as the label.\n\n"
                "c) STRICT HEADER-TO-FIELD MAPPING: Read the column HEADER ROW first. "
                "The number under the header כמות ALWAYS maps to JSON 'qty'. "
                "The number under the header תעריף ALWAYS maps to JSON 'rate'. "
                "The number under סכום/סכום לתשלום ALWAYS maps to JSON 'amount'. "
                "Do NOT swap rate and qty based on which number looks bigger or smaller. "
                "If תעריף=51.00 and כמות=83.75, then rate=51.00 and qty=83.75 — the column "
                "HEADER is the authority, not your expectation of value magnitudes.\n\n"
                "d) VERIFICATION: After each earnings row, write: "
                "'CHECK: {qty} × {rate} = {result} ≈ {amount} ✓/✗'. If ✗, you misaligned — fix it.\n\n"
                "e) EARNINGS TOTAL: After all earnings rows, sum the amounts and compare to "
                "סך-כל התשלומים printed on the payslip: "
                "'EARNINGS TOTAL: {sum of amounts} ≈ סך-כל התשלומים {printed_total} ✓/✗'. "
                "If ✗, go back and fix the misaligned rows.\n\n"
                "f) TAX TABLE: Reconstruct ניכויי חובה as a Markdown table. "
                "Write: 'TAX CHECK: {tax} + {NI} + {health} = {sum} ≈ סה\"כ {total} ✓/✗'.\n\n"
                "g) PENSION TABLE: Reconstruct with SEPARATE columns for ניכוי עובד (employee) "
                "and הפרשת מעסיק (employer). Label which is which.\n\n"
                "h) TOTALS and LEAVE BALANCES: Include as separate tables.\n\n"
                "Close the scratchpad with </scratchpad>.\n\n"
                "═══ PHASE 2: JSON ═══\n\n"
                "After </scratchpad>, produce the final JSON by reading from YOUR OWN "
                "scratchpad tables — NOT by re-reading the image. The scratchpad is now "
                "your source of truth.\n\n"
                f"{EXTRACTION_SCHEMA_HINT}\n\n{_FEW_SHOT_EXAMPLES}"
            )
        else:
            text_prompt = (
                f"Raw extracted text:\n\n{raw_text}\n\n"
                f"{EXTRACTION_SCHEMA_HINT}\n\n{_FEW_SHOT_EXAMPLES}"
            )

        messages_content.append({"type": "text", "text": text_prompt})

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": 8192,
                    "system": EXTRACTION_SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": messages_content}],
                },
            )
            resp.raise_for_status()
            data = resp.json()

        raw_json = data["content"][0]["text"]
        elapsed = time.monotonic() - t_start
        logger.info(
            "ClaudeExtractor: response received in %.2fs (response_chars=%d)",
            elapsed,
            len(raw_json),
        )
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
        import base64

        import httpx

        vision_only = bool(page_images) and _VISION_PLACEHOLDER in raw_text

        t_start = time.monotonic()
        logger.info(
            "OpenAIExtractor: starting extraction (model=%s, text_length=%d, "
            "images=%d, vision_only=%s)",
            self._model,
            len(raw_text),
            len(page_images) if page_images else 0,
            vision_only,
        )

        messages_content: list[dict] = []

        # Add images — images FIRST so the model sees them
        if page_images:
            for i, img_bytes in enumerate(page_images[:3]):
                b64 = base64.b64encode(img_bytes).decode()
                messages_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{b64}",
                        "detail": "high",
                    },
                })
                logger.info(
                    "OpenAIExtractor: attached image %d (%d bytes)",
                    i + 1, len(img_bytes),
                )

        # Build the text prompt — different for vision-only vs text+images
        if vision_only:
            text_prompt = (
                "The above image is a photograph of an Israeli payslip (תלוש שכר). "
                "No OCR text is available — extract ALL data directly from the image. "
                "The image is your ONLY source of data.\n\n"
                "YOU MUST USE THE TWO-PHASE APPROACH BELOW. Do NOT skip Phase 1.\n\n"
                "═══ PHASE 1: SCRATCHPAD — Markdown Grid Reconstruction ═══\n\n"
                "Output a <scratchpad> block FIRST. Inside it, reconstruct every table "
                "from the payslip image as a Markdown table:\n\n"
                "a) STRICT OCR: Read the EXACT characters printed — do NOT guess, autocomplete, "
                "or substitute typical payslip terms. '013 משכורת' stays '013 משכורת'. "
                "'015 נסיעות' stays '015 נסיעות' — NOT 'נשפח'. Include row codes in labels.\n\n"
                "b) WIDE-TABLE ANCHORING: The description column (מלל or תיאור) is on the FAR "
                "RIGHT. The total column (סכום לתשלום or סכום) is on the FAR LEFT. For each "
                "row, start at the description on the far right and follow the SAME horizontal "
                "line all the way to the far left to find the total amount. Intermediate columns "
                "(תעריף, כמות) are between them on the same line. Do NOT let your eyes drift "
                "up or down — numbers must come from the SAME printed line as the label.\n\n"
                "c) STRICT HEADER-TO-FIELD MAPPING: Read the column HEADER ROW first. "
                "The number under the header כמות ALWAYS maps to JSON 'qty'. "
                "The number under the header תעריף ALWAYS maps to JSON 'rate'. "
                "The number under סכום/סכום לתשלום ALWAYS maps to JSON 'amount'. "
                "Do NOT swap rate and qty based on which number looks bigger or smaller. "
                "If תעריף=51.00 and כמות=83.75, then rate=51.00 and qty=83.75 — the column "
                "HEADER is the authority, not your expectation of value magnitudes.\n\n"
                "d) VERIFICATION: After each earnings row, write: "
                "'CHECK: {qty} × {rate} = {result} ≈ {amount} ✓/✗'. If ✗, you misaligned — fix it.\n\n"
                "e) EARNINGS TOTAL: After all earnings rows, sum the amounts and compare to "
                "סך-כל התשלומים printed on the payslip: "
                "'EARNINGS TOTAL: {sum of amounts} ≈ סך-כל התשלומים {printed_total} ✓/✗'. "
                "If ✗, go back and fix the misaligned rows.\n\n"
                "f) TAX TABLE: Reconstruct ניכויי חובה as a Markdown table. "
                "Write: 'TAX CHECK: {tax} + {NI} + {health} = {sum} ≈ סה\"כ {total} ✓/✗'.\n\n"
                "g) PENSION TABLE: Reconstruct with SEPARATE columns for ניכוי עובד (employee) "
                "and הפרשת מעסיק (employer). Label which is which.\n\n"
                "h) TOTALS and LEAVE BALANCES: Include as separate tables.\n\n"
                "Close the scratchpad with </scratchpad>.\n\n"
                "═══ PHASE 2: JSON ═══\n\n"
                "After </scratchpad>, produce the final JSON by reading from YOUR OWN "
                "scratchpad tables — NOT by re-reading the image. The scratchpad is now "
                "your source of truth.\n\n"
                f"{EXTRACTION_SCHEMA_HINT}\n\n{_FEW_SHOT_EXAMPLES}"
            )
        else:
            text_prompt = (
                f"Raw extracted text:\n\n{raw_text}\n\n"
                f"{EXTRACTION_SCHEMA_HINT}\n\n{_FEW_SHOT_EXAMPLES}"
            )

        messages_content.append({"type": "text", "text": text_prompt})

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": 8192,
                    "messages": [
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": messages_content},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()

        raw_json = data["choices"][0]["message"]["content"]
        elapsed = time.monotonic() - t_start
        logger.info(
            "OpenAIExtractor: response received in %.2fs (response_chars=%d)",
            elapsed,
            len(raw_json),
        )
        return self._parse_llm_json(raw_json)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_extractor() -> LLMExtractor:
    """Return the configured LLM extractor instance."""
    if LLM_PROVIDER == "claude":
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY not set but LLM_PROVIDER=claude")
        logger.info("LLM provider: claude (Vision-capable)")
        return ClaudeExtractor(api_key=ANTHROPIC_API_KEY)
    elif LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not set but LLM_PROVIDER=openai")
        logger.info("LLM provider: openai (Vision-capable)")
        return OpenAIExtractor(api_key=OPENAI_API_KEY)
    else:
        logger.warning(
            "LLM provider: MOCK (LLM_PROVIDER=%r) — images will NOT be processed. "
            "Set LLM_PROVIDER=claude or openai in .env for real extraction.",
            LLM_PROVIDER,
        )
        return MockExtractor()
