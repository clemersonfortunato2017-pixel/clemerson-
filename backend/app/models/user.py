from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="operator")   # admin, operator
    status = Column(String(20), default="pending")  # pending, approved, rejected, disabled
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    invite_token = Column(String(64), unique=True, nullable=True)  # convite instantâneo do admin, some depois de usado
    google_id = Column(String(64), unique=True, nullable=True)
