import { WizardProvider, useWizard } from "@/context/WizardContext";
import { Stepper } from "@/components/Stepper";
import { UploadStep } from "@/steps/UploadStep";
import { ConfirmStep } from "@/steps/ConfirmStep";
import { ResultsStep } from "@/steps/ResultsStep";

function WizardContent() {
  const { state } = useWizard();

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white shadow-sm">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4">
          <h1 className="text-2xl font-bold text-blue-700">TlushAI</h1>
          <span className="text-sm text-gray-500">הסבר תלוש שכר ישראלי</span>
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
          <p>
            TlushAI — כלי עזר להבנת תלוש השכר. אין להסתמך על התוצאות כייעוץ
            משפטי או חשבונאי.
          </p>
          <p className="mt-1">
            הקבצים נמחקים מיד לאחר העיבוד. המידע אינו נשמר בשרת.
          </p>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <WizardProvider>
      <WizardContent />
    </WizardProvider>
  );
}
