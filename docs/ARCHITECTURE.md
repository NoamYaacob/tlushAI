# TlushAI — Israel Payroll Slip Explainer

## Architecture Overview

```
┌──────────────┐        ┌──────────────────────────────────────────┐
│   Frontend   │        │            FastAPI Backend               │
│  (React/Next)│        │                                          │
│              │  POST  │  ┌────────────┐   ┌──────────────────┐   │
│  Upload ─────┼───────►│  │  /parse    │──►│ Upload Handler   │   │
│              │        │  └────────────┘   │  - MIME check    │   │
│  Confirm ────┼───┐    │                   │  - Size check    │   │
│              │   │    │                   │  - Hash compute  │   │
│  Results     │   │    │                   │  - PII redact    │   │
│              │   │    │                   └───────┬──────────┘   │
│              │   │    │                           │              │
│              │   │    │                   ┌───────▼──────────┐   │
│              │   │    │                   │ Text Extraction  │   │
│              │   │    │                   │  - pdfplumber    │   │
│              │   │    │                   │  - Tesseract OCR │   │
│              │   │    │                   └───────┬──────────┘   │
│              │   │    │                           │              │
│              │   │    │                   ┌───────▼──────────┐   │
│              │   │    │                   │ LLM Extraction   │   │
│              │   │    │                   │  (Abstraction)   │   │
│              │   │    │                   │  - Claude        │   │
│              │   │    │                   │  - GPT-4o        │   │
│              │   │    │                   │  - Mock (dev)    │   │
│              │   │    │                   └───────┬──────────┘   │
│              │   │    │                           │              │
│              │   │    │                   ┌───────▼──────────┐   │
│              │   │    │  Returns:         │ Payslip Schema   │   │
│◄─────────────┼───┼────│  parsed schema +  │ (Pydantic)       │   │
│              │   │    │  extracted text +  └──────────────────┘   │
│              │   │    │  redacted preview                        │
│              │   │    │                                          │
│              │   │    │  ┌────────────┐   ┌──────────────────┐   │
│              │   └────┼─►│  /analyze  │──►│  Rules Engine    │   │
│              │  POST  │  └────────────┘   │  - 10 IL checks  │   │
│              │        │                   │  - Configurable   │   │
│              │        │                   │    thresholds     │   │
│              │        │                   └───────┬──────────┘   │
│              │        │                           │              │
│              │        │                   ┌───────▼──────────┐   │
│◄─────────────┼────────│  Returns:         │ Explanation Gen  │   │
│              │        │  flags + OK items  │  - Hebrew text   │   │
│              │        │  + explanations +  │  - Line meanings │   │
│              │        │  summary cards     └──────────────────┘   │
└──────────────┘        └──────────────────────────────────────────┘
```

## Two-Step API Flow (CRITICAL)

1. **POST /parse** — User uploads a payslip file
   - Validates file (size, MIME type)
   - Computes file hash for dedup
   - Redacts PII from logs
   - Extracts text (pdfplumber or Tesseract OCR)
   - Sends raw text to LLM extraction service
   - Returns: parsed schema + raw text + redacted preview + required fields status
   - File is deleted from disk after extraction

2. **POST /analyze** — User confirms/edits extracted fields
   - Receives user-confirmed fields merged with parsed schema
   - Runs Rules Engine (10 Israel-specific checks)
   - Generates line-by-line explanations in Hebrew
   - Returns: flags + OK items + explanations + summary cards
   - No file needed — operates on structured data only

## Key Design Decisions

- **LLM Abstraction Layer**: Swappable providers (Claude, GPT-4o, mock).
  The extraction prompt handles RTL Hebrew text and Israeli numeric formats.
- **PII Redaction**: Applied BEFORE any logging or external API calls.
  Israeli ID (9 digits) and bank account patterns are masked.
- **Conservative Language**: All flags use "possible issue / requires verification".
  The system never claims legal certainty.
- **No Permanent Storage**: Files deleted after processing. Parsed data stored
  only if user opts in.
- **Configurable Thresholds**: All constants (minimum wage, tolerance values)
  live in `config/constants.py` with update reminders.

## Directory Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py         # /parse and /analyze endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   ├── payslip.py         # Pydantic Payslip schema
│   │   └── api_contracts.py   # Request/Response models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── upload_handler.py  # File validation, hash, cleanup
│   │   ├── text_extraction.py # pdfplumber + Tesseract OCR
│   │   ├── llm_extraction.py  # LLM abstraction layer
│   │   ├── rules_engine.py    # Israel-specific compliance checks
│   │   └── explanations.py    # Hebrew explanation generator
│   ├── security/
│   │   ├── __init__.py
│   │   ├── pii_masking.py     # Israeli ID + bank account redaction
│   │   ├── rate_limiter.py    # In-memory rate limiter
│   │   └── file_validator.py  # MIME type + size validation
│   └── config/
│       ├── __init__.py
│       ├── constants.py       # Thresholds, min wage, tolerances
│       └── settings.py        # App configuration
├── tests/
│   ├── __init__.py
│   ├── test_pii_masking.py
│   ├── test_number_parsing.py
│   ├── test_rules_engine.py
│   └── fixtures/              # Golden payslip JSON fixtures
│       └── ...
├── requirements.txt
└── pyproject.toml

frontend/                      # Phase 3
├── ...
```
