/** Hebrew UI strings — all user-facing text in one place. */

export const S = {
  // App
  appTitle: "TlushAI",
  appSubtitle: "הסבר תלוש שכר ישראלי",

  // Upload step
  uploadDropzone: "גרור תלוש שכר לכאן או לחץ לבחירת קובץ",
  uploadFormats: "PDF, JPG, PNG — עד 10 מגה-בייט",
  uploadPrivacy: "הקובץ נמחק מהשרת מיד לאחר העיבוד. המידע אינו נשמר.",
  uploadProgress: "מעלה את הקובץ...",
  extractingText: "מחלץ טקסט מהתלוש...",
  parsingData: "מזהה נתונים...",
  analyzingSlip: "מנתח את התלוש...",
  uploadFileTypeError: "סוג קובץ לא נתמך. יש להעלות PDF, JPG או PNG.",
  uploadFileSizeError: "הקובץ גדול מדי. הגודל המרבי הוא 10 מגה-בייט.",

  // Confirm step
  confirmTitle: "אימות נתונים שחולצו",
  confirmDescription: "בדוק את הנתונים שחולצו מהתלוש. שדות שלא זוהו אוטומטית מסומנים בצהוב. יש לאשר או לתקן לפני המשך.",
  confirmRequired: "שדות חובה",
  confirmOptional: "שדות אופציונליים",
  confirmSubmit: "המשך לתוצאות",
  confirmFieldNotDetected: "לא זוהה אוטומטית",
  confirmParseWarnings: "אזהרות חילוץ:",
  confirmFieldsNeedVerification: "שדות שדורשים אימות ידני:",
  confirmShowPreview: "הצג טקסט שחולץ (מצונזר)",
  confirmHidePreview: "הסתר תצוגה מקדימה",
  confirmSelectMonth: "-- בחר חודש --",
  confirmSalaryMonthly: "חודשי",
  confirmSalaryHourly: "שעתי",
  confirmPensionExpected: "צפוי הפרשה לפנסיה",
  confirmTrainingFundExpected: "צפוי הפרשה לקרן השתלמות",
  confirmExtractionMethod: "שיטת חילוץ:",

  // Field labels (used in confirm step)
  fieldMonth: "חודש",
  fieldYear: "שנה",
  fieldSalaryType: "סוג שכר",
  fieldBaseRateMonthly: "שכר בסיס חודשי",
  fieldBaseRateHourly: "שכר שעתי",
  fieldHoursWorked: "שעות עבודה רגילות",
  fieldJobPercent: "אחוז משרה",

  // Validation errors
  errSelectMonth: "יש לבחור חודש",
  errInvalidYear: "שנה לא תקינה",
  errSelectSalaryType: "יש לבחור סוג שכר",
  errBaseRateRequired: "יש להזין שכר בסיס גדול מ-0",

  // Results step
  resultsSummaryTitle: "סיכום תלוש",
  resultsFlagsTitle: "ממצאים",
  resultsOkTitle: "תקין",
  resultsLinesTitle: "פירוט שורות",
  resultsEarningsSection: "הכנסות",
  resultsDeductionsSection: "ניכויים",
  resultsEmployerSection: "הפרשות מעסיק",
  resultsTaxSection: "מסים",
  resultsResetButton: "התחל מחדש",
  resultsExportJson: "ייצוא JSON",
  resultsCopyText: "העתק טקסט",
  resultsCopied: "הועתק!",
  resultsBackToConfirm: "חזור לאימות",

  // Line explanation table headers
  tableLineLabel: "שורה",
  tableQty: "כמות/שעות",
  tableRate: "תעריף",
  tableAmount: "סכום",
  tableCategory: "קטגוריה",
  tableExplanation: "הסבר",
  tableStatus: "סטטוס",

  // Categories
  categoryEarning: "הכנסה",
  categoryDeduction: "ניכוי",
  categoryEmployerContribution: "הפרשת מעסיק",
  categoryTax: "מס",
  categoryLeave: "חופשה/מחלה",
  categoryOther: "אחר",

  // Evidence / debug
  debugToggleShow: "הצג מידע טכני",
  debugToggleHide: "הסתר מידע טכני",
  debugEvidence: "נתונים:",
  debugSuggestion: "המלצה:",

  // Stepper
  stepUpload: "העלאת תלוש",
  stepConfirm: "אימות נתונים",
  stepResults: "תוצאות",

  // Footer
  footerDisclaimer: "TlushAI — כלי עזר להבנת תלוש השכר. אין להסתמך על התוצאות כייעוץ משפטי או חשבונאי.",
  footerPrivacy: "הקבצים נמחקים מיד לאחר העיבוד. המידע אינו נשמר בשרת.",

  // Errors
  networkError: "אין חיבור לשרת. בדוק את החיבור לאינטרנט ונסה שוב.",
  validationError: "שגיאה בנתונים שנשלחו. בדוק את השדות ונסה שוב.",
  rateLimitError: "יותר מדי בקשות. המתן מעט ונסה שוב.",
  serverError: "שגיאת שרת. נסה שוב מאוחר יותר.",
} as const;

export type StringKey = keyof typeof S;
