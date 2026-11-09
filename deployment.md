# ClearEntry AI - Deployment and Local Run Guide

Repository: https://github.com/muralivijai64/ClearEntry-AI

## 1. Overview

ClearEntry AI is a local demonstration of an AI-assisted customs documentation workflow. It supports shipment creation, invoice/packing-list/Bill of Lading uploads, AI-assisted extraction, cross-document checks, human corrections, manager approval and Excel export.

This guide describes a **local development/demo setup**, not a production deployment.

## 2. Prerequisites

- Windows 10/11 (commands below use PowerShell)
- Python 3.13 recommended
- Node.js and npm
- Git
- A Groq API key for AI extraction

## 3. Clone the repository

```powershell
git clone https://github.com/muralivijai64/ClearEntry-AI.git
cd ClearEntry-AI
```

## 4. Backend setup

Open PowerShell:

```powershell
cd .\backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

If PowerShell blocks virtual-environment activation, either run the following for the current terminal only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Or invoke the environment's Python directly using `\.venv\Scripts\python.exe`.

### Environment variables

Set the following values in `backend/.env`:

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes for AI extraction | Your own Groq API key. Never commit it. |
| `GROQ_MODEL` | No | Model name; default example is `openai/gpt-oss-120b`. |
| `SECRET_KEY` | Yes | Long, random secret used to sign JWTs. Replace the placeholder. |
| `DATABASE_URL` | No | SQLAlchemy database URL. Default is `sqlite:///./clearentry.db`. |

Example only (replace the placeholder values):

```dotenv
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
SECRET_KEY=replace_with_a_long_random_secret
DATABASE_URL=sqlite:///./clearentry.db
```

Do not put real credentials in source code, screenshots, documentation or Git commits.

### Seed demo users and shipments

From the `backend` directory, run:

```powershell
python seed.py
```

This creates demo accounts and sample shipments if they do not already exist.

### Start the backend

```powershell
python -m uvicorn app.main:app --reload
```

Backend:
- API: http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

Keep this terminal open while using the frontend.

## 5. Frontend setup

Open a **second** PowerShell terminal at the repository root:

```powershell
cd .\frontend
npm ci
npm run dev
```

Vite normally serves the app at http://localhost:5173. If that port is already in use, Vite may select another port such as 5174. The backend CORS configuration includes localhost and 127.0.0.1 for ports 5173 and 5174.

For Windows environments where `npm` is blocked by PowerShell execution policy, use:

```powershell
npm.cmd ci
npm.cmd run dev
```

The current frontend API client points to `http://127.0.0.1:8000`. This is intended for local demonstration on the same computer. It must be changed to an environment-configured API URL before hosting the frontend remotely.

## 6. Demo login credentials

| Role | Email | Password |
|---|---|---|
| Executive | `executive@clearentry.ai` | `Executive@123` |
| Manager | `manager@clearentry.ai` | `Manager@123` |

These are public demo credentials. Change or disable them before any real deployment. The executive role can upload/review and correct records subject to API permissions. Manager-only actions include approval and export.

## 7. Demonstration workflow

1. Sign in with the executive or manager account.
2. Create or select a shipment.
3. Upload the invoice, packing list and Bill of Lading.
4. Review AI-extracted values, evidence and confidence indicators.
5. Correct inaccurate fields and provide a reason where requested.
6. Run or inspect cross-document validation.
7. Resolve all mismatches and required review items.
8. Sign in as a manager, approve the shipment, then generate the Excel export.
9. Inspect export history and the generated workbook.

The demo workbook contains five sheets: Shipment Summary, Line Items, Validation Checks, Source Documents and Export Information.

The repository includes synthetic sample PDFs in `corrected_sources/`. They are test data only and are not legally valid commercial or customs documents.

## 8. File handling and data

- Uploaded files are stored under the backend upload storage directory.
- Generated workbooks are stored under the backend export storage directory.
- The default SQLite database is local to the backend runtime.
- Local database, upload, export and environment files are excluded from Git by `.gitignore`.

Back up any local demo data you need before deleting local storage. Do not use real personal, commercial or customs-sensitive documents in an unsecured demo environment.

## 9. Known limitations

- The current extraction path reads embedded PDF text. Scanned PDFs need OCR, which is not included.
- AI extraction can be wrong or incomplete. Human review is required.
- The workbook is a demonstration export layout, not a certified filing-software template.
- The application does not submit filings to customs portals and does not determine official HSN classifications or duties.
- SQLite and local file storage are for development/demo use.
- The frontend currently uses a hardcoded local API URL. Remote deployment requires configuration changes, HTTPS and a reachable backend URL.
- The 95% field-accuracy objective is a target only; it has not been measured against 200 labelled shipments.

## 10. Production deployment checklist

Before production use, at minimum:
- Replace demo credentials and rotate all secrets.
- Use HTTPS and a managed secret store.
- Configure `VITE_API_URL` or an equivalent build-time API endpoint.
- Use a managed database and durable private object storage.
- Add OCR if scanned documents are in scope.
- Add access-control review, audit retention, backups and monitoring.
- Run security testing and a labelled extraction/validation evaluation.
- Validate the Excel layout against the customer's actual filing software.
- Obtain legal, customs and operational review before relying on any output.

