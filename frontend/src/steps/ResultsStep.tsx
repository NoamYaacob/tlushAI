import { useWizard } from "@/context/WizardContext";
import type { Flag, FlagSeverity, LineCategory } from "@/types/payslip";

const SEVERITY_ORDER: FlagSeverity[] = ["high", "warn", "info"];

const SEVERITY_STYLES: Record<FlagSeverity, { bg: string; border: string; icon: string; title: string }> = {
  high: { bg: "bg-red-50", border: "border-red-300", icon: "⚠️", title: "text-red-800" },
  warn: { bg: "bg-amber-50", border: "border-amber-300", icon: "⚡", title: "text-amber-800" },
  info: { bg: "bg-blue-50", border: "border-blue-300", icon: "ℹ️", title: "text-blue-800" },
};

const CATEGORY_LABELS: Record<LineCategory, string> = {
  earning: "הכנסה",
  deduction: "ניכוי",
  employer_contribution: "הפרשת מעסיק",
  tax: "מס",
  leave: "חופשה/מחלה",
  other: "אחר",
};

const STATUS_DOT: Record<string, string> = {
  ok: "bg-green-500",
  check: "bg-amber-500",
  warn: "bg-red-500",
  missing: "bg-gray-400",
};

function formatNIS(value: number | null | undefined): string {
  if (value == null) return "---";
  return new Intl.NumberFormat("he-IL", {
    style: "currency",
    currency: "ILS",
    maximumFractionDigits: 2,
  }).format(value);
}

function FlagCard({ flag }: { flag: Flag }) {
  const style = SEVERITY_STYLES[flag.severity];
  return (
    <div className={`rounded-lg border ${style.border} ${style.bg} p-4`}>
      <div className="flex items-start gap-2">
        <span className="text-lg">{style.icon}</span>
        <div className="flex-1">
          <h4 className={`font-semibold ${style.title}`}>{flag.title_he}</h4>
          <p className="mt-1 text-sm text-gray-700">{flag.explanation_he}</p>
          {flag.evidence && (
            <p className="mt-2 text-xs text-gray-500">
              נתונים: {flag.evidence}
            </p>
          )}
          {flag.suggested_next_step && (
            <p className="mt-1 text-xs font-medium text-gray-600">
              המלצה: {flag.suggested_next_step}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export function ResultsStep() {
  const { state, dispatch } = useWizard();
  const result = state.analyzeResult!.result;

  const groupedFlags = SEVERITY_ORDER.reduce<Record<FlagSeverity, Flag[]>>(
    (acc, sev) => {
      acc[sev] = result.flags.filter((f) => f.severity === sev);
      return acc;
    },
    { high: [], warn: [], info: [] }
  );

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      {/* Summary cards */}
      <section>
        <h2 className="mb-3 text-lg font-semibold text-gray-800">סיכום תלוש</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {result.summary_cards.map((card) => (
            <div
              key={card.key}
              className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
            >
              <div className="flex items-center gap-2">
                <span
                  className={`inline-block h-2.5 w-2.5 rounded-full ${
                    STATUS_DOT[card.status] ?? "bg-gray-400"
                  }`}
                />
                <span className="text-xs text-gray-500">{card.label_he}</span>
              </div>
              <p className="mt-1 text-lg font-bold text-gray-900">
                {card.formatted_value ?? formatNIS(card.value)}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Flags */}
      {result.flags.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-gray-800">
            ממצאים ({result.flags.length})
          </h2>
          <div className="space-y-3">
            {SEVERITY_ORDER.flatMap((sev) =>
              groupedFlags[sev].map((flag, i) => (
                <FlagCard key={`${sev}-${i}`} flag={flag} />
              ))
            )}
          </div>
        </section>
      )}

      {/* OK items */}
      {result.ok_items.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-gray-800">תקין</h2>
          <div className="space-y-2">
            {result.ok_items.map((item, i) => (
              <div
                key={i}
                className="flex items-start gap-2 rounded-lg border border-green-200 bg-green-50 p-3"
              >
                <span className="text-green-600">✓</span>
                <div>
                  <p className="text-sm font-medium text-green-800">
                    {item.title_he}
                  </p>
                  <p className="text-xs text-green-700">{item.explanation_he}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Line explanations */}
      {result.line_explanations.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-gray-800">
            פירוט שורות
          </h2>
          <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50 text-gray-600">
                  <th className="p-3 text-start font-medium">שורה</th>
                  <th className="p-3 text-start font-medium">סכום</th>
                  <th className="p-3 text-start font-medium">קטגוריה</th>
                  <th className="p-3 text-start font-medium">הסבר</th>
                  <th className="p-3 text-start font-medium">סטטוס</th>
                </tr>
              </thead>
              <tbody>
                {result.line_explanations.map((line, i) => (
                  <tr
                    key={i}
                    className={`border-b border-gray-100 ${
                      line.status === "warn"
                        ? "bg-red-50"
                        : line.status === "check"
                          ? "bg-amber-50"
                          : ""
                    }`}
                  >
                    <td className="p-3 font-medium text-gray-800">{line.label}</td>
                    <td className="p-3 text-gray-700">{formatNIS(line.amount)}</td>
                    <td className="p-3 text-gray-600">
                      {CATEGORY_LABELS[line.category] ?? line.category}
                    </td>
                    <td className="p-3 text-gray-600">{line.meaning_he}</td>
                    <td className="p-3">
                      <span
                        className={`inline-block h-2.5 w-2.5 rounded-full ${
                          STATUS_DOT[line.status] ?? "bg-gray-400"
                        }`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Disclaimer */}
      <section className="rounded-xl border border-gray-300 bg-gray-100 p-4">
        <p className="text-xs leading-relaxed text-gray-600">
          {result.disclaimer_he}
        </p>
      </section>

      {/* Reset button */}
      <div className="flex justify-center pb-8">
        <button
          type="button"
          onClick={() => dispatch({ type: "RESET" })}
          className="rounded-xl border border-gray-300 bg-white px-6 py-2.5 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:bg-gray-50"
        >
          התחל מחדש
        </button>
      </div>
    </div>
  );
}
