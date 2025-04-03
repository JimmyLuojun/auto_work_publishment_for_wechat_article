import os
from pathlib import Path
from typing import Dict, Any
import configparser
from dotenv import load_dotenv

class Settings:
    """Central configuration management for the application."""
    
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()
        
        # Initialize config parser
        self.config = configparser.ConfigParser()
        
        # Set default paths
        self.base_dir = Path(__file__).parent.parent.parent
        self.data_dir = self.base_dir / "data"
        self.input_dir = self.data_dir / "input"
        self.output_dir = self.data_dir / "output"
        
        # Load config.ini if it exists
        config_path = self.base_dir / "config.ini"
        if config_path.exists():
            self.config.read(config_path)
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a configuration value with fallback to environment variables."""
        # Try config.ini first
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            # Fall back to environment variables
            env_key = f"{section.upper()}_{key.upper()}"
            return os.getenv(env_key, default)
    
    @property
    def wechat_app_id(self) -> str:
        """Get WeChat App ID."""
        return self.get("wechat", "app_id", "")
    
    @property
    def wechat_app_secret(self) -> str:
        """Get WeChat App Secret."""
        return self.get("wechat", "app_secret", "")
    
    @property
    def openai_api_key(self) -> str:
        """Get OpenAI API Key."""
        return self.get("openai", "api_key", "")
    
    @property
    def deepseek_api_key(self) -> str:
        """Get DeepSeek API Key."""
        return self.get("deepseek", "api_key", "")

# Create a singleton instance
settings = Settings() 