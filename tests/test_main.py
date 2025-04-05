# tests/test_main.py

import pytest
import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# Assume these modules are importable
from src.core.article_model import Article
from src.core import settings
from src.main import main, run_workflow

# --- Fixtures ---

@pytest.fixture(autouse=True)
def mock_dependencies(mocker):
    """Mocks external dependencies used by main and run_workflow."""
    # --- REMOVED sys.exit MOCK ---
    # mock_exit = mocker.patch('sys.exit') # No longer mocking exit globally

    mock_path_instance = MagicMock(spec=Path)
    mock_path_instance.is_file.return_value = True
    mock_path_instance.name = "test_article.md"
    mock_path_instance.resolve.return_value = mock_path_instance
    mock_path_constructor = mocker.patch('src.main.Path', return_value=mock_path_instance)

    mock_logger = mocker.patch('src.main.log')

    mock_handler = MagicMock(spec=logging.Handler)
    mock_handler.setLevel = MagicMock()
    mock_app_logger = MagicMock(spec=logging.Logger)
    mock_app_logger.handlers = [mock_handler]
    mock_app_logger.setLevel = MagicMock()
    mocker.patch('logging.getLogger', return_value=mock_app_logger)

    mock_parser_instance = MagicMock()
    mock_article = MagicMock(spec=Article)
    mock_article.title = "Mock Article"
    mock_article.cover_image_placeholder = MagicMock()
    mock_article.cover_image_placeholder.uploaded_media_id = None
    mock_parser_instance.parse_file.return_value = mock_article
    mock_parser_constructor = mocker.patch('src.main.MarkdownParser', return_value=mock_parser_instance)

    mock_uploader_instance = MagicMock()
    mock_uploader_instance.upload_article_media.return_value = True
    mock_uploader_constructor = mocker.patch('src.main.WeChatMediaUploader', return_value=mock_uploader_instance)

    mock_publisher_instance = MagicMock()
    mock_publisher_instance.publish_draft.return_value = "draft_media_id_123"
    mock_publisher_constructor = mocker.patch('src.main.WeChatPublisher', return_value=mock_publisher_instance)

    mock_wechat_client_instance = MagicMock()
    mock_wechat_client_constructor = mocker.patch('src.main.WeChatClient', return_value=mock_wechat_client_instance)

    mock_deepseek_client_instance = MagicMock()
    mock_deepseek_client_constructor = mocker.patch('src.main.DeepSeekClient', return_value=mock_deepseek_client_instance)

    mocker.patch.object(settings, 'DEEPSEEK_API_KEY', 'dummy_key', create=True)
    mocker.patch.object(settings, 'MEDIA_HANDLING_MODE', 'upload', create=True)

    mock_args = MagicMock()
    mock_args.markdown_file = "dummy_path.md"
    mock_args.no_idempotency_check = False
    mock_args.log_level = 'INFO'
    mock_argparse_parser = mocker.patch('argparse.ArgumentParser')
    mock_argparse_parser.return_value.parse_args.return_value = mock_args

    # Return mocks, excluding mock_exit
    return {
        # "mock_exit": mock_exit, # REMOVED
        "mock_path_constructor": mock_path_constructor,
        "mock_path_instance": mock_path_instance,
        "mock_logger": mock_logger,
        "mock_app_logger": mock_app_logger,
        "mock_handler": mock_handler,
        "mock_parser_constructor": mock_parser_constructor,
        "mock_parser_instance": mock_parser_instance,
        "mock_uploader_constructor": mock_uploader_constructor,
        "mock_uploader_instance": mock_uploader_instance,
        "mock_publisher_constructor": mock_publisher_constructor,
        "mock_publisher_instance": mock_publisher_instance,
        "mock_wechat_client_constructor": mock_wechat_client_constructor,
        "mock_wechat_client_instance": mock_wechat_client_instance,
        "mock_deepseek_client_constructor": mock_deepseek_client_constructor,
        "mock_deepseek_client_instance": mock_deepseek_client_instance,
        "mock_argparse": mock_argparse_parser,
        "mock_args": mock_args,
        "mock_article": mock_article
    }

@pytest.fixture
def mock_parsed_args(mock_dependencies):
    """Allows setting attributes on the mocked args object."""
    def _mock_args(**kwargs):
        for key, value in kwargs.items():
            setattr(mock_dependencies["mock_args"], key, value)
    return _mock_args

# --- Test Class ---

class TestMainWorkflow:

    # UPDATED Helper: Catches SystemExit and returns the exit code
    def run_main(self):
        """Runs the main function, catching SystemExit and returning the exit code."""
        exit_code = None # Default if no exit occurs (shouldn't happen)
        try:
            main()
            # If main finishes without sys.exit, capture 0 for tests expecting success
            # Or consider failing if exit is always expected. Assuming 0 is okay for success path.
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code # Capture the actual exit code
        except Exception as e:
            pytest.fail(f"main() raised unexpected exception: {type(e).__name__}: {e}")
        return exit_code

    # --- Tests for main() function (Updated Assertions) ---

    def test_main_successful_run(self, mock_dependencies, mock_parsed_args):
        """Test main calls run_workflow and exits successfully."""
        test_file = "path/to/real_article.md"
        mock_parsed_args(markdown_file=test_file, no_idempotency_check=False, log_level='INFO')
        mock_dependencies["mock_path_instance"].is_file.return_value = True

        # UPDATED Assertion: Check exit code returned by run_main
        assert self.run_main() == 0

        # Verify steps before run_workflow
        mock_dependencies["mock_argparse"].return_value.parse_args.assert_called_once()
        mock_dependencies["mock_path_constructor"].assert_called_once_with(test_file)
        mock_dependencies["mock_path_instance"].resolve.assert_called_once()
        mock_dependencies["mock_path_instance"].is_file.assert_called_once()
        # Verify internal workflow steps were called
        mock_dependencies["mock_parser_instance"].parse_file.assert_called_once()
        mock_dependencies["mock_uploader_instance"].upload_article_media.assert_called_once()
        mock_dependencies["mock_publisher_instance"].publish_draft.assert_called_once()
        mock_dependencies["mock_logger"].info.assert_any_call("WeChat Auto Publisher Workflow Finished Successfully")

    def test_main_no_idempotency_check_arg(self, mock_dependencies, mock_parsed_args):
        """Test main runs with check_existing=False."""
        test_file = "path/to/real_article.md"
        mock_parsed_args(markdown_file=test_file, no_idempotency_check=True, log_level='INFO')
        mock_dependencies["mock_path_instance"].is_file.return_value = True

        # UPDATED Assertion: Check exit code
        assert self.run_main() == 0

        # Verify the effect: publish_draft called with check_existing=False
        mock_dependencies["mock_publisher_instance"].publish_draft.assert_called_once()
        call_args, call_kwargs = mock_dependencies["mock_publisher_instance"].publish_draft.call_args
        assert isinstance(call_args[0], MagicMock)
        assert call_kwargs.get('check_existing') is False

    # THIS IS THE CORRECTED TEST METHOD
    def test_main_file_not_found(self, mock_dependencies, mock_parsed_args):
        """Test main exits early with code 1 if file not found."""
        test_file = "path/to/nonexistent.md"
        mock_parsed_args(markdown_file=test_file)
        mock_dependencies["mock_path_instance"].is_file.return_value = False

        # UPDATED Assertion: Check exit code returned by run_main
        assert self.run_main() == 1

        # Verify checks made *before* the exit point
        mock_dependencies["mock_argparse"].return_value.parse_args.assert_called_once()
        mock_dependencies["mock_path_constructor"].assert_called_once_with(test_file)
        mock_dependencies["mock_path_instance"].resolve.assert_called_once()
        mock_dependencies["mock_path_instance"].is_file.assert_called_once()
        mock_dependencies["mock_logger"].critical.assert_any_call(f"Input Markdown file not found: {mock_dependencies['mock_path_instance']}")

        # *** IMPORTANT ***
        # Now that sys.exit is NOT mocked, the SystemExit(1) prevents run_workflow
        # from being called. We can correctly assert its internal components were NOT called.
        mock_dependencies["mock_parser_instance"].parse_file.assert_not_called()
        mock_dependencies["mock_uploader_instance"].upload_article_media.assert_not_called()
        mock_dependencies["mock_publisher_instance"].publish_draft.assert_not_called()
        mock_dependencies["mock_wechat_client_instance"].close_session.assert_not_called()
        mock_dependencies["mock_deepseek_client_instance"].close_session.assert_not_called()

    def test_main_run_workflow_fails(self, mock_dependencies, mock_parsed_args):
        """Test main exits with code 1 if run_workflow returns False."""
        test_file = "path/to/workflow_fails.md"
        mock_parsed_args(markdown_file=test_file)
        mock_dependencies["mock_path_instance"].is_file.return_value = True
        # Make the *real* run_workflow appear to fail
        mock_dependencies["mock_publisher_instance"].publish_draft.return_value = None

        # UPDATED Assertion: Check exit code
        assert self.run_main() == 1

        # Verify the internal step that causes failure was called
        mock_dependencies["mock_publisher_instance"].publish_draft.assert_called_once()
        mock_dependencies["mock_logger"].error.assert_any_call("WeChat Auto Publisher Workflow Finished With Errors")

    @pytest.mark.parametrize(
            "level_arg, expected_level",
            [("DEBUG", logging.DEBUG), ("INFO", logging.INFO), ("WARNING", logging.WARNING), ("ERROR", logging.ERROR), ("CRITICAL", logging.CRITICAL),]
    )
    def test_main_log_level_setting(self, mock_dependencies, mock_parsed_args, level_arg, expected_level, mocker):
        """Test setting different log levels via command line."""
        test_file = "path/to/article.md"
        mock_parsed_args(markdown_file=test_file, log_level=level_arg)
        # Ensure conditions for a successful run
        mock_dependencies["mock_path_instance"].is_file.return_value = True
        mock_dependencies["mock_parser_instance"].parse_file.return_value = mock_dependencies["mock_article"]
        mock_dependencies["mock_uploader_instance"].upload_article_media.return_value = True
        mock_dependencies["mock_publisher_instance"].publish_draft.return_value = "mock_id"
        mocker.patch.object(settings, 'DEEPSEEK_API_KEY', 'dummy_key') # Ensure needed settings

        # UPDATED Assertion: Check exit code
        assert self.run_main() == 0

        # Check logger and handler levels were set
        mock_dependencies["mock_app_logger"].setLevel.assert_called_with(expected_level)
        mock_dependencies["mock_handler"].setLevel.assert_called_with(expected_level)
        mock_dependencies["mock_logger"].info.assert_any_call(f"Logging level set to: {level_arg.upper()}")

    def test_main_invalid_log_level(self, mock_dependencies, mock_parsed_args, mocker):
        """Test handling of an invalid log level argument."""
        test_file = "path/to/article.md"
        invalid_level = "VERBOSE"
        mock_parsed_args(markdown_file=test_file, log_level=invalid_level)
        # Ensure conditions for a successful run
        mock_dependencies["mock_path_instance"].is_file.return_value = True
        mock_dependencies["mock_parser_instance"].parse_file.return_value = mock_dependencies["mock_article"]
        mock_dependencies["mock_uploader_instance"].upload_article_media.return_value = True
        mock_dependencies["mock_publisher_instance"].publish_draft.return_value = "mock_id"
        mocker.patch.object(settings, 'DEEPSEEK_API_KEY', 'dummy_key') # Ensure needed settings

        # UPDATED Assertion: Check exit code
        assert self.run_main() == 0

        # Check warning log for invalid level
        mock_dependencies["mock_logger"].warning.assert_any_call(f"Invalid log level specified: {invalid_level}. Using default INFO.")
        assert call(None) not in mock_dependencies["mock_app_logger"].setLevel.call_args_list
        assert call(None) not in mock_dependencies["mock_handler"].setLevel.call_args_list

    # --- Tests for run_workflow() function ---
    # These test run_workflow directly and don't need exit code checks

    def test_run_workflow_success(self, mock_dependencies, mocker):
        """Test run_workflow internal logic on success"""
        for mock_obj in mock_dependencies.values():
            if isinstance(mock_obj, MagicMock): mock_obj.reset_mock()
        mocker.patch.object(settings, 'DEEPSEEK_API_KEY', 'dummy_key')
        result = run_workflow(mock_dependencies["mock_path_instance"], check_existing_draft=True)
        assert result is True
        mock_dependencies["mock_wechat_client_constructor"].assert_called_once()
        mock_dependencies["mock_deepseek_client_constructor"].assert_called_once()
        mock_dependencies["mock_parser_constructor"].assert_called_once()
        mock_dependencies["mock_uploader_constructor"].assert_called_once_with(client=mock_dependencies["mock_wechat_client_instance"])
        mock_dependencies["mock_publisher_constructor"].assert_called_once_with(wechat_client=mock_dependencies["mock_wechat_client_instance"], deepseek_client=mock_dependencies["mock_deepseek_client_instance"])
        mock_dependencies["mock_parser_instance"].parse_file.assert_called_once_with(mock_dependencies["mock_path_instance"])
        mock_dependencies["mock_uploader_instance"].upload_article_media.assert_called_once_with(mock_dependencies["mock_article"])
        mock_dependencies["mock_publisher_instance"].publish_draft.assert_called_once_with(mock_dependencies["mock_article"], check_existing=True)
        mock_dependencies["mock_wechat_client_instance"].close_session.assert_called_once()
        mock_dependencies["mock_deepseek_client_instance"].close_session.assert_called_once()

    def test_run_workflow_parser_fails(self, mock_dependencies, mocker):
        """Test run_workflow failure if parser fails"""
        for mock_obj in mock_dependencies.values():
             if isinstance(mock_obj, MagicMock): mock_obj.reset_mock()
        mocker.patch.object(settings, 'DEEPSEEK_API_KEY', 'dummy_key')
        mock_dependencies["mock_parser_instance"].parse_file.return_value = None
        result = run_workflow(mock_dependencies["mock_path_instance"], check_existing_draft=True)
        assert result is False
        mock_dependencies["mock_uploader_instance"].upload_article_media.assert_not_called()
        mock_dependencies["mock_publisher_instance"].publish_draft.assert_not_called()
        mock_dependencies["mock_wechat_client_instance"].close_session.assert_called_once()
        mock_dependencies["mock_deepseek_client_instance"].close_session.assert_called_once()

    def test_run_workflow_uploader_fails(self, mock_dependencies, mocker):
        """Test run_workflow failure if uploader fails critically"""
        for mock_obj in mock_dependencies.values():
             if isinstance(mock_obj, MagicMock): mock_obj.reset_mock()
        mocker.patch.object(settings, 'DEEPSEEK_API_KEY', 'dummy_key')
        mock_dependencies["mock_uploader_instance"].upload_article_media.return_value = False
        result = run_workflow(mock_dependencies["mock_path_instance"], check_existing_draft=True)
        assert result is False
        mock_dependencies["mock_publisher_instance"].publish_draft.assert_not_called()
        mock_dependencies["mock_wechat_client_instance"].close_session.assert_called_once()
        mock_dependencies["mock_deepseek_client_instance"].close_session.assert_called_once()

    def test_run_workflow_publisher_fails(self, mock_dependencies, mocker):
        """Test run_workflow failure if publisher fails"""
        for mock_obj in mock_dependencies.values():
             if isinstance(mock_obj, MagicMock): mock_obj.reset_mock()
        mocker.patch.object(settings, 'DEEPSEEK_API_KEY', 'dummy_key')
        mock_dependencies["mock_publisher_instance"].publish_draft.return_value = None
        result = run_workflow(mock_dependencies["mock_path_instance"], check_existing_draft=True)
        assert result is False
        mock_dependencies["mock_wechat_client_instance"].close_session.assert_called_once()
        mock_dependencies["mock_deepseek_client_instance"].close_session.assert_called_once()

    def test_run_workflow_no_deepseek_key(self, mock_dependencies, mocker):
        """Test run_workflow without deepseek key"""
        for mock_obj in mock_dependencies.values():
             if isinstance(mock_obj, MagicMock): mock_obj.reset_mock()
        mocker.patch.object(settings, 'DEEPSEEK_API_KEY', None) # Override setting
        result = run_workflow(mock_dependencies["mock_path_instance"], check_existing_draft=True)
        assert result is True
        mock_dependencies["mock_deepseek_client_constructor"].assert_not_called()
        mock_dependencies["mock_deepseek_client_instance"].close_session.assert_not_called()
        mock_dependencies["mock_publisher_constructor"].assert_called_once_with(wechat_client=mock_dependencies["mock_wechat_client_instance"], deepseek_client=None)
        mock_dependencies["mock_publisher_instance"].publish_draft.assert_called_once()
        mock_dependencies["mock_wechat_client_instance"].close_session.assert_called_once()