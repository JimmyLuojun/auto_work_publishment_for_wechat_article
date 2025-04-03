import requests
from typing import Optional, Dict, Any
import logging

class BaseAPIClient:
    """Base class for API clients with common functionality."""
    
    def __init__(self):
        self.session = requests.Session()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _make_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        files: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Make an HTTP request with error handling and logging."""
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                files=files,
                headers=headers,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {str(e)}")
            raise 