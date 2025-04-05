# /Users/junluo/Documents/auto_work_publishment_for_wechat_article/src/api/deepseek/deepseek_api.py

"""
DeepSeek API Client

Purpose:
Provides methods to interact with the DeepSeek API, specifically for
generating text summaries based on input content.

Dependencies:
- typing (standard Python library)
- src.api.base_client.BaseApiClient
- src.core.settings
- src.utils.logger

Expected Input: Requires DeepSeek API Key configured in settings.
Expected Output: Methods return generated text (summary) or None on failure.
"""

from typing import Optional, Dict, Any, List, Tuple

from src.api.base_client import BaseApiClient
from src.core import settings
from src.utils.logger import log

# DeepSeek API Endpoints (Consult DeepSeek documentation for specifics)
ENDPOINT_CHAT_COMPLETIONS = '/v1/chat/completions'

class DeepSeekClient(BaseApiClient):
    """
    Client for interacting with the DeepSeek API (specifically Chat Completions).
    """

    def __init__(self):
        """Initializes the DeepSeekClient."""
        if not settings.DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY must be configured in .env")

        super().__init__(base_url=settings.DEEPSEEK_API_BASE_URL, api_key=settings.DEEPSEEK_API_KEY)
        self.model = settings.DEEPSEEK_MODEL
        log.info("DeepSeekClient initialized.")

    def _authenticate(self) -> Dict[str, str]:
        """Handles authentication by adding the API key to headers."""
        if not self.api_key:
             # Should have been caught in __init__, but double-check
            raise ValueError("DeepSeek API Key is not set.")
        return {'Authorization': f'Bearer {self.api_key}'}

    def _make_request(self, *args, **kwargs) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """ Overrides base method to automatically add auth headers. """
        auth_headers = self._authenticate()
        current_headers = kwargs.get('headers', {})
        merged_headers = {**auth_headers, **current_headers} # Add auth header
        kwargs['headers'] = merged_headers
        return super()._make_request(*args, **kwargs)

    def generate_summary(self, text_content: str, max_tokens: int = 150, instruction: Optional[str] = None) -> Optional[str]:
        """
        Generates a summary for the given text content using the DeepSeek Chat API.

        Args:
            text_content (str): The text content to summarize.
            max_tokens (int): The maximum number of tokens for the summary.
            instruction (Optional[str]): An optional specific instruction for the summarization task.

        Returns:
            Optional[str]: The generated summary text, or None if generation fails.
        """
        if not text_content:
            log.warning("Cannot generate summary for empty text content.")
            return None

        default_instruction = (
            "Please generate a concise and engaging summary of the following text, suitable for a WeChat article abstract. "
            "The summary should capture the main points and be approximately 50-120 characters long. "
            "Focus on the key message or takeaway."
            # " Ensure the summary does not exceed 120 characters." # Note: Character limits are hard for LLMs, token limits are better control.
        )
        prompt_instruction = instruction if instruction else default_instruction

        # Construct the messages payload for the Chat API
        messages = [
            {"role": "system", "content": prompt_instruction},
            {"role": "user", "content": text_content[:4000]} # Limit input length if necessary
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7, # Adjust creativity/factuality
            "stream": False # We want the complete response
        }

        log.info(f"Requesting summary from DeepSeek model {self.model}...")
        log.debug(f"DeepSeek Payload: {payload}")

        response_data, error = self._make_request(
            'POST',
            ENDPOINT_CHAT_COMPLETIONS,
            json_payload=payload
        )

        if error or not response_data:
            log.error(f"Failed to generate summary using DeepSeek. Error: {error or 'No data received'}")
            return None

        # Check for API-specific errors if DeepSeek returns them in the JSON body
        if response_data.get('error'):
             log.error(f"DeepSeek API error: {response_data.get('error')}")
             return None

        try:
            # Extract the summary from the response structure
            # Adjust path based on actual DeepSeek API response format
            summary = response_data['choices'][0]['message']['content'].strip()
            log.info(f"Successfully generated summary (length {len(summary)}): '{summary[:100]}...'")
            # Simple post-processing: remove potential quotation marks if needed
            summary = summary.strip('"\'')
            return summary
        except (KeyError, IndexError, TypeError) as e:
            log.error(f"Failed to parse summary from DeepSeek response: {e}. Response: {response_data}")
            return None