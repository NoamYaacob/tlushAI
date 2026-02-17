// ── Enums ──

export type SalaryType = "monthly" | "hourly";
export type FlagSeverity = "info" | "warn" | "high";
export type LineCategory =
  | "earning"
  | "deduction"
  | "employer_contribution"
  | "tax"
  | "leave"
  | "other";

// ── Payslip sub-schemas ──

export interface Employer {
  name?: string | null;
  id?: string | null;
  address?: string | null;
}

export interface Employee {
  name?: string | null;
  id?: string | null;
  job_title?: string | null;
}

export interface Period {
  month?: number | null;
  year?: number | null;
}

export interface Employment {
  salary_type?: SalaryType | null;
  base_rate?: number | null;
  job_percent?: number | null;
  hours_regular?: number | null;
  hours_overtime_125?: number | null;
  hours_overtime_150?: number | null;
  weekend_hours?: number | null;
  holiday_hours?: number | null;
}

export interface EarningsLine {
  label: string;
  label_he?: string | null;
  qty?: number | null;
  rate?: number | null;
  amount: number;
}

export interface DeductionLine {
  label: string;
  label_he?: string | null;
  amount: number;
}

export interface EmployerContribLine {
  label: string;
  label_he?: string | null;
  amount: number;
}

export interface Pension {
  employee_tagmulim?: number | null;
  employer_tagmulim?: number | null;
  employer_pitzuyim?: number | null;
  training_fund_employee?: number | null;
  training_fund_employer?: number | null;
}

export interface LeaveBalances {
  vacation_open?: number | null;
  vacation_accrued?: number | null;
  vacation_used?: number | null;
  vacation_close?: number | null;
  sick_open?: number | null;
  sick_accrued?: number | null;
  sick_used?: number | null;
  sick_close?: number | null;
}

export interface Totals {
  gross?: number | null;
  taxable_gross?: number | null;
  net?: number | null;
  total_deductions?: number | null;
}

export interface ParseMeta {
  parse_warnings: string[];
  needs_user_confirmation_fields: string[];
}

// ── Top-level Payslip ──

export interface Payslip {
  employer: Employer;
  employee: Employee;
  period: Period;
  payment_date?: string | null;
  employment: Employment;
  earnings_lines: EarningsLine[];
  deductions_lines: DeductionLine[];
  employer_contrib_lines: EmployerContribLine[];
  pension: Pension;
  leave: LeaveBalances;
  totals: Totals;
  meta: ParseMeta;
}

// ── Analysis result types ──

export interface Flag {
  severity: FlagSeverity;
  title_he: string;
  explanation_he: string;
  evidence?: string | null;
  suggested_next_step?: string | null;
  confidence: number;
}

export interface OkItem {
  title_he: string;
  explanation_he: string;
  confidence: number;
}

export interface LineExplanation {
  label: string;
  amount: number;
  qty?: number | null;
  rate?: number | null;
  category: LineCategory;
  meaning_he: string;
  affects_gross?: boolean | null;
  affects_taxable?: boolean | null;
  status: string;
  note_he?: string | null;
}

export interface SummaryCard {
  key: string;
  label_he: string;
  value?: number | null;
  formatted_value?: string | null;
  status: string;
}

export interface AnalysisResult {
  flags: Flag[];
  ok_items: OkItem[];
  line_explanations: LineExplanation[];
  summary_cards: SummaryCard[];
  disclaimer_he: string;
}

// ── API contracts ──

export interface RequiredFieldStatus {
  period_month: boolean;
  period_year: boolean;
  salary_type: boolean;
  base_salary_or_rate: boolean;
  regular_hours_worked: boolean;
  job_percent: boolean;
  pension_expected: boolean;
}

export interface ParseResponse {
  payslip: Payslip;
  raw_text: string;
  redacted_preview: string;
  required_fields_status: RequiredFieldStatus;
  file_hash: string;
  extraction_method: string;
}

export interface UserConfirmedFields {
  period_month: number;
  period_year: number;
  salary_type: SalaryType;
  base_salary_or_rate: number;
  regular_hours_worked?: number | null;
  job_percent?: number | null;
  pension_expected: boolean;
  training_fund_expected?: boolean | null;
}

export interface AnalyzeRequest {
  payslip: Payslip;
  confirmed_fields: UserConfirmedFields;
}

export interface AnalyzeResponse {
  result: AnalysisResult;
}

// ── Error type ──

export interface AppError {
  type: "network" | "validation" | "rate_limit" | "server" | "file";
  message: string;
  details?: unknown;
}
