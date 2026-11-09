
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


# -------------------------
# USER MODEL
# -------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# -------------------------
# SHIPMENT MODEL
# -------------------------

class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    shipment_number = Column(String(50), unique=True, index=True)
    importer = Column(String(150), nullable=False)
    supplier = Column(String(150))
    origin_country = Column(String(100))
    status = Column(String(50), default="Awaiting Documents")

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    documents = relationship(
        "Document",
        back_populates="shipment",
        cascade="all, delete-orphan"
    )


# -------------------------
# DOCUMENT MODEL
# -------------------------

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.id"),
        nullable=False
    )

    document_type = Column(String(50), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    extracted_data = Column(Text, nullable=True)

    uploaded_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    shipment = relationship(
        "Shipment",
        back_populates="documents"
    )


# -------------------------
# FIELD CORRECTION MODEL
# -------------------------

class FieldCorrection(Base):
    __tablename__ = "field_corrections"

    id = Column(Integer, primary_key=True, index=True)

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.id"),
        nullable=False
    )

    field_name = Column(String(100), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    corrected_by = Column(String(150), nullable=False)
    reason = Column(Text)

    corrected_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# -------------------------
# EXPORT HISTORY MODEL
# -------------------------

class ExportHistory(Base):
    __tablename__ = "export_history"

    id = Column(Integer, primary_key=True, index=True)

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.id"),
        nullable=False,
        index=True
    )

    filename = Column(String(255), nullable=False)
    exported_by = Column(String(150), nullable=False)

    export_status = Column(
        String(30),
        nullable=False,
        default="SUCCESS"
    )

    exported_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
