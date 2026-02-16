"""
PII masking utilities for Israeli payroll data.

Masks:
- Israeli ID numbers (Teudat Zehut): 9-digit sequences
- Bank account numbers: common Israeli bank/branch/account patterns
- Credit card numbers: 13-19 digit sequences
- Phone numbers: Israeli mobile/landline patterns
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Israeli ID (Teudat Zehut) — exactly 9 digits
# ---------------------------------------------------------------------------
# Matches 9-digit sequences that may appear with or without dashes/spaces.
# We mask the middle 5 digits: 12*****89

_IL_ID_PATTERN = re.compile(
    r"(?<!\d)"           # not preceded by a digit
    r"(\d{2})"           # first 2 digits (keep)
    r"[-\s]?"
    r"(\d{3})"           # middle 3 digits (mask)
    r"[-\s]?"
    r"(\d{2})"           # middle 2 digits (mask)
    r"[-\s]?"
    r"(\d{2})"           # last 2 digits (keep)
    r"(?!\d)"            # not followed by a digit
)


def _mask_il_id(match: re.Match) -> str:
    first = match.group(1)
    last = match.group(4)
    return f"{first}*****{last}"


# ---------------------------------------------------------------------------
# Israeli bank account pattern
# ---------------------------------------------------------------------------
# Common format: bank(2-3 digits) branch(3-4 digits) account(6-9 digits)
# Often separated by dashes or spaces, sometimes preceded by labels
# We mask the account portion.

_BANK_ACCOUNT_PATTERN = re.compile(
    r"(?:בנק|bank|חשבון|account)?"  # optional label
    r"\s*:?\s*"
    r"(\d{2,3})"                    # bank code (keep)
    r"[-/\s]"
    r"(\d{3,4})"                    # branch (keep first digit)
    r"[-/\s]"
    r"(\d{6,9})"                    # account number (mask most)
    ,
    re.IGNORECASE,
)


def _mask_bank_account(match: re.Match) -> str:
    bank = match.group(1)
    branch = match.group(2)
    account = match.group(3)
    masked_account = account[0] + "*" * (len(account) - 2) + account[-1]
    return f"{bank}-{branch[0]}***-{masked_account}"


# ---------------------------------------------------------------------------
# Credit card pattern — 13 to 19 digits, optional separators
# ---------------------------------------------------------------------------

_CREDIT_CARD_PATTERN = re.compile(
    r"(?<!\d)"
    r"(\d{4})"
    r"[-\s]?"
    r"(\d{4})"
    r"[-\s]?"
    r"(\d{4})"
    r"[-\s]?"
    r"(\d{1,7})"
    r"(?!\d)"
)


def _mask_credit_card(match: re.Match) -> str:
    last = match.group(4)
    return f"****-****-****-{last}"


# ---------------------------------------------------------------------------
# Israeli phone numbers
# ---------------------------------------------------------------------------

_PHONE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(0[2-9]\d)"         # area/operator prefix (keep)
    r"[-\s]?"
    r"(\d{3})"            # middle (mask)
    r"[-\s]?"
    r"(\d{4})"            # end (keep last 2)
    r"(?!\d)"
)


def _mask_phone(match: re.Match) -> str:
    prefix = match.group(1)
    end = match.group(3)
    return f"{prefix}-***-**{end[-2:]}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def mask_pii(text: str) -> str:
    """Apply all PII masks to *text* and return the redacted version."""
    result = text
    result = _IL_ID_PATTERN.sub(_mask_il_id, result)
    result = _BANK_ACCOUNT_PATTERN.sub(_mask_bank_account, result)
    result = _CREDIT_CARD_PATTERN.sub(_mask_credit_card, result)
    result = _PHONE_PATTERN.sub(_mask_phone, result)
    return result


def mask_israeli_id(text: str) -> str:
    """Mask only Israeli ID numbers in *text*."""
    return _IL_ID_PATTERN.sub(_mask_il_id, text)


def validate_israeli_id_checksum(id_str: str) -> bool:
    """
    Validate an Israeli ID number using the Luhn-like algorithm.
    Returns True if valid, False otherwise.
    """
    digits = id_str.replace("-", "").replace(" ", "").strip()
    if len(digits) != 9 or not digits.isdigit():
        return False

    total = 0
    for i, ch in enumerate(digits):
        val = int(ch)
        if i % 2 != 0:
            val *= 2
        if val > 9:
            val -= 9
        total += val

    return total % 10 == 0
