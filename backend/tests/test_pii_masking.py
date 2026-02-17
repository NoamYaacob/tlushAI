"""Unit tests for PII masking utilities."""

import pytest

from app.security.pii_masking import (
    mask_israeli_id,
    mask_pii,
    validate_israeli_id_checksum,
)


# ---------------------------------------------------------------------------
# Israeli ID masking
# ---------------------------------------------------------------------------

class TestIsraeliIdMasking:
    def test_masks_9_digit_id(self):
        text = "ת.ז. 012345678"
        result = mask_israeli_id(text)
        assert "012345678" not in result
        assert "01*****78" in result

    def test_masks_id_with_dashes(self):
        text = "01-234-56-78"
        result = mask_israeli_id(text)
        assert "01*****78" in result

    def test_preserves_shorter_numbers(self):
        text = "phone 12345678"  # 8 digits — not an ID
        result = mask_israeli_id(text)
        assert "12345678" in result  # should not be masked

    def test_preserves_longer_numbers(self):
        text = "ref 0123456789"  # 10 digits — not an ID
        result = mask_israeli_id(text)
        # The 10-digit number should not be matched as a 9-digit ID
        assert "0123456789" in result

    def test_multiple_ids(self):
        text = "employee 012345678 employer 987654321"
        result = mask_israeli_id(text)
        assert "012345678" not in result
        assert "987654321" not in result


# ---------------------------------------------------------------------------
# Israeli ID checksum validation
# ---------------------------------------------------------------------------

class TestIsraeliIdChecksum:
    def test_valid_id(self):
        # Known valid Israeli ID: 000000018 (test pattern)
        assert validate_israeli_id_checksum("000000018") is True

    def test_invalid_id(self):
        assert validate_israeli_id_checksum("000000019") is False

    def test_short_id(self):
        assert validate_israeli_id_checksum("12345") is False

    def test_non_numeric(self):
        assert validate_israeli_id_checksum("abcdefghi") is False

    def test_with_dashes(self):
        assert validate_israeli_id_checksum("00-000-00-18") is True


# ---------------------------------------------------------------------------
# Full PII masking pipeline
# ---------------------------------------------------------------------------

class TestFullPiiMasking:
    def test_masks_id_in_payslip_text(self):
        text = "עובד: ישראל ישראלי ת.ז. 012345678 שכר: 15,000"
        result = mask_pii(text)
        assert "012345678" not in result
        assert "15,000" in result  # salary should remain

    def test_masks_phone_number(self):
        text = "טלפון: 052-1234567"
        result = mask_pii(text)
        assert "1234567" not in result
        assert "052" in result  # prefix preserved

    def test_empty_text(self):
        assert mask_pii("") == ""

    def test_no_pii(self):
        text = "שכר יסוד: 15,000 ₪"
        assert mask_pii(text) == text


# ---------------------------------------------------------------------------
# Israeli ID with Hebrew prefixes
# ---------------------------------------------------------------------------

class TestIsraeliIdWithPrefixes:
    def test_tz_with_dots(self):
        text = "ת.ז. 012345678"
        result = mask_israeli_id(text)
        assert "012345678" not in result
        assert "01*****78" in result

    def test_tz_without_final_dot(self):
        text = "ת.ז 012345678"
        result = mask_israeli_id(text)
        assert "01*****78" in result

    def test_tz_with_quotes(self):
        text = 'ת"ז 012345678'
        result = mask_israeli_id(text)
        assert "01*****78" in result

    def test_teudat_zehut_full(self):
        text = "תעודת זהות 012345678"
        result = mask_israeli_id(text)
        assert "01*****78" in result

    def test_tz_colon_space(self):
        text = "ת.ז.: 012345678"
        result = mask_israeli_id(text)
        assert "01*****78" in result

    def test_8digit_with_prefix(self):
        """8-digit ID where leading zero was stripped."""
        text = "ת.ז. 12345678"
        result = mask_pii(text)
        assert "12345678" not in result

    def test_8digit_without_prefix_preserved(self):
        """8-digit number without prefix should NOT be masked."""
        text = "phone 12345678"
        result = mask_israeli_id(text)
        assert "12345678" in result  # should not be masked


# ---------------------------------------------------------------------------
# Bank account patterns
# ---------------------------------------------------------------------------

class TestBankAccountPatterns:
    def test_with_snif_label(self):
        text = "סניף 123 456 12345678"
        result = mask_pii(text)
        assert "12345678" not in result

    def test_bank_with_dashes(self):
        text = "בנק 12-345-12345678"
        result = mask_pii(text)
        assert "12345678" not in result

    def test_unlabeled_with_separator(self):
        """Bank account without label still works when separators present."""
        text = "12-345-12345678"
        result = mask_pii(text)
        assert "12345678" not in result
