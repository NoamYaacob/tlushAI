"""Tests for the explanations service with glossary integration."""

from app.models.payslip import (
    DeductionLine,
    EarningsLine,
    EmployerContribLine,
    Payslip,
    Pension,
    Totals,
)
from app.services.explanations import generate_explanations


class TestLineExplanationSections:
    """Line explanations should be tagged with correct sections."""

    def test_earnings_get_earnings_section(self):
        payslip = Payslip(
            earnings_lines=[
                EarningsLine(label="base_salary", label_he="שכר יסוד", amount=10000.0),
            ],
            totals=Totals(gross=10000.0, net=8000.0),
        )
        result = generate_explanations(payslip, [])
        assert len(result.line_explanations) == 1
        assert result.line_explanations[0].section == "earnings"

    def test_deductions_get_deductions_section(self):
        payslip = Payslip(
            deductions_lines=[
                DeductionLine(label="pension_employee", label_he="תגמולים עובד", amount=900.0),
            ],
        )
        result = generate_explanations(payslip, [])
        assert len(result.line_explanations) == 1
        assert result.line_explanations[0].section == "deductions"

    def test_tax_deductions_get_tax_section(self):
        payslip = Payslip(
            deductions_lines=[
                DeductionLine(label="income_tax", label_he="מס הכנסה", amount=1500.0),
            ],
        )
        result = generate_explanations(payslip, [])
        assert len(result.line_explanations) == 1
        assert result.line_explanations[0].section == "tax"

    def test_employer_contribs_get_employer_section(self):
        payslip = Payslip(
            employer_contrib_lines=[
                EmployerContribLine(label="pension_employer", label_he="תגמולים מעביד", amount=975.0),
            ],
        )
        result = generate_explanations(payslip, [])
        assert len(result.line_explanations) == 1
        assert result.line_explanations[0].section == "employer_contributions"


class TestGlossaryIntegration:
    """The glossary should provide Hebrew explanations."""

    def test_known_item_gets_glossary_explanation(self):
        payslip = Payslip(
            earnings_lines=[
                EarningsLine(label="base_salary", label_he="שכר יסוד", amount=10000.0),
            ],
        )
        result = generate_explanations(payslip, [])
        assert len(result.line_explanations) == 1
        exp = result.line_explanations[0]
        assert "שכר הבסיס" in exp.meaning_he

    def test_unknown_item_gets_fallback(self):
        payslip = Payslip(
            earnings_lines=[
                EarningsLine(label="xyzzy_unknown", amount=500.0),
            ],
        )
        result = generate_explanations(payslip, [])
        assert len(result.line_explanations) == 1
        exp = result.line_explanations[0]
        assert "רכיב שכר" in exp.meaning_he


class TestSummaryCards:
    """Summary cards should be generated correctly."""

    def test_basic_summary_cards(self):
        payslip = Payslip(
            totals=Totals(gross=15000.0, net=12000.0, total_deductions=3000.0),
        )
        result = generate_explanations(payslip, [])
        keys = {c.key for c in result.summary_cards}
        assert "gross" in keys
        assert "net" in keys
        assert "total_deductions" in keys

    def test_pension_cards_split(self):
        """Pension should be split into employee and employer cards."""
        payslip = Payslip(
            pension=Pension(
                employee_tagmulim=900.0,
                employer_tagmulim=975.0,
                employer_pitzuyim=900.0,
            ),
        )
        result = generate_explanations(payslip, [])
        keys = {c.key for c in result.summary_cards}
        assert "pension_employee" in keys
        assert "pension_employer" in keys


class TestOkItems:
    """OK items should be generated when things look correct."""

    def test_gross_net_ok(self):
        payslip = Payslip(
            totals=Totals(gross=15000.0, net=12000.0, total_deductions=3000.0),
        )
        result = generate_explanations(payslip, [])
        ok_titles = [item.title_he for item in result.ok_items]
        assert "ברוטו-נטו תקין" in ok_titles

    def test_earnings_sum_ok(self):
        payslip = Payslip(
            earnings_lines=[
                EarningsLine(label="base_salary", amount=10000.0),
                EarningsLine(label="travel_allowance", amount=500.0),
            ],
            totals=Totals(gross=10500.0, net=8000.0),
        )
        result = generate_explanations(payslip, [])
        ok_titles = [item.title_he for item in result.ok_items]
        assert "סכום הכנסות תואם ברוטו" in ok_titles
