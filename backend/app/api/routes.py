"""FastAPI route handlers for /parse and /analyze endpoints."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, Request, UploadFile

from ..data.glossary import get_field_info
from ..models.api_contracts import (
    AnalyzeRequest,
    AnalyzeResponse,
    ParseResponse,
    RequiredFieldStatus,
)
from ..models.payslip import ConfirmationHint, Payslip
from ..security.pii_masking import mask_pii
from ..security.rate_limiter import rate_limiter
from ..services.explanations import generate_explanations
from ..services.llm_extraction import get_extractor
from ..services.rules_engine import run_rules
from ..services.text_extraction import extract_text
from ..services.upload_handler import cleanup_file, handle_upload

logger = logging.getLogger(__name__)

router = APIRouter()


def _rate_limit(request: Request) -> None:
    rate_limiter.check(request)


def _count_populated_fields(payslip: Payslip) -> int:
    """Count how many key payslip fields have non-null values."""
    count = 0
    if payslip.employer.name:
        count += 1
    if payslip.employee.name:
        count += 1
    if payslip.period.month is not None:
        count += 1
    if payslip.period.year is not None:
        count += 1
    if payslip.totals.gross is not None:
        count += 1
    if payslip.totals.net is not None:
        count += 1
    if payslip.employment.salary_type is not None:
        count += 1
    if payslip.employment.base_rate is not None:
        count += 1
    count += len(payslip.earnings_lines)
    count += len(payslip.deductions_lines)
    return count


_TOTAL_CORE_FIELDS = 10  # core trackable fields before line items


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /parse
# ---------------------------------------------------------------------------

@router.post("/parse", response_model=ParseResponse)
async def parse_payslip(
    file: UploadFile,
    _: None = Depends(_rate_limit),
):
    """
    Upload a payslip file (PDF/JPG/PNG).
    Returns extracted text, parsed schema, and required-field status.
    The file is deleted after processing.
    """
    # 1. Validate and save file
    upload = await handle_upload(file)

    try:
        # 2. Extract text
        t_start = time.monotonic()
        extraction = extract_text(upload.file_path, upload.content_type)
        t_text = time.monotonic()
        method = extraction.method

        # 3. LLM-based structured extraction
        extractor = get_extractor()
        payslip = await extractor.extract(
            raw_text=extraction.raw_text,
            page_images=extraction.page_images or None,
        )
        t_llm = time.monotonic()

        # Merge extraction warnings
        payslip.meta.parse_warnings.extend(extraction.warnings)

        # 4. Determine which required fields were extracted
        required_status = RequiredFieldStatus(
            period_month=payslip.period.month is not None,
            period_year=payslip.period.year is not None,
            salary_type=payslip.employment.salary_type is not None,
            base_salary_or_rate=payslip.employment.base_rate is not None,
            regular_hours_worked=payslip.employment.hours_regular is not None,
            job_percent=payslip.employment.job_percent is not None,
            pension_expected=payslip.pension.employee_tagmulim is not None
            or payslip.pension.employer_tagmulim is not None,
        )

        # Log missing required fields
        missing_required = [
            name
            for name, present in [
                ("period_month", required_status.period_month),
                ("period_year", required_status.period_year),
                ("salary_type", required_status.salary_type),
                ("base_rate", required_status.base_salary_or_rate),
                ("hours_regular", required_status.regular_hours_worked),
            ]
            if not present
        ]
        if missing_required:
            logger.info("Missing required fields for confirmation: %s", missing_required)

        # Build confirmation hints with Hebrew labels from glossary
        hints: list[ConfirmationHint] = []
        for field_key in payslip.meta.needs_user_confirmation_fields:
            fi = get_field_info(field_key)
            hints.append(ConfirmationHint(
                field_key=field_key,
                label_he=fi.label_he if fi else field_key,
                help_he=fi.help_he if fi else None,
            ))
        # Also add hints for required fields not extracted
        for field_key in missing_required:
            if field_key not in {h.field_key for h in hints}:
                fi = get_field_info(field_key)
                hints.append(ConfirmationHint(
                    field_key=field_key,
                    label_he=fi.label_he if fi else field_key,
                    help_he=fi.help_he if fi else None,
                ))
        payslip.meta.confirmation_hints = hints

        # Update LLM extraction method label
        method = f"{method}+llm"

        # 5. Redact PII for the preview (raw text stays for frontend display but IDs masked)
        redacted_preview = mask_pii(extraction.raw_text)

        # Log anonymized metrics with timing
        fields_found = _count_populated_fields(payslip)
        logger.info(
            "Parse complete: method=%s text_chars=%d lines=%d "
            "fields_found=%d/%d warnings=%d "
            "text_extraction_ms=%d llm_extraction_ms=%d total_ms=%d hash=%s",
            method,
            len(extraction.raw_text),
            len(extraction.raw_text.splitlines()),
            fields_found,
            _TOTAL_CORE_FIELDS,
            len(payslip.meta.parse_warnings),
            int((t_text - t_start) * 1000),
            int((t_llm - t_text) * 1000),
            int((time.monotonic() - t_start) * 1000),
            upload.file_hash[:12],
        )

        return ParseResponse(
            payslip=payslip,
            raw_text=extraction.raw_text,
            redacted_preview=redacted_preview,
            required_fields_status=required_status,
            file_hash=upload.file_hash,
            extraction_method=method,
        )

    finally:
        # 6. Clean up temporary file
        cleanup_file(upload.file_path)


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_payslip(
    body: AnalyzeRequest,
    _: None = Depends(_rate_limit),
):
    """
    Receive user-confirmed fields + parsed schema.
    Run rules engine and return flags, OK items, explanations, and summary cards.
    """
    payslip = body.payslip
    confirmed = body.confirmed_fields

    # Merge confirmed fields into payslip (user overrides extraction)
    payslip.period.month = confirmed.period_month
    payslip.period.year = confirmed.period_year
    payslip.employment.salary_type = confirmed.salary_type
    payslip.employment.base_rate = confirmed.base_salary_or_rate
    if confirmed.regular_hours_worked is not None:
        payslip.employment.hours_regular = confirmed.regular_hours_worked
    if confirmed.job_percent is not None:
        payslip.employment.job_percent = confirmed.job_percent

    # Run rules engine
    flags = run_rules(payslip, confirmed)

    # Generate explanations
    result = generate_explanations(payslip, flags)

    logger.info(
        "Analysis complete: flags=%d ok=%d lines=%d",
        len(result.flags),
        len(result.ok_items),
        len(result.line_explanations),
    )

    return AnalyzeResponse(result=result)
