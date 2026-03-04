from datetime import datetime, timedelta
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Integer, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
import enum

Base = declarative_base()

class User(Base):
    """User model for VerifAI"""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    
    # Account status
    is_email_verified = Column(Boolean, default=False)
    is_account_locked = Column(Boolean, default=False)
    locked_until = Column(DateTime, nullable=True)
    
    # Profile settings
    theme = Column(String(50), default="light")  # light/dark
    notifications_enabled = Column(Boolean, default=True)
    email_alerts = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    verification_tokens = relationship("VerificationToken", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email}>"


class TransactionStatus(str, enum.Enum):
    """Transaction decision enum"""
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    HOLD = "HOLD"
    FLAGGED = "FLAGGED"


class Transaction(Base):
    """Transaction model for fraud detection"""
    __tablename__ = "transactions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Transaction details
    amount = Column(Float, nullable=False)
    merchant = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    
    # Fraud scoring
    fraud_score = Column(Float, nullable=False)  # 0.0 - 1.0
    risk_level = Column(String(50), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    decision = Column(SQLEnum(TransactionStatus), default=TransactionStatus.APPROVED)
    
    # Device & Location
    device_ip = Column(String(45), nullable=True)  # IPv4 or IPv6
    device_type = Column(String(50), nullable=True)  # mobile, desktop, api
    device_id = Column(String(255), nullable=True)
    geo_country = Column(String(2), nullable=True)
    geo_city = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)
    
    # Metadata
    meta_data = Column(String(2000), nullable=True)  # JSON string
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction {self.id} - {self.decision}>"


class Device(Base):
    """Device fingerprint model"""
    __tablename__ = "devices"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Device identification
    device_ip = Column(String(45), nullable=False)
    device_fingerprint = Column(String(255), nullable=True)
    device_type = Column(String(50), nullable=False)  # mobile, desktop, api, web
    browser = Column(String(100), nullable=True)
    os = Column(String(100), nullable=True)
    
    # Trust status
    is_trusted = Column(Boolean, default=False)
    trust_score = Column(Float, default=0.5)  # 0.0 - 1.0
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="devices")
    
    def __repr__(self):
        return f"<Device {self.device_ip}>"


class VerificationTokenType(str, enum.Enum):
    """Token types"""
    EMAIL_VERIFY = "EMAIL_VERIFY"
    PASSWORD_RESET = "PASSWORD_RESET"
    EMAIL_CHANGE = "EMAIL_CHANGE"
    TRANSACTION_VERIFY = "TRANSACTION_VERIFY"


class VerificationToken(Base):
    """Email verification and password reset tokens"""
    __tablename__ = "verification_tokens"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Token details
    token = Column(String(255), unique=True, nullable=False, index=True)
    token_type = Column(SQLEnum(VerificationTokenType), nullable=False)
    
    # Expiration
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    is_used = Column(Boolean, default=False)
    
    # Metadata
    meta_data = Column(String(500), nullable=True)  # JSON string - can store extra data
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="verification_tokens")
    
    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at or self.is_used
    
    def __repr__(self):
        return f"<VerificationToken {self.token_type}>"


class AuditLog(Base):
    """Audit log for security events"""
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    
    # Event details
    event_type = Column(String(100), nullable=False)  # login, logout, fraud_alert, account_locked, etc
    event_severity = Column(String(50), nullable=False)  # info, warning, critical
    description = Column(String(500), nullable=False)
    
    # Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    meta_data = Column(String(2000), nullable=True)  # JSON string
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<AuditLog {self.event_type}>"