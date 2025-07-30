from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True, nullable=False)
    submitted_by_ip = Column(String, unique=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_checked_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_status_code = Column(Integer)
    
    uptime_count = Column(Integer, default=0)
    downtime_count = Column(Integer, default=0)
    
    logs = relationship("Log", back_populates="url_info", cascade="all, delete-orphan")

class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    url_id = Column(Integer, ForeignKey("urls.id"), nullable=False)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Float, nullable=True)
    error_message = Column(String, nullable=True)
    is_up = Column(Boolean, nullable=False)
    
    url_info = relationship("URL", back_populates="logs")