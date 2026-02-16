import type { AppError } from "@/types/payslip";

interface ErrorAlertProps {
  error: AppError | null;
  onDismiss: () => void;
}

export function ErrorAlert({ error, onDismiss }: ErrorAlertProps) {
  if (!error) return null;

  return (
    <div className="mb-4 flex items-start justify-between rounded-lg border border-red-300 bg-red-50 p-4">
      <p className="text-sm text-red-800">{error.message}</p>
      <button
        type="button"
        onClick={onDismiss}
        className="ms-4 text-red-500 hover:text-red-700"
        aria-label="סגור"
      >
        ✕
      </button>
    </div>
  );
}
