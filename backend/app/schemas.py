from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str


class ShipmentCreate(BaseModel):
    shipment_number: str = Field(
        min_length=3,
        max_length=50,
    )
    importer: str = Field(
        min_length=2,
        max_length=150,
    )
    supplier: str | None = Field(
        default=None,
        max_length=150,
    )
    origin_country: str | None = Field(
        default=None,
        max_length=100,
    )


class ShipmentResponse(BaseModel):
    id: int
    shipment_number: str
    importer: str
    supplier: str | None = None
    origin_country: str | None = None
    status: str

    class Config:
        from_attributes = True


class CorrectionRequest(BaseModel):
    field_name: str = Field(
        min_length=1,
        max_length=100,
    )
    new_value: str = Field(
        min_length=1,
        max_length=500,
    )
    reason: str = Field(
        min_length=5,
        max_length=1000,
    )