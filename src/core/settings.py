# -*- coding: utf-8 -*-
"""
settings.py - Loads and provides application configuration.

Responsibilities:
- Load sensitive credentials from the .env file at the project root.
- Load non-sensitive settings from config.ini at the project root.
- Merge settings, potentially prioritizing .env over config.ini.
- Provide a unified way to access configuration values.

Dependencies:
- os: For path manipulation.
- dotenv: To load .env files.
- configparser: To parse .ini files.
- logging: To log information and errors during loading.

Expected Input:
- A .env file in the project root (containing WECHAT_APPID, WECHAT_APPSECRET).
- A config.ini file in the project root.

Expected Output:
- A dictionary containing all loaded configuration settings.
"""

import configparser
import logging
import os
from typing import Dict, Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Determine the project root directory relative to this file
# Assumes settings.py is in src/core/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(PROJECT_ROOT, '.env')
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'config.ini')

def load_settings() -> Dict[str, Any]:
    """
    Loads settings from .env and config.ini.

    .env variables take precedence over config.ini values if names collide
    after case normalization (config keys are lowercased).

    Returns:
        Dict[str, Any]: A dictionary containing the merged settings.
    """
    settings: Dict[str, Any] = {}

    # 1. Load from .env (Highest Priority)
    try:
        # load_dotenv will find the .env file automatically if it's in the root
        # or parent directories, but specifying the path is more explicit.
        loaded_env = load_dotenv(dotenv_path=ENV_PATH, verbose=True)
        if loaded_env:
            logger.info(f"Loaded environment variables from: {ENV_PATH}")
            # Add .env variables to settings
            settings['WECHAT_APPID'] = os.getenv('WECHAT_APPID')
            settings['WECHAT_APPSECRET'] = os.getenv('WECHAT_APPSECRET')
            # Add other potential secrets here (e.g., OPENAI_API_KEY)
            # settings['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
        else:
             logger.warning(f".env file not found or empty at: {ENV_PATH}. "
                           "Ensure it exists and contains necessary credentials.")

        # Validate essential secrets
        if not settings.get('WECHAT_APPID') or not settings.get('WECHAT_APPSECRET'):
            logger.error("WECHAT_APPID or WECHAT_APPSECRET not found in .env file. "
                         "These are required for WeChat API interaction.")
            # Depending on requirements, you might raise an error here:
            # raise ValueError("Missing required WeChat API credentials in .env")

    except Exception as e:
        logger.error(f"Error loading .env file from {ENV_PATH}: {e}", exc_info=True)
        # Decide if the application can continue without .env

    # 2. Load from config.ini (Lower Priority)
    config = configparser.ConfigParser()
    try:
        if os.path.exists(CONFIG_PATH):
            config.read(CONFIG_PATH)
            logger.info(f"Loaded configuration from: {CONFIG_PATH}")
            for section in config.sections():
                section_lower = section.lower()
                settings[section_lower] = {}
                for key, value in config.items(section):
                    # Store keys in lowercase for consistency, unless already set by .env
                    setting_key = key.lower()
                    # Simple type inference (can be expanded if needed)
                    processed_value: Any = value
                    if value.lower() in ['true', 'yes', 'on']:
                        processed_value = True
                    elif value.lower() in ['false', 'no', 'off']:
                        processed_value = False
                    elif value.isdigit():
                        processed_value = int(value)
                    elif '.' in value and all(part.isdigit() or part == '' for part in value.split('.', 1)):
                        try:
                            processed_value = float(value)
                        except ValueError:
                            pass # Keep as string if float conversion fails

                    # Only add if not already set by .env (more specific checks might be needed)
                    # A simple check: don't overwrite top-level keys potentially set by .env
                    # A better approach might be to check section.key against ENV_VAR names
                    if section_lower not in settings or setting_key not in settings[section_lower]:
                         # Store config.ini values under their section name (lowercased)
                         settings[section_lower][setting_key] = processed_value
                    else:
                        logger.debug(f"Skipping config setting {section}.{key} as it might conflict with .env")

            # Provide direct access to common settings if desired, merging intelligently
            # Example: Make wechat settings directly accessible
            if 'wechat' in settings:
                for k, v in settings['wechat'].items():
                    settings.setdefault(f'wechat_{k}', v) # e.g., settings['wechat_default_author']

        else:
            logger.warning(f"Configuration file not found at: {CONFIG_PATH}")

    except configparser.Error as e:
        logger.error(f"Error parsing config.ini file from {CONFIG_PATH}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error loading config.ini from {CONFIG_PATH}: {e}", exc_info=True)


    logger.debug(f"Final loaded settings (secrets masked): "
                 f"{{k: ('***' if 'SECRET' in k or 'APPID' in k else v) "
                 f"for k, v in settings.items() if isinstance(v, (str, type(None)))}}")

    return settings

# --- Explanation ---
# Purpose: Centralizes configuration loading from different sources (.env for secrets,
#          config.ini for general settings). This separation is crucial for security
#          and flexibility.
# Design Choices:
# - Uses standard libraries `dotenv` and `configparser`.
# - Prioritizes .env variables for secrets.
# - Stores config.ini values under section keys (e.g., settings['wechat']['default_author']).
# - Includes basic logging for transparency and debugging loading issues.
# - Includes basic type inference for config.ini values (can be made more robust).
# - Explicitly checks for essential secrets (AppID, AppSecret).
# Improvements/Alternatives:
# - Use a dedicated settings management library like Pydantic's BaseSettings for
#   automatic environment variable mapping, type validation, and potentially
#   loading from other sources.
# - Implement more sophisticated merging logic if complex overrides are needed.
# - Add more robust type validation/conversion for config.ini values.