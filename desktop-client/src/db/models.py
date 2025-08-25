"""
Database models for Deep Focus Mode.
Uses SQLAlchemy for ORM with async support.
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

Base = declarative_base()


class BlockAction(str, Enum):
    """Types of blocking actions available."""
    BLOCK = "block"
    DELAY = "delay"
    CONDITIONAL = "conditional"


class ProcessType(str, Enum):
    """Types of processes we monitor."""
    IDE = "ide"
    BROWSER = "browser"
    PRODUCTIVITY = "productivity"
    DISTRACTION = "distraction"
    UNKNOWN = "unknown"


class Rule(Base):
    """Blocking rules configured by the user."""
    __tablename__ = "rules"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    domain_pattern = Column(String(255), nullable=False)
    action = Column(String(20), nullable=False)
    delay_minutes = Column(Integer, default=5)
    required_focus_minutes = Column(Integer, default=30)
    reminder_message = Column(String(500))
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to sessions where this rule was triggered
    blocks = relationship("BlockEvent", back_populates="rule")


class FocusSession(Base):
    """Records of focus sessions (periods of productive work)."""
    __tablename__ = "focus_sessions"
    
    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    total_minutes = Column(Float)
    productive_minutes = Column(Float)
    distraction_attempts = Column(Integer, default=0)
    blocks_enforced = Column(Integer, default=0)
    primary_application = Column(String(100))
    goal_text = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    block_events = relationship("BlockEvent", back_populates="session")
    process_logs = relationship("ProcessLog", back_populates="session")


class BlockEvent(Base):
    """Log of each distraction blocking event."""
    __tablename__ = "block_events"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("focus_sessions.id"))
    rule_id = Column(Integer, ForeignKey("rules.id"))
    url = Column(String(500))
    action_taken = Column(String(20))
    was_overridden = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("FocusSession", back_populates="block_events")
    rule = relationship("Rule", back_populates="blocks")


class ProcessLog(Base):
    """Log of active processes during focus sessions."""
    __tablename__ = "process_logs"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("focus_sessions.id"))
    process_name = Column(String(255))
    process_type = Column(String(20))
    window_title = Column(String(500))
    duration_seconds = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    session = relationship("FocusSession", back_populates="process_logs")


class UserGoal(Base):
    """User-defined goals and reminders."""
    __tablename__ = "user_goals"
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(String(1000))
    target_hours_per_day = Column(Float)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


# Pydantic models for API requests/responses

class RuleCreate(BaseModel):
    """Schema for creating a new rule."""
    name: str = Field(..., min_length=1, max_length=100)
    domain_pattern: str = Field(..., min_length=1, max_length=255)
    action: BlockAction
    delay_minutes: Optional[int] = Field(5, ge=1, le=60)
    required_focus_minutes: Optional[int] = Field(30, ge=5, le=240)
    reminder_message: Optional[str] = Field(None, max_length=500)
    priority: Optional[int] = Field(0, ge=0, le=100)


class RuleResponse(BaseModel):
    """Schema for rule responses."""
    id: int
    name: str
    domain_pattern: str
    action: str
    delay_minutes: int
    required_focus_minutes: int
    reminder_message: Optional[str]
    is_active: bool
    priority: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class BlockDecision(BaseModel):
    """Response for block check requests from browser extension."""
    should_block: bool
    action: BlockAction
    delay_seconds: Optional[int] = None
    reminder_message: Optional[str] = None
    remaining_focus_time: Optional[int] = None


class SessionStats(BaseModel):
    """Statistics for a focus session."""
    session_id: int
    duration_minutes: float
    productive_minutes: float
    distraction_attempts: int
    blocks_enforced: int
    productivity_score: float