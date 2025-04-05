# /Users/junluo/Documents/auto_work_publishment_for_wechat_article/src/utils/logger.py

"""
Logger Configuration Module

Purpose:
Initializes and configures a centralized logger for the application.
Provides a consistent logging format and level across different modules.

Dependencies:
- logging (standard Python library)

Expected Input: None
Expected Output: A configured logging.Logger instance.
"""

import logging
import sys

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = logging.INFO  # Default level, can be configured externally if needed

def setup_logger(name: str = 'wechat_publisher', level: int = LOG_LEVEL) -> logging.Logger:
    """
    Configures and returns a logger instance.

    Args:
        name (str): The name of the logger, typically the module name.
        level (int): The logging level (e.g., logging.INFO, logging.DEBUG).

    Returns:
        logging.Logger: The configured logger instance.
    """
    logger = logging.getLogger(name)

    # Prevent adding multiple handlers if called multiple times
    if not logger.handlers:
        logger.setLevel(level)

        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        # Formatter
        formatter = logging.Formatter(LOG_FORMAT)
        console_handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(console_handler)

        # Optional: File Handler (Uncomment if needed)
        # try:
        #     # Ensure the output directory exists if logging to a file
        #     log_file_path = 'app.log' # Consider making this configurable
        #     file_handler = logging.FileHandler(log_file_path)
        #     file_handler.setLevel(level)
        #     file_handler.setFormatter(formatter)
        #     logger.addHandler(file_handler)
        # except Exception as e:
        #     logger.warning(f"Could not configure file handler: {e}")

    return logger

# Initialize a default logger instance for easy import
log = setup_logger()

# Example Usage (in other modules):
# from src.utils.logger import log
# log.info("This is an info message.")
# log.error("This is an error message.")