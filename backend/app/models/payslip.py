"""Pydantic models for the parsed payslip schema."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SalaryType(str, Enum):
    monthly = "monthly"
    hourly = "hourly"


class FlagSeverity(str, Enum):
    info = "info"
    warn = "warn"
    high = "high"


class LineCategory(str, Enum):
    earning = "earning"
    deduction = "deduction"
    employer_contribution = "employer_contribution"
    tax = "tax"
    leave = "leave"
    other = "other"


# ---------------------------------------------------------------------------
# Sub-schemas
# ---------------------------------------------------------------------------

class Employer(BaseModel):
    name: Optional[str] = None
    id: Optional[str] = None
    address: Optional[str] = None


class Employee(BaseModel):
    name: Optional[str] = None
    id: Optional[str] = None
    job_title: Optional[str] = None


class Period(BaseModel):
    month: Optional[int] = Field(None, ge=1, le=12)
    year: Optional[int] = Field(None, ge=2000, le=2100)


class Employment(BaseModel):
    salary_type: Optional[SalaryType] = None
    base_rate: Optional[float] = None
    job_percent: Optional[float] = Field(None, ge=0, le=200)
    hours_regular: Optional[float] = None
    hours_overtime_125: Optional[float] = None
    hours_overtime_150: Optional[float] = None
    weekend_hours: Optional[float] = None
    holiday_hours: Optional[float] = None


class EarningsLine(BaseModel):
    label: str
    label_he: Optional[str] = None
    qty: Optional[float] = None
    rate: Optional[float] = None
    amount: float


class DeductionLine(BaseModel):
    label: str
    label_he: Optional[str] = None
    amount: float


class EmployerContribLine(BaseModel):
    label: str
    label_he: Optional[str] = None
    amount: float


class Pension(BaseModel):
    employee_tagmulim: Optional[float] = None
    employer_tagmulim: Optional[float] = None
    employer_pitzuyim: Optional[float] = None
    training_fund_employee: Optional[float] = None
    training_fund_employer: Optional[float] = None
    fund_name: Optional[str] = None


class LeaveBalances(BaseModel):
    vacation_open: Optional[float] = None
    vacation_accrued: Optional[float] = None
    vacation_used: Optional[float] = None
    vacation_close: Optional[float] = None
    sick_open: Optional[float] = None
    sick_accrued: Optional[float] = None
    sick_used: Optional[float] = None
    sick_close: Optional[float] = None


class Totals(BaseModel):
    gross: Optional[float] = None
    taxable_gross: Optional[float] = None
    net: Optional[float] = None
    total_deductions: Optional[float] = None
    total_employer_cost: Optional[float] = None


class ConfirmationHint(BaseModel):
    """A field that needs user confirmation, with Hebrew label."""
    field_key: str
    label_he: str
    help_he: Optional[str] = None


class ParseMeta(BaseModel):
    parse_warnings: list[str] = Field(default_factory=list)
    needs_user_confirmation_fields: list[str] = Field(default_factory=list)
    confirmation_hints: list[ConfirmationHint] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level Payslip
# ---------------------------------------------------------------------------

class Payslip(BaseModel):
    employer: Employer = Field(default_factory=Employer)
    employee: Employee = Field(default_factory=Employee)
    period: Period = Field(default_factory=Period)
    payment_date: Optional[str] = None
    employment: Employment = Field(default_factory=Employment)
    earnings_lines: list[EarningsLine] = Field(default_factory=list)
    deductions_lines: list[DeductionLine] = Field(default_factory=list)
    employer_contrib_lines: list[EmployerContribLine] = Field(default_factory=list)
    pension: Pension = Field(default_factory=Pension)
    leave: LeaveBalances = Field(default_factory=LeaveBalances)
    totals: Totals = Field(default_factory=Totals)
    meta: ParseMeta = Field(default_factory=ParseMeta)


# ---------------------------------------------------------------------------
# Rules engine output
# ---------------------------------------------------------------------------

class Flag(BaseModel):
    severity: FlagSeverity
    title_he: str
    explanation_he: str
    evidence: Optional[str] = None
    suggested_next_step: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class OkItem(BaseModel):
    title_he: str
    explanation_he: str
    confidence: float = Field(ge=0.0, le=1.0)


class LineExplanation(BaseModel):
    label: str
    amount: float
    qty: Optional[float] = None
    rate: Optional[float] = None
    category: LineCategory
    meaning_he: str
    affects_gross: Optional[bool] = None
    affects_taxable: Optional[bool] = None
    status: str = "ok"  # "ok" | "check" | "warn"
    note_he: Optional[str] = None
    section: Optional[str] = None  # "earnings" | "deductions" | "employer_contributions" | "tax"


class SummaryCard(BaseModel):
    key: str  # e.g. "gross", "net", "pension"
    label_he: str
    value: Optional[float] = None
    formatted_value: Optional[str] = None
    status: str = "ok"  # "ok" | "check" | "warn" | "missing"


class AnalysisResult(BaseModel):
    flags: list[Flag] = Field(default_factory=list)
    ok_items: list[OkItem] = Field(default_factory=list)
    line_explanations: list[LineExplanation] = Field(default_factory=list)
    summary_cards: list[SummaryCard] = Field(default_factory=list)
    disclaimer_he: str = (
        "מערכת זו מספקת הערכה ראשונית בלבד ואינה מהווה ייעוץ משפטי או חשבונאי. "
        "יש לאמת כל ממצא מול הסכם העבודה, דוחות נוכחות, ודוחות הפרשות פנסיוניות."
    )
