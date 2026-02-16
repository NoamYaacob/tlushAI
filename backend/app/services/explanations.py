"""
Hebrew explanation generator for payslip line items.

Phase 1: basic line categorization and Hebrew labels for common items.
Full implementation with detailed explanations in Phase 2.
"""

from __future__ import annotations

from ..models.payslip import (
    AnalysisResult,
    Flag,
    LineCategory,
    LineExplanation,
    OkItem,
    Payslip,
    SummaryCard,
)

# ---------------------------------------------------------------------------
# Known line-item mappings (label -> Hebrew meaning + category)
# ---------------------------------------------------------------------------

_LINE_MEANINGS: dict[str, tuple[str, LineCategory, bool, bool]] = {
    # label -> (meaning_he, category, affects_gross, affects_taxable)
    "base_salary": ("שכר הבסיס החודשי לפי הסכם העבודה", LineCategory.earning, True, True),
    "overtime_125": ("תוספת שעות נוספות בשיעור 125% מהשכר הרגיל", LineCategory.earning, True, True),
    "overtime_150": ("תוספת שעות נוספות בשיעור 150% מהשכר הרגיל", LineCategory.earning, True, True),
    "travel_allowance": ("החזר הוצאות נסיעה לעבודה וממנה", LineCategory.earning, True, False),
    "recuperation": ("דמי הבראה — זכות שנתית לפי הסכם/צו הרחבה", LineCategory.earning, True, True),
    "bonus": ("בונוס / מענק — בדוק אם חד-פעמי או קבוע", LineCategory.earning, True, True),
    "income_tax": ("מס הכנסה שנוכה במקור לפי מדרגות המס", LineCategory.tax, False, False),
    "national_insurance": ("דמי ביטוח לאומי (עובד) — ביטוח סוציאלי", LineCategory.tax, False, False),
    "health_tax": ("מס בריאות — ניכוי חובה לקופת חולים", LineCategory.tax, False, False),
    "pension_employee": ("הפרשת עובד לפנסיה (תגמולים)", LineCategory.deduction, False, False),
    "pension_employer": ("הפרשת מעביד לפנסיה (תגמולים)", LineCategory.employer_contribution, False, False),
    "severance_employer": ("הפרשת מעביד לפיצויי פיטורין", LineCategory.employer_contribution, False, False),
    "training_fund_employee": ("הפרשת עובד לקרן השתלמות", LineCategory.deduction, False, False),
    "training_fund_employer": ("הפרשת מעביד לקרן השתלמות", LineCategory.employer_contribution, False, False),
}


def generate_explanations(
    payslip: Payslip,
    flags: list[Flag],
) -> AnalysisResult:
    """Build the full analysis result with explanations, OK items, and summary cards."""
    line_explanations = _build_line_explanations(payslip)
    ok_items = _build_ok_items(payslip, flags)
    summary_cards = _build_summary_cards(payslip)

    return AnalysisResult(
        flags=flags,
        ok_items=ok_items,
        line_explanations=line_explanations,
        summary_cards=summary_cards,
    )


# ---------------------------------------------------------------------------
# Line explanations
# ---------------------------------------------------------------------------

def _build_line_explanations(payslip: Payslip) -> list[LineExplanation]:
    explanations: list[LineExplanation] = []

    for line in payslip.earnings_lines:
        info = _LINE_MEANINGS.get(line.label)
        explanations.append(LineExplanation(
            label=line.label_he or line.label,
            amount=line.amount,
            category=info[1] if info else LineCategory.earning,
            meaning_he=info[0] if info else "רכיב שכר — בדוק מול הסכם העבודה",
            affects_gross=info[2] if info else True,
            affects_taxable=info[3] if info else None,
            status="ok",
        ))

    for line in payslip.deductions_lines:
        info = _LINE_MEANINGS.get(line.label)
        explanations.append(LineExplanation(
            label=line.label_he or line.label,
            amount=line.amount,
            category=info[1] if info else LineCategory.deduction,
            meaning_he=info[0] if info else "ניכוי — בדוק מול הסכם העבודה",
            affects_gross=False,
            affects_taxable=info[3] if info else None,
            status="ok",
        ))

    for line in payslip.employer_contrib_lines:
        info = _LINE_MEANINGS.get(line.label)
        explanations.append(LineExplanation(
            label=line.label_he or line.label,
            amount=line.amount,
            category=info[1] if info else LineCategory.employer_contribution,
            meaning_he=info[0] if info else "הפרשת מעסיק — לא מנוכה מהשכר",
            affects_gross=False,
            affects_taxable=False,
            status="ok",
        ))

    return explanations


# ---------------------------------------------------------------------------
# OK items
# ---------------------------------------------------------------------------

def _build_ok_items(payslip: Payslip, flags: list[Flag]) -> list[OkItem]:
    """Generate OK items for things that look correct."""
    ok: list[OkItem] = []
    flagged_titles = {f.title_he for f in flags}

    if payslip.totals.gross and payslip.totals.net and "חוסר התאמה בין ברוטו לנטו" not in flagged_titles:
        ok.append(OkItem(
            title_he="ברוטו-נטו תקין",
            explanation_he="ברוטו פחות סך ניכויים מתאים לנטו בתלוש (בסטייה סבירה).",
            confidence=0.85,
        ))

    if payslip.pension.employee_tagmulim and payslip.pension.employer_tagmulim:
        if "ייתכן חוסר בהפרשת מעסיק לפנסיה" not in flagged_titles:
            ok.append(OkItem(
                title_he="הפרשות פנסיה נמצאו",
                explanation_he="זוהו הפרשות תגמולי עובד ומעביד.",
                confidence=0.8,
            ))

    if payslip.employer.name and payslip.employee.name:
        ok.append(OkItem(
            title_he="פרטי מעסיק ועובד קיימים",
            explanation_he="שם המעסיק והעובד זוהו בתלוש.",
            confidence=0.9,
        ))

    return ok


# ---------------------------------------------------------------------------
# Summary cards
# ---------------------------------------------------------------------------

def _build_summary_cards(payslip: Payslip) -> list[SummaryCard]:
    cards: list[SummaryCard] = []

    def _card(key: str, label_he: str, value: float | None) -> SummaryCard:
        if value is not None:
            return SummaryCard(
                key=key,
                label_he=label_he,
                value=value,
                formatted_value=f"₪ {value:,.2f}",
                status="ok",
            )
        return SummaryCard(key=key, label_he=label_he, status="missing")

    cards.append(_card("gross", "שכר ברוטו", payslip.totals.gross))
    cards.append(_card("net", "שכר נטו", payslip.totals.net))
    cards.append(_card("total_deductions", "סה\"כ ניכויים", payslip.totals.total_deductions))

    # Pension total
    pension_total = None
    if payslip.pension.employee_tagmulim is not None:
        pension_total = payslip.pension.employee_tagmulim
        if payslip.pension.employer_tagmulim:
            pension_total += payslip.pension.employer_tagmulim
        if payslip.pension.employer_pitzuyim:
            pension_total += payslip.pension.employer_pitzuyim
    cards.append(_card("pension", "סה\"כ פנסיה", pension_total))

    # Travel
    travel = next(
        (e.amount for e in payslip.earnings_lines if "travel" in e.label.lower()),
        None,
    )
    cards.append(_card("travel", "נסיעות", travel))

    # Overtime
    overtime = sum(
        e.amount for e in payslip.earnings_lines if "overtime" in e.label.lower()
    ) or None
    cards.append(_card("overtime", "שעות נוספות", overtime))

    return cards
