"""
Hebrew explanation generator for payslip line items.

Uses the centralized glossary for consistent categorization and Hebrew labels.
"""

from __future__ import annotations

from ..data.glossary import classify_line
from ..models.payslip import (
    AnalysisResult,
    Flag,
    LineCategory,
    LineExplanation,
    OkItem,
    Payslip,
    SummaryCard,
)

# Section labels for grouping line explanations
_SECTION_MAP = {
    LineCategory.earning: "earnings",
    LineCategory.deduction: "deductions",
    LineCategory.employer_contribution: "employer_contributions",
    LineCategory.tax: "tax",
    LineCategory.leave: "earnings",
    LineCategory.other: "earnings",
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
        info = classify_line(line.label, line.label_he)
        cat = info.category if info else LineCategory.earning
        explanations.append(LineExplanation(
            label=line.label_he or line.label,
            amount=line.amount,
            qty=line.qty,
            rate=line.rate,
            category=cat,
            meaning_he=info.explanation_he if info else "רכיב שכר — בדוק מול הסכם העבודה",
            affects_gross=info.affects_gross if info else True,
            affects_taxable=info.affects_taxable if info else None,
            status="ok",
            section=_SECTION_MAP.get(cat, "earnings"),
        ))

    for line in payslip.deductions_lines:
        info = classify_line(line.label, line.label_he)
        cat = info.category if info else LineCategory.deduction
        explanations.append(LineExplanation(
            label=line.label_he or line.label,
            amount=line.amount,
            category=cat,
            meaning_he=info.explanation_he if info else "ניכוי — בדוק מול הסכם העבודה",
            affects_gross=False,
            affects_taxable=info.affects_taxable if info else None,
            status="ok",
            section=_SECTION_MAP.get(cat, "deductions"),
        ))

    for line in payslip.employer_contrib_lines:
        info = classify_line(line.label, line.label_he)
        cat = info.category if info else LineCategory.employer_contribution
        explanations.append(LineExplanation(
            label=line.label_he or line.label,
            amount=line.amount,
            category=cat,
            meaning_he=info.explanation_he if info else "הפרשת מעסיק — לא מנוכה מהשכר",
            affects_gross=False,
            affects_taxable=False,
            status="ok",
            section="employer_contributions",
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

    # Gross = sum of earnings check
    if payslip.totals.gross and payslip.earnings_lines:
        earnings_sum = sum(l.amount for l in payslip.earnings_lines)
        if abs(payslip.totals.gross - earnings_sum) <= 5.0:
            if "הפרש בין ברוטו לסכום שורות ההכנסה" not in flagged_titles:
                ok.append(OkItem(
                    title_he="סכום הכנסות תואם ברוטו",
                    explanation_he="סכום שורות ההכנסה תואם לברוטו המצוין בתלוש.",
                    confidence=0.85,
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

    # Pension total (employee only — employer contributions are separate)
    pension_employee = payslip.pension.employee_tagmulim
    cards.append(_card("pension_employee", "פנסיה (עובד)", pension_employee))

    # Employer pension total
    pension_employer = None
    if payslip.pension.employer_tagmulim is not None:
        pension_employer = payslip.pension.employer_tagmulim
        if payslip.pension.employer_pitzuyim:
            pension_employer += payslip.pension.employer_pitzuyim
    cards.append(_card("pension_employer", "פנסיה (מעסיק)", pension_employer))

    # Travel
    travel_kw = {"travel", "נסיעות", "נסיעה"}
    travel = next(
        (e.amount for e in payslip.earnings_lines
         if any(kw in e.label.lower() or kw in (e.label_he or "") for kw in travel_kw)),
        None,
    )
    cards.append(_card("travel", "נסיעות", travel))

    # Overtime
    ot_kw = {"overtime", "נוספות"}
    overtime = sum(
        e.amount for e in payslip.earnings_lines
        if any(kw in e.label.lower() or kw in (e.label_he or "") for kw in ot_kw)
    ) or None
    cards.append(_card("overtime", "שעות נוספות", overtime))

    return cards
