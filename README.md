# TlushAI — Israeli Payroll Slip Explainer

Upload an Israeli payslip (PDF or image), and TlushAI extracts the data, runs 10 compliance checks against Israeli labor law, and explains every line in Hebrew.

## Features

- **Upload PDF or image** — supports scanned payslips via Tesseract OCR (Hebrew + English)
- **RTL-aware extraction** — multi-strategy pdfplumber pipeline (table extraction, word-level RTL reconstruction, Hebrew reversal detection)
- **Structured extraction** — LLM-powered parsing with few-shot examples from 3 Israeli payroll sectors (high-tech, public sector, small business)
- **10 compliance checks** — minimum wage, pension contributions, overtime, travel allowance, and more
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
| `TESSERACT_LANG` | `heb+eng` | Tesseract OCR language packs |
| `DELETE_FILE_AFTER_PROCESSING` | `true` | Delete uploaded files after extraction |

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

## API Reference

### `POST /api/parse`

Upload a payslip file (PDF, JPG, or PNG) as multipart form data.

Returns: parsed payslip schema, extracted text, redacted preview, and field extraction status.

### `POST /api/analyze`

Submit confirmed/edited fields for compliance analysis.

**Request body:**
```json
{
  "payslip": { "..." },
  "confirmed_fields": {
    "period_month": 1,
    "period_year": 2025,
    "salary_type": "monthly",
    "base_salary_or_rate": 7500
  }
}
```

Returns: compliance flags, OK items, line-by-line explanations, and summary cards.

### `GET /api/health`

Returns `{"status": "ok"}` when the backend is running.

## Tech Stack

- **Backend:** FastAPI, Python 3.11, pdfplumber, Tesseract OCR, Pydantic v2
- **Frontend:** React 19, TypeScript, Vite 6, Tailwind CSS v4
- **Deployment:** Docker, nginx

## Project Structure

```
tlushAI/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── api/routes.py        # /parse, /analyze, /health endpoints
│   │   ├── models/              # Pydantic schemas
│   │   ├── services/            # Business logic
│   │   ├── security/            # PII masking, rate limiting, file validation
│   │   └── config/              # Settings, Israeli payroll constants
│   ├── tests/
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
