import { useState } from "react";
import { useWizard } from "@/context/WizardContext";
import { useDebug } from "@/App";
import { S } from "@/lib/strings";
import type { Flag, FlagSeverity, LineExplanation, LineSection } from "@/types/payslip";

const SEVERITY_ORDER: FlagSeverity[] = ["high", "warn", "info"];

const SEVERITY_STYLES: Record<FlagSeverity, {
  bg: string; border: string; icon: string; title: string;
  badge: string; badgeText: string; label: string;
}> = {
  high: {
    bg: "bg-red-50", border: "border-red-300", icon: "\u26A0\uFE0F", title: "text-red-800",
    badge: "bg-red-100 border-red-300", badgeText: "text-red-700", label: S.resultsSeverityHigh,
  },
  warn: {
    bg: "bg-amber-50", border: "border-amber-300", icon: "\u26A1", title: "text-amber-800",
    badge: "bg-amber-100 border-amber-300", badgeText: "text-amber-700", label: S.resultsSeverityWarn,
  },
  info: {
    bg: "bg-blue-50", border: "border-blue-300", icon: "\u2139\uFE0F", title: "text-blue-800",
    badge: "bg-blue-100 border-blue-300", badgeText: "text-blue-700", label: S.resultsSeverityInfo,
  },
};

const SECTION_LABELS: Record<string, string> = {
  earnings: S.resultsEarningsSection,
  deductions: S.resultsDeductionsSection,
  employer_contributions: S.resultsEmployerSection,
  tax: S.resultsTaxSection,
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

function FlagCard({ flag, showDebug }: { flag: Flag; showDebug: boolean }) {
  const style = SEVERITY_STYLES[flag.severity];
  return (
    <div className={`rounded-xl border ${style.border} ${style.bg} p-4`}>
      <div className="flex items-start gap-3">
        <span className="mt-0.5 text-lg leading-none">{style.icon}</span>
        <div className="flex-1 min-w-0">
          {/* Header row: title + severity badge */}
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className={`font-semibold ${style.title}`}>{flag.title_he}</h4>
            <span className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-medium ${style.badge} ${style.badgeText}`}>
              {style.label}
            </span>
          </div>

          {/* Explanation — always visible, user-facing Hebrew */}
          <p className="mt-1.5 text-sm leading-relaxed text-gray-700">{flag.explanation_he}</p>

          {/* Next step — always visible, this is user advice */}
          {flag.suggested_next_step && (
            <p className="mt-2 text-xs font-medium text-gray-600">
              {S.resultsWhatToDo} {flag.suggested_next_step}
            </p>
          )}

          {/* Evidence — debug only (contains English calculation strings) */}
          {showDebug && flag.evidence && (
            <p className="mt-2 rounded bg-gray-100 p-2 text-xs font-mono text-gray-500 break-all" dir="ltr">
              {flag.evidence}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function SectionedLines({
  lines,
  section,
  hasQtyRate,
}: {
  lines: LineExplanation[];
  section: string;
  hasQtyRate: boolean;
}) {
  if (lines.length === 0) return null;

  return (
    <div className="mb-4">
      <h3 className="mb-2 text-sm font-semibold text-gray-600">
        {SECTION_LABELS[section] ?? section}
      </h3>
      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
        <table className="w-full text-sm" dir="rtl">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 text-gray-600">
              <th className="p-3 text-start font-medium">{S.tableLineLabel}</th>
              {hasQtyRate && (
                <>
                  <th className="p-3 text-start font-medium">{S.tableQty}</th>
                  <th className="p-3 text-start font-medium">{S.tableRate}</th>
                </>
              )}
              <th className="p-3 text-start font-medium">{S.tableAmount}</th>
              <th className="p-3 text-start font-medium">{S.tableExplanation}</th>
              <th className="p-3 text-center font-medium">{S.tableStatus}</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line, i) => (
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
                {hasQtyRate && (
                  <>
                    <td className="p-3 text-gray-700">
                      {line.qty != null ? line.qty.toLocaleString("he-IL") : "\u2014"}
                    </td>
                    <td className="p-3 text-gray-700">
                      {line.rate != null ? formatNIS(line.rate) : "\u2014"}
                    </td>
                  </>
                )}
                <td className="p-3 text-gray-700">{formatNIS(line.amount)}</td>
                <td className="p-3 text-gray-600">{line.meaning_he}</td>
                <td className="p-3 text-center">
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
    </div>
  );
}

export function ResultsStep() {
  const { state, dispatch } = useWizard();
  const { debugMode } = useDebug();
  const result = state.analyzeResult!.result;
  const [copied, setCopied] = useState(false);

  const groupedFlags = SEVERITY_ORDER.reduce<Record<FlagSeverity, Flag[]>>(
    (acc, sev) => {
      acc[sev] = result.flags.filter((f) => f.severity === sev);
      return acc;
    },
    { high: [], warn: [], info: [] }
  );

  // Group line explanations by section
  const sectionOrder: LineSection[] = ["earnings", "deductions", "tax", "employer_contributions"];
  const linesBySection: Record<string, LineExplanation[]> = {};
  for (const line of result.line_explanations) {
    const sec = line.section ?? "earnings";
    if (!linesBySection[sec]) linesBySection[sec] = [];
    linesBySection[sec].push(line);
  }

  const hasQtyRate = result.line_explanations.some(
    (l) => l.qty != null || l.rate != null
  );

  function handleExportJson() {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "payslip-analysis.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleCopyText() {
    const sevLabel: Record<string, string> = {
      high: S.resultsSeverityHigh,
      warn: S.resultsSeverityWarn,
      info: S.resultsSeverityInfo,
    };
    const textLines: string[] = [];
    textLines.push("=== " + S.resultsSummaryTitle + " ===");
    for (const card of result.summary_cards) {
      textLines.push(`${card.label_he}: ${card.formatted_value ?? "---"}`);
    }
    textLines.push("");
    if (result.flags.length > 0) {
      textLines.push("=== " + S.resultsFlagsTitle + ` (${result.flags.length}) ===`);
      for (const flag of result.flags) {
        textLines.push(`[${sevLabel[flag.severity] ?? flag.severity}] ${flag.title_he}`);
        textLines.push(`  ${flag.explanation_he}`);
        if (flag.suggested_next_step) {
          textLines.push(`  ${S.resultsWhatToDo} ${flag.suggested_next_step}`);
        }
      }
      textLines.push("");
    }
    if (result.ok_items.length > 0) {
      textLines.push("=== " + S.resultsOkTitle + " ===");
      for (const item of result.ok_items) {
        textLines.push(`\u2713 ${item.title_he}: ${item.explanation_he}`);
      }
    }
    navigator.clipboard.writeText(textLines.join("\n")).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8" dir="rtl">
      {/* Summary cards */}
      <section>
        <h2 className="mb-3 text-lg font-semibold text-gray-800">{S.resultsSummaryTitle}</h2>
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
            {S.resultsFlagsTitle} ({result.flags.length})
          </h2>
          <div className="space-y-3">
            {SEVERITY_ORDER.flatMap((sev) =>
              groupedFlags[sev].map((flag, i) => (
                <FlagCard key={`${sev}-${i}`} flag={flag} showDebug={debugMode} />
              ))
            )}
          </div>
        </section>
      )}

      {/* OK items */}
      {result.ok_items.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-gray-800">{S.resultsOkTitle}</h2>
          <div className="space-y-2">
            {result.ok_items.map((item, i) => (
              <div
                key={i}
                className="flex items-start gap-2 rounded-lg border border-green-200 bg-green-50 p-3"
              >
                <span className="text-green-600">{"\u2713"}</span>
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

      {/* Line explanations — sectioned */}
      {result.line_explanations.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-gray-800">
            {S.resultsLinesTitle}
          </h2>
          {sectionOrder.map((sec) => (
            <SectionedLines
              key={sec}
              lines={linesBySection[sec] ?? []}
              section={sec}
              hasQtyRate={sec === "earnings" && hasQtyRate}
            />
          ))}
        </section>
      )}

      {/* Disclaimer */}
      <section className="rounded-xl border border-gray-300 bg-gray-100 p-4">
        <p className="text-xs leading-relaxed text-gray-600">
          {result.disclaimer_he}
        </p>
      </section>

      {/* Action buttons */}
      <div className="flex flex-wrap justify-center gap-3 pb-8">
        <button
          type="button"
          onClick={() => dispatch({ type: "GO_TO_STEP", payload: "confirm" })}
          className="rounded-xl border border-gray-300 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:bg-gray-50"
        >
          {S.resultsBackToConfirm}
        </button>
        <button
          type="button"
          onClick={handleExportJson}
          className="rounded-xl border border-blue-300 bg-blue-50 px-5 py-2.5 text-sm font-medium text-blue-700 shadow-sm transition-colors hover:bg-blue-100"
        >
          {S.resultsExportJson}
        </button>
        <button
          type="button"
          onClick={handleCopyText}
          className="rounded-xl border border-blue-300 bg-blue-50 px-5 py-2.5 text-sm font-medium text-blue-700 shadow-sm transition-colors hover:bg-blue-100"
        >
          {copied ? S.resultsCopied : S.resultsCopyText}
        </button>
        <button
          type="button"
          onClick={() => dispatch({ type: "RESET" })}
          className="rounded-xl border border-gray-300 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:bg-gray-50"
        >
          {S.resultsResetButton}
        </button>
      </div>
    </div>
  );
}
