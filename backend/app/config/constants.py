"""
Israel payroll constants and thresholds.

╔══════════════════════════════════════════════════════════════════╗
║  UPDATE THIS FILE REGULARLY!                                    ║
║  These values change with Israeli government updates.           ║
║  Last verified: 2026-01 (January 2026).                         ║
║  Source: https://www.kolzchut.org.il / Ministry of Economy      ║
╚══════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Minimum wage (as of 2025-04 — verify for updates)
# ---------------------------------------------------------------------------
MINIMUM_WAGE_MONTHLY: float = 5_880.02  # NIS, full-time (186 hours)
MINIMUM_WAGE_HOURLY: float = 31.61      # NIS
STANDARD_MONTHLY_HOURS: float = 182.0

# ---------------------------------------------------------------------------
# Standard overtime multipliers
# ---------------------------------------------------------------------------
OVERTIME_125_MULTIPLIER: float = 1.25
OVERTIME_150_MULTIPLIER: float = 1.50

# ---------------------------------------------------------------------------
# Pension (mandatory since 2008 expansion orders)
# ---------------------------------------------------------------------------
PENSION_EMPLOYEE_RATE: float = 0.06      # 6%
PENSION_EMPLOYER_TAGMULIM_RATE: float = 0.065  # 6.5%
PENSION_EMPLOYER_PITZUYIM_RATE: float = 0.06   # 6% (up to 8.33%)

# Training fund (common but not always mandatory)
TRAINING_FUND_EMPLOYEE_RATE: float = 0.025  # 2.5%
TRAINING_FUND_EMPLOYER_RATE: float = 0.075  # 7.5%

# ---------------------------------------------------------------------------
# Tolerance values for sanity checks
# ---------------------------------------------------------------------------
NET_TOLERANCE_NIS: float = 5.0          # allow ±5 NIS rounding
LEAVE_BALANCE_TOLERANCE: float = 0.5    # days
EXPENSE_TO_BASE_WARN_RATIO: float = 0.5 # flag if expenses > 50% of base

# ---------------------------------------------------------------------------
# Travel allowance (common reference, not mandatory for all)
# ---------------------------------------------------------------------------
# Just a reference; actual entitlement depends on employment agreement.
TRAVEL_ALLOWANCE_DAILY_MAX: float = 22.60  # NIS (tax-exempt ceiling)

# ---------------------------------------------------------------------------
# Tax brackets — NOT used for computation; only for "is tax line present?" check
# ---------------------------------------------------------------------------
# The system does NOT compute taxes. It only checks that tax lines exist.
