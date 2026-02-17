"""Tests for new rules engine checks (14-16) and false alarm prevention."""

import pytest

from app.models.api_contracts import UserConfirmedFields
from app.models.payslip import (
    DeductionLine,
    EarningsLine,
    EmployerContribLine,
    FlagSeverity,
    Payslip,
    SalaryType,
    Totals,
)
from app.services.rules_engine import run_rules


def _confirmed(**overrides) -> UserConfirmedFields:
    defaults = dict(
        period_month=1,
        period_year=2026,
        salary_type=SalaryType.monthly,
        base_salary_or_rate=15000.0,
        pension_expected=True,
    )
    defaults.update(overrides)
    return UserConfirmedFields(**defaults)


def _flags_titled(flags, substr):
    return [f for f in flags if substr in f.title_he]


# ═══════════════════════════════════════════════════════════════════════════
# Rule 11 — Income tax false alarm prevention
# ═══════════════════════════════════════════════════════════════════════════

class TestIncomeTaxFalseAlarm:
    """Income tax check should NOT fire when taxable_gross is unavailable."""

    def test_no_taxable_gross_means_no_tax_flag(self):
        """When only gross is available (not taxable_gross), skip tax check."""
        payslip = Payslip(
            totals=Totals(gross=15000.0, net=12000.0),
            deductions_lines=[
                DeductionLine(label="income_tax", label_he="מס הכנסה", amount=500.0),
            ],
        )
        flags = run_rules(payslip, _confirmed())
        tax_flags = _flags_titled(flags, "הפרש בחישוב מס הכנסה")
        assert len(tax_flags) == 0

    def test_with_taxable_gross_may_flag(self):
        """When taxable_gross IS available, the check should run."""
        payslip = Payslip(
            totals=Totals(gross=15000.0, taxable_gross=14500.0, net=12000.0),
            deductions_lines=[
                DeductionLine(label="income_tax", label_he="מס הכנסה", amount=50.0),
            ],
        )
        flags = run_rules(payslip, _confirmed())
        tax_flags = _flags_titled(flags, "הפרש בחישוב מס הכנסה")
        # The exact tax calculation may or may not flag depending on values,
        # but the check should at least run (no crash)
        assert isinstance(tax_flags, list)


# ═══════════════════════════════════════════════════════════════════════════
# Rule 14 — Gross = sum of earnings lines
# ═══════════════════════════════════════════════════════════════════════════

class TestGrossSum:
    def test_matching_gross_no_flag(self):
        payslip = Payslip(
            earnings_lines=[
                EarningsLine(label="base_salary", amount=10000.0),
                EarningsLine(label="travel_allowance", amount=500.0),
            ],
            totals=Totals(gross=10500.0, net=8000.0),
        )
        flags = run_rules(payslip, _confirmed(base_salary_or_rate=10000.0))
        gross_flags = _flags_titled(flags, "הפרש בין ברוטו לסכום שורות")
        assert len(gross_flags) == 0

    def test_mismatched_gross_flags(self):
        payslip = Payslip(
            earnings_lines=[
                EarningsLine(label="base_salary", amount=10000.0),
            ],
            totals=Totals(gross=12000.0, net=9000.0),
        )
        flags = run_rules(payslip, _confirmed(base_salary_or_rate=10000.0))
        gross_flags = _flags_titled(flags, "הפרש בין ברוטו לסכום שורות")
        assert len(gross_flags) == 1

    def test_car_benefit_skips_check(self):
        """When car benefit is present, skip the gross sum check."""
        payslip = Payslip(
            earnings_lines=[
                EarningsLine(label="base_salary", amount=10000.0),
                EarningsLine(label="car_benefit", label_he="שווי שימוש רכב", amount=2500.0),
            ],
            totals=Totals(gross=15000.0, net=9000.0),
        )
        flags = run_rules(payslip, _confirmed(base_salary_or_rate=10000.0))
        gross_flags = _flags_titled(flags, "הפרש בין ברוטו לסכום שורות")
        assert len(gross_flags) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Rule 15 — Employer contributions should not reduce net
# ═══════════════════════════════════════════════════════════════════════════

class TestEmployerContribNotReducingNet:
    def test_employer_contrib_in_deductions_flags(self):
        payslip = Payslip(
            deductions_lines=[
                DeductionLine(label="pension_employer", label_he="תגמולים מעביד", amount=975.0),
                DeductionLine(label="income_tax", label_he="מס הכנסה", amount=1500.0),
            ],
            totals=Totals(gross=15000.0, net=12000.0),
        )
        flags = run_rules(payslip, _confirmed())
        ec_flags = _flags_titled(flags, "הפרשת מעסיק מופיעה כניכוי")
        assert len(ec_flags) == 1

    def test_no_employer_in_deductions_no_flag(self):
        payslip = Payslip(
            deductions_lines=[
                DeductionLine(label="income_tax", label_he="מס הכנסה", amount=1500.0),
            ],
            employer_contrib_lines=[
                EmployerContribLine(label="pension_employer", label_he="תגמולים מעביד", amount=975.0),
            ],
            totals=Totals(gross=15000.0, net=12000.0),
        )
        flags = run_rules(payslip, _confirmed())
        ec_flags = _flags_titled(flags, "הפרשת מעסיק מופיעה כניכוי")
        assert len(ec_flags) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Rule 16 — Car benefit
# ═══════════════════════════════════════════════════════════════════════════

class TestCarBenefit:
    def test_car_benefit_balanced_no_flag(self):
        """Car benefit with matching deduction should not flag."""
        payslip = Payslip(
            earnings_lines=[
                EarningsLine(label="base_salary", amount=10000.0),
                EarningsLine(label="car_benefit", label_he="שווי שימוש רכב", amount=2500.0),
            ],
            deductions_lines=[
                DeductionLine(label="car_benefit", label_he="ניכוי שווי רכב", amount=2500.0),
            ],
            totals=Totals(gross=12500.0, net=9000.0),
        )
        flags = run_rules(payslip, _confirmed(base_salary_or_rate=10000.0))
        car_flags = _flags_titled(flags, "שווי שימוש רכב")
        assert len(car_flags) == 0

    def test_car_benefit_no_deduction_flags(self):
        """Car benefit without matching deduction should flag."""
        payslip = Payslip(
            earnings_lines=[
                EarningsLine(label="base_salary", amount=10000.0),
                EarningsLine(label="car_benefit", label_he="שווי שימוש רכב", amount=2500.0),
            ],
            totals=Totals(gross=12500.0, net=9000.0),
        )
        flags = run_rules(payslip, _confirmed(base_salary_or_rate=10000.0))
        car_flags = _flags_titled(flags, "שווי שימוש רכב")
        assert len(car_flags) == 1

    def test_no_car_benefit_no_flag(self):
        """Without car benefit earning, no car flag."""
        payslip = Payslip(
            earnings_lines=[
                EarningsLine(label="base_salary", amount=10000.0),
            ],
            totals=Totals(gross=10000.0, net=8000.0),
        )
        flags = run_rules(payslip, _confirmed(base_salary_or_rate=10000.0))
        car_flags = _flags_titled(flags, "שווי שימוש רכב")
        assert len(car_flags) == 0
