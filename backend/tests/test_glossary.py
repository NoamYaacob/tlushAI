"""Tests for the payslip glossary and field registry."""

import pytest

from app.data.glossary import (
    classify_line,
    get_all_field_info,
    get_field_info,
    get_line_item_entry,
)
from app.models.payslip import LineCategory


# ═══════════════════════════════════════════════════════════════════════════
# classify_line — exact match on canonical key
# ═══════════════════════════════════════════════════════════════════════════

class TestClassifyByCanonicalKey:
    def test_base_salary(self):
        info = classify_line("base_salary")
        assert info is not None
        assert info.canonical_key == "base_salary"
        assert info.category == LineCategory.earning
        assert info.affects_gross is True
        assert info.affects_taxable is True

    def test_income_tax(self):
        info = classify_line("income_tax")
        assert info is not None
        assert info.category == LineCategory.tax

    def test_pension_employee(self):
        info = classify_line("pension_employee")
        assert info is not None
        assert info.category == LineCategory.deduction

    def test_pension_employer(self):
        info = classify_line("pension_employer")
        assert info is not None
        assert info.category == LineCategory.employer_contribution


# ═══════════════════════════════════════════════════════════════════════════
# classify_line — Hebrew synonym match
# ═══════════════════════════════════════════════════════════════════════════

class TestClassifyByHebrew:
    def test_hebrew_base_salary(self):
        info = classify_line("unknown_label", label_he="שכר יסוד")
        assert info is not None
        assert info.canonical_key == "base_salary"

    def test_hebrew_travel(self):
        info = classify_line("unknown", label_he="דמי נסיעות")
        assert info is not None
        assert info.canonical_key == "travel_allowance"

    def test_hebrew_health_tax(self):
        info = classify_line("unknown", label_he="מס בריאות")
        assert info is not None
        assert info.canonical_key == "health_tax"

    def test_hebrew_pension_employee(self):
        info = classify_line("unknown", label_he="תגמולים עובד")
        assert info is not None
        assert info.canonical_key == "pension_employee"

    def test_hebrew_recuperation(self):
        info = classify_line("unknown", label_he="דמי הבראה")
        assert info is not None
        assert info.canonical_key == "recuperation"

    def test_hebrew_car_benefit(self):
        info = classify_line("unknown", label_he="שווי שימוש רכב")
        assert info is not None
        assert info.canonical_key == "car_benefit"


# ═══════════════════════════════════════════════════════════════════════════
# classify_line — substring match
# ═══════════════════════════════════════════════════════════════════════════

class TestClassifyBySubstring:
    def test_overtime_125_in_label(self):
        info = classify_line("overtime_125_percent")
        assert info is not None
        assert "overtime" in info.canonical_key

    def test_hebrew_overtime_in_label_he(self):
        info = classify_line("code_024", label_he="024 שעות נוספות 125%")
        assert info is not None
        assert "overtime" in info.canonical_key


# ═══════════════════════════════════════════════════════════════════════════
# classify_line — unknown returns None
# ═══════════════════════════════════════════════════════════════════════════

class TestClassifyUnknown:
    def test_unknown_label(self):
        info = classify_line("xyzzy_unknown_thing")
        assert info is None

    def test_unknown_hebrew(self):
        info = classify_line("unknown", label_he="רכיב לא מוכר בכלל")
        assert info is None


# ═══════════════════════════════════════════════════════════════════════════
# classify_line — category correctness
# ═══════════════════════════════════════════════════════════════════════════

class TestClassifyCategories:
    @pytest.mark.parametrize("key,expected_cat", [
        ("base_salary", LineCategory.earning),
        ("overtime_125", LineCategory.earning),
        ("travel_allowance", LineCategory.earning),
        ("income_tax", LineCategory.tax),
        ("national_insurance", LineCategory.tax),
        ("health_tax", LineCategory.tax),
        ("pension_employee", LineCategory.deduction),
        ("training_fund_employee", LineCategory.deduction),
        ("pension_employer", LineCategory.employer_contribution),
        ("severance_employer", LineCategory.employer_contribution),
        ("training_fund_employer", LineCategory.employer_contribution),
    ])
    def test_category(self, key, expected_cat):
        info = classify_line(key)
        assert info is not None
        assert info.category == expected_cat


# ═══════════════════════════════════════════════════════════════════════════
# Field registry
# ═══════════════════════════════════════════════════════════════════════════

class TestFieldRegistry:
    def test_get_known_field(self):
        info = get_field_info("period_month")
        assert info is not None
        assert info.label_he == "חודש שכר"
        assert info.section == "period"

    def test_get_unknown_field(self):
        assert get_field_info("nonexistent_field") is None

    def test_all_fields_have_hebrew(self):
        all_fields = get_all_field_info()
        assert len(all_fields) > 0
        for key, info in all_fields.items():
            assert info.label_he, f"Field {key} missing label_he"
            assert info.help_he, f"Field {key} missing help_he"


# ═══════════════════════════════════════════════════════════════════════════
# Line item entries
# ═══════════════════════════════════════════════════════════════════════════

class TestLineItemEntry:
    def test_get_existing_entry(self):
        entry = get_line_item_entry("base_salary")
        assert entry is not None
        assert "hebrew_names" in entry
        assert len(entry["hebrew_names"]) > 0

    def test_get_nonexistent_entry(self):
        assert get_line_item_entry("nonexistent") is None
