"""
Rules engine — Israel-specific payslip compliance checks.

13 checks, each returning a list of Flag objects:
 1. Required basics present
 2. Net sanity (gross - deductions ~ net)
 3. Pension lines
 4. Travel allowance
 5. Overtime
 6. Leave balances
 7. Duplicate / unknown deductions
 8. Minimum wage
 9. Tax lines presence
10. Unusually large expense reimbursements
11. Income tax bracket verification (2026 brackets + credit points)
12. National Insurance tiered calculation verification
13. Health tax tiered calculation verification

IMPORTANT: All results use conservative language ("possible issue",
"requires verification"). The system does NOT claim legal certainty.
"""

from __future__ import annotations

import logging
from collections import Counter

from ..config.constants import (
    CREDIT_POINT_MONTHLY_VALUE,
    DEFAULT_CREDIT_POINTS_MALE,
    EXPENSE_TO_BASE_WARN_RATIO,
    HEALTH_EMPLOYEE_FULL_RATE,
    HEALTH_EMPLOYEE_REDUCED_RATE,
    LEAVE_BALANCE_TOLERANCE,
    MINIMUM_WAGE_HOURLY,
    MINIMUM_WAGE_MONTHLY,
    NET_TOLERANCE_NIS,
    NI_EMPLOYEE_FULL_RATE,
    NI_EMPLOYEE_REDUCED_RATE,
    NI_HEALTH_TOLERANCE_NIS,
    NI_MAX_INSURABLE_MONTHLY,
    NI_THRESHOLD_MONTHLY,
    STANDARD_MONTHLY_HOURS,
    TAX_BRACKETS_MONTHLY,
    TAX_TOLERANCE_NIS,
)
from ..models.api_contracts import UserConfirmedFields
from ..models.payslip import Flag, FlagSeverity, Payslip, SalaryType

logger = logging.getLogger(__name__)

# Known legitimate deduction labels (English + Hebrew).
_KNOWN_DEDUCTION_LABELS: set[str] = {
    "income_tax", "national_insurance", "health_tax",
    "pension_employee", "training_fund_employee",
    "union_fee", "loan_repayment", "advanced_study_fund",
    "child_care", "parking", "meals",
    "מס הכנסה", "ביטוח לאומי", "מס בריאות",
    "תגמולים עובד", "קרן השתלמות עובד", "קרן השתלמות",
    "ועד עובדים", "דמי ועד", "הלוואה", "החזר הלוואה",
    "חניה", "ארוחות",
}

# Keywords hinting at expense reimbursements (not travel).
_EXPENSE_KEYWORDS: set[str] = {
    "expense", "reimbursement", "refund",
    "החזר", "הוצאות", 'אש"ל', "כלכלה",
}


# ───────────────────────────────────────────────────────────────────────────
# Public entry point
# ───────────────────────────────────────────────────────────────────────────

def run_rules(payslip: Payslip, confirmed: UserConfirmedFields) -> list[Flag]:
    """Run all compliance checks and return flags."""
    flags: list[Flag] = []
    flags.extend(_check_required_basics(payslip))          # 1
    flags.extend(_check_net_sanity(payslip))               # 2
    flags.extend(_check_pension_lines(payslip, confirmed)) # 3
    flags.extend(_check_travel_allowance(payslip))         # 4
    flags.extend(_check_overtime(payslip))                 # 5
    flags.extend(_check_leave_balances(payslip))           # 6
    flags.extend(_check_unknown_deductions(payslip))       # 7
    flags.extend(_check_minimum_wage(payslip, confirmed))  # 8
    flags.extend(_check_tax_lines_present(payslip))        # 9
    flags.extend(_check_large_expenses(payslip, confirmed))# 10
    flags.extend(_check_income_tax(payslip))               # 11
    flags.extend(_check_national_insurance(payslip))        # 12
    flags.extend(_check_health_tax(payslip))                # 13
    return flags


# ───────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────

def _label_matches_any(label: str, label_he: str | None, keywords: set[str]) -> bool:
    """Check if an English or Hebrew label contains any keyword."""
    lo = label.lower()
    he = (label_he or "").strip()
    return any(kw in lo for kw in keywords) or any(kw in he for kw in keywords)


# ═══════════════════════════════════════════════════════════════════════════
# Rule 1 — Required basics present
# ═══════════════════════════════════════════════════════════════════════════

def _check_required_basics(payslip: Payslip) -> list[Flag]:
    missing: list[str] = []
    if not payslip.employer.name:
        missing.append("שם מעסיק")
    if not payslip.employee.name:
        missing.append("שם עובד")
    if payslip.period.month is None or payslip.period.year is None:
        missing.append("חודש/שנת שכר")
    if payslip.totals.gross is None:
        missing.append("שכר ברוטו")
    if payslip.totals.net is None:
        missing.append("שכר נטו")
    if not missing:
        return []
    return [Flag(
        severity=FlagSeverity.warn,
        title_he="שדות חובה חסרים",
        explanation_he=(
            f"השדות הבאים לא זוהו בתלוש: {', '.join(missing)}. "
            "ייתכן שמדובר בבעיית חילוץ טקסט. מומלץ לבדוק את התלוש המקורי."
        ),
        evidence=f"Missing: {', '.join(missing)}",
        suggested_next_step="בדוק את התלוש המקורי והשלם את השדות החסרים",
        confidence=0.9,
    )]


# ═══════════════════════════════════════════════════════════════════════════
# Rule 2 — Net sanity (gross - deductions ~ net)
# ═══════════════════════════════════════════════════════════════════════════

def _check_net_sanity(payslip: Payslip) -> list[Flag]:
    if payslip.totals.gross is None or payslip.totals.net is None:
        return []
    total_ded = payslip.totals.total_deductions
    if total_ded is None:
        total_ded = sum(d.amount for d in payslip.deductions_lines)
    expected = payslip.totals.gross - total_ded
    diff = abs(expected - payslip.totals.net)
    if diff <= NET_TOLERANCE_NIS:
        return []
    return [Flag(
        severity=FlagSeverity.warn,
        title_he="חוסר התאמה בין ברוטו לנטו",
        explanation_he=(
            f"ברוטו ({payslip.totals.gross:,.2f} ₪) פחות סך ניכויים "
            f"({total_ded:,.2f} ₪) = {expected:,.2f} ₪, "
            f"אך הנטו בתלוש הוא {payslip.totals.net:,.2f} ₪ "
            f"(הפרש: {diff:,.2f} ₪). ייתכן שחסרים ניכויים או שיש טעות."
        ),
        evidence=f"Expected net: {expected:.2f}, Actual net: {payslip.totals.net:.2f}, Diff: {diff:.2f}",
        suggested_next_step="בדוק שכל שורות הניכויים מופיעות ושהסכומים נכונים",
        confidence=0.85,
    )]


# ═══════════════════════════════════════════════════════════════════════════
# Rule 3 — Pension lines
# ═══════════════════════════════════════════════════════════════════════════

def _check_pension_lines(payslip: Payslip, confirmed: UserConfirmedFields) -> list[Flag]:
    if not confirmed.pension_expected:
        return []
    flags: list[Flag] = []
    ee = payslip.pension.employee_tagmulim
    er = payslip.pension.employer_tagmulim
    pitz = payslip.pension.employer_pitzuyim

    # A — employee pays but employer missing
    if ee and ee > 0 and (er is None or er == 0):
        flags.append(Flag(
            severity=FlagSeverity.warn,
            title_he="ייתכן חוסר בהפרשת מעסיק לפנסיה",
            explanation_he=(
                "זוהה ניכוי תגמולי עובד לפנסיה אך לא נמצאה הפרשת מעסיק תואמת. "
                "על פי צווי ההרחבה, המעסיק מחויב להפריש לתגמולים ולפיצויים. "
                "ייתכן שההפרשה קיימת אך לא זוהתה בחילוץ."
            ),
            evidence=f"Employee pension: {ee}, Employer pension: {er}",
            suggested_next_step="בדוק את דוח ההפרשות הפנסיוניות מול קופת הגמל/ביטוח המנהלים",
            confidence=0.7,
        ))

    # B — both missing
    if (ee is None or ee == 0) and (er is None or er == 0):
        flags.append(Flag(
            severity=FlagSeverity.warn,
            title_he="לא זוהו הפרשות פנסיוניות",
            explanation_he=(
                "לא נמצאו שורות הפרשה לפנסיה (תגמולי עובד/מעביד). "
                "אם אתה זכאי לפנסיה, ייתכן שמדובר בבעיית חילוץ טקסט "
                "או שההפרשות חסרות בפועל. מומלץ לבדוק."
            ),
            evidence="No pension lines found",
            suggested_next_step="בדוק הסכם עבודה ודוח הפרשות פנסיוניות",
            confidence=0.75,
        ))

    # C — pitzuyim missing when tagmulim exist
    if er and er > 0 and (pitz is None or pitz == 0):
        flags.append(Flag(
            severity=FlagSeverity.info,
            title_he="לא זוהתה הפרשה לפיצויים",
            explanation_he=(
                "זוהו תגמולי מעביד אך לא נמצאה שורת פיצויים. "
                "ייתכן שהפיצויים כלולים בשורה אחרת או שלא זוהו בחילוץ. "
                "מומלץ לוודא מול דוח ההפרשות."
            ),
            evidence=f"Employer tagmulim: {er}, Pitzuyim: {pitz}",
            suggested_next_step="בדוק דוח הפרשות פנסיוניות — האם הפיצויים מופקדים בנפרד",
            confidence=0.6,
        ))

    # D — training fund
    if confirmed.training_fund_expected:
        tf_ee = payslip.pension.training_fund_employee
        tf_er = payslip.pension.training_fund_employer
        if (tf_ee is None or tf_ee == 0) and (tf_er is None or tf_er == 0):
            flags.append(Flag(
                severity=FlagSeverity.info,
                title_he="לא זוהו הפרשות לקרן השתלמות",
                explanation_he=(
                    "ציפית להפרשות לקרן השתלמות אך לא נמצאו שורות תואמות. "
                    "ייתכן שהשם שונה בתלוש או שלא זוהו בחילוץ."
                ),
                evidence="No training fund lines found",
                suggested_next_step="בדוק הסכם עבודה ודוח קרן השתלמות",
                confidence=0.65,
            ))

    return flags


# ═══════════════════════════════════════════════════════════════════════════
# Rule 4 — Travel allowance
# ═══════════════════════════════════════════════════════════════════════════

def _check_travel_allowance(payslip: Payslip) -> list[Flag]:
    kw = {"travel", "נסיעות", "נסיעה", "החזר נסיעות", "דמי נסיעות"}
    has = any(_label_matches_any(l.label, l.label_he, kw) for l in payslip.earnings_lines)
    if has:
        return []
    return [Flag(
        severity=FlagSeverity.info,
        title_he="לא זוהו דמי נסיעות",
        explanation_he=(
            "לא נמצאה שורת החזר/דמי נסיעות בתלוש. "
            "ייתכן שהעובד פטור (עובד מרחוק / הסדר אחר), "
            "או שהשורה קיימת אך לא זוהתה. מומלץ לבדוק מול הסכם העבודה."
        ),
        evidence="No travel allowance line found in earnings",
        suggested_next_step="בדוק הסכם עבודה — האם קיימת זכאות לדמי נסיעות",
        confidence=0.5,
    )]


# ═══════════════════════════════════════════════════════════════════════════
# Rule 5 — Overtime
# ═══════════════════════════════════════════════════════════════════════════

def _check_overtime(payslip: Payslip) -> list[Flag]:
    """
    Disclaimer: accurate overtime calculation requires daily attendance
    records. This check only verifies monthly totals.
    """
    flags: list[Flag] = []
    ot_kw = {"overtime", "נוספות", "שעות נוספות"}

    has_hours = (
        (payslip.employment.hours_overtime_125 or 0) > 0
        or (payslip.employment.hours_overtime_150 or 0) > 0
    )
    has_pay = any(
        _label_matches_any(l.label, l.label_he, ot_kw) for l in payslip.earnings_lines
    )

    if has_hours and not has_pay:
        flags.append(Flag(
            severity=FlagSeverity.warn,
            title_he="שעות נוספות ללא שורת תשלום",
            explanation_he=(
                "זוהו שעות נוספות בתלוש אך לא נמצאה שורת תשלום עבור שעות נוספות. "
                "ייתכן שהתשלום כלול בשורה אחרת או שחסר. "
                "הערה: חישוב מדויק של שעות נוספות מחייב דוח נוכחות יומי. "
                "בדיקה זו מתייחסת לסיכום חודשי בלבד."
            ),
            evidence=(
                f"OT hours 125%: {payslip.employment.hours_overtime_125}, "
                f"OT hours 150%: {payslip.employment.hours_overtime_150}, "
                "OT pay lines: 0"
            ),
            suggested_next_step="בדוק דוח נוכחות יומי מול שורות התשלום בתלוש",
            confidence=0.7,
        ))

    if has_pay and not has_hours:
        flags.append(Flag(
            severity=FlagSeverity.info,
            title_he="תשלום שעות נוספות ללא פירוט שעות",
            explanation_he=(
                "נמצאה שורת תשלום שעות נוספות אך לא זוהו שעות נוספות בפירוט. "
                "ייתכן שהשעות לא חולצו כראוי מהתלוש. "
                "הערה: חישוב מדויק של שעות נוספות מחייב דוח נוכחות יומי."
            ),
            evidence="Overtime pay line found but no hours in employment section",
            suggested_next_step="בדוק שהשעות הנוספות מפורטות בתלוש ובדוח הנוכחות",
            confidence=0.5,
        ))

    return flags


# ═══════════════════════════════════════════════════════════════════════════
# Rule 6 — Leave balances
# ═══════════════════════════════════════════════════════════════════════════

def _check_leave_balances(payslip: Payslip) -> list[Flag]:
    flags: list[Flag] = []
    lv = payslip.leave

    for label_he, opn, acc, usd, cls in [
        ("חופשה", lv.vacation_open, lv.vacation_accrued, lv.vacation_used, lv.vacation_close),
        ("מחלה", lv.sick_open, lv.sick_accrued, lv.sick_used, lv.sick_close),
    ]:
        f = _check_single_leave(label_he, opn, acc, usd, cls)
        if f:
            flags.append(f)
    return flags


def _check_single_leave(
    name_he: str,
    opening: float | None,
    accrued: float | None,
    used: float | None,
    closing: float | None,
) -> Flag | None:
    if any(v is None for v in (opening, accrued, used, closing)):
        return None

    expected = opening + accrued - used  # type: ignore[operator]
    diff = abs(expected - closing)       # type: ignore[operator]

    if diff > LEAVE_BALANCE_TOLERANCE:
        return Flag(
            severity=FlagSeverity.warn,
            title_he=f"חוסר התאמה ביתרת {name_he}",
            explanation_he=(
                f"יתרת פתיחה ({opening}) + צבירה ({accrued}) - ניצול ({used}) "
                f"= {expected:.2f}, אך יתרת הסגירה בתלוש היא {closing}. "
                f"הפרש: {diff:.2f} ימים. ייתכן שיש שגיאה או שחסר מידע."
            ),
            evidence=(
                f"{name_he}: open={opening}, accrued={accrued}, used={used}, "
                f"expected_close={expected:.2f}, actual_close={closing}, diff={diff:.2f}"
            ),
            suggested_next_step=f"בדוק את יתרת ה{name_he} מול מערכת הנוכחות",
            confidence=0.75,
        )

    if closing < 0:  # type: ignore[operator]
        return Flag(
            severity=FlagSeverity.warn,
            title_he=f"יתרת {name_he} שלילית",
            explanation_he=(
                f"יתרת הסגירה של {name_he} היא {closing} (שלילית). "
                "ייתכן שנוצלו יותר ימים מהצבירה, או שיש טעות בנתונים."
            ),
            evidence=f"{name_he} closing balance: {closing}",
            suggested_next_step=f"בדוק ניצול {name_he} ואשר מול מחלקת משאבי אנוש",
            confidence=0.8,
        )
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Rule 7 — Duplicate / unknown deductions
# ═══════════════════════════════════════════════════════════════════════════

def _check_unknown_deductions(payslip: Payslip) -> list[Flag]:
    flags: list[Flag] = []

    # Unknown labels
    unknown: list[str] = []
    for d in payslip.deductions_lines:
        lo = d.label.lower()
        he = (d.label_he or "").strip()
        if lo not in _KNOWN_DEDUCTION_LABELS and he not in _KNOWN_DEDUCTION_LABELS:
            display = he if he else d.label
            unknown.append(f"{display} ({d.amount:,.2f} ₪)")

    if unknown:
        flags.append(Flag(
            severity=FlagSeverity.info,
            title_he="ניכויים לא מזוהים",
            explanation_he=(
                f"הניכויים הבאים לא זוהו כסוג מוכר: {', '.join(unknown)}. "
                "ייתכן שמדובר בניכויים לגיטימיים (כגון ועד, הלוואה, חניה) "
                "או בטעות. מומלץ לברר את מהות הניכוי."
            ),
            evidence=f"Unknown deductions: {unknown}",
            suggested_next_step="בדוק מול תלוש השכר וההסכם — מה כל ניכוי מייצג",
            confidence=0.5,
        ))

    # Duplicate labels
    counts = Counter(d.label.lower() for d in payslip.deductions_lines)
    dupes = [lbl for lbl, c in counts.items() if c > 1]
    if dupes:
        flags.append(Flag(
            severity=FlagSeverity.info,
            title_he="ניכויים כפולים",
            explanation_he=(
                f"הניכויים הבאים מופיעים יותר מפעם אחת: {', '.join(dupes)}. "
                "ייתכן שזה תקין (למשל, שתי הלוואות שונות) אך מומלץ לוודא."
            ),
            evidence=f"Duplicate deduction labels: {dupes}",
            suggested_next_step="בדוק שאין כפילות בניכויים — ייתכן שניכוי חויב פעמיים",
            confidence=0.5,
        ))

    return flags


# ═══════════════════════════════════════════════════════════════════════════
# Rule 8 — Minimum wage
# ═══════════════════════════════════════════════════════════════════════════

def _check_minimum_wage(payslip: Payslip, confirmed: UserConfirmedFields) -> list[Flag]:
    base = confirmed.base_salary_or_rate
    stype = confirmed.salary_type

    if stype == SalaryType.hourly:
        if base < MINIMUM_WAGE_HOURLY:
            return [Flag(
                severity=FlagSeverity.high,
                title_he="ייתכן ששכר השעה נמוך משכר המינימום",
                explanation_he=(
                    f"שכר השעה שדווח ({base:,.2f} ₪) נמוך משכר המינימום "
                    f"({MINIMUM_WAGE_HOURLY:,.2f} ₪ לשעה). "
                    "ייתכן שיש תוספות המעלות את השכר האפקטיבי, "
                    "או שמדובר בסוג העסקה מיוחד. מומלץ לבדוק."
                ),
                evidence=f"Hourly rate: {base}, Minimum: {MINIMUM_WAGE_HOURLY}",
                suggested_next_step="בדוק הסכם העבודה וודא שהשכר עומד בדרישות חוק שכר מינימום",
                confidence=0.8,
            )]
        return []

    # Monthly salary
    hours = confirmed.regular_hours_worked
    job_pct = confirmed.job_percent

    if hours and hours > 0:
        eff = base / hours
    elif job_pct and job_pct > 0:
        equiv = STANDARD_MONTHLY_HOURS * (job_pct / 100.0)
        eff = base / equiv if equiv > 0 else 0.0
    else:
        # No hours / job% — compare monthly directly
        if base < MINIMUM_WAGE_MONTHLY:
            return [Flag(
                severity=FlagSeverity.high,
                title_he="ייתכן ששכר הבסיס נמוך משכר המינימום",
                explanation_he=(
                    f"שכר הבסיס ({base:,.2f} ₪) נמוך משכר המינימום "
                    f"({MINIMUM_WAGE_MONTHLY:,.2f} ₪ לחודש למשרה מלאה). "
                    "ייתכן שמדובר במשרה חלקית או שיש טעות. "
                    "ללא פירוט שעות או אחוז משרה, לא ניתן לחשב שכר שעתי אפקטיבי."
                ),
                evidence=f"Monthly base: {base}, Minimum monthly: {MINIMUM_WAGE_MONTHLY}",
                suggested_next_step="בדוק אחוז משרה ושעות עבודה בהסכם העבודה",
                confidence=0.6,
            )]
        return []

    if eff < MINIMUM_WAGE_HOURLY:
        return [Flag(
            severity=FlagSeverity.high,
            title_he="ייתכן ששכר השעה האפקטיבי נמוך משכר המינימום",
            explanation_he=(
                f"שכר בסיס ({base:,.2f} ₪) חלקי שעות/משרה = "
                f"{eff:,.2f} ₪ לשעה, "
                f"מתחת לשכר מינימום ({MINIMUM_WAGE_HOURLY:,.2f} ₪). "
                "ייתכן שיש תוספות קבועות הנכללות בבסיס לחישוב, "
                "או שאחוז המשרה/שעות שהוזנו אינם מדויקים."
            ),
            evidence=(
                f"Base: {base}, Hours: {hours}, Job%: {job_pct}, "
                f"Effective hourly: {eff:.2f}, Minimum: {MINIMUM_WAGE_HOURLY}"
            ),
            suggested_next_step="בדוק שעות ואחוז משרה בהסכם העבודה ובדוח הנוכחות",
            confidence=0.7,
        )]

    return []


# ═══════════════════════════════════════════════════════════════════════════
# Rule 9 — Tax lines presence
# ═══════════════════════════════════════════════════════════════════════════

def _check_tax_lines_present(payslip: Payslip) -> list[Flag]:
    if payslip.totals.gross is None or payslip.totals.gross <= 0:
        return []

    all_labels: list[str] = []
    for d in payslip.deductions_lines:
        all_labels.append(d.label.lower())
        if d.label_he:
            all_labels.append(d.label_he.strip())
    combined = " ".join(all_labels)

    has_income = any(kw in combined for kw in ("income_tax", "מס הכנסה"))
    has_bituach = any(kw in combined for kw in ("national_insurance", "ביטוח לאומי"))
    has_health = any(kw in combined for kw in ("health_tax", "מס בריאות"))

    missing: list[str] = []
    if not has_income:
        missing.append("מס הכנסה")
    if not has_bituach:
        missing.append("ביטוח לאומי")
    if not has_health:
        missing.append("מס בריאות")

    if not missing:
        return []
    return [Flag(
        severity=FlagSeverity.warn,
        title_he="ייתכן שחסרות שורות מס",
        explanation_he=(
            f"לא זוהו השורות הבאות: {', '.join(missing)}. "
            "ייתכן שהשורות קיימות בתלוש אך לא זוהו בחילוץ, "
            "או שהעובד פטור (הכנסה נמוכה / נקודות זיכוי). מומלץ לוודא."
        ),
        evidence=f"Missing tax lines: {', '.join(missing)}",
        suggested_next_step="בדוק את התלוש המקורי ואת תיאום המס",
        confidence=0.6,
    )]


# ═══════════════════════════════════════════════════════════════════════════
# Rule 10 — Unusually large expense reimbursements
# ═══════════════════════════════════════════════════════════════════════════

def _check_large_expenses(payslip: Payslip, confirmed: UserConfirmedFields) -> list[Flag]:
    base = confirmed.base_salary_or_rate
    if not base or base <= 0:
        return []

    if confirmed.salary_type == SalaryType.hourly:
        hrs = confirmed.regular_hours_worked or STANDARD_MONTHLY_HOURS
        monthly_base = base * hrs
    else:
        monthly_base = base

    total_exp = 0.0
    exp_labels: list[str] = []
    for line in payslip.earnings_lines:
        if _label_matches_any(line.label, line.label_he, _EXPENSE_KEYWORDS):
            # Exclude travel (covered in Rule 4)
            if "travel" in line.label.lower() or "נסיעות" in (line.label_he or ""):
                continue
            total_exp += line.amount
            exp_labels.append(f"{line.label_he or line.label} ({line.amount:,.2f} ₪)")

    if total_exp <= 0 or monthly_base <= 0:
        return []

    ratio = total_exp / monthly_base
    if ratio <= EXPENSE_TO_BASE_WARN_RATIO:
        return []

    return [Flag(
        severity=FlagSeverity.info,
        title_he="החזרי הוצאות גבוהים ביחס לשכר הבסיס",
        explanation_he=(
            f"סך החזרי הוצאות ({total_exp:,.2f} ₪) מהווים "
            f"{ratio:.0%} משכר הבסיס ({monthly_base:,.2f} ₪). "
            "ייתכן שזה לגיטימי (למשל, הוצאות רכב / אש\"ל / ציוד), "
            "אך יחס גבוה עלול להצביע על סיווג שגוי של רכיבי שכר."
        ),
        evidence=f"Expenses: {total_exp:.2f}, Base: {monthly_base:.2f}, Ratio: {ratio:.2%}",
        suggested_next_step="בדוק שהחזרי ההוצאות מגובים בקבלות ואושרו כנדרש",
        confidence=0.45,
    )]


# ═══════════════════════════════════════════════════════════════════════════
# Calculation helpers — Israeli tax, NI, health
# ═══════════════════════════════════════════════════════════════════════════

def calc_income_tax(
    taxable_monthly: float,
    credit_points: float = DEFAULT_CREDIT_POINTS_MALE,
) -> float:
    """
    Calculate expected monthly income tax using 2026 brackets.
    Subtracts credit-point benefit from the gross tax liability.
    """
    if taxable_monthly <= 0:
        return 0.0
    tax = 0.0
    prev_bound = 0.0
    for upper, rate in TAX_BRACKETS_MONTHLY:
        if taxable_monthly <= prev_bound:
            break
        band = min(taxable_monthly, upper) - prev_bound
        if band > 0:
            tax += band * rate
        prev_bound = upper

    # Subtract credit-point benefit (cannot go below zero)
    credit_benefit = credit_points * CREDIT_POINT_MONTHLY_VALUE
    return max(tax - credit_benefit, 0.0)


def calc_national_insurance(gross_monthly: float) -> float:
    """
    Calculate expected employee National Insurance contribution (2026).
    Two tiers: reduced rate up to 60% of average wage, full rate above.
    """
    if gross_monthly <= 0:
        return 0.0
    capped = min(gross_monthly, NI_MAX_INSURABLE_MONTHLY)
    if capped <= NI_THRESHOLD_MONTHLY:
        return capped * NI_EMPLOYEE_REDUCED_RATE
    return (
        NI_THRESHOLD_MONTHLY * NI_EMPLOYEE_REDUCED_RATE
        + (capped - NI_THRESHOLD_MONTHLY) * NI_EMPLOYEE_FULL_RATE
    )


def calc_health_tax(gross_monthly: float) -> float:
    """
    Calculate expected employee health tax contribution (2026).
    Same tier structure as National Insurance.
    """
    if gross_monthly <= 0:
        return 0.0
    capped = min(gross_monthly, NI_MAX_INSURABLE_MONTHLY)
    if capped <= NI_THRESHOLD_MONTHLY:
        return capped * HEALTH_EMPLOYEE_REDUCED_RATE
    return (
        NI_THRESHOLD_MONTHLY * HEALTH_EMPLOYEE_REDUCED_RATE
        + (capped - NI_THRESHOLD_MONTHLY) * HEALTH_EMPLOYEE_FULL_RATE
    )


# ═══════════════════════════════════════════════════════════════════════════
# Rule 11 — Income tax bracket verification
# ═══════════════════════════════════════════════════════════════════════════

def _check_income_tax(payslip: Payslip) -> list[Flag]:
    """
    Compare the income tax deducted on the payslip against the expected
    amount from the 2026 tax brackets (with default credit points).
    """
    gross = payslip.totals.taxable_gross or payslip.totals.gross
    if not gross or gross <= 0:
        return []

    # Find the actual income tax deduction
    actual_tax: float | None = None
    for d in payslip.deductions_lines:
        lo = d.label.lower()
        he = (d.label_he or "").strip()
        if "income_tax" in lo or "מס הכנסה" in he:
            actual_tax = d.amount
            break

    if actual_tax is None:
        return []  # Rule 9 already flags missing tax lines

    expected = calc_income_tax(gross)
    diff = abs(actual_tax - expected)

    if diff <= TAX_TOLERANCE_NIS:
        return []

    return [Flag(
        severity=FlagSeverity.info,
        title_he="הפרש בחישוב מס הכנסה",
        explanation_he=(
            f"מס הכנסה בתלוש: {actual_tax:,.2f} ₪. "
            f"חישוב משוער לפי מדרגות 2026 (עם {DEFAULT_CREDIT_POINTS_MALE} "
            f"נקודות זיכוי ✕ {CREDIT_POINT_MONTHLY_VALUE} ₪): "
            f"{expected:,.2f} ₪ (הפרש: {diff:,.2f} ₪). "
            "הפער יכול לנבוע מנקודות זיכוי נוספות, תיאום מס, "
            "הכנסה ממעסיקים נוספים, או רכיבים פטורים. "
            "מומלץ לבדוק תיאום מס ואישורי זיכוי."
        ),
        evidence=(
            f"Gross: {gross:.2f}, Actual tax: {actual_tax:.2f}, "
            f"Expected (default credits): {expected:.2f}, Diff: {diff:.2f}"
        ),
        suggested_next_step="בדוק אישור תיאום מס ונקודות זיכוי מול פקיד השומה",
        confidence=0.55,
    )]


# ═══════════════════════════════════════════════════════════════════════════
# Rule 12 — National Insurance tiered calculation
# ═══════════════════════════════════════════════════════════════════════════

def _check_national_insurance(payslip: Payslip) -> list[Flag]:
    """
    Verify National Insurance deduction against the tiered 2026 rates.
    """
    gross = payslip.totals.gross
    if not gross or gross <= 0:
        return []

    actual_ni: float | None = None
    for d in payslip.deductions_lines:
        lo = d.label.lower()
        he = (d.label_he or "").strip()
        if "national_insurance" in lo or "ביטוח לאומי" in he:
            actual_ni = d.amount
            break

    if actual_ni is None:
        return []  # Rule 9 already flags missing NI

    expected = calc_national_insurance(gross)
    diff = abs(actual_ni - expected)

    if diff <= NI_HEALTH_TOLERANCE_NIS:
        return []

    return [Flag(
        severity=FlagSeverity.info,
        title_he="הפרש בחישוב ביטוח לאומי",
        explanation_he=(
            f"ביטוח לאומי בתלוש: {actual_ni:,.2f} ₪. "
            f"חישוב משוער לפי תעריפי 2026 "
            f"({NI_EMPLOYEE_REDUCED_RATE:.2%} עד {NI_THRESHOLD_MONTHLY:,.0f} ₪, "
            f"{NI_EMPLOYEE_FULL_RATE:.2%} מעל): {expected:,.2f} ₪ "
            f"(הפרש: {diff:,.2f} ₪). "
            "הפער יכול לנבוע מהכנסות נוספות, פטורים, "
            "או בסיס שונה לחישוב. מומלץ לבדוק."
        ),
        evidence=(
            f"Gross: {gross:.2f}, Actual NI: {actual_ni:.2f}, "
            f"Expected: {expected:.2f}, Diff: {diff:.2f}"
        ),
        suggested_next_step="בדוק את בסיס החישוב לביטוח לאומי מול אישור ביטוח לאומי",
        confidence=0.55,
    )]


# ═══════════════════════════════════════════════════════════════════════════
# Rule 13 — Health tax tiered calculation
# ═══════════════════════════════════════════════════════════════════════════

def _check_health_tax(payslip: Payslip) -> list[Flag]:
    """
    Verify health tax deduction against the tiered 2026 rates.
    """
    gross = payslip.totals.gross
    if not gross or gross <= 0:
        return []

    actual_health: float | None = None
    for d in payslip.deductions_lines:
        lo = d.label.lower()
        he = (d.label_he or "").strip()
        if "health_tax" in lo or "מס בריאות" in he:
            actual_health = d.amount
            break

    if actual_health is None:
        return []  # Rule 9 already flags missing health tax

    expected = calc_health_tax(gross)
    diff = abs(actual_health - expected)

    if diff <= NI_HEALTH_TOLERANCE_NIS:
        return []

    return [Flag(
        severity=FlagSeverity.info,
        title_he="הפרש בחישוב מס בריאות",
        explanation_he=(
            f"מס בריאות בתלוש: {actual_health:,.2f} ₪. "
            f"חישוב משוער לפי תעריפי 2026 "
            f"({HEALTH_EMPLOYEE_REDUCED_RATE:.2%} עד {NI_THRESHOLD_MONTHLY:,.0f} ₪, "
            f"{HEALTH_EMPLOYEE_FULL_RATE:.2%} מעל): {expected:,.2f} ₪ "
            f"(הפרש: {diff:,.2f} ₪). "
            "הפער יכול לנבוע מבסיס שונה לחישוב או פטורים. מומלץ לבדוק."
        ),
        evidence=(
            f"Gross: {gross:.2f}, Actual health: {actual_health:.2f}, "
            f"Expected: {expected:.2f}, Diff: {diff:.2f}"
        ),
        suggested_next_step="בדוק את בסיס החישוב למס בריאות",
        confidence=0.55,
    )]
