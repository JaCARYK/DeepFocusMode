"""
FastAPI server for communication with browser extension.
Provides endpoints for checking block status and managing rules.
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ..db.database import db_manager
from ..db.models import (
    Rule, FocusSession, BlockEvent,
    RuleCreate, RuleResponse, BlockDecision, SessionStats,
    BlockAction
)
from ..monitor.process_monitor import ProcessMonitor
from ..monitor.keystroke_monitor import KeystrokeMonitor, ActivityDetector
from ..rules.rule_engine import RuleEngine


logger = logging.getLogger(__name__)

# Global instances
process_monitor = ProcessMonitor()
keystroke_monitor = KeystrokeMonitor()
activity_detector = ActivityDetector(process_monitor, keystroke_monitor)
rule_engine = RuleEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.
    Initialize resources on startup, cleanup on shutdown.
    """
    # Startup
    logger.info("Starting Deep Focus Mode API server")
    
    # Initialize database
    await db_manager.init_db()
    
    # Start monitors
    keystroke_monitor.start_monitoring()
    # Note: process_monitor.start_monitoring() should be called with asyncio
    
    yield
    
    # Shutdown
    logger.info("Shutting down Deep Focus Mode API server")
    
    # Stop monitors
    keystroke_monitor.stop_monitoring()
    process_monitor.stop_monitoring()
    
    # Close database
    await db_manager.close()


# Create FastAPI app
app = FastAPI(
    title="Deep Focus Mode API",
    description="API for intelligent distraction blocking",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for browser extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact extension origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency for database sessions
async def get_db() -> AsyncSession:
    """Get database session dependency."""
    async with db_manager.get_session() as session:
        yield session


# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "monitors": {
            "process": process_monitor.is_monitoring,
            "keystroke": keystroke_monitor.is_monitoring
        }
    }


@app.get("/api/status")
async def get_focus_status():
    """Get current focus session status."""
    is_coding = activity_detector.is_actively_coding()
    process_stats = process_monitor.get_focus_stats()
    keystroke_metrics = keystroke_monitor.get_activity_metrics()
    
    session_info = None
    if activity_detector.session_start_time:
        duration = (datetime.now() - activity_detector.session_start_time).total_seconds() / 60
        session_info = {
            "start_time": activity_detector.session_start_time.isoformat(),
            "duration_minutes": round(duration, 2)
        }
    
    return {
        "is_actively_coding": is_coding,
        "current_app": process_stats["current_app"],
        "is_ide_active": process_stats["is_ide_active"],
        "keystroke_activity": keystroke_metrics["activity_level"],
        "keystrokes_per_minute": keystroke_metrics["keystrokes_per_minute"],
        "current_session": session_info
    }


@app.post("/api/check-block")
async def check_block(
    url: str,
    db: AsyncSession = Depends(get_db)
) -> BlockDecision:
    """
    Check if a URL should be blocked based on current rules and focus state.
    
    Args:
        url: The URL to check.
        db: Database session.
        
    Returns:
        BlockDecision with action to take.
    """
    # Extract domain from URL
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    
    # Get active rules from database
    result = await db.execute(
        select(Rule).where(Rule.is_active == True).order_by(Rule.priority.desc())
    )
    rules = result.scalars().all()
    
    # Check if user is actively coding
    is_coding = activity_detector.is_actively_coding()
    
    # Get session duration if active
    session_minutes = 0
    if activity_detector.session_start_time:
        session_minutes = (datetime.now() - activity_detector.session_start_time).total_seconds() / 60
    
    # Evaluate rules
    decision = await rule_engine.evaluate(
        domain=domain,
        rules=rules,
        is_coding=is_coding,
        session_minutes=session_minutes
    )
    
    # Log block event if blocking
    if decision.should_block:
        # Find the matching rule
        matching_rule = next(
            (r for r in rules if domain_matches(domain, r.domain_pattern)),
            None
        )
        
        if matching_rule:
            # Create block event
            block_event = BlockEvent(
                rule_id=matching_rule.id,
                url=url,
                action_taken=decision.action,
                timestamp=datetime.now()
            )
            db.add(block_event)
            await db.commit()
    
    return decision


@app.get("/api/rules", response_model=List[RuleResponse])
async def get_rules(
    db: AsyncSession = Depends(get_db)
):
    """Get all blocking rules."""
    result = await db.execute(
        select(Rule).order_by(Rule.priority.desc(), Rule.created_at.desc())
    )
    rules = result.scalars().all()
    return rules


@app.post("/api/rules", response_model=RuleResponse)
async def create_rule(
    rule_data: RuleCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new blocking rule."""
    rule = Rule(
        name=rule_data.name,
        domain_pattern=rule_data.domain_pattern,
        action=rule_data.action,
        delay_minutes=rule_data.delay_minutes,
        required_focus_minutes=rule_data.required_focus_minutes,
        reminder_message=rule_data.reminder_message,
        priority=rule_data.priority or 0
    )
    
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    
    return rule


@app.put("/api/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: int,
    rule_data: RuleCreate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing rule."""
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Update fields
    rule.name = rule_data.name
    rule.domain_pattern = rule_data.domain_pattern
    rule.action = rule_data.action
    rule.delay_minutes = rule_data.delay_minutes
    rule.required_focus_minutes = rule_data.required_focus_minutes
    rule.reminder_message = rule_data.reminder_message
    rule.priority = rule_data.priority or rule.priority
    rule.updated_at = datetime.now()
    
    await db.commit()
    await db.refresh(rule)
    
    return rule


@app.delete("/api/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a rule."""
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await db.delete(rule)
    await db.commit()
    
    return {"message": "Rule deleted successfully"}


@app.post("/api/rules/{rule_id}/toggle")
async def toggle_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Toggle a rule's active status."""
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    rule.is_active = not rule.is_active
    rule.updated_at = datetime.now()
    
    await db.commit()
    await db.refresh(rule)
    
    return {"id": rule.id, "is_active": rule.is_active}


@app.get("/api/sessions/current")
async def get_current_session(
    db: AsyncSession = Depends(get_db)
):
    """Get current focus session information."""
    if not activity_detector.session_start_time:
        return {"active": False}
    
    duration = (datetime.now() - activity_detector.session_start_time).total_seconds() / 60
    
    # Get block events for current session (last hour for simplicity)
    one_hour_ago = datetime.now() - timedelta(hours=1)
    result = await db.execute(
        select(BlockEvent).where(BlockEvent.timestamp > one_hour_ago)
    )
    recent_blocks = result.scalars().all()
    
    return {
        "active": True,
        "start_time": activity_detector.session_start_time.isoformat(),
        "duration_minutes": round(duration, 2),
        "blocks_count": len(recent_blocks),
        "keystroke_activity": keystroke_monitor.get_activity_metrics()
    }


@app.get("/api/stats/today")
async def get_today_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get today's focus statistics."""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Get today's sessions
    result = await db.execute(
        select(FocusSession).where(FocusSession.start_time >= today_start)
    )
    sessions = result.scalars().all()
    
    # Get today's blocks
    result = await db.execute(
        select(BlockEvent).where(BlockEvent.timestamp >= today_start)
    )
    blocks = result.scalars().all()
    
    # Calculate statistics
    total_focus_minutes = sum(s.total_minutes or 0 for s in sessions)
    productive_minutes = sum(s.productive_minutes or 0 for s in sessions)
    
    return {
        "date": today_start.date().isoformat(),
        "total_sessions": len(sessions),
        "total_focus_minutes": round(total_focus_minutes, 2),
        "productive_minutes": round(productive_minutes, 2),
        "distractions_blocked": len(blocks),
        "productivity_score": calculate_productivity_score(
            productive_minutes, total_focus_minutes, len(blocks)
        )
    }


# Helper functions

def domain_matches(domain: str, pattern: str) -> bool:
    """
    Check if a domain matches a pattern.
    Supports wildcards (*) and exact matches.
    
    Args:
        domain: The domain to check.
        pattern: The pattern to match against.
        
    Returns:
        True if domain matches pattern.
    """
    import fnmatch
    
    # Normalize domain and pattern
    domain = domain.lower().strip()
    pattern = pattern.lower().strip()
    
    # Handle wildcards
    if '*' in pattern:
        return fnmatch.fnmatch(domain, pattern)
    
    # Check if pattern is in domain (for partial matches)
    return pattern in domain


def calculate_productivity_score(
    productive_minutes: float,
    total_minutes: float,
    blocks_count: int
) -> float:
    """
    Calculate a productivity score from 0-100.
    
    Args:
        productive_minutes: Minutes spent productively.
        total_minutes: Total minutes tracked.
        blocks_count: Number of distractions blocked.
        
    Returns:
        Productivity score.
    """
    if total_minutes == 0:
        return 0.0
    
    # Base score from productive time ratio
    base_score = (productive_minutes / total_minutes) * 70
    
    # Bonus for blocking distractions (up to 30 points)
    block_bonus = min(blocks_count * 2, 30)
    
    return min(base_score + block_bonus, 100.0)