/** Maps internal field keys to Hebrew labels for user-facing display. */

export interface FieldRegistryEntry {
  label_he: string;
  section: string;
  help_he: string;
}

const FIELD_REGISTRY: Record<string, FieldRegistryEntry> = {
  period_month: { label_he: "חודש שכר", section: "period", help_he: "החודש שעבורו משולם השכר" },
  period_year: { label_he: "שנת שכר", section: "period", help_he: "השנה שעבורה משולם השכר" },
  salary_type: { label_he: "סוג שכר", section: "employment", help_he: "חודשי (גלובלי) או שעתי" },
  base_salary_or_rate: { label_he: "שכר בסיס", section: "employment", help_he: "שכר בסיס חודשי או שכר לשעה" },
  regular_hours_worked: { label_he: "שעות עבודה רגילות", section: "employment", help_he: "מספר שעות עבודה רגילות בחודש" },
  job_percent: { label_he: "אחוז משרה", section: "employment", help_he: "אחוז משרה (100% = משרה מלאה)" },
  pension_expected: { label_he: "הפרשת פנסיה", section: "benefits", help_he: "האם צפויה הפרשה לפנסיה" },
  training_fund_expected: { label_he: "קרן השתלמות", section: "benefits", help_he: "האם צפויה הפרשה לקרן השתלמות" },
  employer_name: { label_he: "שם מעסיק", section: "employer", help_he: "שם החברה או המעסיק" },
  employee_name: { label_he: "שם עובד", section: "employee", help_he: "שם העובד כפי שמופיע בתלוש" },
  gross: { label_he: "שכר ברוטו", section: "totals", help_he: "סך כל ההכנסות לפני ניכויים" },
  net: { label_he: "שכר נטו", section: "totals", help_he: "הסכום שמועבר בפועל לחשבון הבנק" },
  total_deductions: { label_he: "סה\"כ ניכויים", section: "totals", help_he: "סך כל הניכויים (מס, ביטוח לאומי, פנסיה וכו')" },
};

/**
 * Get the Hebrew label for an internal field key.
 * Returns the key itself if not found (graceful fallback, but should not happen).
 */
export function getFieldLabel(key: string): string {
  return FIELD_REGISTRY[key]?.label_he ?? key;
}

/**
 * Get full field info. Returns null if key is not in registry.
 */
export function getFieldInfo(key: string): FieldRegistryEntry | null {
  return FIELD_REGISTRY[key] ?? null;
}

/**
 * Convert a list of internal field keys to Hebrew labels.
 */
export function fieldKeysToLabels(keys: string[]): string[] {
  return keys.map(getFieldLabel);
}
