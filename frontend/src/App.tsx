import { createContext, useContext, useState, type ReactNode } from "react";
import { WizardProvider, useWizard } from "@/context/WizardContext";
import { Stepper } from "@/components/Stepper";
import { UploadStep } from "@/steps/UploadStep";
import { ConfirmStep } from "@/steps/ConfirmStep";
import { ResultsStep } from "@/steps/ResultsStep";
import { S } from "@/lib/strings";

// ── Debug mode context ──

interface DebugContextValue {
  debugMode: boolean;
  toggleDebug: () => void;
}

const DebugContext = createContext<DebugContextValue>({
  debugMode: false,
  toggleDebug: () => {},
});

export function useDebug() {
  return useContext(DebugContext);
}

function DebugProvider({ children }: { children: ReactNode }) {
  const [debugMode, setDebugMode] = useState(false);
  return (
    <DebugContext.Provider
      value={{ debugMode, toggleDebug: () => setDebugMode((v) => !v) }}
    >
      {children}
    </DebugContext.Provider>
  );
}

// ── Main content ──

function WizardContent() {
  const { state } = useWizard();
  const { debugMode, toggleDebug } = useDebug();

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white shadow-sm">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4">
          <h1 className="text-2xl font-bold text-blue-700">{S.appTitle}</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">{S.appSubtitle}</span>
            <button
              type="button"
              onClick={toggleDebug}
              className={`rounded-md px-2 py-1 text-xs transition-colors ${
                debugMode
                  ? "bg-amber-100 text-amber-700 border border-amber-300"
                  : "bg-gray-100 text-gray-400 border border-gray-200 hover:bg-gray-200"
              }`}
              title={debugMode ? S.debugToggleHide : S.debugToggleShow}
            >
              {debugMode ? S.debugToggleHide : S.debugToggleShow}
            </button>
          </div>
        </div>
      </header>

      {/* Stepper */}
      <div className="mx-auto max-w-4xl px-4">
        <Stepper />
      </div>

      {/* Step content */}
      <main className="mx-auto max-w-4xl px-4 py-6">
        {state.step === "upload" && <UploadStep />}
        {state.step === "confirm" && <ConfirmStep />}
        {state.step === "results" && <ResultsStep />}
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-gray-200 bg-white py-4">
        <div className="mx-auto max-w-4xl px-4 text-center text-xs text-gray-400">
          <p>{S.footerDisclaimer}</p>
          <p className="mt-1">{S.footerPrivacy}</p>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <DebugProvider>
      <WizardProvider>
        <WizardContent />
      </WizardProvider>
    </DebugProvider>
  );
}
