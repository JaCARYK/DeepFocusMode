"""
Configuration management for Deep Focus Mode.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import logging

logger = logging.getLogger(__name__)


class Config:
    """Application configuration manager."""
    
    DEFAULT_CONFIG = {
        "api_host": "localhost",
        "api_port": 5000,
        "process_check_interval": 5,
        "keystroke_window_size": 60,
        "idle_threshold_minutes": 5,
        "database_url": None,
        "enable_ml": False,
        "log_level": "INFO",
        "blocked_domains": [],
        "productivity_apps": [],
        "focus_goal": "Complete my coding tasks without distractions"
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration.
        
        Args:
            config_path: Optional path to JSON configuration file.
        """
        self.config_path = config_path or self._get_default_config_path()
        self.config = self.DEFAULT_CONFIG.copy()
        
        # Load from file if exists
        if config_path and config_path.exists():
            self.load_from_file(config_path)
        elif self.config_path.exists():
            self.load_from_file(self.config_path)
        
        # Override with environment variables
        self.load_from_env()
    
    def _get_default_config_path(self) -> Path:
        """Get default configuration file path."""
        config_dir = Path.home() / ".deep_focus_mode"
        config_dir.mkdir(exist_ok=True)
        return config_dir / "config.json"
    
    def load_from_file(self, path: Path):
        """Load configuration from JSON file."""
        try:
            with open(path, 'r') as f:
                file_config = json.load(f)
                self.config.update(file_config)
                logger.info(f"Loaded configuration from {path}")
        except Exception as e:
            logger.warning(f"Failed to load config from {path}: {e}")
    
    def load_from_env(self):
        """Load configuration from environment variables."""
        env_mapping = {
            "DFM_API_HOST": "api_host",
            "DFM_API_PORT": ("api_port", int),
            "DFM_DATABASE_URL": "database_url",
            "DFM_LOG_LEVEL": "log_level",
            "DFM_ENABLE_ML": ("enable_ml", lambda x: x.lower() == "true")
        }
        
        for env_key, config_key in env_mapping.items():
            if env_key in os.environ:
                value = os.environ[env_key]
                
                # Handle type conversion
                if isinstance(config_key, tuple):
                    config_key, converter = config_key
                    value = converter(value)
                
                self.config[config_key] = value
                logger.debug(f"Loaded {config_key} from environment")
    
    def save(self):
        """Save current configuration to file."""
        try:
            self.config_path.parent.mkdir(exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Saved configuration to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value."""
        self.config[key] = value
    
    def update(self, updates: Dict[str, Any]):
        """Update multiple configuration values."""
        self.config.update(updates)
    
    # Convenience properties
    @property
    def api_host(self) -> str:
        return self.config["api_host"]
    
    @api_host.setter
    def api_host(self, value: str):
        self.config["api_host"] = value
    
    @property
    def api_port(self) -> int:
        return self.config["api_port"]
    
    @api_port.setter
    def api_port(self, value: int):
        self.config["api_port"] = value
    
    @property
    def database_url(self) -> Optional[str]:
        return self.config["database_url"]
    
    @property
    def log_level(self) -> str:
        return self.config["log_level"]
    
    @property
    def enable_ml(self) -> bool:
        return self.config["enable_ml"]