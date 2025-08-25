"""
Keystroke activity monitoring module.
Tracks keyboard activity to detect active coding sessions.
Note: Only tracks activity levels, not actual keystrokes for privacy.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging
from threading import Thread, Lock

from pynput import keyboard


logger = logging.getLogger(__name__)


class KeystrokeMonitor:
    """
    Monitors keyboard activity to detect active work sessions.
    Does NOT log actual keystrokes - only activity metrics for privacy.
    """
    
    def __init__(self, window_size_seconds: int = 60):
        """
        Initialize keystroke monitor.
        
        Args:
            window_size_seconds: Time window for calculating activity metrics.
        """
        self.window_size = window_size_seconds
        self.keystroke_times = []
        self.last_keystroke_time: Optional[datetime] = None
        self.total_keystrokes = 0
        self.is_monitoring = False
        self._lock = Lock()
        self._listener: Optional[keyboard.Listener] = None
        
    def _on_key_press(self, key):
        """
        Handle key press events.
        Note: We don't log the actual key, only the timestamp.
        
        Args:
            key: The key that was pressed (ignored for privacy).
        """
        with self._lock:
            current_time = datetime.now()
            self.last_keystroke_time = current_time
            self.total_keystrokes += 1
            
            # Add timestamp to rolling window
            self.keystroke_times.append(current_time)
            
            # Remove old timestamps outside the window
            cutoff_time = current_time - timedelta(seconds=self.window_size)
            self.keystroke_times = [
                t for t in self.keystroke_times if t > cutoff_time
            ]
    
    def get_activity_metrics(self) -> Dict:
        """
        Get current keyboard activity metrics.
        
        Returns:
            Dictionary with activity metrics.
        """
        with self._lock:
            current_time = datetime.now()
            
            # Clean old timestamps
            cutoff_time = current_time - timedelta(seconds=self.window_size)
            self.keystroke_times = [
                t for t in self.keystroke_times if t > cutoff_time
            ]
            
            # Calculate metrics
            keystrokes_per_minute = (len(self.keystroke_times) / self.window_size) * 60
            
            time_since_last = None
            if self.last_keystroke_time:
                time_since_last = (current_time - self.last_keystroke_time).total_seconds()
            
            # Determine activity level
            if keystrokes_per_minute > 60:
                activity_level = "high"
            elif keystrokes_per_minute > 20:
                activity_level = "medium"
            elif keystrokes_per_minute > 5:
                activity_level = "low"
            else:
                activity_level = "idle"
            
            return {
                "keystrokes_per_minute": round(keystrokes_per_minute, 2),
                "total_keystrokes": self.total_keystrokes,
                "time_since_last_keystroke": time_since_last,
                "activity_level": activity_level,
                "is_active": activity_level != "idle"
            }
    
    def is_user_active(self, idle_threshold_seconds: int = 30) -> bool:
        """
        Check if user is actively typing.
        
        Args:
            idle_threshold_seconds: Seconds without keystrokes before considered idle.
            
        Returns:
            True if user is active, False otherwise.
        """
        with self._lock:
            if not self.last_keystroke_time:
                return False
            
            time_since_last = (datetime.now() - self.last_keystroke_time).total_seconds()
            return time_since_last < idle_threshold_seconds
    
    def start_monitoring(self):
        """Start monitoring keyboard activity."""
        if self.is_monitoring:
            logger.warning("Keystroke monitoring is already active")
            return
        
        self.is_monitoring = True
        
        # Start keyboard listener in a separate thread
        self._listener = keyboard.Listener(on_press=self._on_key_press)
        self._listener.start()
        
        logger.info("Keystroke monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring keyboard activity."""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        if self._listener:
            self._listener.stop()
            self._listener = None
        
        logger.info("Keystroke monitoring stopped")
    
    def reset_metrics(self):
        """Reset all activity metrics."""
        with self._lock:
            self.keystroke_times = []
            self.last_keystroke_time = None
            self.total_keystrokes = 0
            logger.info("Keystroke metrics reset")


class ActivityDetector:
    """
    Combines process and keystroke monitoring to detect coding activity.
    """
    
    def __init__(self, process_monitor, keystroke_monitor):
        """
        Initialize activity detector.
        
        Args:
            process_monitor: ProcessMonitor instance.
            keystroke_monitor: KeystrokeMonitor instance.
        """
        self.process_monitor = process_monitor
        self.keystroke_monitor = keystroke_monitor
        self.session_start_time: Optional[datetime] = None
        self.current_session_duration = timedelta()
        
    def is_actively_coding(self) -> bool:
        """
        Determine if user is actively coding based on multiple signals.
        
        Returns:
            True if actively coding, False otherwise.
        """
        # Check if IDE is active
        if not self.process_monitor.is_ide_active():
            return False
        
        # Check keyboard activity
        keystroke_metrics = self.keystroke_monitor.get_activity_metrics()
        
        # Consider coding if:
        # 1. IDE is active AND
        # 2. There's recent keyboard activity OR reasonable typing rate
        return (
            keystroke_metrics['is_active'] or
            keystroke_metrics['keystrokes_per_minute'] > 10
        )
    
    def start_session(self):
        """Start a new focus session."""
        self.session_start_time = datetime.now()
        self.current_session_duration = timedelta()
        logger.info("Focus session started")
    
    def end_session(self) -> Dict:
        """
        End current focus session and return statistics.
        
        Returns:
            Session statistics dictionary.
        """
        if not self.session_start_time:
            return {}
        
        session_end = datetime.now()
        total_duration = session_end - self.session_start_time
        
        stats = {
            "start_time": self.session_start_time.isoformat(),
            "end_time": session_end.isoformat(),
            "duration_minutes": total_duration.total_seconds() / 60,
            "total_keystrokes": self.keystroke_monitor.total_keystrokes,
            "average_kpm": self.keystroke_monitor.get_activity_metrics()['keystrokes_per_minute']
        }
        
        # Reset for next session
        self.session_start_time = None
        self.keystroke_monitor.reset_metrics()
        
        logger.info(f"Focus session ended. Duration: {stats['duration_minutes']:.1f} minutes")
        
        return stats
    
    async def monitor_activity(self, check_interval: int = 5):
        """
        Monitor activity and track focus sessions.
        
        Args:
            check_interval: Seconds between activity checks.
        """
        was_coding = False
        
        while True:
            try:
                is_coding = self.is_actively_coding()
                
                # Detect session start
                if is_coding and not was_coding:
                    self.start_session()
                
                # Detect session end
                elif not is_coding and was_coding:
                    stats = self.end_session()
                    # Here you could save stats to database
                    logger.info(f"Session stats: {stats}")
                
                # Update session duration if active
                if is_coding and self.session_start_time:
                    self.current_session_duration = datetime.now() - self.session_start_time
                
                was_coding = is_coding
                
            except Exception as e:
                logger.error(f"Error in activity monitoring: {e}")
            
            await asyncio.sleep(check_interval)