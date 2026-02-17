"""
PII masking utilities for Israeli payroll data.

Masks:
- Israeli ID numbers (Teudat Zehut): 9-digit sequences (with Hebrew prefixes)
- Israeli ID numbers: 8-digit sequences (when preceded by a Hebrew prefix)
- Bank account numbers: common Israeli bank/branch/account patterns
- Credit card numbers: 13-19 digit sequences
- Phone numbers: Israeli mobile/landline patterns
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Israeli ID (Teudat Zehut) — 9 digits with optional Hebrew prefix
# ---------------------------------------------------------------------------
# Matches 9-digit sequences that may appear with or without dashes/spaces.
# Optionally preceded by Hebrew labels: ת.ז., ת.ז, ת"ז, תעודת זהות, מס' זהות
# We mask the middle 5 digits: 12*****89

_IL_ID_PREFIX = (
    r'(?:ת\.?ז\.?\s*:?\s*|ת"ז\s*:?\s*|תעודת\s+זהות\s*:?\s*|מס[\'׳]\s*זהות\s*:?\s*)?'
)

_IL_ID_PATTERN = re.compile(
    _IL_ID_PREFIX
    + r"(?<!\d)"           # not preceded by a digit
    r"(\d{2})"             # first 2 digits (keep)
    r"[-\s]?"
    r"(\d{3})"             # middle 3 digits (mask)
    r"[-\s]?"
    r"(\d{2})"             # middle 2 digits (mask)
    r"[-\s]?"
    r"(\d{2})"             # last 2 digits (keep)
    r"(?!\d)"              # not followed by a digit
)


def _mask_il_id(match: re.Match) -> str:
    first = match.group(1)
    last = match.group(4)
    return f"{first}*****{last}"


# ---------------------------------------------------------------------------
# Israeli ID — 8 digits (leading zero stripped), REQUIRES Hebrew prefix
# ---------------------------------------------------------------------------

_IL_ID_8DIGIT_PATTERN = re.compile(
    r'(?:ת\.?ז\.?\s*:?\s*|ת"ז\s*:?\s*|תעודת\s+זהות\s*:?\s*)'  # REQUIRED prefix
    r"(\d{1})"             # first digit (keep)
    r"[-\s]?"
    r"(\d{3})"             # middle 3 (mask)
    r"[-\s]?"
    r"(\d{2})"             # middle 2 (mask)
    r"[-\s]?"
    r"(\d{2})"             # last 2 (keep)
    r"(?!\d)"
)


def _mask_il_id_8digit(match: re.Match) -> str:
    first = match.group(1)
    last = match.group(4)
    return f"{first}****{last}"


# ---------------------------------------------------------------------------
# Israeli bank account pattern — labeled (prefix required, separator optional)
# ---------------------------------------------------------------------------
# Common format: bank(2-3 digits) branch(3-4 digits) account(6-9 digits)
# When a Hebrew/English label is present, separators are optional.

_BANK_ACCOUNT_LABELED = re.compile(
    r"(?:בנק|bank|חשבון|account|מס[\'׳]\s*חשבון|סניף)"
    r"\s*:?\s*"
    r"(\d{2,3})"                    # bank code (keep)
    r"[-/\s]?"
    r"(\d{3,4})"                    # branch (keep first digit)
    r"[-/\s]?"
    r"(\d{6,9})"                    # account number (mask most)
    ,
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Israeli bank account pattern — unlabeled (separator required)
# ---------------------------------------------------------------------------
# Without a label, separators are required to avoid false positives on
# arbitrary long numbers.

_BANK_ACCOUNT_UNLABELED = re.compile(
    r"(?<!\d)"
    r"(\d{2,3})"                    # bank code (keep)
    r"[-/\s]"
    r"(\d{3,4})"                    # branch (keep first digit)
    r"[-/\s]"
    r"(\d{6,9})"                    # account number (mask most)
    r"(?!\d)"
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
    # 9-digit Israeli ID (with optional prefix) — must come before 8-digit
    result = _IL_ID_PATTERN.sub(_mask_il_id, result)
    # 8-digit Israeli ID (prefix required)
    result = _IL_ID_8DIGIT_PATTERN.sub(_mask_il_id_8digit, result)
    # Bank accounts
    result = _BANK_ACCOUNT_LABELED.sub(_mask_bank_account, result)
    result = _BANK_ACCOUNT_UNLABELED.sub(_mask_bank_account, result)
    # Credit cards
    result = _CREDIT_CARD_PATTERN.sub(_mask_credit_card, result)
    # Phone numbers
    result = _PHONE_PATTERN.sub(_mask_phone, result)
    return result


def mask_israeli_id(text: str) -> str:
    """Mask Israeli ID numbers in *text* (both 9-digit and 8-digit with prefix)."""
    result = _IL_ID_PATTERN.sub(_mask_il_id, text)
    result = _IL_ID_8DIGIT_PATTERN.sub(_mask_il_id_8digit, result)
    return result


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
