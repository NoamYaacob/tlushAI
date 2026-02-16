import { useWizard, type WizardStep } from "@/context/WizardContext";

const STEPS: { key: WizardStep; label: string }[] = [
  { key: "upload", label: "העלאת תלוש" },
  { key: "confirm", label: "אימות נתונים" },
  { key: "results", label: "תוצאות" },
];

const STEP_ORDER: WizardStep[] = ["upload", "confirm", "results"];

export function Stepper() {
  const { state, dispatch } = useWizard();
  const currentIdx = STEP_ORDER.indexOf(state.step);

  return (
    <nav className="flex items-center justify-center gap-4 py-6">
      {STEPS.map((s, idx) => {
        const isCompleted = idx < currentIdx;
        const isCurrent = idx === currentIdx;
        const canClick = idx < currentIdx;

        return (
          <div key={s.key} className="flex items-center gap-4">
            {idx > 0 && (
              <div
                className={`h-0.5 w-12 ${
                  idx <= currentIdx ? "bg-blue-500" : "bg-gray-300"
                }`}
              />
            )}
            <button
              type="button"
              disabled={!canClick}
              onClick={() => canClick && dispatch({ type: "GO_TO_STEP", payload: s.key })}
              className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                isCurrent
                  ? "bg-blue-600 text-white shadow-md"
                  : isCompleted
                    ? "bg-blue-100 text-blue-700 hover:bg-blue-200 cursor-pointer"
                    : "bg-gray-100 text-gray-400 cursor-default"
              }`}
            >
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                  isCurrent
                    ? "bg-white text-blue-600"
                    : isCompleted
                      ? "bg-blue-600 text-white"
                      : "bg-gray-300 text-gray-500"
                }`}
              >
                {isCompleted ? "✓" : idx + 1}
              </span>
              {s.label}
            </button>
          </div>
        );
      })}
    </nav>
  );
}
