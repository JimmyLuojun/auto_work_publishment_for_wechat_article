# -*- coding: utf-8 -*-
"""
main.py - Application Entry Point and Workflow Orchestrator.

Responsibilities:
- Parse command-line arguments (e.g., input Markdown file path).
- Initialize the application: load settings, set up logging.
- Instantiate necessary components (Parser, API Client, Publisher).
- Drive the high-level workflow: Parse -> Publish Draft.
- Handle overall application start, graceful exit, and final user feedback.

Dependencies:
- argparse: For command-line argument parsing.
- logging: For logging application start/end and errors.
- os: For path validation.
- src.core.settings: To load configuration.
- src.utils.logger: To set up logging.
- src.parsing.md_parser: To parse the input file.
- src.api.wechat.client: To interact with the WeChat API.
- src.platforms.wechat.publisher: To orchestrate the publishing process.
- typing: For type hints.

Expected Input: Command-line arguments (e.g., path to markdown file).
Expected Output: Console messages indicating success or failure. Exit code 0 on
                 success, non-zero on failure.
"""

import argparse
import logging
import os
import sys
from typing import Dict, Any, Optional

import requests

# Add src directory to Python path if running script directly for easy imports
# This might not be needed if installed as a package or using `python -m src.main`
# sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.settings import load_settings
from src.utils.logger import setup_logging
from src.parsing.md_parser import MarkdownParser
from src.api.wechat.client import WeChatAPIClient, WeChatAPIError
from src.platforms.wechat.publisher import WeChatPublisher

# Initialize logger early in case setup_logging fails
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Get root logger or specific logger

def main():
    """Main execution function."""
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Publish Markdown articles to WeChat Official Account as drafts.")
    parser.add_argument(
        "markdown_file",
        type=str,
        help="Path to the input Markdown file (e.g., data/input/article.md)",
    )
    # Add optional arguments if needed (e.g., --config, --env-file, --verbose)
    # parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # --- Initialization ---
    settings: Optional[Dict[str, Any]] = None
    try:
        # Load settings first, as they might influence logging setup
        settings = load_settings()

        # Setup logging based on loaded settings (or defaults)
        setup_logging(settings) # Reconfigures logging based on settings

        logger.info("Application starting...")
        # If verbose flag was added:
        # if args.verbose:
        #    logging.getLogger().setLevel(logging.DEBUG)
        #    for handler in logging.getLogger().handlers:
        #        handler.setLevel(logging.DEBUG)
        #    logger.debug("Verbose logging enabled.")

        # Validate input file path
        if not os.path.exists(args.markdown_file):
            logger.error(f"Input Markdown file not found: {args.markdown_file}")
            sys.exit(1) # Exit with error code

        logger.info(f"Using input Markdown file: {os.path.abspath(args.markdown_file)}")

    except Exception as e:
        logger.critical(f"Initialization failed: {e}", exc_info=True)
        sys.exit(1) # Exit if essential setup fails

    if not settings:
         logger.critical("Settings could not be loaded. Cannot continue.")
         sys.exit(1)

    # --- Instantiate Core Components ---
    # Ensure necessary settings are present before instantiating clients/publishers
    if not settings.get('WECHAT_APPID') or not settings.get('WECHAT_APPSECRET'):
         logger.critical("Missing WeChat credentials in settings. Cannot proceed.")
         sys.exit(1)

    markdown_parser = MarkdownParser()
    wechat_api_client = WeChatAPIClient(settings)
    wechat_publisher = WeChatPublisher(settings, wechat_api_client)

    # --- Core Workflow ---
    draft_media_id: Optional[str] = None
    exit_code = 0
    try:
        # 1. Parse Markdown
        logger.info(f"Parsing Markdown file: {args.markdown_file}")
        article = markdown_parser.parse_file(args.markdown_file)
        logger.info(f"Markdown parsing complete. Article Title: '{article.title}'")

        # 2. Publish Draft
        logger.info("Initiating WeChat draft publishing process...")
        draft_media_id = wechat_publisher.publish_draft(article)

        if draft_media_id:
            logger.info(f"Successfully published draft to WeChat. Draft Media ID: {draft_media_id}")
            print(f"\nSuccess! Article '{article.title}' saved as draft on WeChat.")
            print(f"Draft Media ID: {draft_media_id}")
        else:
            logger.error("Failed to publish draft to WeChat.")
            print(f"\nError: Failed to save article '{article.title}' as draft. Check logs for details.")
            exit_code = 1

    # --- Error Handling ---
    except FileNotFoundError as e:
        logger.error(f"File not found during processing: {e}")
        print(f"\nError: Input file not found. {e}")
        exit_code = 1
    except WeChatAPIError as e:
        logger.error(f"WeChat API error occurred: {e.errcode} - {e.errmsg}")
        print(f"\nError: WeChat API request failed ({e.errcode}: {e.errmsg}). Check logs.")
        exit_code = 1
    except requests.exceptions.RequestException as e:
         logger.error(f"Network error during API communication: {e}", exc_info=True)
         print(f"\nError: Network problem connecting to WeChat API. {e}")
         exit_code = 1
    except Exception as e:
        # Catch any other unexpected exceptions
        logger.critical(f"An unexpected critical error occurred: {e}", exc_info=True)
        print(f"\nCritical Error: An unexpected error occurred. Check logs for details. {e}")
        exit_code = 1

    # --- Completion ---
    logger.info(f"Application finished with exit code {exit_code}.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

# --- Explanation ---
# Purpose: Serves as the main entry point for the application when run from the
#          command line. It orchestrates the overall workflow by calling the
#          necessary modules in sequence.
# Design Choices:
# - Uses `argparse` for standard command-line argument handling.
# - Performs initialization steps (settings, logging) early.
# - Instantiates the main components (parser, API client, publisher) after
#   successful initialization.
# - Executes the core logic (parse -> publish) within a `try...except` block
#   to catch potential errors from any stage of the process.
# - Provides user-friendly feedback to the console upon success or failure.
# - Uses `sys.exit()` with appropriate exit codes (0 for success, non-zero for
#   failure) for scripting purposes.
# - Includes basic validation (checking if input file exists).
# - Catches specific expected exceptions (`FileNotFoundError`, `WeChatAPIError`,
#   `RequestException`) as well as a general `Exception` for unexpected issues.
# Improvements/Alternatives:
# - **Configuration:** Allow overriding config/env file paths via command-line args.
# - **Command Structure:** For more complex applications, use a framework like `click`
#   or `typer` to build more sophisticated command-line interfaces with subcommands
#   (e.g., `publish`, `preview`, `validate-config`).
# - **Dependency Injection Framework:** For very large applications, a dependency
#   injection framework could manage the instantiation and wiring of components,
#   but it's likely overkill here.
# - **Plugin System:** If supporting multiple platforms (besides WeChat) becomes a goal,
#   refactoring `main.py` and `platforms/` into a plugin-based architecture would be
#   beneficial.