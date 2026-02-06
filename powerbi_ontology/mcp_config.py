"""
Configuration loader for MCP Server.

Loads and validates configuration from YAML file.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Default configuration
DEFAULT_CONFIG = {
    "server": {
        "name": "PowerBI Ontology Extractor MCP",
        "version": "0.1.0",
        "description": "Extract semantic intelligence from Power BI files via MCP",
    },
    "log_level": "INFO",
    "extraction": {
        "include_measures": True,
        "include_security": True,
        "cleanup_temp": True,
        "max_file_size_mb": 100,
    },
    "export": {
        "default_format": "xml",
        "include_action_rules": True,
        "include_constraints": True,
        "default_roles": ["Admin", "Analyst", "Viewer"],
    },
    "analysis": {
        "similarity_threshold": 0.8,
    },
    "chat": {
        "model": "gpt-4o-mini",
        "temperature": 0.3,
        "max_tokens": 1000,
    },
    "security": {
        "allowed_paths": [],
    },
    "cache": {
        "enabled": True,
        "ttl_seconds": 3600,
    },
}


class MCPConfig:
    """Configuration manager for MCP Server."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to config.yaml file. If None, checks:
                        1. POWERBI_MCP_CONFIG environment variable
                        2. config/mcp_config.yaml relative to package
                        3. Uses default configuration
        """
        self._config: Dict[str, Any] = DEFAULT_CONFIG.copy()
        self._config_path: Optional[str] = None

        # Load configuration
        self._load_config(config_path)

    def _load_config(self, config_path: Optional[str] = None):
        """Load configuration from YAML file."""
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML not installed, using default configuration")
            return

        # Determine config path
        if config_path is None:
            config_path = os.getenv("POWERBI_MCP_CONFIG")

        if config_path is None or not Path(config_path).exists():
            # Try default locations
            possible_paths = [
                Path("config/mcp_config.yaml"),
                Path(__file__).parent.parent / "config" / "mcp_config.yaml",
                Path.home() / ".powerbi-ontology" / "mcp_config.yaml",
            ]

            for path in possible_paths:
                if path.exists():
                    config_path = str(path)
                    break

        if config_path is None or not Path(config_path).exists():
            logger.info("No config file found, using default configuration")
            return

        self._config_path = config_path
        logger.info(f"Loading configuration from: {config_path}")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded_config = yaml.safe_load(f) or {}

            # Deep merge with defaults
            self._config = self._deep_merge(DEFAULT_CONFIG, loaded_config)
            logger.info("Configuration loaded successfully")

        except Exception as e:
            logger.warning(f"Error loading config file: {e}, using defaults")

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    # Server settings
    @property
    def server_name(self) -> str:
        return self._config["server"]["name"]

    @property
    def server_version(self) -> str:
        return self._config["server"]["version"]

    @property
    def server_description(self) -> str:
        return self._config["server"]["description"]

    # Logging
    @property
    def log_level(self) -> str:
        return self._config.get("log_level", "INFO").upper()

    # Extraction settings
    @property
    def include_measures(self) -> bool:
        return self._config["extraction"]["include_measures"]

    @property
    def include_security(self) -> bool:
        return self._config["extraction"]["include_security"]

    @property
    def cleanup_temp(self) -> bool:
        return self._config["extraction"]["cleanup_temp"]

    @property
    def max_file_size_mb(self) -> int:
        return self._config["extraction"]["max_file_size_mb"]

    # Export settings
    @property
    def default_format(self) -> str:
        return self._config["export"]["default_format"]

    @property
    def include_action_rules(self) -> bool:
        return self._config["export"]["include_action_rules"]

    @property
    def include_constraints(self) -> bool:
        return self._config["export"]["include_constraints"]

    @property
    def default_roles(self) -> List[str]:
        return self._config["export"]["default_roles"]

    # Analysis settings
    @property
    def similarity_threshold(self) -> float:
        return self._config["analysis"]["similarity_threshold"]

    # Chat settings
    @property
    def chat_model(self) -> str:
        return self._config["chat"]["model"]

    @property
    def chat_temperature(self) -> float:
        return self._config["chat"]["temperature"]

    @property
    def chat_max_tokens(self) -> int:
        return self._config["chat"]["max_tokens"]

    # Security settings
    @property
    def allowed_paths(self) -> List[str]:
        return self._config.get("security", {}).get("allowed_paths", [])

    # Cache settings
    @property
    def cache_enabled(self) -> bool:
        return self._config["cache"]["enabled"]

    @property
    def cache_ttl(self) -> int:
        return self._config["cache"]["ttl_seconds"]

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key."""
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self._config.copy()


# Global configuration instance
_config: Optional[MCPConfig] = None


def get_config() -> MCPConfig:
    """Get or create global configuration instance."""
    global _config
    if _config is None:
        _config = MCPConfig()
    return _config


def reload_config(config_path: Optional[str] = None) -> MCPConfig:
    """Reload configuration from file."""
    global _config
    _config = MCPConfig(config_path)
    return _config
