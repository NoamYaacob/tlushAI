import { useState, type FormEvent } from "react";
import { useWizard } from "@/context/WizardContext";
import { analyzePayslip } from "@/lib/api";
import { ErrorAlert } from "@/components/ErrorAlert";
import { Spinner } from "@/components/Spinner";
import { S } from "@/lib/strings";
import type { AppError, SalaryType, UserConfirmedFields } from "@/types/payslip";

const HEBREW_MONTHS = [
  { value: 1, label: "ינואר" },
  { value: 2, label: "פברואר" },
  { value: 3, label: "מרץ" },
  { value: 4, label: "אפריל" },
  { value: 5, label: "מאי" },
  { value: 6, label: "יוני" },
  { value: 7, label: "יולי" },
  { value: 8, label: "אוגוסט" },
  { value: 9, label: "ספטמבר" },
  { value: 10, label: "אוקטובר" },
  { value: 11, label: "נובמבר" },
  { value: 12, label: "דצמבר" },
];

interface FieldErrors {
  period_month?: string;
  period_year?: string;
  salary_type?: string;
  base_salary_or_rate?: string;
}

export function ConfirmStep() {
  const { state, dispatch } = useWizard();
  const parseResult = state.parseResult!;
  const payslip = parseResult.payslip;
  const status = parseResult.required_fields_status;

  // Form state — pre-populated from extracted data
  const [month, setMonth] = useState(payslip.period.month ?? 0);
  const [year, setYear] = useState(payslip.period.year ?? new Date().getFullYear());
  const [salaryType, setSalaryType] = useState<SalaryType | "">(
    payslip.employment.salary_type ?? ""
  );
  const [baseRate, setBaseRate] = useState(payslip.employment.base_rate ?? 0);
  const [hoursWorked, setHoursWorked] = useState(payslip.employment.hours_regular ?? 0);
  const [jobPercent, setJobPercent] = useState(payslip.employment.job_percent ?? 100);
  const [pensionExpected, setPensionExpected] = useState(true);
  const [trainingFundExpected, setTrainingFundExpected] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [showPreview, setShowPreview] = useState(false);

  function validate(): FieldErrors {
    const errs: FieldErrors = {};
    if (month < 1 || month > 12) errs.period_month = "יש לבחור חודש";
    if (year < 2000 || year > 2100) errs.period_year = "שנה לא תקינה";
    if (!salaryType) errs.salary_type = "יש לבחור סוג שכר";
    if (!baseRate || baseRate <= 0) errs.base_salary_or_rate = "יש להזין שכר בסיס גדול מ-0";
    return errs;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    setErrors({});

    const confirmedFields: UserConfirmedFields = {
      period_month: month,
      period_year: year,
      salary_type: salaryType as SalaryType,
      base_salary_or_rate: baseRate,
      regular_hours_worked: hoursWorked || null,
      job_percent: jobPercent || null,
      pension_expected: pensionExpected,
      training_fund_expected: trainingFundExpected || null,
    };

    dispatch({ type: "SET_LOADING", payload: true });
    try {
      const result = await analyzePayslip({
        payslip: parseResult.payslip,
        confirmed_fields: confirmedFields,
      });
      dispatch({ type: "SET_ANALYZE_RESULT", payload: result });
    } catch (err) {
      dispatch({ type: "SET_ERROR", payload: err as AppError });
    }
  }

  if (state.isLoading) {
    return <Spinner message="מנתח את התלוש..." />;
  }

  const warnings = payslip.meta.parse_warnings;
  const needsConfirmation = payslip.meta.needs_user_confirmation_fields;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <ErrorAlert
        error={state.error}
        onDismiss={() => dispatch({ type: "SET_ERROR", payload: null })}
      />

      <h2 className="text-xl font-semibold text-gray-800">אימות נתונים שחולצו</h2>
      <p className="text-sm text-gray-600">
        בדוק את הנתונים שחולצו מהתלוש. שדות שלא זוהו אוטומטית מסומנים בצהוב.
        יש לאשר או לתקן לפני המשך.
      </p>

      {/* Parse warnings */}
      {warnings.length > 0 && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3">
          <p className="mb-1 text-sm font-medium text-amber-800">אזהרות חילוץ:</p>
          <ul className="list-inside list-disc text-sm text-amber-700">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {needsConfirmation.length > 0 && (
        <div className="rounded-lg border border-blue-300 bg-blue-50 p-3">
          <p className="text-sm text-blue-800">
            {S.confirmFieldsNeedVerification}{" "}
            {(payslip.meta.confirmation_hints ?? []).length > 0
              ? payslip.meta.confirmation_hints
                  .filter((h) => needsConfirmation.includes(h.field_key))
                  .map((h) => h.label_he)
                  .join(", ") || needsConfirmation.join(", ")
              : needsConfirmation.join(", ")}
          </p>
        </div>
      )}

      {/* Redacted preview toggle */}
      <div>
        <button
          type="button"
          onClick={() => setShowPreview(!showPreview)}
          className="text-sm text-blue-600 hover:text-blue-800 underline"
        >
          {showPreview ? "הסתר תצוגה מקדימה" : "הצג טקסט שחולץ (מצונזר)"}
        </button>
        {showPreview && (
          <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-gray-100 p-3 text-xs leading-relaxed text-gray-700" dir="rtl">
            {parseResult.redacted_preview}
          </pre>
        )}
      </div>

      {/* Confirmation form */}
      <form onSubmit={handleSubmit} className="space-y-5">
        <fieldset className="space-y-4 rounded-xl border border-gray-200 bg-white p-5">
          <legend className="px-2 text-sm font-semibold text-gray-700">
            שדות חובה
          </legend>

          {/* Period month */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              חודש <span className="text-red-500">*</span>
            </label>
            <select
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className={`w-full rounded-lg border p-2.5 text-sm ${
                !status.period_month
                  ? "border-amber-400 bg-amber-50"
                  : "border-gray-300"
              } ${errors.period_month ? "border-red-500" : ""}`}
            >
              <option value={0}>-- בחר חודש --</option>
              {HEBREW_MONTHS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
            {!status.period_month && (
              <p className="mt-1 text-xs text-amber-600">לא זוהה אוטומטית</p>
            )}
            {errors.period_month && (
              <p className="mt-1 text-xs text-red-600">{errors.period_month}</p>
            )}
          </div>

          {/* Period year */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              שנה <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              min={2000}
              max={2100}
              className={`w-full rounded-lg border p-2.5 text-sm ${
                !status.period_year
                  ? "border-amber-400 bg-amber-50"
                  : "border-gray-300"
              } ${errors.period_year ? "border-red-500" : ""}`}
            />
            {!status.period_year && (
              <p className="mt-1 text-xs text-amber-600">לא זוהה אוטומטית</p>
            )}
            {errors.period_year && (
              <p className="mt-1 text-xs text-red-600">{errors.period_year}</p>
            )}
          </div>

          {/* Salary type */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              סוג שכר <span className="text-red-500">*</span>
            </label>
            <div className="flex gap-6">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="salary_type"
                  value="monthly"
                  checked={salaryType === "monthly"}
                  onChange={() => setSalaryType("monthly")}
                />
                חודשי
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="salary_type"
                  value="hourly"
                  checked={salaryType === "hourly"}
                  onChange={() => setSalaryType("hourly")}
                />
                שעתי
              </label>
            </div>
            {!status.salary_type && (
              <p className="mt-1 text-xs text-amber-600">לא זוהה אוטומטית</p>
            )}
            {errors.salary_type && (
              <p className="mt-1 text-xs text-red-600">{errors.salary_type}</p>
            )}
          </div>

          {/* Base salary / rate */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {salaryType === "hourly" ? "שכר שעתי" : "שכר בסיס חודשי"} (₪){" "}
              <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              step="0.01"
              value={baseRate || ""}
              onChange={(e) => setBaseRate(Number(e.target.value))}
              className={`w-full rounded-lg border p-2.5 text-sm ${
                !status.base_salary_or_rate
                  ? "border-amber-400 bg-amber-50"
                  : "border-gray-300"
              } ${errors.base_salary_or_rate ? "border-red-500" : ""}`}
              placeholder="0.00"
            />
            {!status.base_salary_or_rate && (
              <p className="mt-1 text-xs text-amber-600">לא זוהה אוטומטית</p>
            )}
            {errors.base_salary_or_rate && (
              <p className="mt-1 text-xs text-red-600">{errors.base_salary_or_rate}</p>
            )}
          </div>
        </fieldset>

        <fieldset className="space-y-4 rounded-xl border border-gray-200 bg-white p-5">
          <legend className="px-2 text-sm font-semibold text-gray-700">
            שדות אופציונליים
          </legend>

          {/* Hours worked */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              שעות עבודה רגילות
            </label>
            <input
              type="number"
              step="0.5"
              value={hoursWorked || ""}
              onChange={(e) => setHoursWorked(Number(e.target.value))}
              className={`w-full rounded-lg border p-2.5 text-sm ${
                !status.regular_hours_worked
                  ? "border-amber-400 bg-amber-50"
                  : "border-gray-300"
              }`}
              placeholder="182"
            />
          </div>

          {/* Job percent */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              אחוז משרה
            </label>
            <input
              type="number"
              step="1"
              min={0}
              max={200}
              value={jobPercent || ""}
              onChange={(e) => setJobPercent(Number(e.target.value))}
              className={`w-full rounded-lg border p-2.5 text-sm ${
                !status.job_percent
                  ? "border-amber-400 bg-amber-50"
                  : "border-gray-300"
              }`}
              placeholder="100"
            />
          </div>

          {/* Pension expected */}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={pensionExpected}
              onChange={(e) => setPensionExpected(e.target.checked)}
              className="h-4 w-4 rounded"
            />
            צפוי הפרשה לפנסיה
          </label>

          {/* Training fund expected */}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={trainingFundExpected}
              onChange={(e) => setTrainingFundExpected(e.target.checked)}
              className="h-4 w-4 rounded"
            />
            צפוי הפרשה לקרן השתלמות
          </label>
        </fieldset>

        <div className="flex justify-start">
          <button
            type="submit"
            className="rounded-xl bg-blue-600 px-8 py-3 text-sm font-semibold text-white shadow-md transition-colors hover:bg-blue-700"
          >
            המשך לתוצאות
          </button>
        </div>
      </form>

      <p className="text-xs text-gray-400">
        שיטת חילוץ: {parseResult.extraction_method}
      </p>
    </div>
  );
}
