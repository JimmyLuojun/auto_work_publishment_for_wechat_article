# /Users/junluo/Documents/auto_work_publishment_for_wechat_article/src/main.py

"""
Main Application Entry Point (Refined)

Purpose:
Orchestrates the entire workflow of parsing a Markdown article, handling media,
generating summaries, and publishing the result as a draft to WeChat.
Includes improved error handling per step and guaranteed resource cleanup.

Workflow:
1. Parse command-line arguments & Setup logging.
2. Validate input Markdown file existence.
3. Initialize API clients (WeChat, DeepSeek) and core services (Parser, Uploader, Publisher).
4. Execute main workflow within a try...finally block:
    a. Parse Markdown file. Exit on failure.
    b. Upload media (cover + content). Exit on critical (cover) failure.
    c. Publish draft to WeChat. Log success/failure.
5. Ensure API client sessions are closed in the 'finally' block.
6. Log final status and exit with appropriate code.

Dependencies: (Same as before)
- argparse, pathlib, sys, logging
- src.utils.logger, src.core.settings, src.core.article_model
- src.parsing.md_parser, src.api.wechat.client, src.api.deepseek.deepseek_api
- src.platforms.wechat.media_uploader, src.platforms.wechat.publisher

Execution:
python src/main.py <path_to_markdown_file.md> [--no-idempotency-check] [--log-level LEVEL]
"""

import argparse
import sys
import logging # Import logging module directly for level setting
from pathlib import Path
from typing import Optional

# --- Core Application Imports ---
# Logger is initialized here, settings loaded on import
from src.utils.logger import log, setup_logger
from src.core import settings
from src.core.article_model import Article
from src.parsing.md_parser import MarkdownParser
from src.api.wechat.client import WeChatClient
from src.api.deepseek.deepseek_api import DeepSeekClient
from src.platforms.wechat.media_uploader import WeChatMediaUploader
from src.platforms.wechat.publisher import WeChatPublisher

def run_workflow(markdown_path: Path, check_existing_draft: bool):
    """
    Encapsulates the main workflow logic.

    Args:
        markdown_path (Path): Path to the input Markdown file.
        check_existing_draft (bool): Whether to perform idempotency check.

    Returns:
        bool: True if the workflow completed successfully (draft published), False otherwise.
    """
    # --- Initialize Clients and Services ---
    # Declare variables outside try block for finally clause access
    wechat_client: Optional[WeChatClient] = None
    deepseek_client: Optional[DeepSeekClient] = None
    exit_code = 1 # Default to failure exit code
    draft_media_id: Optional[str] = None

    try:
        log.info("Initializing API Clients...")
        wechat_client = WeChatClient()

        if settings.DEEPSEEK_API_KEY:
            deepseek_client = DeepSeekClient()
            log.info("DeepSeekClient initialized.")
        else:
            log.warning("DeepSeek API Key not found, summary generation will be skipped.")

        log.info("Initializing Core Services...")
        md_parser = MarkdownParser()
        media_uploader = WeChatMediaUploader(client=wechat_client)
        publisher = WeChatPublisher(wechat_client=wechat_client, deepseek_client=deepseek_client)
        log.info("Initialization complete.")

        # --- Step 1: Parse Markdown ---
        log.info(f"--- Starting Step 1: Parse Markdown [{markdown_path.name}] ---")
        article: Optional[Article] = None
        try:
            article = md_parser.parse_file(markdown_path)
            if not article:
                # Error should have been logged by parser
                log.critical("Markdown parsing failed. See previous errors.")
                return False # Indicate workflow failure
            log.info(f"Successfully parsed Markdown. Title: '{article.title}'")
        except Exception as e:
            log.critical(f"An unexpected error occurred during Markdown parsing: {e}", exc_info=True)
            return False # Indicate workflow failure

        # --- Step 2: Handle Media Uploads ---
        log.info(f"--- Starting Step 2: Upload Media [{article.title}] ---")
        media_success: bool = False
        try:
            # upload_article_media returns False only if *cover* upload fails
            media_success = media_uploader.upload_article_media(article)
            if not media_success:
                 # Critical error (cover fail) logged by uploader
                 log.critical("Media handling failed critically (cover image).")
                 return False # Indicate workflow failure
            # If media_success is True, content media might still have failed (logged as warnings)
            log.info("Media handling step completed.")
        except Exception as e:
            log.critical(f"An unexpected error occurred during media handling: {e}", exc_info=True)
            return False # Indicate workflow failure

        # --- Step 3: Publish Draft ---
        log.info(f"--- Starting Step 3: Publish Draft [{article.title}] ---")
        try:
            draft_media_id = publisher.publish_draft(article, check_existing=check_existing_draft)
            if draft_media_id:
                log.info(f"Successfully published draft. Media ID: {draft_media_id}")
                exit_code = 0 # Mark as success
            else:
                # Error should have been logged by publisher
                log.error("Publishing draft failed. See previous errors.")
                exit_code = 1 # Mark as failure
        except Exception as e:
            log.critical(f"An unexpected error occurred during draft publishing: {e}", exc_info=True)
            exit_code = 1 # Mark as failure

        # If we reach here, return True if exit_code is 0 (success), False otherwise
        return exit_code == 0

    finally:
        # --- Resource Cleanup ---
        log.info("Closing API client sessions...")
        if wechat_client:
            try:
                wechat_client.close_session()
            except Exception as e:
                log.warning(f"Error closing WeChat client session: {e}", exc_info=True)
        if deepseek_client:
            try:
                deepseek_client.close_session()
            except Exception as e:
                log.warning(f"Error closing DeepSeek client session: {e}", exc_info=True)
        log.info("Resource cleanup finished.")


def main():
    """Main execution function: parses arguments and calls the workflow."""
    # --- Argument Parsing and Logging Setup ---
    log.info("=================================================")
    log.info("Starting WeChat Auto Publisher Workflow")
    log.info(f"Media Handling Mode: {settings.MEDIA_HANDLING_MODE}")
    log.info(f"Current Time (UTC): {log.handlers[0].formatter.converter(None)}")  # Log timestamp format info
    log.info("=================================================")

    parser = argparse.ArgumentParser(description="Parse Markdown and publish to WeChat drafts.")
    parser.add_argument(
        "markdown_file",
        type=str,
        help="Path to the input Markdown file (.md)."
    )
    parser.add_argument(
        "--no-idempotency-check",
        action="store_true",
        help="Skip checking for existing drafts with the same title before creating a new one."
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set the logging level (default: INFO).'
    )

    args = parser.parse_args()

    # Check if the markdown file exists before proceeding
    markdown_path = Path(args.markdown_file).resolve()  # Resolve to absolute path early
    if not markdown_path.is_file():
        log.critical(f"Input Markdown file not found: {markdown_path}")
        sys.exit(1)  # Exit immediately if the file does not exist

    # Configure logger level based on arguments
    log_level_name = args.log_level.upper()
    log_level = getattr(logging, log_level_name, None)
    if isinstance(log_level, int):
         # Get the specific logger instance returned by setup_logger and set its level
         app_logger = logging.getLogger('wechat_publisher')  # Use the name defined in logger.py
         app_logger.setLevel(log_level)
         # Also set level on handlers if needed, though setting logger level is usually enough
         for handler in app_logger.handlers:
              handler.setLevel(log_level)
         log.info(f"Logging level set to: {log_level_name}")
    else:
        log.warning(f"Invalid log level specified: {args.log_level}. Using default INFO.")

    # --- Execute Workflow ---
    check_existing_draft = not args.no_idempotency_check
    workflow_successful = run_workflow(markdown_path, check_existing_draft)

    # --- Final Status ---
    log.info("=================================================")
    if workflow_successful:
        log.info("WeChat Auto Publisher Workflow Finished Successfully")
        exit_code = 0
    else:
        log.error("WeChat Auto Publisher Workflow Finished With Errors")
        exit_code = 1
    log.info("=================================================")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()