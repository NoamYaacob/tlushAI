# TlushAI — Israeli Payroll Slip Explainer

Upload an Israeli payslip (PDF or image), and TlushAI extracts the data, runs 13 compliance checks against Israeli labor law (2026 tax year), and explains every line in Hebrew.

## Features

- **Upload PDF or image** — PDFs use pdfplumber; images (JPG/PNG) bypass OCR entirely and are sent directly to LLM Vision for accurate Hebrew table extraction
- **RTL-aware extraction** — multi-strategy pdfplumber pipeline (table extraction, word-level RTL reconstruction, Hebrew reversal detection)
- **LLM Vision for images** — Claude/GPT-4o Vision reads Hebrew tabular payslip images directly, avoiding pytesseract hallucination on RTL content
- **Structured extraction** — LLM-powered parsing with few-shot examples from 3 Israeli payroll sectors (high-tech, public sector, small business)
- **13 compliance checks** — income tax brackets, National Insurance tiers, health tax, credit points, minimum wage, pension contributions, overtime, travel allowance, and more
- **Financial due diligence** — income tax calculated against 2026 brackets with credit point deductions; NI/health verified against tiered rates (reduced rate up to 60% avg. wage, full rate above)
- **Hebrew explanations** — line-by-line meanings and summary cards, all in Hebrew RTL
- **Privacy-first** — uploaded files are deleted immediately after processing; PII is redacted from logs (supports ת.ז., ת"ז, תעודת זהות prefixes)
- **Diagnostic logging** — timing instrumentation, Hebrew ratio detection, field extraction counts, missing field alerts

## Quick Start (Docker)

```bash
# Clone the repository
git clone https://github.com/NoamYaacob/tlushAI.git
cd tlushAI

# (Optional) Configure environment variables
cp backend/.env.example backend/.env
# Edit backend/.env to set LLM_PROVIDER, API keys, etc.

# Start both services
docker-compose up --build
```

Open **http://localhost:5173** in your browser.

The app works out of the box with `LLM_PROVIDER=mock` — no API keys required for testing.

## Environment Variables

Configure in `backend/.env` (see `backend/.env.example` for defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `mock` | LLM provider: `mock`, `claude`, or `openai` |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=claude` |
| `OPENAI_API_KEY` | — | Required when `LLM_PROVIDER=openai` |
| `MAX_FILE_SIZE_MB` | `10` | Maximum upload file size |
| `RATE_LIMIT_RPM` | `20` | Requests per minute per IP |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Allowed CORS origins |
| `TESSERACT_LANG` | `heb+eng` | Tesseract OCR language packs (used for scanned PDFs only) |
| `DELETE_FILE_AFTER_PROCESSING` | `true` | Delete uploaded files after extraction |

## Extraction Pipeline

```
Upload file
  │
  ├─ PDF ──► pdfplumber (tables + RTL text)
  │            │
  │            └─ < 50 chars? ──► OCR fallback (scanned PDFs)
  │
  └─ Image (JPG/PNG) ──► LLM Vision (bypasses OCR entirely)
                           │
                           └─ Claude/GPT-4o reads Hebrew tables directly
```

Images are sent as base64-encoded PNG to the configured LLM provider's Vision API. This avoids pytesseract's poor handling of RTL Hebrew tabular data.

## Compliance Checks (13 Rules)

| # | Rule | Severity | Description |
|---|------|----------|-------------|
| 1 | Required basics | warn | Employer name, employee name, period, gross, net |
| 2 | Net sanity | warn | Gross - deductions ≈ net |
| 3 | Pension lines | warn/info | Employee + employer tagmulim, pitzuyim, training fund |
| 4 | Travel allowance | info | Presence of travel/commute reimbursement |
| 5 | Overtime | warn/info | Hours vs. pay line consistency |
| 6 | Leave balances | warn | Vacation/sick: open + accrued - used = close |
| 7 | Unknown deductions | info | Unrecognized or duplicate deduction labels |
| 8 | Minimum wage | high | Hourly/monthly rate vs. legal minimum (2026) |
| 9 | Tax lines presence | warn | Income tax, NI, health tax lines exist |
| 10 | Large expenses | info | Expense reimbursements > 50% of base salary |
| 11 | Income tax brackets | info | Actual tax vs. 2026 brackets + credit points |
| 12 | National Insurance | info | Actual NI vs. tiered 2026 rates |
| 13 | Health tax | info | Actual health tax vs. tiered 2026 rates |

### 2026 Tax Constants

- **Income tax brackets**: 10% / 14% / 20% / 31% / 35% / 47% / 50%
- **Credit point value**: ₪242/month (default: 2.25 points for male resident)
- **NI employee**: 1.04% up to ₪7,703, 7.00% above (max ₪51,910)
- **Health tax**: 3.23% up to ₪7,703, 5.17% above
- **Minimum wage**: ₪5,880.02/month, ₪32.30/hour

Constants are in `backend/app/config/constants.py` and should be updated when rates change.

## Local Development (without Docker)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:5173** and proxies `/api` requests to the backend.

### Running Tests

```bash
cd backend
pytest
```

147 tests covering text extraction, rules engine (all 13 rules), LLM extraction, PII masking, and Vision bypass.

## API Reference

### `POST /api/parse`

Upload a payslip file (PDF, JPG, or PNG) as multipart form data.

Returns: parsed payslip schema, extracted text, redacted preview, and field extraction status.

The `extraction_method` field indicates the pipeline used:
- `pdf_text+llm` — pdfplumber text → LLM
- `vision+llm` — image → LLM Vision (no OCR)
- `ocr+llm` — scanned PDF → Tesseract → LLM

### `POST /api/analyze`

Submit confirmed/edited fields for compliance analysis.

**Request body:**
```json
{
  "payslip": { "..." },
  "confirmed_fields": {
    "period_month": 1,
    "period_year": 2026,
    "salary_type": "monthly",
    "base_salary_or_rate": 15000
  }
}
```

Returns: compliance flags, OK items, line-by-line explanations, and summary cards.

### `GET /api/health`

Returns `{"status": "ok"}` when the backend is running.

## Tech Stack

- **Backend:** FastAPI, Python 3.11, pdfplumber, Tesseract OCR, Pydantic v2
- **Frontend:** React 19, TypeScript, Vite 6, Tailwind CSS v4
- **LLM:** Claude (Anthropic) or GPT-4o (OpenAI) with Vision support
- **Deployment:** Docker, nginx

## Project Structure

```
tlushAI/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── api/routes.py        # /parse, /analyze, /health endpoints
│   │   ├── models/              # Pydantic schemas (payslip, API contracts)
│   │   ├── services/
│   │   │   ├── text_extraction.py    # PDF/image → text (Vision bypass for images)
│   │   │   ├── llm_extraction.py     # LLM-based structured extraction
│   │   │   ├── rules_engine.py       # 13 compliance checks + tax calculators
│   │   │   └── explanations.py       # Hebrew line explanations + summary cards
│   │   ├── security/            # PII masking, rate limiting, file validation
│   │   └── config/
│   │       ├── settings.py      # Environment config
│   │       └── constants.py     # 2026 Israeli tax brackets, NI, health, min wage
│   ├── tests/                   # 147 unit tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Main app (3-step wizard)
│   │   ├── steps/               # Upload, Confirm, Results
│   │   ├── components/          # Stepper, Spinner, ErrorAlert
│   │   ├── context/             # Wizard state management
│   │   ├── types/               # TypeScript interfaces
│   │   └── lib/api.ts           # API client
│   ├── Dockerfile
│   └── nginx.conf
├── docs/ARCHITECTURE.md
├── docker-compose.yml
└── README.md
```

## Disclaimer

TlushAI is an informational tool. It uses conservative language ("possible issue", "requires verification") and does not claim legal certainty. Always verify results against the original payslip and consult a payroll professional for definitive answers.
