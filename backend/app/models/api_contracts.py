"""Request and response models for the API endpoints."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .payslip import AnalysisResult, Payslip, SalaryType


# ---------------------------------------------------------------------------
# POST /parse — response
# ---------------------------------------------------------------------------

class RequiredFieldStatus(BaseModel):
    """Tracks which required fields were extracted vs need user input."""
    period_month: bool = False
    period_year: bool = False
    salary_type: bool = False
    base_salary_or_rate: bool = False
    regular_hours_worked: bool = False
    job_percent: bool = False
    pension_expected: bool = False


class ParseResponse(BaseModel):
    """Returned by POST /parse after file upload + extraction."""
    payslip: Payslip
    raw_text: str
    redacted_preview: str
    required_fields_status: RequiredFieldStatus
    file_hash: str
    extraction_method: str  # "pdf_text" | "ocr" | "ocr+llm" | "pdf_text+llm"


# ---------------------------------------------------------------------------
# POST /analyze — request
# ---------------------------------------------------------------------------

class UserConfirmedFields(BaseModel):
    """Fields the user confirms or edits in the Review & Confirm step."""
    period_month: int = Field(ge=1, le=12)
    period_year: int = Field(ge=2000, le=2100)
    salary_type: SalaryType
    base_salary_or_rate: float = Field(gt=0)
    regular_hours_worked: Optional[float] = Field(None, ge=0)
    job_percent: Optional[float] = Field(None, ge=0, le=200)
    pension_expected: bool = True
    training_fund_expected: Optional[bool] = None


class AnalyzeRequest(BaseModel):
    """Sent by frontend after user confirms/edits fields."""
    payslip: Payslip
    confirmed_fields: UserConfirmedFields


# ---------------------------------------------------------------------------
# POST /analyze — response
# ---------------------------------------------------------------------------

class AnalyzeResponse(BaseModel):
    """Returned by POST /analyze after rules engine runs."""
    result: AnalysisResult
