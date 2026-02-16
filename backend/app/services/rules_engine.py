"""
Rules engine — Israel-specific payslip compliance checks.

Phase 1 stub: implements basic checks (required fields, net sanity).
Full 10-rule implementation in Phase 2.

IMPORTANT: All results use conservative language ("possible issue",
"requires verification"). The system does NOT claim legal certainty.
"""

from __future__ import annotations

import logging

from ..config.constants import NET_TOLERANCE_NIS
from ..models.api_contracts import UserConfirmedFields
from ..models.payslip import Flag, FlagSeverity, Payslip

logger = logging.getLogger(__name__)


def run_rules(payslip: Payslip, confirmed: UserConfirmedFields) -> list[Flag]:
    """
    Run all compliance checks and return a list of flags.
    Each rule function returns a list of Flag objects.
    """
    flags: list[Flag] = []

    flags.extend(_check_required_basics(payslip))
    flags.extend(_check_net_sanity(payslip))
    flags.extend(_check_pension_lines(payslip, confirmed))
    flags.extend(_check_tax_lines_present(payslip))

    return flags


# ---------------------------------------------------------------------------
# Rule 1: Required basics present
# ---------------------------------------------------------------------------

def _check_required_basics(payslip: Payslip) -> list[Flag]:
    """Check that essential fields are populated."""
    flags: list[Flag] = []
    missing: list[str] = []

    if not payslip.employer.name:
        missing.append("שם מעסיק")
    if not payslip.employee.name:
        missing.append("שם עובד")
    if payslip.period.month is None or payslip.period.year is None:
        missing.append("חודש/שנת שכר")
    if payslip.totals.gross is None:
        missing.append("שכר ברוטו")
    if payslip.totals.net is None:
        missing.append("שכר נטו")

    if missing:
        flags.append(Flag(
            severity=FlagSeverity.warn,
            title_he="שדות חובה חסרים",
            explanation_he=(
                f"השדות הבאים לא זוהו בתלוש: {', '.join(missing)}. "
                "ייתכן שמדובר בבעיית חילוץ טקסט. מומלץ לבדוק את התלוש המקורי."
            ),
            evidence=f"Missing: {', '.join(missing)}",
            suggested_next_step="בדוק את התלוש המקורי והשלם את השדות החסרים",
            confidence=0.9,
        ))

    return flags


# ---------------------------------------------------------------------------
# Rule 2: Net sanity check (gross - deductions ≈ net)
# ---------------------------------------------------------------------------

def _check_net_sanity(payslip: Payslip) -> list[Flag]:
    """Verify that gross minus deductions approximately equals net."""
    if payslip.totals.gross is None or payslip.totals.net is None:
        return []

    total_deductions = payslip.totals.total_deductions
    if total_deductions is None:
        # Sum deduction lines as fallback
        total_deductions = sum(d.amount for d in payslip.deductions_lines)

    expected_net = payslip.totals.gross - total_deductions
    diff = abs(expected_net - payslip.totals.net)

    if diff > NET_TOLERANCE_NIS:
        return [Flag(
            severity=FlagSeverity.warn,
            title_he="חוסר התאמה בין ברוטו לנטו",
            explanation_he=(
                f"ברוטו ({payslip.totals.gross:,.2f} ₪) פחות סך ניכויים "
                f"({total_deductions:,.2f} ₪) = {expected_net:,.2f} ₪, "
                f"אך הנטו בתלוש הוא {payslip.totals.net:,.2f} ₪ "
                f"(הפרש: {diff:,.2f} ₪). ייתכן שחסרים ניכויים או שיש טעות."
            ),
            evidence=f"Expected net: {expected_net:.2f}, Actual net: {payslip.totals.net:.2f}, Diff: {diff:.2f}",
            suggested_next_step="בדוק שכל שורות הניכויים מופיעות ושהסכומים נכונים",
            confidence=0.85,
        )]

    return []


# ---------------------------------------------------------------------------
# Rule 3: Pension lines (basic check)
# ---------------------------------------------------------------------------

def _check_pension_lines(payslip: Payslip, confirmed: UserConfirmedFields) -> list[Flag]:
    """Check pension contributions if user expects pension."""
    if not confirmed.pension_expected:
        return []

    flags: list[Flag] = []

    employee_pension = payslip.pension.employee_tagmulim
    employer_pension = payslip.pension.employer_tagmulim

    if employee_pension and employee_pension > 0 and (employer_pension is None or employer_pension == 0):
        flags.append(Flag(
            severity=FlagSeverity.warn,
            title_he="ייתכן חוסר בהפרשת מעסיק לפנסיה",
            explanation_he=(
                "זוהה ניכוי תגמולי עובד לפנסיה אך לא נמצאה הפרשת מעסיק תואמת. "
                "על פי צווי ההרחבה, המעסיק מחויב להפריש לתגמולים ולפיצויים. "
                "ייתכן שההפרשה קיימת אך לא זוהתה בחילוץ."
            ),
            evidence=f"Employee pension: {employee_pension}, Employer pension: {employer_pension}",
            suggested_next_step="בדוק את דוח ההפרשות הפנסיוניות מול קופת הגמל/ביטוח המנהלים",
            confidence=0.7,
        ))

    if (employee_pension is None or employee_pension == 0) and (employer_pension is None or employer_pension == 0):
        flags.append(Flag(
            severity=FlagSeverity.warn,
            title_he="לא זוהו הפרשות פנסיוניות",
            explanation_he=(
                "לא נמצאו שורות הפרשה לפנסיה (תגמולי עובד/מעביד). "
                "אם אתה זכאי לפנסיה, ייתכן שמדובר בבעיית חילוץ טקסט "
                "או שההפרשות חסרות בפועל. מומלץ לבדוק."
            ),
            evidence="No pension lines found",
            suggested_next_step="בדוק הסכם עבודה ודוח הפרשות פנסיוניות",
            confidence=0.75,
        ))

    return flags


# ---------------------------------------------------------------------------
# Rule 9: Tax lines presence
# ---------------------------------------------------------------------------

def _check_tax_lines_present(payslip: Payslip) -> list[Flag]:
    """Check that basic tax deduction lines exist when gross is above 0."""
    if payslip.totals.gross is None or payslip.totals.gross <= 0:
        return []

    all_labels: list[str] = []
    for d in payslip.deductions_lines:
        all_labels.append(d.label.lower())
        if d.label_he:
            all_labels.append(d.label_he.strip())

    combined = " ".join(all_labels)

    flags: list[Flag] = []

    # Income tax
    has_income_tax = any(
        kw in combined
        for kw in ("income_tax", "מס הכנסה")
    )

    # National insurance
    has_bituach = any(
        kw in combined
        for kw in ("national_insurance", "ביטוח לאומי")
    )

    # Health tax
    has_health = any(
        kw in combined
        for kw in ("health_tax", "מס בריאות")
    )

    missing_taxes: list[str] = []
    if not has_income_tax:
        missing_taxes.append("מס הכנסה")
    if not has_bituach:
        missing_taxes.append("ביטוח לאומי")
    if not has_health:
        missing_taxes.append("מס בריאות")

    if missing_taxes:
        flags.append(Flag(
            severity=FlagSeverity.warn,
            title_he="ייתכן שחסרות שורות מס",
            explanation_he=(
                f"לא זוהו השורות הבאות: {', '.join(missing_taxes)}. "
                "ייתכן שהשורות קיימות בתלוש אך לא זוהו בחילוץ, "
                "או שהעובד פטור (הכנסה נמוכה / נקודות זיכוי). מומלץ לוודא."
            ),
            evidence=f"Missing tax lines: {', '.join(missing_taxes)}",
            suggested_next_step="בדוק את התלוש המקורי ואת תיאום המס",
            confidence=0.6,
        ))

    return flags
