"""Unit tests for the rules engine — all 13 Israel-specific checks."""

import json
from pathlib import Path

import pytest

from app.models.api_contracts import UserConfirmedFields
from app.models.payslip import (
    DeductionLine,
    EarningsLine,
    EmployerContribLine,
    FlagSeverity,
    Payslip,
    SalaryType,
)
from app.services.rules_engine import (
    calc_health_tax,
    calc_income_tax,
    calc_national_insurance,
    run_rules,
)

FIXTURES = Path(__file__).parent / "fixtures"


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


def _load_fixture(name: str) -> Payslip:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return Payslip.model_validate(data)


# ═══════════════════════════════════════════════════════════════════════════
# Rule 1: Required basics
# ═══════════════════════════════════════════════════════════════════════════

class TestRule1RequiredBasics:
    def test_all_present_no_flag(self):
        p = Payslip.model_validate({
            "employer": {"name": "Corp"}, "employee": {"name": "Emp"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 15000, "net": 12000},
        })
        assert len(_flags_titled(run_rules(p, _confirmed()), "חסרים")) == 0

    def test_missing_employer(self):
        p = Payslip.model_validate({
            "employee": {"name": "Emp"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 15000, "net": 12000},
        })
        flags = _flags_titled(run_rules(p, _confirmed()), "חסרים")
        assert len(flags) == 1
        assert "מעסיק" in flags[0].explanation_he

    def test_missing_net(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 15000},
        })
        flags = _flags_titled(run_rules(p, _confirmed()), "חסרים")
        assert len(flags) == 1
        assert "נטו" in flags[0].explanation_he

    def test_missing_multiple(self):
        p = Payslip()
        flags = _flags_titled(run_rules(p, _confirmed()), "חסרים")
        assert len(flags) == 1
        assert "מעסיק" in flags[0].explanation_he
        assert "נטו" in flags[0].explanation_he


# ═══════════════════════════════════════════════════════════════════════════
# Rule 2: Net sanity
# ═══════════════════════════════════════════════════════════════════════════

class TestRule2NetSanity:
    def test_matching_no_flag(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 1000},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 500},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 300},
            ],
            "totals": {"gross": 15000, "net": 13200, "total_deductions": 1800},
        })
        assert len(_flags_titled(run_rules(p, _confirmed()), "ברוטו לנטו")) == 0

    def test_large_discrepancy(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 15000, "net": 10000, "total_deductions": 1000},
        })
        flags = _flags_titled(run_rules(p, _confirmed()), "ברוטו לנטו")
        assert len(flags) == 1
        assert flags[0].severity == FlagSeverity.warn

    def test_within_tolerance(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 15000, "net": 12003, "total_deductions": 3000},
        })
        assert len(_flags_titled(run_rules(p, _confirmed()), "ברוטו לנטו")) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Rule 3: Pension
# ═══════════════════════════════════════════════════════════════════════════

class TestRule3Pension:
    def test_no_flag_when_not_expected(self):
        p = Payslip()
        flags = run_rules(p, _confirmed(pension_expected=False))
        assert len([f for f in flags if "פנסיה" in f.title_he or "פנסיוניות" in f.title_he]) == 0

    def test_both_missing_when_expected(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 15000, "net": 12000},
        })
        assert len(_flags_titled(run_rules(p, _confirmed()), "לא זוהו הפרשות פנסיוניות")) == 1

    def test_employee_only_no_employer(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "pension": {"employee_tagmulim": 900, "employer_tagmulim": 0},
            "totals": {"gross": 15000, "net": 12000},
        })
        assert len(_flags_titled(run_rules(p, _confirmed()), "חוסר בהפרשת מעסיק לפנסיה")) == 1

    def test_pitzuyim_missing(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "pension": {"employee_tagmulim": 900, "employer_tagmulim": 975, "employer_pitzuyim": 0},
            "totals": {"gross": 15000, "net": 12000},
        })
        flags = _flags_titled(run_rules(p, _confirmed()), "פיצויים")
        assert len(flags) == 1
        assert flags[0].severity == FlagSeverity.info

    def test_training_fund_missing_when_expected(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "pension": {"employee_tagmulim": 900, "employer_tagmulim": 975, "employer_pitzuyim": 900},
            "totals": {"gross": 15000, "net": 12000},
        })
        flags = _flags_titled(
            run_rules(p, _confirmed(training_fund_expected=True)), "קרן השתלמות"
        )
        assert len(flags) == 1

    def test_all_pension_present_no_flag(self):
        p = _load_fixture("monthly_with_pension.json")
        flags = run_rules(p, _confirmed())
        pension = [f for f in flags if "פנסיה" in f.title_he or "פנסיוניות" in f.title_he or "פיצויים" in f.title_he]
        assert len(pension) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Rule 4: Travel allowance
# ═══════════════════════════════════════════════════════════════════════════

class TestRule4Travel:
    def test_present_no_flag(self):
        p = _load_fixture("monthly_with_pension.json")
        assert len(_flags_titled(run_rules(p, _confirmed()), "נסיעות")) == 0

    def test_missing_flags(self):
        p = _load_fixture("monthly_overtime_no_travel.json")
        flags = _flags_titled(run_rules(p, _confirmed(base_salary_or_rate=22000)), "נסיעות")
        assert len(flags) == 1
        assert flags[0].severity == FlagSeverity.info

    def test_no_earnings_at_all(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 15000, "net": 12000},
        })
        assert len(_flags_titled(run_rules(p, _confirmed()), "נסיעות")) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Rule 5: Overtime
# ═══════════════════════════════════════════════════════════════════════════

class TestRule5Overtime:
    def test_hours_and_pay_no_flag(self):
        p = _load_fixture("monthly_with_pension.json")
        assert len([f for f in run_rules(p, _confirmed()) if "נוספות" in f.title_he]) == 0

    def test_hours_without_pay(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "employment": {"hours_overtime_125": 10},
            "earnings_lines": [{"label": "base_salary", "label_he": "שכר יסוד", "amount": 15000}],
            "totals": {"gross": 15000, "net": 12000},
        })
        flags = _flags_titled(run_rules(p, _confirmed()), "ללא שורת תשלום")
        assert len(flags) == 1
        assert flags[0].severity == FlagSeverity.warn

    def test_pay_without_hours(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "earnings_lines": [
                {"label": "base_salary", "label_he": "שכר יסוד", "amount": 15000},
                {"label": "overtime_125", "label_he": "שעות נוספות 125%", "amount": 1000},
            ],
            "totals": {"gross": 16000, "net": 13000},
        })
        flags = _flags_titled(run_rules(p, _confirmed()), "ללא פירוט שעות")
        assert len(flags) == 1
        assert flags[0].severity == FlagSeverity.info

    def test_no_overtime_at_all(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "earnings_lines": [{"label": "base_salary", "label_he": "שכר יסוד", "amount": 15000}],
            "totals": {"gross": 15000, "net": 12000},
        })
        assert len([f for f in run_rules(p, _confirmed()) if "נוספות" in f.title_he]) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Rule 6: Leave balances
# ═══════════════════════════════════════════════════════════════════════════

class TestRule6Leave:
    def test_balanced_no_flag(self):
        p = _load_fixture("monthly_with_pension.json")
        leave = [f for f in run_rules(p, _confirmed()) if "יתרת" in f.title_he or "התאמה ביתרת" in f.title_he]
        assert len(leave) == 0

    def test_vacation_imbalance(self):
        p = _load_fixture("leave_imbalance_unknown_deductions.json")
        flags = _flags_titled(run_rules(p, _confirmed(base_salary_or_rate=12000)), "התאמה ביתרת חופשה")
        assert len(flags) == 1
        assert flags[0].severity == FlagSeverity.warn

    def test_negative_closing(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "leave": {"vacation_open": 2.0, "vacation_accrued": 1.0, "vacation_used": 5.0, "vacation_close": -2.0},
            "totals": {"gross": 15000, "net": 12000},
        })
        assert len([f for f in run_rules(p, _confirmed()) if "שלילית" in f.title_he]) == 1

    def test_partial_data_skips(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "leave": {"vacation_open": 10.0, "vacation_close": 5.0},
            "totals": {"gross": 15000, "net": 12000},
        })
        assert len([f for f in run_rules(p, _confirmed()) if "יתרת" in f.title_he]) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Rule 7: Unknown / duplicate deductions
# ═══════════════════════════════════════════════════════════════════════════

class TestRule7Deductions:
    def test_all_known_no_flag(self):
        p = _load_fixture("monthly_with_pension.json")
        assert len(_flags_titled(run_rules(p, _confirmed()), "לא מזוהים")) == 0

    def test_unknown_deduction(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 1000},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 500},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 300},
                {"label": "weird_charge", "label_he": "חיוב מוזר", "amount": 150},
            ],
            "totals": {"gross": 15000, "net": 13050, "total_deductions": 1950},
        })
        flags = _flags_titled(run_rules(p, _confirmed()), "לא מזוהים")
        assert len(flags) == 1
        assert "חיוב מוזר" in flags[0].explanation_he

    def test_duplicate_deduction(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 1000},
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 500},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 500},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 300},
            ],
            "totals": {"gross": 15000, "net": 12700, "total_deductions": 2300},
        })
        assert len(_flags_titled(run_rules(p, _confirmed()), "כפולים")) == 1

    def test_fixture_unknown_and_duplicate(self):
        p = _load_fixture("leave_imbalance_unknown_deductions.json")
        all_flags = run_rules(p, _confirmed(base_salary_or_rate=12000))
        assert len(_flags_titled(all_flags, "לא מזוהים")) == 1
        assert len(_flags_titled(all_flags, "כפולים")) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Rule 8: Minimum wage
# ═══════════════════════════════════════════════════════════════════════════

class TestRule8MinimumWage:
    def test_above_minimum_no_flag(self):
        p = _load_fixture("monthly_with_pension.json")
        assert len([f for f in run_rules(p, _confirmed()) if "מינימום" in f.title_he]) == 0

    def test_hourly_below_minimum(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 4500, "net": 4000},
        })
        c = _confirmed(salary_type=SalaryType.hourly, base_salary_or_rate=25.0, pension_expected=False)
        flags = [f for f in run_rules(p, c) if "מינימום" in f.title_he]
        assert len(flags) == 1 and flags[0].severity == FlagSeverity.high

    def test_hourly_above_minimum(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 6000, "net": 5500},
        })
        c = _confirmed(salary_type=SalaryType.hourly, base_salary_or_rate=35.0, pension_expected=False)
        assert len([f for f in run_rules(p, c) if "מינימום" in f.title_he]) == 0

    def test_monthly_below_no_hours(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 5000, "net": 4500},
        })
        c = _confirmed(base_salary_or_rate=5000.0, pension_expected=False)
        flags = [f for f in run_rules(p, c) if "מינימום" in f.title_he]
        assert len(flags) == 1 and flags[0].severity == FlagSeverity.high

    def test_monthly_effective_hourly_below(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 5500, "net": 5000},
        })
        c = _confirmed(base_salary_or_rate=5500.0, regular_hours_worked=182.0, pension_expected=False)
        # 5500/182 = 30.22 < 31.61
        assert len([f for f in run_rules(p, c) if "אפקטיבי" in f.title_he]) == 1

    def test_monthly_via_job_percent(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 2500, "net": 2200},
        })
        c = _confirmed(base_salary_or_rate=2500.0, job_percent=50.0, pension_expected=False)
        # 2500 / (182*0.5) = 27.47 < 31.61
        assert len([f for f in run_rules(p, c) if "אפקטיבי" in f.title_he]) == 1

    def test_fixture_low_wage(self):
        p = _load_fixture("low_wage_missing_pension.json")
        c = _confirmed(salary_type=SalaryType.hourly, base_salary_or_rate=28.0, regular_hours_worked=170.0)
        assert len([f for f in run_rules(p, c) if "מינימום" in f.title_he]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Rule 9: Tax lines
# ═══════════════════════════════════════════════════════════════════════════

class TestRule9TaxLines:
    def test_all_present_no_flag(self):
        p = _load_fixture("monthly_with_pension.json")
        assert len(_flags_titled(run_rules(p, _confirmed()), "שורות מס")) == 0

    def test_missing_income_tax(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "deductions_lines": [
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 500},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 300},
            ],
            "totals": {"gross": 15000, "net": 14200, "total_deductions": 800},
        })
        flags = _flags_titled(run_rules(p, _confirmed()), "שורות מס")
        assert len(flags) == 1
        assert "מס הכנסה" in flags[0].explanation_he

    def test_zero_gross_skips(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 0, "net": 0},
        })
        assert len(_flags_titled(run_rules(p, _confirmed()), "שורות מס")) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Rule 10: Large expenses
# ═══════════════════════════════════════════════════════════════════════════

class TestRule10LargeExpenses:
    def test_no_expenses_no_flag(self):
        p = _load_fixture("monthly_with_pension.json")
        assert len(_flags_titled(run_rules(p, _confirmed()), "הוצאות")) == 0

    def test_over_threshold(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "earnings_lines": [
                {"label": "base_salary", "label_he": "שכר יסוד", "amount": 10000},
                {"label": "travel_allowance", "label_he": "החזר נסיעות", "amount": 500},
                {"label": "expense_car", "label_he": "החזר הוצאות רכב", "amount": 6000},
            ],
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 1000},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 500},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 300},
            ],
            "totals": {"gross": 16500, "net": 14700, "total_deductions": 1800},
        })
        c = _confirmed(base_salary_or_rate=10000.0, pension_expected=False)
        # 6000/10000 = 60% > 50%
        flags = _flags_titled(run_rules(p, c), "הוצאות גבוהים")
        assert len(flags) == 1
        assert flags[0].severity == FlagSeverity.info

    def test_travel_excluded(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "earnings_lines": [
                {"label": "base_salary", "label_he": "שכר יסוד", "amount": 10000},
                {"label": "travel_allowance", "label_he": "החזר נסיעות", "amount": 8000},
            ],
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 1000},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 500},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 300},
            ],
            "totals": {"gross": 18000, "net": 16200, "total_deductions": 1800},
        })
        c = _confirmed(base_salary_or_rate=10000.0, pension_expected=False)
        assert len(_flags_titled(run_rules(p, c), "הוצאות גבוהים")) == 0

    def test_hourly_expense_ratio(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "earnings_lines": [
                {"label": "base_salary", "label_he": "שכר שעתי", "amount": 5600},
                {"label": "travel_allowance", "label_he": "החזר נסיעות", "amount": 300},
                {"label": "expense_car", "label_he": "החזר הוצאות רכב", "amount": 4000},
            ],
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 500},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 200},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 150},
            ],
            "totals": {"gross": 9900, "net": 9050, "total_deductions": 850},
        })
        c = _confirmed(
            salary_type=SalaryType.hourly, base_salary_or_rate=35.0,
            regular_hours_worked=160.0, pension_expected=False,
        )
        # monthly_base = 35*160 = 5600, expense = 4000, 71% > 50%
        assert len(_flags_titled(run_rules(p, c), "הוצאות גבוהים")) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Integration: fixture end-to-end
# ═══════════════════════════════════════════════════════════════════════════

class TestFixtureIntegration:
    def test_monthly_with_pension_clean(self):
        p = _load_fixture("monthly_with_pension.json")
        flags = run_rules(p, _confirmed())
        assert len([f for f in flags if f.severity == FlagSeverity.high]) == 0

    def test_hourly_no_pension_triggers_pension_flag(self):
        p = _load_fixture("hourly_no_pension.json")
        c = _confirmed(salary_type=SalaryType.hourly, base_salary_or_rate=35.0, regular_hours_worked=160.0)
        assert len(_flags_titled(run_rules(p, c), "לא זוהו הפרשות פנסיוניות")) == 1

    def test_low_wage_triggers_minimum_wage(self):
        p = _load_fixture("low_wage_missing_pension.json")
        c = _confirmed(salary_type=SalaryType.hourly, base_salary_or_rate=28.0, regular_hours_worked=170.0)
        assert len([f for f in run_rules(p, c) if "מינימום" in f.title_he]) == 1

    def test_high_salary_complete_clean(self):
        p = _load_fixture("high_salary_complete.json")
        c = _confirmed(base_salary_or_rate=45000.0)
        flags = run_rules(p, c)
        assert len([f for f in flags if f.severity in (FlagSeverity.warn, FlagSeverity.high)]) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Calculation helpers
# ═══════════════════════════════════════════════════════════════════════════

class TestCalcIncomeTax:
    def test_zero_income(self):
        assert calc_income_tax(0) == 0.0

    def test_negative_income(self):
        assert calc_income_tax(-1000) == 0.0

    def test_low_income_covered_by_credits(self):
        # Low income where credit points fully cover the tax
        # 2.25 * 242 = 544.50 credit benefit
        # 3000 * 0.10 = 300 tax → 300 - 544.50 = max(0, -244.5) = 0
        assert calc_income_tax(3000) == 0.0

    def test_first_bracket(self):
        # 7,310 * 10% = 731 - 544.50 credits = 186.50
        assert abs(calc_income_tax(7_310) - 186.50) < 0.01

    def test_second_bracket(self):
        # 10,480: 731 + 3,170*0.14=443.80 = 1,174.80 - 544.50 = 630.30
        assert abs(calc_income_tax(10_480) - 630.30) < 0.01

    def test_high_income(self):
        # 50,000: compute step by step
        tax = (
            7_310 * 0.10
            + (10_480 - 7_310) * 0.14
            + (19_000 - 10_480) * 0.20
            + (25_101 - 19_000) * 0.31
            + (41_410 - 25_101) * 0.35
            + (50_000 - 41_410) * 0.47
        )
        expected = max(tax - 2.25 * 242, 0)
        assert abs(calc_income_tax(50_000) - expected) < 0.01

    def test_custom_credit_points(self):
        # Female resident: 2.75 credit points
        tax_male = calc_income_tax(20_000, credit_points=2.25)
        tax_female = calc_income_tax(20_000, credit_points=2.75)
        assert tax_female < tax_male
        assert abs(tax_male - tax_female - (0.5 * 242)) < 0.01


class TestCalcNationalInsurance:
    def test_zero_income(self):
        assert calc_national_insurance(0) == 0.0

    def test_below_threshold(self):
        # 5,000 * 1.04% = 52.0
        assert abs(calc_national_insurance(5_000) - 52.0) < 0.01

    def test_at_threshold(self):
        # 7,703 * 1.04% = 80.1112
        assert abs(calc_national_insurance(7_703) - 80.11) < 0.01

    def test_above_threshold(self):
        # 15,000: 7,703*0.0104 + (15000-7703)*0.07 = 80.11 + 510.79 = 590.90
        expected = 7_703 * 0.0104 + (15_000 - 7_703) * 0.07
        assert abs(calc_national_insurance(15_000) - expected) < 0.01

    def test_above_max_insurable(self):
        # 60,000 (over max 51,910): capped at 51,910
        capped = calc_national_insurance(60_000)
        at_max = calc_national_insurance(51_910)
        assert abs(capped - at_max) < 0.01


class TestCalcHealthTax:
    def test_zero_income(self):
        assert calc_health_tax(0) == 0.0

    def test_below_threshold(self):
        # 5,000 * 3.23% = 161.50
        assert abs(calc_health_tax(5_000) - 161.50) < 0.01

    def test_above_threshold(self):
        # 15,000: 7,703*0.0323 + (15000-7703)*0.0517
        expected = 7_703 * 0.0323 + (15_000 - 7_703) * 0.0517
        assert abs(calc_health_tax(15_000) - expected) < 0.01


# ═══════════════════════════════════════════════════════════════════════════
# Rule 11: Income tax bracket verification
# ═══════════════════════════════════════════════════════════════════════════

class TestRule11IncomeTax:
    def test_matching_tax_no_flag(self):
        """Tax matches expected calculation within tolerance."""
        gross = 10_000.0
        expected_tax = calc_income_tax(gross)
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": expected_tax},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 300},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 200},
            ],
            "totals": {"gross": gross, "net": gross - expected_tax - 500},
        })
        assert len(_flags_titled(run_rules(p, _confirmed(base_salary_or_rate=gross)), "מס הכנסה")) == 0

    def test_large_tax_discrepancy_flags(self):
        """Tax far from expected triggers info flag."""
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 100.0},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 500},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 300},
            ],
            "totals": {"gross": 20000, "taxable_gross": 20000, "net": 19100},
        })
        flags = _flags_titled(run_rules(p, _confirmed(base_salary_or_rate=20000)), "מס הכנסה")
        assert len(flags) == 1
        assert flags[0].severity == FlagSeverity.info

    def test_no_tax_line_skips(self):
        """When no income tax line exists, rule 11 should not flag (rule 9 handles it)."""
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "deductions_lines": [
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 500},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 300},
            ],
            "totals": {"gross": 15000, "net": 14200},
        })
        assert len(_flags_titled(run_rules(p, _confirmed()), "הפרש בחישוב מס הכנסה")) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Rule 12: National Insurance tiered calculation
# ═══════════════════════════════════════════════════════════════════════════

class TestRule12NationalInsurance:
    def test_matching_ni_no_flag(self):
        gross = 15_000.0
        expected_ni = calc_national_insurance(gross)
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 1500},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": expected_ni},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 500},
            ],
            "totals": {"gross": gross, "net": gross - 2000 - expected_ni},
        })
        assert len(_flags_titled(run_rules(p, _confirmed(base_salary_or_rate=gross)), "ביטוח לאומי")) == 0

    def test_large_ni_discrepancy_flags(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 1500},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 50.0},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 500},
            ],
            "totals": {"gross": 20000, "net": 17950},
        })
        flags = _flags_titled(run_rules(p, _confirmed(base_salary_or_rate=20000)), "ביטוח לאומי")
        assert len(flags) == 1
        assert flags[0].severity == FlagSeverity.info


# ═══════════════════════════════════════════════════════════════════════════
# Rule 13: Health tax tiered calculation
# ═══════════════════════════════════════════════════════════════════════════

class TestRule13HealthTax:
    def test_matching_health_no_flag(self):
        gross = 15_000.0
        expected_health = calc_health_tax(gross)
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 1500},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 600},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": expected_health},
            ],
            "totals": {"gross": gross, "net": gross - 2100 - expected_health},
        })
        assert len(_flags_titled(run_rules(p, _confirmed(base_salary_or_rate=gross)), "בריאות")) == 0

    def test_large_health_discrepancy_flags(self):
        p = Payslip.model_validate({
            "employer": {"name": "C"}, "employee": {"name": "E"},
            "period": {"month": 1, "year": 2026},
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 1500},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 600},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 10.0},
            ],
            "totals": {"gross": 20000, "net": 17890},
        })
        flags = _flags_titled(run_rules(p, _confirmed(base_salary_or_rate=20000)), "בריאות")
        assert len(flags) == 1
        assert flags[0].severity == FlagSeverity.info
