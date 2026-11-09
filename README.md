# ClearEntry AI

**AI-Powered Customs Document Extraction, Cross-Validation and Human Review System**

[GitHub Repository](https://github.com/muralivijai64/ClearEntry-AI)

## Overview

ClearEntry AI is a demonstration application designed to simplify customs documentation workflows for import shipments.

It uses AI-assisted document extraction to process commercial invoices, packing lists and Bills of Lading (BOLs), compares extracted information across documents, and helps documentation teams identify inconsistencies before manager approval.

The system combines automated extraction with human verification to improve the reliability and efficiency of shipment documentation.

## Key Features

- **Shipment Management:** Create and manage import shipment records.
- **Document Upload:** Upload invoices, packing lists and Bills of Lading.
- **AI-Powered Extraction:** Extract structured shipment information from supported documents using an LLM.
- **Confidence and Evidence:** Display extracted values with supporting evidence and confidence information.
- **Cross-Document Validation:** Identify matching values, discrepancies and pending checks.
- **Human Review:** Allow users to verify and correct extracted information.
- **Audit Trail:** Record field corrections, including previous values and updated values.
- **Role-Based Access:** Separate executive and manager permissions.
- **Manager Approval:** Block approval when required validation or review steps remain incomplete.
- **Excel Export:** Generate a structured multi-sheet workbook after approval.
- **Export History:** Track generated exports.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React, Vite, JavaScript |
| Backend | Python, FastAPI |
| Database | SQLite, SQLAlchemy |
| AI Integration | Groq API, OpenAI Python SDK |
| Document Processing | PyMuPDF |
| Authentication | JWT, bcrypt |
| Excel Generation | openpyxl |
| API Testing | FastAPI Swagger UI |

## Application Workflow

1. User logs into the application.
2. User creates or selects an import shipment.
3. Invoice, packing list and Bill of Lading are uploaded.
4. AI extracts relevant information from the documents.
5. Extracted fields are presented for human verification.
6. The system compares supported fields across documents.
7. Users correct inaccurate information where necessary.
8. A manager approves the shipment after all required checks are cleared.
9. The system generates an Excel workbook and records the export history.

## Project Structure

```text
ClearEntry-AI/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── ai_extraction.py
│   │   ├── cross_validation.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── security.py
│   ├── requirements.txt
│   ├── seed.py
│   └── .env.example
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
├── corrected_sources/
├── ClearEntry_AI_Technical_Design_Document.docx
├── deployment.md
├── .gitignore
└── README.md
```

## Local Setup

### Prerequisites

- Python 3.13
- Node.js and npm
- Git
- Groq API key

### Backend

```powershell
cd backend

py -3.13 -m venv .venv

.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

Copy-Item .env.example .env
```

Configure the required environment variables in `backend/.env`.

```powershell
python seed.py

python -m uvicorn app.main:app --reload
```

Backend API: http://127.0.0.1:8000

Swagger documentation: http://127.0.0.1:8000/docs

### Frontend

Open another terminal:

```powershell
cd frontend

npm ci

npm run dev
```

Frontend: http://localhost:5173

For detailed setup instructions, see [deployment.md](deployment.md).

## Demo Accounts

| Role | Email | Password |
|---|---|---|
| Executive | executive@clearentry.ai | Executive@123 |
| Manager | manager@clearentry.ai | Manager@123 |

These are demonstration credentials only. Change them before any real deployment.

## Technical Documentation

- [Technical Design Document](ClearEntry_AI_Technical_Design_Document.pdf)
- [Deployment Guide](deployment.md)

## Validation and Testing

The demonstration includes:

- Successful shipment validation and manager approval.
- Successful Excel export after approval.
- Detection of a gross-weight mismatch across documents.
- Blocking manager approval when validation fails.
- Blocking Excel export when validation fails.
- Backend authorization checks for executive and manager roles.

## Limitations

- Scanned PDFs requiring OCR are not currently supported.
- AI-extracted values require human verification.
- The application does not submit documents to customs portals.
- It does not perform official HSN classification or duty calculations.
- The Excel workbook is a demonstration layout, not a certified filing-software template.
- The current database and file storage configuration is intended for local demonstration.

## Future Improvements

- OCR support for scanned documents.
- Larger labelled datasets for extraction accuracy evaluation.
- Customer-specific validation rules and Excel templates.
- Production database and cloud document storage.
- Monitoring, automated testing and enterprise integrations.

## Disclaimer

ClearEntry AI is an academic/technical demonstration project. Synthetic sample documents are provided for testing and are not legally valid commercial or customs documents. AI-generated information must be reviewed by an authorized person before operational use.
