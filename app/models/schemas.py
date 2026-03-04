from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict
from datetime import datetime


class UserRegister(BaseModel):
    phone_number: str
    email: Optional[str] = None
    name: Optional[str] = None


class TransactionRequest(BaseModel):
    user_id: str
    amount: float = Field(gt=0, description="Transaction amount must be positive")
    merchant: str = Field(min_length=1, max_length=255)
    merchant_category: str = Field(min_length=1, max_length=100)
    device_type: str = Field(min_length=1, max_length=50)
    device_ip: str = Field(min_length=7, max_length=45, description="IPv4 or IPv6 address string")
    user_location: Dict[str, float]
    email: Optional[EmailStr] = None          # Validated email for sending alerts
    device_id: Optional[str] = None           # Device fingerprint for tracking
    timestamp: Optional[datetime] = None      # Transaction timestamp (used for time-based features)


class TransactionResponse(BaseModel):
    id: str
    user_id: str
    amount: float
    merchant: str
    fraud_score: float
    risk_level: str
    status: str
    action: Optional[str] = None
    message: str
    requires_confirmation: bool


class WhatsAppConfirmation(BaseModel):
    transaction_id: str
    user_confirmed: bool
    user_message: Optional[str] = None


class UserBehaviorProfile(BaseModel):
    user_id: str
    avg_transaction_amount: float
    typical_daily_frequency: int
    typical_locations: List[Dict[str, float]]
    last_updated: datetime
