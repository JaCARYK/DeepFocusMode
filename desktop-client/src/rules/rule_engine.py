"""
Rule engine for evaluating blocking decisions.
Implements the logic for different blocking strategies.
"""

import re
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from ..db.models import Rule, BlockDecision, BlockAction


logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Evaluates blocking rules based on current context.
    Supports multiple blocking strategies and conditions.
    """
    
    def __init__(self):
        """Initialize rule engine."""
        self.cache = {}  # Cache for compiled regex patterns
        
    async def evaluate(
        self,
        domain: str,
        rules: List[Rule],
        is_coding: bool,
        session_minutes: float
    ) -> BlockDecision:
        """
        Evaluate rules and determine blocking decision.
        
        Args:
            domain: Domain to check.
            rules: List of active rules.
            is_coding: Whether user is actively coding.
            session_minutes: Minutes in current focus session.
            
        Returns:
            BlockDecision with action to take.
        """
        # Default: don't block
        decision = BlockDecision(
            should_block=False,
            action=BlockAction.BLOCK
        )
        
        # Find matching rule with highest priority
        matching_rule = None
        for rule in rules:
            if self._domain_matches(domain, rule.domain_pattern):
                matching_rule = rule
                break  # Rules are already sorted by priority
        
        if not matching_rule:
            return decision
        
        # Apply rule based on action type
        if matching_rule.action == BlockAction.BLOCK:
            # Always block if rule matches
            decision = BlockDecision(
                should_block=True,
                action=BlockAction.BLOCK,
                reminder_message=matching_rule.reminder_message or 
                               "This site is blocked during focus time."
            )
            
        elif matching_rule.action == BlockAction.DELAY:
            # Delay access with reminder
            decision = BlockDecision(
                should_block=True,
                action=BlockAction.DELAY,
                delay_seconds=matching_rule.delay_minutes * 60,
                reminder_message=matching_rule.reminder_message or
                               f"Access will be granted in {matching_rule.delay_minutes} minutes."
            )
            
        elif matching_rule.action == BlockAction.CONDITIONAL:
            # Block only if not enough focus time
            if session_minutes < matching_rule.required_focus_minutes:
                remaining = matching_rule.required_focus_minutes - session_minutes
                decision = BlockDecision(
                    should_block=True,
                    action=BlockAction.CONDITIONAL,
                    remaining_focus_time=int(remaining * 60),  # Convert to seconds
                    reminder_message=matching_rule.reminder_message or
                                   f"Focus for {remaining:.0f} more minutes to unlock this site."
                )
            else:
                # Enough focus time, allow access
                decision = BlockDecision(
                    should_block=False,
                    action=BlockAction.CONDITIONAL
                )
        
        # Override: Don't block if not in a coding session (optional)
        # Uncomment this if you want blocking only during active coding
        # if not is_coding and decision.should_block:
        #     decision.should_block = False
        
        logger.debug(f"Rule evaluation for {domain}: "
                    f"Block={decision.should_block}, Action={decision.action}")
        
        return decision
    
    def _domain_matches(self, domain: str, pattern: str) -> bool:
        """
        Check if domain matches a pattern.
        Supports wildcards, regex, and exact matches.
        
        Args:
            domain: Domain to check.
            pattern: Pattern to match against.
            
        Returns:
            True if domain matches pattern.
        """
        # Normalize inputs
        domain = domain.lower().strip()
        pattern = pattern.lower().strip()
        
        # Check cache for compiled regex
        if pattern not in self.cache:
            self.cache[pattern] = self._compile_pattern(pattern)
        
        regex = self.cache[pattern]
        
        # Try regex match
        if regex:
            return bool(regex.search(domain))
        
        # Fallback to simple substring match
        return pattern in domain
    
    def _compile_pattern(self, pattern: str) -> Optional[re.Pattern]:
        """
        Compile pattern to regex.
        
        Args:
            pattern: Pattern string.
            
        Returns:
            Compiled regex or None if invalid.
        """
        try:
            # Check if pattern is already regex
            if any(char in pattern for char in ['^', '$', '(', ')', '[', ']']):
                return re.compile(pattern)
            
            # Convert wildcard pattern to regex
            if '*' in pattern or '?' in pattern:
                # Escape special chars except wildcards
                escaped = re.escape(pattern)
                # Convert wildcards to regex
                escaped = escaped.replace(r'\*', '.*').replace(r'\?', '.')
                return re.compile(f'^{escaped}$')
            
            # Exact match pattern
            return re.compile(re.escape(pattern))
            
        except re.error as e:
            logger.warning(f"Invalid regex pattern '{pattern}': {e}")
            return None
    
    def validate_rule(self, rule: Rule) -> List[str]:
        """
        Validate a rule configuration.
        
        Args:
            rule: Rule to validate.
            
        Returns:
            List of validation errors (empty if valid).
        """
        errors = []
        
        # Validate pattern
        if not rule.domain_pattern:
            errors.append("Domain pattern cannot be empty")
        else:
            # Try to compile pattern
            regex = self._compile_pattern(rule.domain_pattern)
            if regex is None:
                errors.append(f"Invalid domain pattern: {rule.domain_pattern}")
        
        # Validate action-specific fields
        if rule.action == BlockAction.DELAY:
            if rule.delay_minutes <= 0:
                errors.append("Delay minutes must be positive")
            elif rule.delay_minutes > 60:
                errors.append("Delay cannot exceed 60 minutes")
                
        elif rule.action == BlockAction.CONDITIONAL:
            if rule.required_focus_minutes <= 0:
                errors.append("Required focus minutes must be positive")
            elif rule.required_focus_minutes > 240:
                errors.append("Required focus cannot exceed 4 hours")
        
        # Validate priority
        if rule.priority < 0 or rule.priority > 100:
            errors.append("Priority must be between 0 and 100")
        
        return errors


class SmartBlocker:
    """
    Advanced blocking logic with machine learning integration (optional).
    Can learn from user behavior to improve blocking decisions.
    """
    
    def __init__(self, rule_engine: RuleEngine):
        """
        Initialize smart blocker.
        
        Args:
            rule_engine: Base rule engine.
        """
        self.rule_engine = rule_engine
        self.user_overrides = {}  # Track when user overrides blocks
        self.productivity_scores = {}  # Track site productivity scores
        
    async def evaluate_with_ml(
        self,
        domain: str,
        rules: List[Rule],
        is_coding: bool,
        session_minutes: float,
        user_history: Optional[List] = None
    ) -> BlockDecision:
        """
        Evaluate with machine learning enhancements.
        
        Args:
            domain: Domain to check.
            rules: List of active rules.
            is_coding: Whether user is actively coding.
            session_minutes: Minutes in current focus session.
            user_history: Optional browsing history for ML analysis.
            
        Returns:
            Enhanced blocking decision.
        """
        # Start with rule-based evaluation
        decision = await self.rule_engine.evaluate(
            domain, rules, is_coding, session_minutes
        )
        
        # Apply ML enhancements if available
        if domain in self.productivity_scores:
            score = self.productivity_scores[domain]
            
            # Override decision based on learned productivity score
            if score < 0.3 and not decision.should_block:
                # Low productivity site not in rules - suggest blocking
                decision = BlockDecision(
                    should_block=True,
                    action=BlockAction.DELAY,
                    delay_seconds=300,  # 5 minute delay
                    reminder_message=f"AI detected {domain} as unproductive. "
                                   "Delaying access for 5 minutes."
                )
            elif score > 0.7 and decision.should_block:
                # High productivity site in block list - reduce restriction
                if decision.action == BlockAction.BLOCK:
                    decision.action = BlockAction.DELAY
                    decision.delay_seconds = 60  # Just 1 minute
                    decision.reminder_message = (
                        f"AI detected {domain} might be work-related. "
                        "Reduced delay to 1 minute."
                    )
        
        # Check for user override patterns
        if domain in self.user_overrides:
            override_count = self.user_overrides[domain]
            if override_count > 3:
                # User frequently overrides this block - adapt
                decision.reminder_message = (
                    f"{decision.reminder_message}\n"
                    f"Note: You've overridden this block {override_count} times. "
                    "Consider adjusting your rules."
                )
        
        return decision
    
    def record_override(self, domain: str):
        """Record when user overrides a block."""
        self.user_overrides[domain] = self.user_overrides.get(domain, 0) + 1
    
    def update_productivity_score(self, domain: str, score: float):
        """Update ML-based productivity score for a domain."""
        self.productivity_scores[domain] = max(0.0, min(1.0, score))