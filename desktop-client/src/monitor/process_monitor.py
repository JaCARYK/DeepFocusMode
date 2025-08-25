"""
Process monitoring module.
Detects active applications and categorizes them as productive or distracting.
"""

import asyncio
import platform
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
import logging

import psutil

from ..db.models import ProcessType


logger = logging.getLogger(__name__)


class ProcessMonitor:
    """Monitors system processes to detect active applications."""
    
    # Known IDE and development tool process names
    IDE_PROCESSES = {
        "code", "code.exe", "Code",  # VS Code
        "pycharm", "pycharm64.exe", "PyCharm",  # PyCharm
        "idea", "idea64.exe", "IntelliJIdea",  # IntelliJ IDEA
        "sublime_text", "sublime_text.exe", "Sublime Text",  # Sublime Text
        "atom", "atom.exe", "Atom",  # Atom
        "webstorm", "webstorm64.exe", "WebStorm",  # WebStorm
        "goland", "goland64.exe", "GoLand",  # GoLand
        "rubymine", "rubymine64.exe", "RubyMine",  # RubyMine
        "clion", "clion64.exe", "CLion",  # CLion
        "datagrip", "datagrip64.exe", "DataGrip",  # DataGrip
        "vim", "nvim", "emacs",  # Terminal editors
        "eclipse", "Eclipse",  # Eclipse
        "netbeans", "NetBeans",  # NetBeans
        "xcode", "Xcode",  # Xcode (macOS)
        "devenv.exe", "Visual Studio",  # Visual Studio
    }
    
    # Browser process names
    BROWSER_PROCESSES = {
        "chrome", "chrome.exe", "Google Chrome",
        "firefox", "firefox.exe", "Firefox",
        "safari", "Safari",
        "msedge", "msedge.exe", "Microsoft Edge",
        "brave", "brave.exe", "Brave Browser",
        "opera", "opera.exe", "Opera",
    }
    
    # Productivity applications
    PRODUCTIVITY_PROCESSES = {
        "terminal", "Terminal", "cmd.exe", "powershell.exe", "iTerm2",
        "docker", "Docker",
        "postman", "Postman",
        "slack", "Slack",  # Can be productive for work communication
        "teams", "Teams",
        "zoom", "Zoom",
        "notion", "Notion",
        "obsidian", "Obsidian",
    }
    
    def __init__(self, check_interval: int = 5):
        """
        Initialize process monitor.
        
        Args:
            check_interval: Seconds between process checks.
        """
        self.check_interval = check_interval
        self.active_processes: Dict[int, Dict] = {}
        self.current_focus_app: Optional[str] = None
        self.last_activity_time = datetime.now()
        self.is_monitoring = False
        
    def categorize_process(self, process_name: str) -> ProcessType:
        """
        Categorize a process by type.
        
        Args:
            process_name: Name of the process.
            
        Returns:
            ProcessType: Category of the process.
        """
        process_lower = process_name.lower()
        
        # Check against known categories
        if any(ide in process_lower for ide in self.IDE_PROCESSES):
            return ProcessType.IDE
        elif any(browser in process_lower for browser in self.BROWSER_PROCESSES):
            return ProcessType.BROWSER
        elif any(prod in process_lower for prod in self.PRODUCTIVITY_PROCESSES):
            return ProcessType.PRODUCTIVITY
        else:
            return ProcessType.UNKNOWN
    
    def get_active_window_info(self) -> Dict[str, str]:
        """
        Get information about the currently active window.
        Platform-specific implementation.
        
        Returns:
            Dict with process_name and window_title.
        """
        system = platform.system()
        
        try:
            if system == "Darwin":  # macOS
                # This requires additional permissions on macOS
                # For production, consider using pyobjc or Quartz
                return self._get_active_window_macos()
            elif system == "Windows":
                return self._get_active_window_windows()
            elif system == "Linux":
                return self._get_active_window_linux()
        except Exception as e:
            logger.warning(f"Could not get active window info: {e}")
            
        return {"process_name": "unknown", "window_title": ""}
    
    def _get_active_window_macos(self) -> Dict[str, str]:
        """Get active window on macOS using AppleScript."""
        try:
            import subprocess
            
            # Get frontmost application name
            script = '''
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
            end tell
            '''
            
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                app_name = result.stdout.strip()
                return {
                    "process_name": app_name,
                    "window_title": ""  # Getting window title requires more permissions
                }
        except Exception as e:
            logger.debug(f"macOS active window detection failed: {e}")
            
        return {"process_name": "unknown", "window_title": ""}
    
    def _get_active_window_windows(self) -> Dict[str, str]:
        """Get active window on Windows."""
        try:
            import win32gui
            import win32process
            
            window = win32gui.GetForegroundWindow()
            pid = win32process.GetWindowThreadProcessId(window)[1]
            process = psutil.Process(pid)
            window_title = win32gui.GetWindowText(window)
            
            return {
                "process_name": process.name(),
                "window_title": window_title
            }
        except Exception as e:
            logger.debug(f"Windows active window detection failed: {e}")
            
        return {"process_name": "unknown", "window_title": ""}
    
    def _get_active_window_linux(self) -> Dict[str, str]:
        """Get active window on Linux using xdotool."""
        try:
            import subprocess
            
            # Get active window ID
            window_id = subprocess.check_output(
                ["xdotool", "getactivewindow"],
                text=True,
                timeout=2
            ).strip()
            
            # Get window PID
            pid = subprocess.check_output(
                ["xdotool", "getwindowpid", window_id],
                text=True,
                timeout=2
            ).strip()
            
            # Get window title
            window_title = subprocess.check_output(
                ["xdotool", "getwindowname", window_id],
                text=True,
                timeout=2
            ).strip()
            
            process = psutil.Process(int(pid))
            
            return {
                "process_name": process.name(),
                "window_title": window_title
            }
        except Exception as e:
            logger.debug(f"Linux active window detection failed: {e}")
            
        return {"process_name": "unknown", "window_title": ""}
    
    def get_running_processes(self) -> List[Dict]:
        """
        Get list of currently running processes.
        
        Returns:
            List of process information dictionaries.
        """
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                pinfo['type'] = self.categorize_process(pinfo['name'])
                processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        return processes
    
    def is_ide_active(self) -> bool:
        """
        Check if an IDE is currently the active window.
        
        Returns:
            True if an IDE is active, False otherwise.
        """
        window_info = self.get_active_window_info()
        process_type = self.categorize_process(window_info['process_name'])
        return process_type == ProcessType.IDE
    
    def is_coding_session_active(self, idle_threshold_minutes: int = 5) -> bool:
        """
        Determine if user is actively coding.
        
        Args:
            idle_threshold_minutes: Minutes of inactivity before session is considered inactive.
            
        Returns:
            True if actively coding, False otherwise.
        """
        if not self.is_ide_active():
            return False
            
        # Check if there has been recent activity
        time_since_activity = datetime.now() - self.last_activity_time
        return time_since_activity < timedelta(minutes=idle_threshold_minutes)
    
    async def start_monitoring(self):
        """Start the process monitoring loop."""
        self.is_monitoring = True
        logger.info("Process monitoring started")
        
        while self.is_monitoring:
            try:
                # Get active window information
                window_info = self.get_active_window_info()
                
                # Update current focus application
                self.current_focus_app = window_info['process_name']
                
                # Update last activity time if IDE is active
                if self.is_ide_active():
                    self.last_activity_time = datetime.now()
                
                # Log current state
                logger.debug(f"Active app: {self.current_focus_app}, "
                           f"Type: {self.categorize_process(self.current_focus_app)}")
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            await asyncio.sleep(self.check_interval)
    
    def stop_monitoring(self):
        """Stop the process monitoring loop."""
        self.is_monitoring = False
        logger.info("Process monitoring stopped")
    
    def get_focus_stats(self) -> Dict:
        """
        Get current focus session statistics.
        
        Returns:
            Dictionary with focus statistics.
        """
        return {
            "current_app": self.current_focus_app,
            "is_ide_active": self.is_ide_active(),
            "is_coding": self.is_coding_session_active(),
            "last_activity": self.last_activity_time.isoformat(),
            "time_since_activity": (datetime.now() - self.last_activity_time).total_seconds()
        }