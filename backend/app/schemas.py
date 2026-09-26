import uuid
from datetime import datetime, date
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# Auth Schemas
class UserSignup(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str
    phone_number: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[uuid.UUID] = None


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone_number: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Citizen Profile Schemas
class CitizenProfileBase(BaseModel):
    aadhaar_hash: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    income_annual: Optional[float] = None
    category: Optional[str] = None


class CitizenProfileCreate(CitizenProfileBase):
    pass


class CitizenProfileRead(CitizenProfileBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Document Schemas
class DocumentBase(BaseModel):
    document_type: str
    title: str
    file_path: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    application_id: Optional[uuid.UUID] = None


class DocumentCreate(DocumentBase):
    pass


class DocumentRead(DocumentBase):
    id: uuid.UUID
    user_id: uuid.UUID
    verified: bool
    verification_status: str = "PENDING"
    extracted_data: Optional[Any] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Service Schemas
class ServiceBase(BaseModel):
    code: str
    title: str
    description: Optional[str] = None
    department: str
    required_documents: Optional[Any] = None
    required_fields: Optional[Any] = None
    processing_time_days: int = 7
    fee_amount: float = 0.0
    is_active: bool = True


class ServiceRead(ServiceBase):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Application Schemas
class ApplicationCreate(BaseModel):
    service_id: uuid.UUID
    form_data: Optional[Any] = None
    remarks: Optional[str] = None


class ApplicationRead(BaseModel):
    id: uuid.UUID
    application_number: str
    user_id: uuid.UUID
    service_id: uuid.UUID
    status: str
    government_status: Optional[str] = None
    government_reference: Optional[str] = None
    progress_percentage: int = 0
    form_data: Optional[Any] = None
    remarks: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    service: Optional[ServiceRead] = None

    model_config = ConfigDict(from_attributes=True)


# Consent Schemas
class ConsentCreate(BaseModel):
    application_id: uuid.UUID
    purpose: str
    requesting_department: str
    data_requested: Any
    data_snapshot: Any
    expires_at: Optional[datetime] = None


class ConsentRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    application_id: uuid.UUID
    purpose: str
    requesting_department: str
    data_requested: Any
    data_snapshot: Any
    status: str
    expires_at: Optional[datetime] = None
    created_at: datetime
    responded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ConsentRespond(BaseModel):
    action: str  # "approve" or "deny"


# Chat Schemas
class ChatRequest(BaseModel):
    citizen_id: uuid.UUID
    message: str
    application_id: Optional[uuid.UUID] = None


class ChatResponse(BaseModel):
    reply: str
    application_id: Optional[str] = None
    service_code: Optional[str] = None
    status: Optional[str] = None
    required_documents: List[str] = []
    required_fields: List[str] = []
    detected_intent: Optional[str] = None
    normalized_message: Optional[str] = None
    missing_documents: List[str] = []
    verified_documents: List[str] = []
    clarification_options: List[str] = []
    jurisdiction: Optional[str] = None
    jurisdiction_notice: Optional[Dict[str, Any]] = None
    responsible_officer: Optional[str] = None


class ChatMessageRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    application_id: Optional[uuid.UUID] = None
    role: str
    original_message: str
    normalized_message: Optional[str] = None
    intent: Optional[str] = None
    service_code: Optional[str] = None
    corrections: Optional[Any] = None
    reply: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VaultStats(BaseModel):
    total: int
    verified: int
    shared: int

