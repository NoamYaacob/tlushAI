import { useState, useRef, type DragEvent, type ChangeEvent } from "react";
import { useWizard } from "@/context/WizardContext";
import { uploadPayslip } from "@/lib/api";
import { ErrorAlert } from "@/components/ErrorAlert";
import { Spinner } from "@/components/Spinner";
import type { AppError } from "@/types/payslip";

const ACCEPTED_TYPES = ["application/pdf", "image/jpeg", "image/png"];
const MAX_SIZE = 10 * 1024 * 1024; // 10 MB
const ACCEPT_ATTR = ".pdf,.jpg,.jpeg,.png";

export function UploadStep() {
  const { state, dispatch } = useWizard();
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function validateFile(file: File): AppError | null {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      return {
        type: "file",
        message: "סוג קובץ לא נתמך. יש להעלות PDF, JPG או PNG.",
      };
    }
    if (file.size > MAX_SIZE) {
      return {
        type: "file",
        message: "הקובץ גדול מדי. הגודל המרבי הוא 10 מגה-בייט.",
      };
    }
    return null;
  }

  async function handleFile(file: File) {
    const validationError = validateFile(file);
    if (validationError) {
      dispatch({ type: "SET_ERROR", payload: validationError });
      return;
    }

    dispatch({ type: "SET_LOADING", payload: true });
    try {
      const result = await uploadPayslip(file);
      dispatch({ type: "SET_PARSE_RESULT", payload: result });
    } catch (err) {
      dispatch({ type: "SET_ERROR", payload: err as AppError });
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) void handleFile(file);
  }

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) void handleFile(file);
    // Reset input so re-uploading the same file triggers change
    e.target.value = "";
  }

  if (state.isLoading) {
    return <Spinner message="מחלץ נתונים מהתלוש..." />;
  }

  return (
    <div className="mx-auto max-w-xl">
      <ErrorAlert
        error={state.error}
        onDismiss={() => dispatch({ type: "SET_ERROR", payload: null })}
      />

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-12 transition-colors ${
          isDragOver
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 bg-white hover:border-blue-400 hover:bg-gray-50"
        }`}
      >
        <div className="text-5xl text-gray-400">📄</div>
        <p className="text-lg font-medium text-gray-700">
          גרור תלוש שכר לכאן או לחץ לבחירת קובץ
        </p>
        <p className="text-sm text-gray-500">PDF, JPG, PNG — עד 10 מגה-בייט</p>

        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT_ATTR}
          onChange={onFileChange}
          className="hidden"
        />
      </div>

      <p className="mt-4 text-center text-xs text-gray-400">
        🔒 הקובץ נמחק מהשרת מיד לאחר העיבוד. המידע אינו נשמר.
      </p>
    </div>
  );
}
