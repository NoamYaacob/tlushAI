"""
Fixture-based tests that lock rule behavior for the sample payslips.

Each test loads a real fixture JSON, runs the rules engine, and asserts the
exact set of flags produced.  This prevents regressions when rules are
modified and catches new false-positives / false-negatives.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.api_contracts import UserConfirmedFields
from app.models.payslip import Payslip, SalaryType

from app.services.rules_engine import run_rules

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> Payslip:
    raw = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return Payslip(**raw)


def _confirmed(
    base: float = 10000,
    salary_type: SalaryType = SalaryType.monthly,
    month: int = 1,
    year: int = 2026,
    hours: float | None = None,
    job_pct: float | None = None,
    pension: bool = True,
    training: bool | None = None,
) -> UserConfirmedFields:
    return UserConfirmedFields(
        period_month=month,
        period_year=year,
        salary_type=salary_type,
        base_salary_or_rate=base,
        regular_hours_worked=hours,
        job_percent=job_pct,
        pension_expected=pension,
        training_fund_expected=training,
    )


def _flag_titles(flags) -> set[str]:
    return {f.title_he for f in flags}


# ──────────────────────────────────────────────────────────────────
# monthly_with_pension.json — well-formed monthly payslip
# Should produce zero high-severity flags.
# ──────────────────────────────────────────────────────────────────


class TestMonthlyWithPension:
    @pytest.fixture()
    def payslip(self):
        return _load("monthly_with_pension.json")

    def test_no_high_severity(self, payslip):
        flags = run_rules(payslip, _confirmed(base=15000, hours=182, pension=True, training=True))
        high = [f for f in flags if f.severity.value == "high"]
        assert high == [], f"Unexpected high flags: {[f.title_he for f in high]}"

    def test_no_gross_sum_flag(self, payslip):
        flags = run_rules(payslip, _confirmed(base=15000, hours=182))
        assert "הפרש בין ברוטו לסכום שורות ההכנסה" not in _flag_titles(flags)

    def test_net_sanity_passes(self, payslip):
        flags = run_rules(payslip, _confirmed(base=15000, hours=182))
        assert "חוסר התאמה בין ברוטו לנטו" not in _flag_titles(flags)

    def test_pension_ok(self, payslip):
        flags = run_rules(payslip, _confirmed(base=15000, hours=182, pension=True))
        assert "לא זוהו הפרשות פנסיוניות" not in _flag_titles(flags)
        assert "ייתכן חוסר בהפרשת מעסיק לפנסיה" not in _flag_titles(flags)


# ──────────────────────────────────────────────────────────────────
# high_salary_complete.json — high earner with car benefit
# Car benefit should NOT trigger gross sum mismatch.
# ──────────────────────────────────────────────────────────────────


class TestHighSalaryComplete:
    @pytest.fixture()
    def payslip(self):
        return _load("high_salary_complete.json")

    def test_no_gross_sum_false_positive(self, payslip):
        """Car benefit (שווי רכב) inflates gross — Rule 14 must not fire."""
        flags = run_rules(payslip, _confirmed(base=45000, hours=182))
        assert "הפרש בין ברוטו לסכום שורות ההכנסה" not in _flag_titles(flags)

    def test_no_high_flags(self, payslip):
        flags = run_rules(payslip, _confirmed(base=45000, hours=182, pension=True))
        high = [f for f in flags if f.severity.value == "high"]
        assert high == [], f"Unexpected high flags: {[f.title_he for f in high]}"


# ──────────────────────────────────────────────────────────────────
# hightech_global.json — tech company with overtime and travel
# ──────────────────────────────────────────────────────────────────


class TestHightechGlobal:
    @pytest.fixture()
    def payslip(self):
        return _load("hightech_global.json")

    def test_no_high_severity(self, payslip):
        flags = run_rules(payslip, _confirmed(base=25000, hours=182, pension=True, training=True))
        high = [f for f in flags if f.severity.value == "high"]
        assert high == [], f"Unexpected high flags: {[f.title_he for f in high]}"

    def test_gross_sum_no_false_positive(self, payslip):
        flags = run_rules(payslip, _confirmed(base=25000, hours=182))
        assert "הפרש בין ברוטו לסכום שורות ההכנסה" not in _flag_titles(flags)

    def test_pension_found(self, payslip):
        flags = run_rules(payslip, _confirmed(base=25000, hours=182, pension=True))
        assert "לא זוהו הפרשות פנסיוניות" not in _flag_titles(flags)

    def test_tax_lines_present(self, payslip):
        flags = run_rules(payslip, _confirmed(base=25000))
        assert "ייתכן שחסרות שורות מס" not in _flag_titles(flags)


# ──────────────────────────────────────────────────────────────────
# public_sector.json — public sector teacher
# ──────────────────────────────────────────────────────────────────


class TestPublicSector:
    @pytest.fixture()
    def payslip(self):
        return _load("public_sector.json")

    def test_no_high_severity(self, payslip):
        flags = run_rules(payslip, _confirmed(base=12500, hours=182, pension=True, month=12, year=2025))
        high = [f for f in flags if f.severity.value == "high"]
        assert high == [], f"Unexpected high flags: {[f.title_he for f in high]}"

    def test_training_fund_missing_flagged(self, payslip):
        """Public sector fixture has no training fund — flag should appear if expected."""
        flags = run_rules(payslip, _confirmed(base=12500, pension=True, training=True, month=12, year=2025))
        assert "לא זוהו הפרשות לקרן השתלמות" in _flag_titles(flags)


# ──────────────────────────────────────────────────────────────────
# low_wage_missing_pension.json — should trigger min wage + pension
# ──────────────────────────────────────────────────────────────────


class TestLowWageMissingPension:
    @pytest.fixture()
    def payslip(self):
        return _load("low_wage_missing_pension.json")

    def test_pension_missing_flagged(self, payslip):
        flags = run_rules(payslip, _confirmed(base=5000, pension=True))
        titles = _flag_titles(flags)
        assert "לא זוהו הפרשות פנסיוניות" in titles

    def test_minimum_wage_flagged(self, payslip):
        flags = run_rules(payslip, _confirmed(base=5000, pension=True))
        titles = _flag_titles(flags)
        assert any("שכר" in t and "מינימום" in t for t in titles)


# ──────────────────────────────────────────────────────────────────
# hourly_no_pension.json — hourly worker, no pension
# ──────────────────────────────────────────────────────────────────


class TestHourlyNoPension:
    @pytest.fixture()
    def payslip(self):
        return _load("hourly_no_pension.json")

    def test_pension_missing_flagged(self, payslip):
        flags = run_rules(payslip, _confirmed(
            base=35, salary_type=SalaryType.hourly, hours=160, pension=True,
        ))
        titles = _flag_titles(flags)
        assert "לא זוהו הפרשות פנסיוניות" in titles

    def test_above_minimum_wage(self, payslip):
        """35 NIS/hour is above minimum — should not flag."""
        flags = run_rules(payslip, _confirmed(
            base=35, salary_type=SalaryType.hourly, hours=160, pension=True,
        ))
        titles = _flag_titles(flags)
        assert not any("שכר" in t and "מינימום" in t for t in titles)


# ──────────────────────────────────────────────────────────────────
# Regression: Rule 14 must not fire for benefit-in-kind payslips
# ──────────────────────────────────────────────────────────────────


class TestBenefitInKindNoFalsePositive:
    """Construct a payslip where car benefit inflates gross."""

    def test_car_benefit_suppresses_gross_sum_flag(self):
        payslip = Payslip(**{
            "employer": {"name": "test"},
            "employee": {"name": "test"},
            "period": {"month": 1, "year": 2026},
            "employment": {"salary_type": "monthly", "base_rate": 20000},
            "earnings_lines": [
                {"label": "base_salary", "label_he": "שכר יסוד", "amount": 20000},
                {"label": "car_benefit", "label_he": "שווי שימוש רכב", "amount": 2500},
            ],
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 2000},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 500},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 400},
            ],
            "totals": {"gross": 22500, "net": 17100, "total_deductions": 2900},
        })
        flags = run_rules(payslip, _confirmed(base=20000))
        assert "הפרש בין ברוטו לסכום שורות ההכנסה" not in _flag_titles(flags)

    def test_meal_benefit_suppresses_gross_sum_flag(self):
        """Meal value (שווי ארוחות) is also a benefit-in-kind."""
        payslip = Payslip(**{
            "employer": {"name": "test"},
            "employee": {"name": "test"},
            "period": {"month": 1, "year": 2026},
            "employment": {"salary_type": "monthly", "base_rate": 10000},
            "earnings_lines": [
                {"label": "base_salary", "label_he": "שכר יסוד", "amount": 10000},
                {"label": "meals", "label_he": "שווי ארוחות", "amount": 500},
            ],
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 500},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 200},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 150},
            ],
            "totals": {"gross": 10500, "net": 9150, "total_deductions": 850},
        })
        flags = run_rules(payslip, _confirmed(base=10000))
        assert "הפרש בין ברוטו לסכום שורות ההכנסה" not in _flag_titles(flags)


# ──────────────────────────────────────────────────────────────────
# Regression: Rule 11 should not fire without taxable_gross
# ──────────────────────────────────────────────────────────────────


class TestIncomeTaxGating:
    def test_no_false_alarm_without_taxable_gross(self):
        """Rule 11 only runs when taxable_gross is explicitly set."""
        payslip = Payslip(**{
            "employer": {"name": "test"},
            "employee": {"name": "test"},
            "period": {"month": 1, "year": 2026},
            "employment": {"salary_type": "monthly", "base_rate": 20000},
            "earnings_lines": [
                {"label": "base_salary", "label_he": "שכר יסוד", "amount": 20000},
            ],
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 100},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 500},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 400},
            ],
            "totals": {"gross": 20000, "net": 19000, "total_deductions": 1000},
        })
        flags = run_rules(payslip, _confirmed(base=20000))
        assert "הפרש בחישוב מס הכנסה" not in _flag_titles(flags)

    def test_fires_with_taxable_gross(self):
        """Rule 11 fires when taxable_gross is set and there's a large discrepancy."""
        payslip = Payslip(**{
            "employer": {"name": "test"},
            "employee": {"name": "test"},
            "period": {"month": 1, "year": 2026},
            "employment": {"salary_type": "monthly", "base_rate": 20000},
            "earnings_lines": [
                {"label": "base_salary", "label_he": "שכר יסוד", "amount": 20000},
            ],
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 100},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 500},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 400},
            ],
            "totals": {"gross": 20000, "taxable_gross": 20000, "net": 19000, "total_deductions": 1000},
        })
        flags = run_rules(payslip, _confirmed(base=20000))
        assert "הפרש בחישוב מס הכנסה" in _flag_titles(flags)
