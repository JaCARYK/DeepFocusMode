"""
Tests for process monitoring functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.monitor.process_monitor import ProcessMonitor, ProcessType


class TestProcessMonitor:
    """Test suite for ProcessMonitor class."""
    
    @pytest.fixture
    def monitor(self):
        """Create a ProcessMonitor instance for testing."""
        return ProcessMonitor(check_interval=1)
    
    def test_categorize_process_ide(self, monitor):
        """Test IDE process categorization."""
        assert monitor.categorize_process("code") == ProcessType.IDE
        assert monitor.categorize_process("Code.exe") == ProcessType.IDE
        assert monitor.categorize_process("pycharm64.exe") == ProcessType.IDE
        assert monitor.categorize_process("IntelliJIdea") == ProcessType.IDE
        assert monitor.categorize_process("vim") == ProcessType.IDE
    
    def test_categorize_process_browser(self, monitor):
        """Test browser process categorization."""
        assert monitor.categorize_process("chrome") == ProcessType.BROWSER
        assert monitor.categorize_process("firefox.exe") == ProcessType.BROWSER
        assert monitor.categorize_process("Safari") == ProcessType.BROWSER
        assert monitor.categorize_process("Microsoft Edge") == ProcessType.BROWSER
    
    def test_categorize_process_productivity(self, monitor):
        """Test productivity app categorization."""
        assert monitor.categorize_process("terminal") == ProcessType.PRODUCTIVITY
        assert monitor.categorize_process("Docker") == ProcessType.PRODUCTIVITY
        assert monitor.categorize_process("slack") == ProcessType.PRODUCTIVITY
        assert monitor.categorize_process("notion") == ProcessType.PRODUCTIVITY
    
    def test_categorize_process_unknown(self, monitor):
        """Test unknown process categorization."""
        assert monitor.categorize_process("random_app") == ProcessType.UNKNOWN
        assert monitor.categorize_process("game.exe") == ProcessType.UNKNOWN
        assert monitor.categorize_process("") == ProcessType.UNKNOWN
    
    @patch('src.monitor.process_monitor.psutil.process_iter')
    def test_get_running_processes(self, mock_process_iter, monitor):
        """Test getting list of running processes."""
        # Mock process data
        mock_processes = [
            MagicMock(info={'pid': 1234, 'name': 'code', 
                          'cpu_percent': 5.0, 'memory_percent': 2.5}),
            MagicMock(info={'pid': 5678, 'name': 'chrome', 
                          'cpu_percent': 10.0, 'memory_percent': 8.0}),
        ]
        mock_process_iter.return_value = mock_processes
        
        processes = monitor.get_running_processes()
        
        assert len(processes) == 2
        assert processes[0]['name'] == 'code'
        assert processes[0]['type'] == ProcessType.IDE
        assert processes[1]['name'] == 'chrome'
        assert processes[1]['type'] == ProcessType.BROWSER
    
    def test_is_coding_session_active_when_ide_active(self, monitor):
        """Test coding session detection when IDE is active."""
        # Mock IDE being active
        monitor.is_ide_active = Mock(return_value=True)
        monitor.last_activity_time = datetime.now()
        
        assert monitor.is_coding_session_active(idle_threshold_minutes=5) is True
    
    def test_is_coding_session_active_when_idle(self, monitor):
        """Test coding session detection when idle."""
        # Mock IDE being active but user idle
        monitor.is_ide_active = Mock(return_value=True)
        monitor.last_activity_time = datetime.now() - timedelta(minutes=10)
        
        assert monitor.is_coding_session_active(idle_threshold_minutes=5) is False
    
    def test_is_coding_session_active_when_no_ide(self, monitor):
        """Test coding session detection when no IDE is active."""
        # Mock no IDE active
        monitor.is_ide_active = Mock(return_value=False)
        monitor.last_activity_time = datetime.now()
        
        assert monitor.is_coding_session_active(idle_threshold_minutes=5) is False
    
    def test_get_focus_stats(self, monitor):
        """Test getting focus statistics."""
        monitor.current_focus_app = "Visual Studio Code"
        monitor.is_ide_active = Mock(return_value=True)
        monitor.is_coding_session_active = Mock(return_value=True)
        monitor.last_activity_time = datetime.now()
        
        stats = monitor.get_focus_stats()
        
        assert stats['current_app'] == "Visual Studio Code"
        assert stats['is_ide_active'] is True
        assert stats['is_coding'] is True
        assert 'last_activity' in stats
        assert stats['time_since_activity'] >= 0
    
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, monitor):
        """Test starting and stopping monitoring."""
        assert monitor.is_monitoring is False
        
        # Start monitoring in background
        import asyncio
        task = asyncio.create_task(monitor.start_monitoring())
        
        # Give it a moment to start
        await asyncio.sleep(0.1)
        assert monitor.is_monitoring is True
        
        # Stop monitoring
        monitor.stop_monitoring()
        assert monitor.is_monitoring is False
        
        # Cancel the task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass