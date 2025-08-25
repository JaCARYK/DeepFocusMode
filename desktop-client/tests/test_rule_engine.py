"""
Tests for rule engine functionality.
"""

import pytest
from datetime import datetime

from src.rules.rule_engine import RuleEngine, SmartBlocker
from src.db.models import Rule, BlockDecision, BlockAction


class TestRuleEngine:
    """Test suite for RuleEngine class."""
    
    @pytest.fixture
    def engine(self):
        """Create a RuleEngine instance for testing."""
        return RuleEngine()
    
    @pytest.fixture
    def sample_rules(self):
        """Create sample rules for testing."""
        return [
            Rule(
                id=1,
                name="Block YouTube",
                domain_pattern="*youtube.com*",
                action=BlockAction.BLOCK,
                reminder_message="YouTube is blocked",
                priority=90,
                is_active=True
            ),
            Rule(
                id=2,
                name="Delay Reddit",
                domain_pattern="reddit.com",
                action=BlockAction.DELAY,
                delay_minutes=5,
                reminder_message="Reddit delay",
                priority=80,
                is_active=True
            ),
            Rule(
                id=3,
                name="Conditional Twitter",
                domain_pattern="twitter.com",
                action=BlockAction.CONDITIONAL,
                required_focus_minutes=30,
                reminder_message="Focus more for Twitter",
                priority=85,
                is_active=True
            )
        ]
    
    @pytest.mark.asyncio
    async def test_evaluate_block_action(self, engine, sample_rules):
        """Test evaluation of BLOCK action."""
        decision = await engine.evaluate(
            domain="www.youtube.com",
            rules=sample_rules,
            is_coding=True,
            session_minutes=10
        )
        
        assert decision.should_block is True
        assert decision.action == BlockAction.BLOCK
        assert "YouTube is blocked" in decision.reminder_message
    
    @pytest.mark.asyncio
    async def test_evaluate_delay_action(self, engine, sample_rules):
        """Test evaluation of DELAY action."""
        decision = await engine.evaluate(
            domain="reddit.com",
            rules=sample_rules,
            is_coding=True,
            session_minutes=10
        )
        
        assert decision.should_block is True
        assert decision.action == BlockAction.DELAY
        assert decision.delay_seconds == 300  # 5 minutes
        assert "Reddit delay" in decision.reminder_message
    
    @pytest.mark.asyncio
    async def test_evaluate_conditional_blocked(self, engine, sample_rules):
        """Test CONDITIONAL action when focus time insufficient."""
        decision = await engine.evaluate(
            domain="twitter.com",
            rules=sample_rules,
            is_coding=True,
            session_minutes=10  # Less than required 30
        )
        
        assert decision.should_block is True
        assert decision.action == BlockAction.CONDITIONAL
        assert decision.remaining_focus_time == 1200  # 20 minutes in seconds
        assert "Focus more for Twitter" in decision.reminder_message
    
    @pytest.mark.asyncio
    async def test_evaluate_conditional_allowed(self, engine, sample_rules):
        """Test CONDITIONAL action when focus time sufficient."""
        decision = await engine.evaluate(
            domain="twitter.com",
            rules=sample_rules,
            is_coding=True,
            session_minutes=35  # More than required 30
        )
        
        assert decision.should_block is False
        assert decision.action == BlockAction.CONDITIONAL
    
    @pytest.mark.asyncio
    async def test_evaluate_no_matching_rule(self, engine, sample_rules):
        """Test evaluation when no rule matches."""
        decision = await engine.evaluate(
            domain="stackoverflow.com",
            rules=sample_rules,
            is_coding=True,
            session_minutes=10
        )
        
        assert decision.should_block is False
    
    def test_domain_matches_wildcard(self, engine):
        """Test wildcard domain matching."""
        assert engine._domain_matches("www.youtube.com", "*youtube.com*") is True
        assert engine._domain_matches("youtube.com", "*youtube.com*") is True
        assert engine._domain_matches("m.youtube.com", "*youtube.com*") is True
        assert engine._domain_matches("google.com", "*youtube.com*") is False
    
    def test_domain_matches_exact(self, engine):
        """Test exact domain matching."""
        assert engine._domain_matches("reddit.com", "reddit.com") is True
        assert engine._domain_matches("www.reddit.com", "reddit.com") is True
        assert engine._domain_matches("old.reddit.com", "reddit.com") is True
        assert engine._domain_matches("reddit.org", "reddit.com") is False
    
    def test_validate_rule_valid(self, engine):
        """Test validation of valid rule."""
        rule = Rule(
            name="Test Rule",
            domain_pattern="test.com",
            action=BlockAction.BLOCK,
            priority=50
        )
        
        errors = engine.validate_rule(rule)
        assert len(errors) == 0
    
    def test_validate_rule_invalid_pattern(self, engine):
        """Test validation of rule with invalid pattern."""
        rule = Rule(
            name="Test Rule",
            domain_pattern="",  # Empty pattern
            action=BlockAction.BLOCK,
            priority=50
        )
        
        errors = engine.validate_rule(rule)
        assert len(errors) > 0
        assert "Domain pattern cannot be empty" in errors[0]
    
    def test_validate_rule_invalid_delay(self, engine):
        """Test validation of rule with invalid delay."""
        rule = Rule(
            name="Test Rule",
            domain_pattern="test.com",
            action=BlockAction.DELAY,
            delay_minutes=0,  # Invalid delay
            priority=50
        )
        
        errors = engine.validate_rule(rule)
        assert len(errors) > 0
        assert "Delay minutes must be positive" in errors[0]


class TestSmartBlocker:
    """Test suite for SmartBlocker class."""
    
    @pytest.fixture
    def smart_blocker(self):
        """Create a SmartBlocker instance for testing."""
        engine = RuleEngine()
        return SmartBlocker(engine)
    
    @pytest.mark.asyncio
    async def test_evaluate_with_ml_low_productivity(self, smart_blocker):
        """Test ML enhancement for low productivity site."""
        # Set a low productivity score
        smart_blocker.update_productivity_score("distracting.com", 0.2)
        
        decision = await smart_blocker.evaluate_with_ml(
            domain="distracting.com",
            rules=[],  # No rules
            is_coding=True,
            session_minutes=10
        )
        
        assert decision.should_block is True
        assert decision.action == BlockAction.DELAY
        assert "AI detected" in decision.reminder_message
    
    @pytest.mark.asyncio
    async def test_evaluate_with_ml_high_productivity(self, smart_blocker):
        """Test ML enhancement for high productivity site."""
        # Set a high productivity score
        smart_blocker.update_productivity_score("productive.com", 0.8)
        
        # Create a blocking rule
        rule = Rule(
            name="Block Productive",
            domain_pattern="productive.com",
            action=BlockAction.BLOCK,
            priority=90
        )
        
        decision = await smart_blocker.evaluate_with_ml(
            domain="productive.com",
            rules=[rule],
            is_coding=True,
            session_minutes=10
        )
        
        # Should reduce restriction
        assert decision.action == BlockAction.DELAY
        assert decision.delay_seconds == 60
        assert "AI detected" in decision.reminder_message
        assert "work-related" in decision.reminder_message
    
    def test_record_override(self, smart_blocker):
        """Test recording user overrides."""
        smart_blocker.record_override("test.com")
        assert smart_blocker.user_overrides["test.com"] == 1
        
        smart_blocker.record_override("test.com")
        assert smart_blocker.user_overrides["test.com"] == 2
    
    def test_update_productivity_score(self, smart_blocker):
        """Test updating productivity scores."""
        smart_blocker.update_productivity_score("test.com", 0.5)
        assert smart_blocker.productivity_scores["test.com"] == 0.5
        
        # Test clamping
        smart_blocker.update_productivity_score("test2.com", 1.5)
        assert smart_blocker.productivity_scores["test2.com"] == 1.0
        
        smart_blocker.update_productivity_score("test3.com", -0.5)
        assert smart_blocker.productivity_scores["test3.com"] == 0.0