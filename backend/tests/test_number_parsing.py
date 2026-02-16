"""Unit tests for Israeli numeric format handling and Pydantic model parsing."""

import json

import pytest

from app.models.payslip import (
    EarningsLine,
    Payslip,
    SalaryType,
)


class TestPayslipModelParsing:
    """Test that the Pydantic model correctly handles Israeli numeric data."""

    def test_basic_payslip_construction(self):
        p = Payslip()
        assert p.totals.gross is None
        assert p.employer.name is None
        assert p.earnings_lines == []

    def test_earnings_line_with_float_amount(self):
        line = EarningsLine(label="base", amount=15000.50)
        assert line.amount == 15000.50

    def test_full_payslip_from_json(self):
        data = {
            "employer": {"name": "Test Corp"},
            "employee": {"name": "Test Employee"},
            "period": {"month": 6, "year": 2025},
            "employment": {
                "salary_type": "monthly",
                "base_rate": 12345.67,
            },
            "earnings_lines": [
                {"label": "base_salary", "amount": 12345.67},
                {"label": "overtime_125", "qty": 10, "rate": 82.30, "amount": 823.0},
            ],
            "deductions_lines": [
                {"label": "income_tax", "amount": 1000.0},
            ],
            "totals": {
                "gross": 13168.67,
                "net": 12168.67,
                "total_deductions": 1000.0,
            },
        }
        p = Payslip.model_validate(data)
        assert p.employer.name == "Test Corp"
        assert p.employment.salary_type == SalaryType.monthly
        assert p.employment.base_rate == 12345.67
        assert len(p.earnings_lines) == 2
        assert p.totals.gross == 13168.67

    def test_salary_type_enum(self):
        assert SalaryType("monthly") == SalaryType.monthly
        assert SalaryType("hourly") == SalaryType.hourly
        with pytest.raises(ValueError):
            SalaryType("daily")

    def test_period_validation(self):
        p = Payslip.model_validate({"period": {"month": 1, "year": 2025}})
        assert p.period.month == 1
        assert p.period.year == 2025

    def test_period_invalid_month(self):
        with pytest.raises(Exception):
            Payslip.model_validate({"period": {"month": 13, "year": 2025}})

    def test_model_json_roundtrip(self):
        """Serialize to JSON and back — ensures no data loss."""
        p = Payslip.model_validate({
            "employer": {"name": "חברה בע\"מ"},
            "totals": {"gross": 10000.0, "net": 7500.0},
        })
        json_str = p.model_dump_json()
        p2 = Payslip.model_validate_json(json_str)
        assert p2.employer.name == "חברה בע\"מ"
        assert p2.totals.gross == 10000.0

    def test_hebrew_label_preservation(self):
        line = EarningsLine(
            label="base_salary",
            label_he="שכר יסוד",
            amount=15000.0,
        )
        assert line.label_he == "שכר יסוד"

    def test_negative_amount_handling(self):
        """Israeli payslips sometimes show negatives in parentheses;
        by the time we parse to float, they should be negative."""
        line = EarningsLine(label="adjustment", amount=-500.0)
        assert line.amount == -500.0


class TestIsraeliNumberFormats:
    """Test that common Israeli number formats parse correctly to float."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("15000", 15000.0),
            ("15,000", 15000.0),
            ("15,000.50", 15000.50),
            ("1,234,567.89", 1234567.89),
            ("0.50", 0.50),
        ],
    )
    def test_comma_separated_thousands(self, raw: str, expected: float):
        """Verify that comma-separated strings parse to correct float values."""
        cleaned = raw.replace(",", "")
        assert float(cleaned) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("(1,234.56)", -1234.56),
            ("(500)", -500.0),
        ],
    )
    def test_parenthesized_negatives(self, raw: str, expected: float):
        """Israeli accounting style: negatives in parentheses."""
        cleaned = raw.replace(",", "").replace("(", "-").replace(")", "")
        assert float(cleaned) == expected

    def test_shekel_symbol_stripping(self):
        raw = "₪ 15,000.50"
        cleaned = raw.replace("₪", "").replace(",", "").strip()
        assert float(cleaned) == 15000.50
