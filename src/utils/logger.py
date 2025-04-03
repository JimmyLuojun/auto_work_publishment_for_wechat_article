# -*- coding: utf-8 -*-
"""
logger.py - Configures application-wide logging.

Responsibilities:
- Set up the root logger with appropriate level, format, and handlers.
- Centralize logging configuration for consistency.

Dependencies:
- logging: Standard Python logging library.
- logging.config: For dictionary-based configuration (optional but flexible).
- os: To construct file paths.

Expected Input: Optionally, configuration settings (e.g., log level, file path).
Expected Output: None (Configures the logging system).
"""

import logging
import logging.config
import os
from typing import Dict, Any

# Assumes logger.py is in src/utils/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO", # Default console level
            "formatter": "standard",
            "stream": "ext://sys.stdout", # Use stdout
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG", # Default file level (more verbose)
            "formatter": "detailed",
            "filename": os.path.join(PROJECT_ROOT, "app.log"), # Default log file name
            "maxBytes": 10485760,  # 10MB
            "backupCount": 3,
            "encoding": "utf8",
        },
    },
    "loggers": {
        "": { # Root logger
            "handlers": ["console", "file"],
            "level": "DEBUG", # Set root logger level to lowest (handlers control output)
            "propagate": False, # Avoid duplicating messages if other loggers are configured
        },
        # Example: Quieter logging for noisy libraries
        "requests": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
         "urllib3": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

def setup_logging(settings: Dict[str, Any] = None):
    """
    Configures the logging system using a dictionary configuration.

    Args:
        settings (Dict[str, Any], optional): Application settings dictionary.
                                             Can override defaults like log level/file path.
                                             Defaults to None.
    """
    config = DEFAULT_LOG_CONFIG.copy() # Start with defaults

    # Override defaults using application settings if provided
    if settings:
        log_settings = settings.get('logging', {})
        log_level_str = log_settings.get('level', 'INFO').upper()
        log_level = getattr(logging, log_level_str, logging.INFO)

        # Update handler levels
        config['handlers']['console']['level'] = log_level_str
        # Keep file logging potentially more verbose unless specified otherwise
        config['handlers']['file']['level'] = log_settings.get('file_level', 'DEBUG').upper()

        # Update root logger level if needed (usually DEBUG is fine if handlers filter)
        # config['loggers']['']['level'] = log_level_str

        # Update log file path
        paths_settings = settings.get('paths', {})
        log_file = paths_settings.get('log_file', 'app.log')
        # Ensure log file path is absolute or relative to project root
        if not os.path.isabs(log_file):
            log_file = os.path.join(PROJECT_ROOT, log_file)
        config['handlers']['file']['filename'] = log_file
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
             try:
                 os.makedirs(log_dir)
             except OSError as e:
                 logging.error(f"Could not create log directory {log_dir}: {e}")


    try:
        logging.config.dictConfig(config)
        logging.info("Logging configured successfully.")
        logging.debug(f"Log file path: {config['handlers']['file']['filename']}")
        logging.debug(f"Console log level: {config['handlers']['console']['level']}")
        logging.debug(f"File log level: {config['handlers']['file']['level']}")
    except Exception as e:
        # Fallback to basic config if dictConfig fails
        logging.basicConfig(level=logging.INFO)
        logging.error(f"Error configuring logging with dictConfig: {e}. Falling back to basicConfig.", exc_info=True)


# --- Explanation ---
# Purpose: To provide a single point of configuration for logging across the
#          entire application, ensuring consistent format and output destinations.
# Design Choices:
# - Uses `logging.config.dictConfig` which is flexible for defining formatters,
#   handlers (console, rotating file), and levels for different loggers.
# - Defines default settings but allows overrides via the main `settings` dict.
# - Configures a console handler (for immediate feedback) and a rotating file
#   handler (for persistent, detailed logs).
# - Sets different default levels for console (INFO) and file (DEBUG) handlers.
# - Quiets down noisy libraries like `requests` by default.
# - Includes basic error handling for configuration and directory creation.
# Improvements/Alternatives:
# - Could add more handlers (e.g., SysLogHandler, HTTPHandler) if needed.
# - Could use environment variables directly for log level overrides.
# - For very complex scenarios, external logging configuration files (JSON, YAML)
#   could be loaded.