# /Users/junluo/Documents/auto_work_publishment_for_wechat_article/src/core/settings.py

"""
Configuration Loading Module

Purpose:
Loads application settings from environment variables (.env file) and
a configuration file (config.ini). Provides easy access to settings
constants throughout the application.

Dependencies:
- os (standard Python library)
- configparser (standard Python library)
- python-dotenv (external library)
- src.utils.logger

Expected Input:
- .env file in the project root or parent directories (for secrets).
- config.ini file in the project root.

Expected Output:
- Constants containing configuration values.
"""

import configparser
import os
import sys # Needed for potential reload_settings function if ever implemented
from pathlib import Path
from dotenv import load_dotenv
from src.utils.logger import log
import importlib # Added for potential future use if refactoring test interaction

# --- Determine Base Directory ---
# Assumes settings.py is in src/core. Adjust if structure changes.
# BASE_DIR should point to '/Users/junluo/Documents/auto_work_publishment_for_wechat_article'
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Load Environment Variables (.env) ---
# Load .env file from BASE_DIR or parent directories
env_path = BASE_DIR / '.env'
secrets_env_path = BASE_DIR / 'secrets' / '.env'

# Try loading from secrets first, then root .env. Do not override existing env vars.
# This makes testing with monkeypatch.setenv easier.
if secrets_env_path.exists():
    log.info(f"Loading environment variables from {secrets_env_path}")
    load_dotenv(dotenv_path=secrets_env_path, override=False) # Changed override to False
elif env_path.exists():
    log.info(f"Loading environment variables from {env_path}")
    load_dotenv(dotenv_path=env_path, override=False) # Changed override to False
else:
    log.warning(f".env file not found at {env_path} or {secrets_env_path}. Relying on existing environment variables.")
    # Optionally load defaults or raise error if critical env vars missing later

log.info(f"Project Base Directory: {BASE_DIR}")

# --- Load Configuration File (config.ini) ---
CONFIG_FILE_PATH = BASE_DIR / 'config.ini'
config = configparser.ConfigParser()
config_loaded = False # Flag to track successful loading

# Store original Path.exists method for potential restoration if needed,
# though monkeypatch usually handles cleanup.
# We need the *original* method before any test patching.
# Note: Accessing this *within* the module might be tricky if tests patch Path globally.
# Relying on monkeypatch's cleanup is generally safer for tests.
# Let's remove this internal reference as it can cause issues with testing frameworks.
# _original_path_exists = Path.exists

# Check for config file existence using the determined path
if not CONFIG_FILE_PATH.exists():
    log.error(f"Configuration file not found: {CONFIG_FILE_PATH}. Proceeding with defaults/environment variables where possible.")
    # config remains an empty ConfigParser object, checks later will use defaults
    config = None # Explicitly set to None to indicate missing config
else:
    try:
        # Read the config file
        read_files = config.read(CONFIG_FILE_PATH, encoding='utf-8')
        if not read_files:
            # config.read returns an empty list if the file exists but is empty or unreadable
            log.error(f"Configuration file exists but could not be read or is empty: {CONFIG_FILE_PATH}")
            config = None # Treat as failed load
        else:
            log.info(f"Loaded configuration from: {CONFIG_FILE_PATH}")
            config_loaded = True # Set flag ONLY on successful read
    except configparser.Error as e:
        log.error(f"Error reading configuration file {CONFIG_FILE_PATH}: {e}. Proceeding with defaults/environment variables.")
        config = None # Indicate config reading failed

# --- Helper Function to Safely Get Config ---
# Use a unique sentinel object to differentiate missing keys from None values
_sentinel = object()

def get_config_value(section, key, default=None, required=False):
    """
    Safely retrieves a value from the loaded configparser object.
    Uses the global 'config' and 'config_loaded' variables.
    Raises ValueError if 'required' is True and the value cannot be found.
    """
    # Determine current config path status for error messages
    # Note: CONFIG_FILE_PATH reflects the path checked at module load time.
    config_path_status = f"{CONFIG_FILE_PATH}"
    config_file_was_found_and_loaded = config is not None and config_loaded

    # Initial check: If config object is invalid (None) or wasn't loaded successfully
    if not config_file_was_found_and_loaded:
        if required:
            # Logic to determine actual reason (not found vs read error)
            # This relies on checking existence again, which might be problematic if Path is mocked by tests.
            # Simplification: Base the error message on the state determined during load.
            error_reason = "config read error or empty" if Path(CONFIG_FILE_PATH).exists() else "config file not found"
            if not Path(CONFIG_FILE_PATH).exists():
                 config_path_status += " (Not Found)"

            log.error(f"Required configuration missing: section='{section}', key='{key}' ({error_reason}). Path: {config_path_status}")
            raise ValueError(f"Missing required config: [{section}] {key} ({error_reason}, path: {config_path_status}).")
        else:
            # Config missing/invalid, not required, return default
            log.debug(f"Config key '[{section}] {key}' not found (config file missing or error), using default: {default}")
            return default

    # Config object exists and was loaded, try to get the value
    value = config.get(section, key, fallback=_sentinel) # Use sentinel fallback

    # Check if the value was found (i.e., not the sentinel)
    if value is _sentinel:
        # Value was not found in the config file section/key
        if required:
            log.error(f"Required configuration key not found in config file: section='{section}', key='{key}'. Path: {CONFIG_FILE_PATH}")
            raise ValueError(f"Missing required config key: [{section}] {key} in {CONFIG_FILE_PATH}")
        else:
            # Not required, return the provided default value
            log.debug(f"Config key '[{section}] {key}' not found, using default: {default}")
            return default
    else:
        # Value was found, return it
        return value

# --- Define Settings Constants ---

# WeChat API Settings (Prioritize Environment Variables)
WECHAT_APP_ID = os.getenv('WECHAT_APP_ID')
WECHAT_APP_SECRET = os.getenv('WECHAT_APP_SECRET')
# Get BaseUrl from config, fallback to default
WECHAT_API_BASE_URL = get_config_value('WeChatAPI', 'BaseUrl', default='https://api.weixin.qq.com')

# DeepSeek API Settings (Prioritize Environment Variables)
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
# Get BaseUrl and Model from config, fallback to defaults
DEEPSEEK_API_BASE_URL = get_config_value('DeepSeekAPI', 'BaseUrl', default='https://api.deepseek.com')
DEEPSEEK_MODEL = get_config_value('DeepSeekAPI', 'Model', default='deepseek-chat')

# OpenAI API Settings (Optional - Prioritize Environment Variables)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
# Get ImageModel from config, fallback to default
OPENAI_IMAGE_MODEL = get_config_value('OpenAIAPI', 'ImageModel', default='dall-e-3')

# File Paths (Relative to BASE_DIR, defined via config with defaults)
# **** REMOVED required=True **** to allow loading with defaults if config.ini is missing
INPUT_DIR_REL = get_config_value('Paths', 'Input', default='data/input')
OUTPUT_DIR_REL = get_config_value('Paths', 'Output', default='data/output')
# Keep other paths potentially optional or required based on actual needs
TEMPLATE_DIR_REL = get_config_value('Paths', 'Templates', default='src/templates')
SECRETS_DIR_REL = get_config_value('Paths', 'Secrets', default='secrets')

INPUT_DIR = BASE_DIR / INPUT_DIR_REL
OUTPUT_DIR = BASE_DIR / OUTPUT_DIR_REL
TEMPLATE_DIR = BASE_DIR / TEMPLATE_DIR_REL
SECRETS_DIR = BASE_DIR / SECRETS_DIR_REL
GENERATED_IMAGES_DIR = OUTPUT_DIR / 'generated_images'
INPUT_MEDIA_DIR = INPUT_DIR / 'inserting_media'
INPUT_COVER_IMAGE_DIR = INPUT_MEDIA_DIR / 'cover_image'
INPUT_CONTENT_IMAGE_DIR = INPUT_MEDIA_DIR / 'content_image'

# Ensure output directories exist
GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
# Optionally ensure input dirs exist or handle errors later
# INPUT_MEDIA_DIR.mkdir(parents=True, exist_ok=True) # Example

# Article Publishing Defaults (from config with defaults)
# **** REMOVED required=True **** for Author as an example, adjust based on actual needs
ARTICLE_AUTHOR = get_config_value('PublishingDefaults', 'Author', default='Default Author')
ARTICLE_CREATION_SOURCE = get_config_value('PublishingDefaults', 'CreationSource', default='Personal opinion, for reference only.')
# Safely get boolean values from config
mark_as_original_str = get_config_value('PublishingDefaults', 'MarkAsOriginal', default='true')
MARK_AS_ORIGINAL = mark_as_original_str.lower() == 'true'

enable_appreciation_str = get_config_value('PublishingDefaults', 'EnableAppreciation', default='true')
ENABLE_APPRECIATION = enable_appreciation_str.lower() == 'true'

enable_platform_rec_str = get_config_value('PublishingDefaults', 'EnablePlatformRecommendation', default='true')
ENABLE_PLATFORM_RECOMMENDATION = enable_platform_rec_str.lower() == 'true'

# Media Handling Mode (from config with default)
MEDIA_HANDLING_MODE = get_config_value('Media', 'Mode', default='pre-prepared').lower()

# --- Validate Critical Settings ---
# These checks run after attempting to load from env vars and config defaults
if not WECHAT_APP_ID:
    log.warning("WECHAT_APP_ID not found in environment variables or .env file.")
    # Consider raising ValueError if essential and no default mechanism exists
    # raise ValueError("WECHAT_APP_ID must be set via environment or .env file")

if not WECHAT_APP_SECRET:
    log.warning("WECHAT_APP_SECRET not found in environment variables or .env file.")
    # Consider raising ValueError if essential
    # raise ValueError("WECHAT_APP_SECRET must be set via environment or .env file")

if not DEEPSEEK_API_KEY:
    log.warning("DEEPSEEK_API_KEY not found in environment variables or .env file.")
    # Raise error only if summary generation is absolutely critical at startup
    # raise ValueError("DEEPSEEK_API_KEY must be set via environment or .env file")

if MEDIA_HANDLING_MODE == 'api-generated' and not OPENAI_API_KEY:
     log.warning("Media mode is 'api-generated' but OPENAI_API_KEY is missing in environment variables or .env file.")
     # Add checks for other potential media generation APIs if needed

log.info("Settings loading process completed.")

# Optional: Function to reload settings if needed, though generally avoided
# def reload_settings():
#     log.info("Reloading settings...")
#     # Ensure modules are available
#     import sys
#     import importlib
#     # Be cautious with reloading, it can have side effects
#     importlib.reload(sys.modules[__name__])