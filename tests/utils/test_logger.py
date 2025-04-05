import logging
import pytest
from src.utils.logger import setup_logger, LOG_FORMAT, LOG_LEVEL

def test_setup_logger_creation():
    """Test if setup_logger returns a Logger instance."""
    logger = setup_logger("test_creation_logger", logging.DEBUG)
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_creation_logger"

def test_setup_logger_level():
    """Test if the logger level is set correctly."""
    debug_logger = setup_logger("test_level_debug_logger", logging.DEBUG)
    info_logger = setup_logger("test_level_info_logger", logging.INFO)

    assert debug_logger.level == logging.DEBUG
    assert info_logger.level == logging.INFO
    # Clean up handlers for subsequent tests if run in same process
    debug_logger.handlers.clear()
    info_logger.handlers.clear()


def test_setup_logger_handler_added():
    """Test if at least one handler (console) is added."""
    logger = setup_logger("test_handler_logger", logging.INFO)
    assert len(logger.handlers) > 0
    # Check if it's a StreamHandler by default
    assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
    logger.handlers.clear() # Cleanup


def test_setup_logger_formatter():
    """Test if the handler has the correct formatter."""
    logger = setup_logger("test_formatter_logger", logging.INFO)
    assert len(logger.handlers) > 0
    # Assuming the first handler is the console handler added
    formatter = logger.handlers[0].formatter
    assert isinstance(formatter, logging.Formatter)
    # Accessing protected _fmt but common in testing
    assert formatter._fmt == LOG_FORMAT
    logger.handlers.clear() # Cleanup

def test_setup_logger_idempotency():
    """Test that calling setup_logger multiple times doesn't add duplicate handlers."""
    logger_name = "idempotent_test_logger"
    logger1 = setup_logger(logger_name, logging.INFO)
    initial_handler_count = len(logger1.handlers)
    assert initial_handler_count > 0 # Ensure handler was added first time

    logger2 = setup_logger(logger_name, logging.INFO)
    assert len(logger2.handlers) == initial_handler_count # Should not add more
    assert logger1 is logger2 # Should return the same logger instance

    logger1.handlers.clear() # Cleanup


# Example using caplog fixture (requires pytest)
def test_log_output(caplog):
    """Test if logging messages are captured with the correct level and content."""
    logger = setup_logger("test_caplog_logger", logging.INFO)
    logger.handlers.clear() # Clear default handler to avoid double logging in capture

    # Re-setup with caplog's handler implicitly added by fixture
    logger = setup_logger("test_caplog_logger", logging.INFO)

    test_message_info = "This is an info test message."
    test_message_warning = "This is a warning test message."

    with caplog.at_level(logging.INFO):
        logger.info(test_message_info)
        logger.warning(test_message_warning)
        logger.debug("This debug message should NOT be captured.") # Below INFO level

    assert test_message_info in caplog.text
    assert test_message_warning in caplog.text
    assert "This debug message should NOT be captured." not in caplog.text
    assert len(caplog.records) == 2
    assert caplog.records[0].levelname == "INFO"
    assert caplog.records[1].levelname == "WARNING"
    assert caplog.records[0].message == test_message_info

    logger.handlers.clear() # Cleanup 