"""
Israel payroll constants and thresholds — 2026 tax year.

╔══════════════════════════════════════════════════════════════════╗
║  UPDATE THIS FILE REGULARLY!                                    ║
║  These values change with Israeli government updates.           ║
║  Last verified: 2026-02 (February 2026).                        ║
║  Source: Israel Tax Authority, National Insurance Institute,     ║
║          https://www.kolzchut.org.il / Ministry of Economy      ║
╚══════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Minimum wage (as of 2025-12 — verify for April 2026 updates)
# ---------------------------------------------------------------------------
MINIMUM_WAGE_MONTHLY: float = 5_880.02  # NIS, full-time
MINIMUM_WAGE_HOURLY: float = 32.30      # NIS
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
# Income tax brackets 2026 — monthly NIS (מדרגות מס הכנסה)
# Source: Israel Tax Authority publications for 2026 tax year
# Each tuple: (upper_bound_monthly, marginal_rate)
# ---------------------------------------------------------------------------
TAX_BRACKETS_MONTHLY: list[tuple[float, float]] = [
    (7_310.0, 0.10),     # 10% on first ₪7,310
    (10_480.0, 0.14),    # 14% on ₪7,310 — ₪10,480
    (19_000.0, 0.20),    # 20% on ₪10,480 — ₪19,000
    (25_101.0, 0.31),    # 31% on ₪19,000 — ₪25,101
    (41_410.0, 0.35),    # 35% on ₪25,101 — ₪41,410
    (53_970.0, 0.47),    # 47% on ₪41,410 — ₪53,970
    (float("inf"), 0.50),  # 50% on income above ₪53,970
]

# ---------------------------------------------------------------------------
# Credit points (נקודות זיכוי) — 2026
# ---------------------------------------------------------------------------
CREDIT_POINT_MONTHLY_VALUE: float = 242.0    # ₪ per credit point per month
CREDIT_POINT_ANNUAL_VALUE: float = 2_904.0   # ₪ per credit point per year
DEFAULT_CREDIT_POINTS_MALE: float = 2.25     # base credit points (resident male)
DEFAULT_CREDIT_POINTS_FEMALE: float = 2.75   # base credit points (resident female)

# ---------------------------------------------------------------------------
# National Insurance (ביטוח לאומי) — 2026 rates
# Two tiers: reduced rate up to 60% of average wage, full rate above
# ---------------------------------------------------------------------------
NI_THRESHOLD_MONTHLY: float = 7_703.0   # 60% of average wage (₪12,838)
NI_MAX_INSURABLE_MONTHLY: float = 51_910.0  # maximum insurable income

# Employee rates
NI_EMPLOYEE_REDUCED_RATE: float = 0.0104   # 1.04% (up to threshold)
NI_EMPLOYEE_FULL_RATE: float = 0.07        # 7.00% (threshold to max)

# Employer rates
NI_EMPLOYER_REDUCED_RATE: float = 0.0451   # 4.51% (up to threshold)
NI_EMPLOYER_FULL_RATE: float = 0.076       # 7.60% (threshold to max)

# ---------------------------------------------------------------------------
# Health tax (מס בריאות) — 2026 rates
# Same tier structure as National Insurance
# ---------------------------------------------------------------------------
HEALTH_EMPLOYEE_REDUCED_RATE: float = 0.0323  # 3.23% (up to threshold)
HEALTH_EMPLOYEE_FULL_RATE: float = 0.0517     # 5.17% (threshold to max)

# ---------------------------------------------------------------------------
# Tolerance values for sanity checks
# ---------------------------------------------------------------------------
NET_TOLERANCE_NIS: float = 5.0          # allow ±5 NIS rounding
TAX_TOLERANCE_NIS: float = 50.0         # allow ±50 NIS for tax calculation comparison
NI_HEALTH_TOLERANCE_NIS: float = 30.0   # allow ±30 NIS for NI/health comparison
LEAVE_BALANCE_TOLERANCE: float = 0.5    # days
EXPENSE_TO_BASE_WARN_RATIO: float = 0.5 # flag if expenses > 50% of base

# ---------------------------------------------------------------------------
# Travel allowance (common reference, not mandatory for all)
# ---------------------------------------------------------------------------
TRAVEL_ALLOWANCE_DAILY_MAX: float = 22.60  # NIS (tax-exempt ceiling)
