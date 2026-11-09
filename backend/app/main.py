import re
from decimal import Decimal, InvalidOperation
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Query,
    Body,
)
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from app.ai_extraction import extract_document_data
from app.cross_validation import validate_shipment_documents

from app.database import Base, engine, get_db
from app.models import (
    User,
    Shipment,
    Document,
    FieldCorrection,
    ExportHistory,
)
from app.schemas import (
    LoginRequest,
    ShipmentResponse,
    CorrectionRequest,
)
from app.security import (
    verify_password,
    create_access_token,
    decode_access_token,
)


# ==================================================
# REQUEST MODELS
# ==================================================

class ShipmentCreate(BaseModel):
    shipment_number: str = Field(min_length=3, max_length=50)
    importer: str = Field(min_length=2, max_length=150)
    supplier: str | None = Field(default=None, max_length=150)
    origin_country: str | None = Field(default=None, max_length=100)


# ==================================================
# DIRECTORIES
# ==================================================

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

EXPORT_DIR = Path(__file__).resolve().parents[1] / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


# ==================================================
# DATABASE INITIALIZATION
# ==================================================

Base.metadata.create_all(bind=engine)


# ==================================================
# FASTAPI APPLICATION
# ==================================================

app = FastAPI(
    title="ClearEntry AI API",
    description="AI-powered customs document extraction and cross-check system",
    version="1.0.0",
)


# ==================================================
# CORS CONFIGURATION
# ==================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# FILE CONFIGURATION
# ==================================================

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
}

MAX_FILE_SIZE = 15 * 1024 * 1024

ALLOWED_DOCUMENT_TYPES = {
    "invoice",
    "packing_list",
    "bill_of_lading",
}

EXCEL_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)


# ==================================================
# AUTHENTICATION
# ==================================================

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token",
        )

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
        )

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
        )

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    return user


# ==================================================
# BASIC ROUTES
# ==================================================

@app.get("/")
def root():
    return {
        "message": "Welcome to ClearEntry AI API",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "ClearEntry AI",
    }


# ==================================================
# LOGIN
# ==================================================

@app.post("/api/auth/login")
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if not user or not verify_password(
        request.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(
        user_id=user.id,
        role=user.role,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        },
    }


@app.get("/api/auth/me")
def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
    }


# ==================================================
# SHIPMENTS
# ==================================================

@app.post(
    "/api/shipments",
    response_model=ShipmentResponse,
    status_code=201,
)
def create_shipment(
    request: ShipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shipment_number = request.shipment_number.strip().upper()
    importer = request.importer.strip()

    supplier = (
        request.supplier.strip()
        if request.supplier and request.supplier.strip()
        else None
    )

    origin_country = (
        request.origin_country.strip()
        if request.origin_country and request.origin_country.strip()
        else None
    )

    if not shipment_number:
        raise HTTPException(
            status_code=422,
            detail="Shipment number cannot be empty.",
        )

    if not importer:
        raise HTTPException(
            status_code=422,
            detail="Importer cannot be empty.",
        )

    existing_shipment = (
        db.query(Shipment)
        .filter(Shipment.shipment_number == shipment_number)
        .first()
    )

    if existing_shipment:
        raise HTTPException(
            status_code=409,
            detail="Shipment number already exists.",
        )

    shipment = Shipment(
        shipment_number=shipment_number,
        importer=importer,
        supplier=supplier,
        origin_country=origin_country,
        status="Awaiting Documents",
    )

    try:
        db.add(shipment)
        db.commit()
        db.refresh(shipment)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Shipment number already exists.",
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Could not create shipment.",
        )

    return shipment


@app.get(
    "/api/shipments",
    response_model=list[ShipmentResponse],
)
def get_shipments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Shipment)
        .order_by(Shipment.created_at.desc())
        .all()
    )


@app.get("/api/shipments/{shipment_id}")
def get_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shipment = (
        db.query(Shipment)
        .filter(Shipment.id == shipment_id)
        .first()
    )

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found",
        )

    return {
        "id": shipment.id,
        "shipment_number": shipment.shipment_number,
        "importer": shipment.importer,
        "supplier": shipment.supplier,
        "origin_country": shipment.origin_country,
        "status": shipment.status,
        "created_at": shipment.created_at,
    }


# ==================================================
# DOCUMENT FILE VALIDATION
# ==================================================

def validate_file_signature(
    file_bytes: bytes,
    extension: str,
):
    if extension == ".pdf":
        return file_bytes.startswith(b"%PDF-")

    if extension in {".jpg", ".jpeg"}:
        return file_bytes.startswith(b"\xff\xd8\xff")

    if extension == ".png":
        return file_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    return False


# ==================================================
# UPLOAD DOCUMENT
# ==================================================

@app.post("/api/shipments/{shipment_id}/documents")
async def upload_document(
    shipment_id: int,
    document_type: str = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shipment = (
        db.query(Shipment)
        .filter(Shipment.id == shipment_id)
        .first()
    )

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found",
        )

    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid document type. Use invoice, "
                "packing_list, or bill_of_lading."
            ),
        )

    original_filename = Path(
        file.filename or "uploaded_file"
    ).name

    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, JPG, JPEG, and PNG files are allowed",
        )

    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty",
        )

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File size must not exceed 15 MB",
        )

    if not validate_file_signature(file_bytes, extension):
        raise HTTPException(
            status_code=400,
            detail="File content does not match its extension",
        )

    stored_filename = f"{uuid.uuid4().hex}{extension}"
    file_path = UPLOAD_DIR / stored_filename

    try:
        file_path.write_bytes(file_bytes)

        document = Document(
            shipment_id=shipment_id,
            document_type=document_type,
            original_filename=original_filename,
            stored_filename=stored_filename,
            uploaded_at=datetime.now(timezone.utc),
        )

        db.add(document)

        shipment.status = "Under Review"

        db.commit()
        db.refresh(document)

        return {
            "message": "Document uploaded successfully",
            "document": {
                "id": document.id,
                "shipment_id": document.shipment_id,
                "document_type": document.document_type,
                "filename": document.original_filename,
                "uploaded_at": document.uploaded_at,
            },
        }

    except Exception:
        db.rollback()

        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=500,
            detail="Document upload failed",
        )

    finally:
        await file.close()


# ==================================================
# LIST SHIPMENT DOCUMENTS
# ==================================================

@app.get("/api/shipments/{shipment_id}/documents")
def get_shipment_documents(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shipment = (
        db.query(Shipment)
        .filter(Shipment.id == shipment_id)
        .first()
    )

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found",
        )

    documents = (
        db.query(Document)
        .filter(Document.shipment_id == shipment_id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )

    return [
        {
            "id": document.id,
            "shipment_id": document.shipment_id,
            "document_type": document.document_type,
            "filename": document.original_filename,
            "uploaded_at": document.uploaded_at,
        }
        for document in documents
    ]


# ==================================================
# DOWNLOAD ORIGINAL DOCUMENT
# ==================================================

@app.get("/api/documents/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    file_path = UPLOAD_DIR / document.stored_filename

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Document file is missing from storage",
        )

    media_type = (
        "application/pdf"
        if file_path.suffix.lower() == ".pdf"
        else "application/octet-stream"
    )

    return FileResponse(
        path=file_path,
        filename=document.original_filename,
        media_type=media_type,
    )


# ==================================================
# AI DOCUMENT EXTRACTION
# ==================================================

@app.post("/api/documents/{document_id}/extract")
def extract_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    file_path = UPLOAD_DIR / document.stored_filename

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Document file is missing from storage",
        )

    if file_path.suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="AI text extraction currently supports PDF files only",
        )

    try:
        extracted_data = extract_document_data(
            file_path=str(file_path),
            document_type=document.document_type,
        )

        document.extracted_data = json.dumps(
            extracted_data,
            ensure_ascii=False,
        )

        shipment = (
            db.query(Shipment)
            .filter(Shipment.id == document.shipment_id)
            .first()
        )

        if shipment:
            shipment.status = "Under Review"

        db.commit()
        db.refresh(document)

        return {
            "message": (
                "AI extraction completed. "
                "Human review is required."
            ),
            "document_id": document.id,
            "shipment_id": document.shipment_id,
            "filename": document.original_filename,
            "extraction": extracted_data,
        }

    except ValueError as error:
        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(error),
        )

    except RuntimeError as error:
        db.rollback()

        raise HTTPException(
            status_code=502,
            detail=str(error),
        )

    except Exception as error:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Document extraction failed: {str(error)}",
        )


# ==================================================
# GET SAVED EXTRACTION
# ==================================================

@app.get("/api/documents/{document_id}/extraction")
def get_document_extraction(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    if not document.extracted_data:
        raise HTTPException(
            status_code=404,
            detail="No AI extraction is available for this document yet",
        )

    return {
        "document_id": document.id,
        "shipment_id": document.shipment_id,
        "filename": document.original_filename,
        "extraction": json.loads(document.extracted_data),
    }


# ==================================================
# HUMAN REVIEW AND FIELD CORRECTION
# ==================================================

REVIEWABLE_FIELDS = {
    "document_number",
    "document_date",
    "supplier",
    "importer",
    "currency",
    "incoterm",
    "origin_country",
    "destination_port",
    "invoice_total",
    "package_count",
    "package_type",
    "gross_weight_kg",
    "net_weight_kg",
    "measurement_cbm",
    "bill_of_lading_number",
    "vessel_name",
    "port_of_loading",
    "port_of_discharge",
}


@app.patch("/api/documents/{document_id}/review")
def correct_document_field(
    document_id: int,
    request: CorrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role.lower() not in {"executive", "manager"}:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to correct document fields.",
        )

    if request.field_name not in REVIEWABLE_FIELDS:
        raise HTTPException(
            status_code=400,
            detail="This field is not available for correction.",
        )

    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    if not document.extracted_data:
        raise HTTPException(
            status_code=409,
            detail="Extract the document before correcting its fields.",
        )

    shipment = (
        db.query(Shipment)
        .filter(Shipment.id == document.shipment_id)
        .first()
    )

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Associated shipment not found.",
        )

    try:
        extracted_data = json.loads(document.extracted_data)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(
            status_code=500,
            detail="Saved extraction data could not be read.",
        )

    old_value = extracted_data.get(request.field_name)

    extracted_data[request.field_name] = request.new_value

    verified_fields = extracted_data.get(
        "human_verified_fields",
        [],
    )

    if not isinstance(verified_fields, list):
        verified_fields = []

    if request.field_name not in verified_fields:
        verified_fields.append(request.field_name)

    extracted_data["human_verified_fields"] = verified_fields
    extracted_data["review_required"] = True

    correction = FieldCorrection(
        shipment_id=shipment.id,
        field_name=request.field_name,
        old_value=json.dumps(
            old_value,
            ensure_ascii=False,
        ),
        new_value=json.dumps(
            request.new_value,
            ensure_ascii=False,
        ),
        corrected_by=current_user.email,
        reason=request.reason,
        corrected_at=datetime.now(timezone.utc),
    )

    try:
        document.extracted_data = json.dumps(
            extracted_data,
            ensure_ascii=False,
        )

        shipment.status = "Under Review"

        db.add(correction)
        db.commit()
        db.refresh(correction)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Could not save the correction.",
        )

    return {
        "message": "Field correction saved successfully.",
        "correction": {
            "id": correction.id,
            "shipment_id": correction.shipment_id,
            "document_id": document.id,
            "field_name": correction.field_name,
            "old_value": old_value,
            "new_value": request.new_value,
            "corrected_by": correction.corrected_by,
            "reason": correction.reason,
            "corrected_at": correction.corrected_at,
        },
        "shipment_status": shipment.status,
    }


# ==================================================
# CORRECTION HISTORY HELPERS
# ==================================================

def display_correction_value(value):
    if value is None:
        return None

    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


# ==================================================
# GET CORRECTION HISTORY
# ==================================================

@app.get("/api/shipments/{shipment_id}/corrections")
def get_correction_history(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shipment = (
        db.query(Shipment)
        .filter(Shipment.id == shipment_id)
        .first()
    )

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found.",
        )

    corrections = (
        db.query(FieldCorrection)
        .filter(FieldCorrection.shipment_id == shipment_id)
        .order_by(FieldCorrection.corrected_at.desc())
        .all()
    )

    return [
        {
            "id": item.id,
            "field_name": item.field_name,
            "old_value": display_correction_value(item.old_value),
            "new_value": display_correction_value(item.new_value),
            "corrected_by": item.corrected_by,
            "reason": item.reason,
            "corrected_at": item.corrected_at,
        }
        for item in corrections
    ]


# ==================================================
# LOAD EXTRACTED DOCUMENTS
# ==================================================

def get_extracted_documents(
    shipment_id: int,
    db: Session,
):
    db_documents = (
        db.query(Document)
        .filter(Document.shipment_id == shipment_id)
        .order_by(Document.id.desc())
        .all()
    )

    extracted_documents = []

    for document in db_documents:
        if not document.extracted_data:
            continue

        try:
            extraction = json.loads(document.extracted_data)
        except (json.JSONDecodeError, TypeError):
            continue

        extracted_documents.append({
            "document_id": document.id,
            "document_type": document.document_type,
            "extraction": extraction,
        })

    return extracted_documents


# ==================================================
# MANAGER APPROVAL
# ==================================================

@app.post("/api/shipments/{shipment_id}/approve")
def approve_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role.lower() != "manager":
        raise HTTPException(
            status_code=403,
            detail="Only managers can approve shipments.",
        )

    shipment = (
        db.query(Shipment)
        .filter(Shipment.id == shipment_id)
        .first()
    )

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found.",
        )

    extracted_documents = get_extracted_documents(
        shipment_id,
        db,
    )

    validation = jsonable_encoder(
        validate_shipment_documents(extracted_documents)
    )

    if validation.get("overall_status") != "CLEAR":
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Shipment cannot be approved. Resolve all "
                    "document mismatches and pending checks first."
                ),
                "validation": validation,
            },
        )

    applicable_fields = {
        "invoice": {
            "document_number",
            "document_date",
            "supplier",
            "importer",
            "currency",
            "incoterm",
            "origin_country",
            "invoice_total",
            "line_items",
            "package_count",
            "package_type",
            "gross_weight_kg",
            "net_weight_kg",
            "measurement_cbm",
        },
        "packing_list": {
            "document_number",
            "document_date",
            "supplier",
            "importer",
            "origin_country",
            "line_items",
            "package_count",
            "package_type",
            "gross_weight_kg",
            "net_weight_kg",
            "measurement_cbm",
        },
        "bill_of_lading": {
            "document_number",
            "document_date",
            "supplier",
            "importer",
            "origin_country",
            "destination_port",
            "line_items",
            "package_count",
            "package_type",
            "gross_weight_kg",
            "measurement_cbm",
            "container_numbers",
            "vessel_name",
            "port_of_loading",
            "port_of_discharge",
        },
    }

    unverified_low_confidence_fields = []

    latest_by_type = {}

    for document in extracted_documents:
        document_type = document["document_type"]

        if document_type not in latest_by_type:
            latest_by_type[document_type] = document

    for document in latest_by_type.values():
        extraction = document["extraction"]
        document_type = document["document_type"]

        relevant_fields = applicable_fields.get(
            document_type,
            set(),
        )

        confidence = extraction.get("field_confidence", {})
        verified = extraction.get("human_verified_fields", [])

        if not isinstance(confidence, dict):
            confidence = {}

        if not isinstance(verified, list):
            verified = []

        for field_name, score in confidence.items():
            if field_name not in relevant_fields:
                continue

            field_value = extraction.get(field_name)

            if field_value is None or field_value == "":
                continue

            if field_value == [] or field_value == {}:
                continue

            try:
                confidence_score = float(score)
            except (ValueError, TypeError):
                confidence_score = 0.0

            if (
                confidence_score < 0.85
                and field_name not in verified
            ):
                unverified_low_confidence_fields.append({
                    "document_id": document["document_id"],
                    "document_type": document_type,
                    "field": field_name,
                    "confidence": confidence_score,
                })

    if unverified_low_confidence_fields:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Applicable low-confidence fields require "
                    "human verification before manager approval."
                ),
                "unverified_fields": unverified_low_confidence_fields,
            },
        )

    previous_status = shipment.status

    approval_record = FieldCorrection(
        shipment_id=shipment.id,
        field_name="manager_approval",
        old_value=json.dumps(previous_status),
        new_value=json.dumps("Approved for Export"),
        corrected_by=current_user.email,
        reason=(
            "Manager approved shipment after successful "
            "document validation and human verification."
        ),
        corrected_at=datetime.now(timezone.utc),
    )

    try:
        shipment.status = "Approved for Export"

        db.add(approval_record)
        db.commit()
        db.refresh(approval_record)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Could not save manager approval.",
        )

    return {
        "message": "Shipment approved successfully.",
        "shipment_id": shipment.id,
        "shipment_number": shipment.shipment_number,
        "approved_by": current_user.email,
        "status": shipment.status,
    }


# ==================================================
# CROSS-DOCUMENT VALIDATION
# ==================================================

@app.post("/api/shipments/{shipment_id}/validate")
def validate_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shipment = (
        db.query(Shipment)
        .filter(Shipment.id == shipment_id)
        .first()
    )

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found.",
        )

    extracted_documents = get_extracted_documents(
        shipment_id,
        db,
    )

    result = jsonable_encoder(
        validate_shipment_documents(extracted_documents)
    )

    if (
        shipment.status == "Approved for Export"
        and result.get("overall_status") != "CLEAR"
    ):
        shipment.status = "Under Review"
        db.commit()

    approved = (
        shipment.status == "Approved for Export"
        and result.get("overall_status") == "CLEAR"
    )

    result["export_allowed"] = approved

    if approved:
        result["message"] = (
            "Document checks passed and manager approval is recorded. "
            "Shipment is eligible for export."
        )
    else:
        result["message"] = (
            "Export is blocked until all checks pass and a manager "
            "approves the shipment."
        )

    return {
        "shipment_id": shipment.id,
        "shipment_number": shipment.shipment_number,
        "shipment_status": shipment.status,
        "validation": result,
    }


# ==================================================
# EXCEL EXPORT HELPERS
# ==================================================

def safe_excel_value(value):
    """
    Convert values to Excel-compatible values and prevent
    untrusted text from being interpreted as a formula.
    """

    if value is None:
        return ""

    if isinstance(value, (int, float, bool)):
        return value

    if isinstance(value, (dict, list)):
        value = json.dumps(
            value,
            ensure_ascii=False,
        )

    value = str(value).strip()

    if value.startswith(("=", "+", "-", "@")):
        return "'" + value

    return value


def parse_decimal_value(value):
    """
    Extract a numeric value from strings such as:
    '2400', 'USD 6.80', '2,400', or '1.25E+3'.
    """

    if value is None or isinstance(value, bool):
        return None

    text_value = str(value).strip()

    if not text_value:
        return None

    cleaned_value = text_value.replace(",", "")

    try:
        return Decimal(cleaned_value)
    except (InvalidOperation, ValueError):
        pass

    match = re.search(
        r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?",
        cleaned_value,
    )

    if not match:
        return None

    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def get_line_item_total(item):
    """
    Prefer the extracted line total.
    If missing, calculate quantity multiplied by unit price.
    """

    extracted_total = item.get("total")

    if extracted_total in (None, ""):
        extracted_total = item.get("total_value")

    if extracted_total in (None, ""):
        extracted_total = item.get("amount")

    if extracted_total not in (None, ""):
        parsed_total = parse_decimal_value(extracted_total)

        if parsed_total is not None:
            return float(parsed_total)

        return safe_excel_value(extracted_total)

    quantity = parse_decimal_value(
        item.get("quantity")
    )

    unit_price = parse_decimal_value(
        item.get("unit_price")
    )

    if quantity is None or unit_price is None:
        return ""

    calculated_total = quantity * unit_price

    return float(calculated_total)


def latest_extracted_documents_for_export(documents):
    """
    The input is ordered by descending document ID.
    Keep the first extracted version of each document type.
    """

    selected = {}

    for document in documents:
        document_type = document.get("document_type")

        if document_type not in selected:
            selected[document_type] = document

    return selected


def get_latest_manager_approval(shipment_id, db):
    """
    Confirm the latest approval action belongs to a manager.
    """

    latest_record = (
        db.query(FieldCorrection)
        .filter(
            FieldCorrection.shipment_id == shipment_id,
            FieldCorrection.field_name == "manager_approval",
        )
        .order_by(FieldCorrection.id.desc())
        .first()
    )

    if not latest_record:
        return None

    approval_value = display_correction_value(
        latest_record.new_value
    )

    if approval_value != "Approved for Export":
        return None

    manager = (
        db.query(User)
        .filter(User.email == latest_record.corrected_by)
        .first()
    )

    if not manager or manager.role.lower() != "manager":
        return None

    return latest_record


def get_export_data(shipment_id, db):
    """
    Check shipment status, approval, required documents,
    and current validation before allowing Excel export.
    """

    shipment = (
        db.query(Shipment)
        .filter(Shipment.id == shipment_id)
        .first()
    )

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found.",
        )

    if shipment.status != "Approved for Export":
        raise HTTPException(
            status_code=409,
            detail=(
                "Export is blocked. A manager must approve "
                "the shipment after all checks pass."
            ),
        )

    manager_approval = get_latest_manager_approval(
        shipment_id,
        db,
    )

    if not manager_approval:
        raise HTTPException(
            status_code=409,
            detail=(
                "No valid manager approval record was found. "
                "Please obtain manager approval again."
            ),
        )

    extracted_documents = get_extracted_documents(
        shipment_id,
        db,
    )

    validation = jsonable_encoder(
        validate_shipment_documents(extracted_documents)
    )

    if validation.get("overall_status") != "CLEAR":
        shipment.status = "Under Review"
        db.commit()

        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Export blocked because the latest document "
                    "validation is not CLEAR."
                ),
                "validation": validation,
            },
        )

    selected_documents = latest_extracted_documents_for_export(
        extracted_documents
    )

    required_types = {
        "invoice",
        "packing_list",
        "bill_of_lading",
    }

    missing_types = required_types - set(selected_documents.keys())

    if missing_types:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "All three required document types are needed "
                    "before export."
                ),
                "missing_documents": sorted(missing_types),
            },
        )

    source_documents = (
        db.query(Document)
        .filter(Document.shipment_id == shipment_id)
        .order_by(Document.id.desc())
        .all()
    )

    return (
        shipment,
        selected_documents,
        validation,
        source_documents,
        manager_approval,
    )


# ==================================================
# EXCEL WORKSHEET FORMATTING
# ==================================================

def style_worksheet(worksheet):
    header_fill = PatternFill(
        fill_type="solid",
        fgColor="17365D",
    )

    header_font = Font(
        bold=True,
        color="FFFFFF",
        size=11,
    )

    for cell in worksheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )

    worksheet.freeze_panes = "A2"

    if worksheet.max_row > 1:
        worksheet.auto_filter.ref = worksheet.dimensions

    for column_cells in worksheet.columns:
        max_length = 0

        column_letter = get_column_letter(
            column_cells[0].column
        )

        for cell in column_cells:
            try:
                cell_length = len(str(cell.value or ""))
                max_length = max(max_length, cell_length)
            except Exception:
                continue

        worksheet.column_dimensions[column_letter].width = min(
            max(max_length + 3, 14),
            45,
        )

    worksheet.row_dimensions[1].height = 30


# ==================================================
# CREATE EXCEL WORKBOOK
# ==================================================

def create_filing_workbook(
    shipment,
    selected_documents,
    validation,
    source_documents,
    manager_approval,
):
    workbook = Workbook()

    # SHEET 1: SHIPMENT SUMMARY

    summary = workbook.active
    summary.title = "Shipment Summary"

    summary.append(["Field", "Value"])

    summary_data = {
        "Shipment ID": shipment.id,
        "Shipment Number": shipment.shipment_number,
        "Importer": shipment.importer,
        "Supplier": shipment.supplier,
        "Origin Country": shipment.origin_country,
        "Shipment Status": shipment.status,
        "Validation Status": validation.get("overall_status"),
        "Manager Approved By": manager_approval.corrected_by,
        "Manager Approval Date": manager_approval.corrected_at,
        "Export Generated At": datetime.now(timezone.utc).isoformat(),
    }

    for key, value in summary_data.items():
        summary.append([
            safe_excel_value(key),
            safe_excel_value(value),
        ])

    style_worksheet(summary)

    # SHEET 2: LINE ITEMS

    line_items_sheet = workbook.create_sheet("Line Items")

    line_items_sheet.append([
        "Document Type",
        "Item Description",
        "HSN Code",
        "Quantity",
        "Unit",
        "Unit Price",
        "Total Value",
        "Currency",
    ])

    invoice_extraction = selected_documents.get(
        "invoice", {}
    ).get("extraction", {})

    packing_extraction = selected_documents.get(
        "packing_list", {}
    ).get("extraction", {})

    line_items = (
        invoice_extraction.get("line_items")
        or invoice_extraction.get("items")
        or packing_extraction.get("line_items")
        or packing_extraction.get("items")
        or []
    )

    if isinstance(line_items, dict):
        line_items = [line_items]

    if isinstance(line_items, list):
        for item in line_items:
            if not isinstance(item, dict):
                continue

            line_total = get_line_item_total(item)

            line_items_sheet.append([
                "Invoice",
                safe_excel_value(
                    item.get("description")
                    or item.get("item_description")
                    or item.get("product_description")
                ),
                safe_excel_value(
                    item.get("hsn_code")
                    or item.get("hsn")
                ),
                safe_excel_value(item.get("quantity")),
                safe_excel_value(
                    item.get("unit")
                    or item.get("unit_of_measure")
                ),
                safe_excel_value(item.get("unit_price")),
                line_total,
                safe_excel_value(
                    item.get("currency")
                    or invoice_extraction.get("currency")
                ),
            ])

            total_cell = line_items_sheet.cell(
                row=line_items_sheet.max_row,
                column=7,
            )

            if isinstance(line_total, (int, float)):
                total_cell.number_format = '#,##0.00'

    if line_items_sheet.max_row == 1:
        line_items_sheet.append([
            "No line items found",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ])

    style_worksheet(line_items_sheet)

    # SHEET 3: VALIDATION CHECKS

    validation_sheet = workbook.create_sheet(
        "Validation Checks"
    )

    validation_sheet.append([
        "Check",
        "Status",
        "Details",
    ])

    checks = validation.get("checks", [])

    if isinstance(checks, dict):
        checks = [
            {"check": key, "result": value}
            for key, value in checks.items()
        ]

    if isinstance(checks, list):
        for check in checks:
            if isinstance(check, dict):
                check_name = (
                    check.get("name")
                    or check.get("field")
                    or check.get("check")
                    or "Validation check"
                )

                check_status = (
                    check.get("status")
                    or check.get("result")
                    or ""
                )

                details = (
                    check.get("details")
                    or check.get("message")
                    or check.get("values")
                    or ""
                )

                validation_sheet.append([
                    safe_excel_value(check_name),
                    safe_excel_value(check_status),
                    safe_excel_value(details),
                ])

            else:
                validation_sheet.append([
                    "Validation check",
                    "",
                    safe_excel_value(check),
                ])

    if validation_sheet.max_row == 1:
        validation_sheet.append([
            "Overall validation",
            validation.get("overall_status", ""),
            validation.get("summary", ""),
        ])

    style_worksheet(validation_sheet)

    # SHEET 4: SOURCE DOCUMENTS

    documents_sheet = workbook.create_sheet(
        "Source Documents"
    )

    documents_sheet.append([
        "Document ID",
        "Document Type",
        "Original Filename",
        "Uploaded At",
        "Selected For Export",
    ])

    selected_ids = {
        document.get("document_id")
        for document in selected_documents.values()
    }

    for document in source_documents:
        documents_sheet.append([
            safe_excel_value(document.id),
            safe_excel_value(document.document_type),
            safe_excel_value(document.original_filename),
            safe_excel_value(document.uploaded_at),
            "Yes" if document.id in selected_ids else "No",
        ])

    style_worksheet(documents_sheet)

    # SHEET 5: EXPORT INFORMATION

    export_info = workbook.create_sheet(
        "Export Information"
    )

    export_info.append(["Field", "Value"])

    export_details = {
        "Application": "ClearEntry AI",
        "Export Type": "Demo Customs Filing Workbook",
        "Shipment Number": shipment.shipment_number,
        "Export Status": "Generated",
        "Approval Status": "Manager Approved",
        "Approved By": manager_approval.corrected_by,
        "Validation Status": validation.get("overall_status"),
        "Generated At": datetime.now(timezone.utc).isoformat(),
        "Purpose": (
            "Structured data export for demonstration and review."
        ),
        "Important Notice": (
            "This is a demonstration workbook, not an official "
            "customs authority or filing-software template. "
            "Review all values before operational use."
        ),
    }

    for key, value in export_details.items():
        export_info.append([
            safe_excel_value(key),
            safe_excel_value(value),
        ])

    style_worksheet(export_info)

    return workbook


# ==================================================
# GENERATE EXCEL EXPORT
# ==================================================

@app.post("/api/shipments/{shipment_id}/export")
def export_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role.lower() != "manager":
        raise HTTPException(
            status_code=403,
            detail="Only managers can generate shipment exports.",
        )

    (
        shipment,
        selected_documents,
        validation,
        source_documents,
        manager_approval,
    ) = get_export_data(shipment_id, db)

    filename = (
        f"ClearEntry_{shipment.shipment_number}_"
        f"{uuid.uuid4().hex[:8]}.xlsx"
    )

    file_path = EXPORT_DIR / filename

    try:
        workbook = create_filing_workbook(
            shipment=shipment,
            selected_documents=selected_documents,
            validation=validation,
            source_documents=source_documents,
            manager_approval=manager_approval,
        )

        workbook.save(file_path)

        export_record = ExportHistory(
            shipment_id=shipment.id,
            filename=filename,
            exported_by=current_user.email,
            export_status="SUCCESS",
            exported_at=datetime.now(timezone.utc),
        )

        db.add(export_record)
        db.commit()
        db.refresh(export_record)

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=EXCEL_MIME_TYPE,
        )

    except Exception:
        db.rollback()

        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=500,
            detail="Excel export generation failed.",
        )


# ==================================================
# LIST SHIPMENT EXPORT HISTORY
# ==================================================

@app.get("/api/shipments/{shipment_id}/exports")
def get_shipment_exports(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shipment = (
        db.query(Shipment)
        .filter(Shipment.id == shipment_id)
        .first()
    )

    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found.",
        )

    exports = (
        db.query(ExportHistory)
        .filter(ExportHistory.shipment_id == shipment_id)
        .order_by(ExportHistory.exported_at.desc())
        .all()
    )

    return [
        {
            "id": item.id,
            "shipment_id": item.shipment_id,
            "filename": item.filename,
            "exported_by": item.exported_by,
            "export_status": item.export_status,
            "exported_at": item.exported_at,
        }
        for item in exports
    ]


# ==================================================
# DOWNLOAD PREVIOUS EXPORT
# ==================================================

@app.get("/api/exports/{export_id}/download")
def download_shipment_export(
    export_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    export_record = (
        db.query(ExportHistory)
        .filter(ExportHistory.id == export_id)
        .first()
    )

    if not export_record:
        raise HTTPException(
            status_code=404,
            detail="Export record not found.",
        )

    if export_record.export_status != "SUCCESS":
        raise HTTPException(
            status_code=409,
            detail="This export was not generated successfully.",
        )

    safe_filename = Path(export_record.filename).name
    file_path = EXPORT_DIR / safe_filename

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Export file is missing from storage.",
        )

    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type=EXCEL_MIME_TYPE,
    )