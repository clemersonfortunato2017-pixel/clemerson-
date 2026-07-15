from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database import Base


class MLCredential(Base):
    __tablename__ = "ml_credentials"

    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(String(255))
    refresh_token = Column(String(255))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
