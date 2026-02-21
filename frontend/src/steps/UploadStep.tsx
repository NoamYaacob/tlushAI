import { useState, useRef, useEffect, useCallback, type DragEvent, type ChangeEvent } from "react";
import { useWizard } from "@/context/WizardContext";
import { uploadPayslip } from "@/lib/api";
import { ErrorAlert } from "@/components/ErrorAlert";
import { Spinner } from "@/components/Spinner";
import { S } from "@/lib/strings";
import type { AppError } from "@/types/payslip";

const ACCEPTED_TYPES = ["application/pdf", "image/jpeg", "image/png"];
const MAX_SIZE = 10 * 1024 * 1024; // 10 MB
const ACCEPT_ATTR = ".pdf,.jpg,.jpeg,.png";
const UPLOAD_TIMEOUT_MS = 90_000; // 90 seconds

// Progress phases shown while upload+extraction runs
const PROGRESS_PHASES = [
  { delay: 0, message: S.uploadPhaseUploading },
  { delay: 3_000, message: S.uploadPhaseExtracting },
  { delay: 10_000, message: S.uploadPhaseParsing },
  { delay: 30_000, message: S.uploadPhaseAlmost },
];

export function UploadStep() {
  const { state, dispatch } = useWizard();
  const [isDragOver, setIsDragOver] = useState(false);
  const [progressMsg, setProgressMsg] = useState(PROGRESS_PHASES[0].message);
  const [timedOut, setTimedOut] = useState(false);
  const [lastFile, setLastFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Cycle through progress messages while loading
  useEffect(() => {
    if (!state.isLoading) return;
    setProgressMsg(PROGRESS_PHASES[0].message);
    setTimedOut(false);

    const timers: ReturnType<typeof setTimeout>[] = [];
    for (const phase of PROGRESS_PHASES) {
      if (phase.delay > 0) {
        timers.push(setTimeout(() => setProgressMsg(phase.message), phase.delay));
      }
    }
    // Timeout handler
    timers.push(
      setTimeout(() => {
        setTimedOut(true);
        abortRef.current?.abort();
      }, UPLOAD_TIMEOUT_MS)
    );

    return () => timers.forEach(clearTimeout);
  }, [state.isLoading]);

  function validateFile(file: File): AppError | null {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      return { type: "file", message: S.uploadFileTypeError };
    }
    if (file.size > MAX_SIZE) {
      return { type: "file", message: S.uploadFileSizeError };
    }
    return null;
  }

  const handleFile = useCallback(async (file: File) => {
    const validationError = validateFile(file);
    if (validationError) {
      dispatch({ type: "SET_ERROR", payload: validationError });
      return;
    }

    setLastFile(file);
    setTimedOut(false);
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    dispatch({ type: "SET_LOADING", payload: true });
    try {
      const result = await uploadPayslip(file);
      dispatch({ type: "SET_PARSE_RESULT", payload: result });
    } catch (err) {
      // If aborted due to timeout, don't show network error
      if (abortRef.current?.signal.aborted) return;
      dispatch({ type: "SET_ERROR", payload: err as AppError });
    }
  }, [dispatch]);

  function handleRetry() {
    if (lastFile) {
      void handleFile(lastFile);
    } else {
      dispatch({ type: "SET_LOADING", payload: false });
      dispatch({ type: "SET_ERROR", payload: null });
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
    e.target.value = "";
  }

  // Loading state with progress phases
  if (state.isLoading) {
    if (timedOut) {
      return (
        <div className="mx-auto max-w-xl text-center">
          <div className="rounded-2xl border border-amber-300 bg-amber-50 p-8">
            <p className="mb-4 text-sm text-amber-800">{S.uploadTimeout}</p>
            <button
              type="button"
              onClick={handleRetry}
              className="rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white shadow-md transition-colors hover:bg-blue-700"
            >
              {S.uploadRetry}
            </button>
          </div>
        </div>
      );
    }
    return <Spinner message={progressMsg} />;
  }

  return (
    <div className="mx-auto max-w-xl">
      <ErrorAlert
        error={state.error}
        onDismiss={() => dispatch({ type: "SET_ERROR", payload: null })}
      />

      {/* Retry button when there was an error and we have a file */}
      {state.error && lastFile && (
        <div className="mb-4 text-center">
          <button
            type="button"
            onClick={handleRetry}
            className="rounded-xl border border-blue-300 bg-blue-50 px-5 py-2 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100"
          >
            {S.uploadRetry}
          </button>
        </div>
      )}

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
        <div className="text-5xl text-gray-400">{"\uD83D\uDCC4"}</div>
        <p className="text-lg font-medium text-gray-700">{S.uploadDropzone}</p>
        <p className="text-sm text-gray-500">{S.uploadFormats}</p>

        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT_ATTR}
          onChange={onFileChange}
          className="hidden"
        />
      </div>

      <p className="mt-4 text-center text-xs text-gray-400">
        {"\uD83D\uDD12"} {S.uploadPrivacyNote}
      </p>
    </div>
  );
}
