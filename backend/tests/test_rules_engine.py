"""Unit tests for the rules engine."""

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
from app.services.rules_engine import run_rules


def _base_confirmed(**overrides) -> UserConfirmedFields:
    defaults = dict(
        period_month=1,
        period_year=2026,
        salary_type=SalaryType.monthly,
        base_salary_or_rate=15000.0,
        pension_expected=True,
    )
    defaults.update(overrides)
    return UserConfirmedFields(**defaults)


class TestRequiredBasics:
    def test_all_present_no_flag(self):
        p = Payslip.model_validate({
            "employer": {"name": "Corp"},
            "employee": {"name": "Employee"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 15000, "net": 12000},
        })
        flags = run_rules(p, _base_confirmed())
        basics_flags = [f for f in flags if "חסרים" in f.title_he]
        assert len(basics_flags) == 0

    def test_missing_employer_name(self):
        p = Payslip.model_validate({
            "employee": {"name": "Employee"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 15000, "net": 12000},
        })
        flags = run_rules(p, _base_confirmed())
        basics_flags = [f for f in flags if "חסרים" in f.title_he]
        assert len(basics_flags) == 1
        assert "מעסיק" in basics_flags[0].explanation_he

    def test_missing_net(self):
        p = Payslip.model_validate({
            "employer": {"name": "Corp"},
            "employee": {"name": "Employee"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 15000},
        })
        flags = run_rules(p, _base_confirmed())
        basics_flags = [f for f in flags if "חסרים" in f.title_he]
        assert len(basics_flags) == 1
        assert "נטו" in basics_flags[0].explanation_he


class TestNetSanity:
    def test_matching_net_no_flag(self):
        p = Payslip.model_validate({
            "employer": {"name": "Corp"},
            "employee": {"name": "Emp"},
            "period": {"month": 1, "year": 2026},
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 1000},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 500},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 300},
            ],
            "totals": {"gross": 15000, "net": 13200, "total_deductions": 1800},
        })
        flags = run_rules(p, _base_confirmed())
        net_flags = [f for f in flags if "ברוטו לנטו" in f.title_he]
        assert len(net_flags) == 0

    def test_large_discrepancy_flags(self):
        p = Payslip.model_validate({
            "employer": {"name": "Corp"},
            "employee": {"name": "Emp"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 15000, "net": 10000, "total_deductions": 1000},
        })
        flags = run_rules(p, _base_confirmed())
        net_flags = [f for f in flags if "ברוטו לנטו" in f.title_he]
        assert len(net_flags) == 1
        assert net_flags[0].severity == FlagSeverity.warn


class TestPensionChecks:
    def test_no_flag_when_pension_not_expected(self):
        p = Payslip()
        confirmed = _base_confirmed(pension_expected=False)
        flags = run_rules(p, confirmed)
        pension_flags = [f for f in flags if "פנסיה" in f.title_he or "פנסיוניות" in f.title_he]
        assert len(pension_flags) == 0

    def test_flag_when_pension_expected_but_missing(self):
        p = Payslip.model_validate({
            "employer": {"name": "Corp"},
            "employee": {"name": "Emp"},
            "period": {"month": 1, "year": 2026},
            "totals": {"gross": 15000, "net": 12000},
        })
        confirmed = _base_confirmed(pension_expected=True)
        flags = run_rules(p, confirmed)
        pension_flags = [f for f in flags if "פנסיוניות" in f.title_he]
        assert len(pension_flags) == 1

    def test_flag_when_employee_pension_but_no_employer(self):
        p = Payslip.model_validate({
            "employer": {"name": "Corp"},
            "employee": {"name": "Emp"},
            "period": {"month": 1, "year": 2026},
            "pension": {"employee_tagmulim": 900, "employer_tagmulim": 0},
            "totals": {"gross": 15000, "net": 12000},
        })
        confirmed = _base_confirmed(pension_expected=True)
        flags = run_rules(p, confirmed)
        pension_flags = [f for f in flags if "מעסיק" in f.title_he and "פנסיה" in f.title_he]
        assert len(pension_flags) == 1


class TestTaxLinesPresent:
    def test_all_tax_lines_present_no_flag(self):
        p = Payslip.model_validate({
            "employer": {"name": "Corp"},
            "employee": {"name": "Emp"},
            "period": {"month": 1, "year": 2026},
            "deductions_lines": [
                {"label": "income_tax", "label_he": "מס הכנסה", "amount": 1000},
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 500},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 300},
            ],
            "totals": {"gross": 15000, "net": 13200, "total_deductions": 1800},
        })
        flags = run_rules(p, _base_confirmed())
        tax_flags = [f for f in flags if "מס" in f.title_he and "חסרות" in f.title_he]
        assert len(tax_flags) == 0

    def test_missing_income_tax_flags(self):
        p = Payslip.model_validate({
            "employer": {"name": "Corp"},
            "employee": {"name": "Emp"},
            "period": {"month": 1, "year": 2026},
            "deductions_lines": [
                {"label": "national_insurance", "label_he": "ביטוח לאומי", "amount": 500},
                {"label": "health_tax", "label_he": "מס בריאות", "amount": 300},
            ],
            "totals": {"gross": 15000, "net": 14200, "total_deductions": 800},
        })
        flags = run_rules(p, _base_confirmed())
        tax_flags = [f for f in flags if "שורות מס" in f.title_he]
        assert len(tax_flags) == 1
        assert "מס הכנסה" in tax_flags[0].explanation_he
