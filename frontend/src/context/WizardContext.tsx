import {
  createContext,
  useContext,
  useReducer,
  type ReactNode,
  type Dispatch,
} from "react";
import type { ParseResponse, AnalyzeResponse, AppError } from "@/types/payslip";

// ── State ──

export type WizardStep = "upload" | "confirm" | "results";

export interface WizardState {
  step: WizardStep;
  parseResult: ParseResponse | null;
  analyzeResult: AnalyzeResponse | null;
  isLoading: boolean;
  error: AppError | null;
}

const initialState: WizardState = {
  step: "upload",
  parseResult: null,
  analyzeResult: null,
  isLoading: false,
  error: null,
};

// ── Actions ──

type Action =
  | { type: "SET_PARSE_RESULT"; payload: ParseResponse }
  | { type: "SET_ANALYZE_RESULT"; payload: AnalyzeResponse }
  | { type: "GO_TO_STEP"; payload: WizardStep }
  | { type: "SET_LOADING"; payload: boolean }
  | { type: "SET_ERROR"; payload: AppError | null }
  | { type: "RESET" };

function reducer(state: WizardState, action: Action): WizardState {
  switch (action.type) {
    case "SET_PARSE_RESULT":
      return {
        ...state,
        parseResult: action.payload,
        step: "confirm",
        isLoading: false,
        error: null,
      };
    case "SET_ANALYZE_RESULT":
      return {
        ...state,
        analyzeResult: action.payload,
        step: "results",
        isLoading: false,
        error: null,
      };
    case "GO_TO_STEP":
      if (action.payload === "upload") {
        return { ...initialState };
      }
      if (action.payload === "confirm") {
        return {
          ...state,
          step: "confirm",
          analyzeResult: null,
          error: null,
        };
      }
      return { ...state, step: action.payload, error: null };
    case "SET_LOADING":
      return { ...state, isLoading: action.payload, error: null };
    case "SET_ERROR":
      return { ...state, error: action.payload, isLoading: false };
    case "RESET":
      return { ...initialState };
    default:
      return state;
  }
}

// ── Context ──

interface WizardContextValue {
  state: WizardState;
  dispatch: Dispatch<Action>;
}

const WizardContext = createContext<WizardContextValue | null>(null);

export function WizardProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <WizardContext.Provider value={{ state, dispatch }}>
      {children}
    </WizardContext.Provider>
  );
}

export function useWizard() {
  const ctx = useContext(WizardContext);
  if (!ctx) {
    throw new Error("useWizard must be used within WizardProvider");
  }
  return ctx;
}
