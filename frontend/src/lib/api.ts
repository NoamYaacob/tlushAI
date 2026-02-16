import type {
  ParseResponse,
  AnalyzeRequest,
  AnalyzeResponse,
  AppError,
} from "@/types/payslip";

function makeAppError(
  type: AppError["type"],
  message: string,
  details?: unknown
): AppError {
  return { type, message, details };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) {
    return (await res.json()) as T;
  }

  let body: unknown;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  switch (res.status) {
    case 422:
      throw makeAppError(
        "validation",
        "שגיאה בנתונים שנשלחו. בדוק את השדות ונסה שוב.",
        body
      );
    case 429:
      throw makeAppError(
        "rate_limit",
        "יותר מדי בקשות. המתן מעט ונסה שוב.",
        body
      );
    default:
      throw makeAppError(
        "server",
        "שגיאת שרת. נסה שוב מאוחר יותר.",
        body
      );
  }
}

export async function uploadPayslip(file: File): Promise<ParseResponse> {
  const formData = new FormData();
  formData.append("file", file);

  let res: Response;
  try {
    res = await fetch("/api/parse", {
      method: "POST",
      body: formData,
      // Do NOT set Content-Type — browser sets multipart boundary automatically
    });
  } catch (err) {
    throw makeAppError(
      "network",
      "אין חיבור לשרת. בדוק את החיבור לאינטרנט ונסה שוב.",
      err
    );
  }

  return handleResponse<ParseResponse>(res);
}

export async function analyzePayslip(
  request: AnalyzeRequest
): Promise<AnalyzeResponse> {
  let res: Response;
  try {
    res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  } catch (err) {
    throw makeAppError(
      "network",
      "אין חיבור לשרת. בדוק את החיבור לאינטרנט ונסה שוב.",
      err
    );
  }

  return handleResponse<AnalyzeResponse>(res);
}
