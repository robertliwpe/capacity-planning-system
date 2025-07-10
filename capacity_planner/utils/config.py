"""Configuration management."""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv


class Config:
    """Configuration manager."""
    
    def __init__(self, env_file: Optional[str] = None):
        """Initialize configuration.
        
        Args:
            env_file: Path to .env file
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from environment variables."""
        # SSH Configuration
        self._config["ssh_key_path"] = os.getenv("SSH_KEY_PATH", "~/.ssh/id_rsa")
        self._config["default_ssh_user"] = os.getenv("DEFAULT_SSH_USER", "")
        self._config["sudo_password"] = os.getenv("SUDO_PASSWORD", "")
        
        # Database Configuration
        self._config["database_url"] = os.getenv(
            "DATABASE_URL", "sqlite:///./data/capacity_planner.db"
        )
        self._config["chroma_persist_directory"] = os.getenv(
            "CHROMA_PERSIST_DIRECTORY", "./data/chroma"
        )
        
        # Logging Configuration
        self._config["log_level"] = os.getenv("LOG_LEVEL", "INFO")
        self._config["log_file"] = os.getenv("LOG_FILE", "./logs/capacity_planner.log")
        
        # Analysis Configuration
        self._config["confidence_threshold"] = float(
            os.getenv("CONFIDENCE_THRESHOLD", "0.75")
        )
        self._config["historical_lookback_days"] = int(
            os.getenv("HISTORICAL_LOOKBACK_DAYS", "30")
        )
        self._config["max_workers"] = int(os.getenv("MAX_WORKERS", "10"))
        
        # GUI Configuration
        self._config["streamlit_port"] = int(os.getenv("STREAMLIT_PORT", "8501"))
        self._config["streamlit_server_address"] = os.getenv(
            "STREAMLIT_SERVER_ADDRESS", "localhost"
        )
        
        # Matrix Configuration
        self._config["config_matrix_path"] = os.getenv(
            "CONFIG_MATRIX_PATH",
            "/Users/robert.li/Desktop/technical-solutions/wpod-config-python/matrix_cleaned.csv"
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self._config[key] = value
    
    @property
    def ssh_key_path(self) -> str:
        """Get SSH key path."""
        path = self._config["ssh_key_path"]
        return str(Path(path).expanduser())
    
    @property
    def default_ssh_user(self) -> str:
        """Get default SSH user."""
        return self._config["default_ssh_user"]
    
    @property
    def sudo_password(self) -> str:
        """Get sudo password."""
        return self._config["sudo_password"]
    
    @property
    def database_url(self) -> str:
        """Get database URL."""
        return self._config["database_url"]
    
    @property
    def log_level(self) -> str:
        """Get log level."""
        return self._config["log_level"]
    
    @property
    def log_file(self) -> str:
        """Get log file path."""
        return self._config["log_file"]
    
    @property
    def confidence_threshold(self) -> float:
        """Get confidence threshold."""
        return self._config["confidence_threshold"]
    
    @property
    def config_matrix_path(self) -> str:
        """Get configuration matrix path."""
        return self._config["config_matrix_path"]
    
    @property
    def max_workers(self) -> int:
        """Get maximum number of workers."""
        return self._config["max_workers"]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return self._config.copy()