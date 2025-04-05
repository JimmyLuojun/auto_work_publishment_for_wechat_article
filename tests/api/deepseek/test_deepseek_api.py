# tests/api/deepseek/test_deepseek_api.py

import pytest
from unittest.mock import MagicMock, patch, ANY # Import ANY for flexible matching

# Modules to test
from src.api.deepseek.deepseek_api import DeepSeekClient, ENDPOINT_CHAT_COMPLETIONS
from src.core import settings
from src.api.base_client import BaseApiClient # Import BaseApiClient for patching target

# --- Fixtures ---

@pytest.fixture
def mock_settings_deepseek(mocker):
    """Mocks settings used by DeepSeekClient."""
    mocker.patch('src.core.settings.DEEPSEEK_API_KEY', 'test-deepseek-key')
    mocker.patch('src.core.settings.DEEPSEEK_API_BASE_URL', 'https://mock.deepseek.com')
    mocker.patch('src.core.settings.DEEPSEEK_MODEL', 'deepseek-test-model')
    return settings

@pytest.fixture
def mock_base_make_request(mocker):
    """Mocks the BaseApiClient._make_request method."""
    # This mock will be called via super() in DeepSeekClient._make_request
    mock = mocker.patch.object(BaseApiClient, '_make_request', return_value=(None, None))
    return mock

@pytest.fixture
def deepseek_client(mock_settings_deepseek, mock_base_make_request):
    """Provides a DeepSeekClient instance using mocked settings and base request."""
    # Initialization will use mocked settings
    # The _make_request override in DeepSeekClient will call the mocked BaseApiClient._make_request
    client = DeepSeekClient()
    return client

# --- Test Cases ---

def test_deepseek_client_init_success(mock_settings_deepseek):
    """Test successful initialization."""
    # We need mock_base_make_request here too because __init__ calls super() which might use it indirectly if base init logic changes
    with patch.object(BaseApiClient, '_make_request'): # Ensure base init doesn't fail if it makes calls
         client = DeepSeekClient()
    assert client.api_key == 'test-deepseek-key'
    assert client.base_url == 'https://mock.deepseek.com'
    assert client.model == 'deepseek-test-model'

def test_deepseek_client_init_missing_key(mocker):
    """Test initialization fails if API key is missing."""
    mocker.patch('src.core.settings.DEEPSEEK_API_KEY', None)
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY must be configured"):
        DeepSeekClient()

def test_generate_summary_success(deepseek_client, mock_base_make_request):
    """Test successful summary generation and header addition."""
    mock_response = {
        "choices": [
            {"message": {"content": " This is the generated summary. "}}
        ],
        "usage": {"total_tokens": 50}
    }
    # Configure the mock for the *base* client's method
    mock_base_make_request.return_value = (mock_response, None)

    text_content = "This is the input text to summarize."
    summary = deepseek_client.generate_summary(text_content)

    assert summary == "This is the generated summary." # Check stripping

    # Assert that the *mocked base client's* _make_request was called
    mock_base_make_request.assert_called_once()
    # Inspect the arguments passed to the mocked base client's method
    call_args, call_kwargs = mock_base_make_request.call_args
    assert call_args[0] == 'POST' # method
    assert call_args[1] == ENDPOINT_CHAT_COMPLETIONS # endpoint

    # Check payload passed to base method
    payload = call_kwargs.get('json_payload')
    assert payload is not None
    assert payload['model'] == 'deepseek-test-model'
    assert payload['messages'][1]['role'] == 'user'
    assert payload['messages'][1]['content'] == text_content

    # Check that headers *including Authorization* were passed to the base method
    headers = call_kwargs.get('headers')
    assert headers is not None
    assert 'Authorization' in headers
    assert headers['Authorization'] == 'Bearer test-deepseek-key'

def test_generate_summary_api_error(deepseek_client, mock_base_make_request, caplog):
    """Test handling of API error returned by base _make_request."""
    # Configure the mock for the *base* client's method to return an error
    mock_base_make_request.return_value = (None, "Simulated API Error 500")

    summary = deepseek_client.generate_summary("Some input text.")

    assert summary is None
    # Check that the base method was called
    mock_base_make_request.assert_called_once()
    assert "Failed to generate summary using DeepSeek. Error: Simulated API Error 500" in caplog.text

def test_generate_summary_api_error_field(deepseek_client, mock_base_make_request, caplog):
    """Test handling of error structure within JSON response from base request."""
    mock_response = {"error": {"message": "Invalid API Key", "code": "auth_error"}}
    # Configure the mock for the *base* client's method
    mock_base_make_request.return_value = (mock_response, None)

    summary = deepseek_client.generate_summary("Some input text.")

    assert summary is None
    # Check that the base method was called
    mock_base_make_request.assert_called_once()
    assert f"DeepSeek API error: {mock_response['error']}" in caplog.text

def test_generate_summary_malformed_response(deepseek_client, mock_base_make_request, caplog):
    """Test handling of unexpected successful response structure from base request."""
    mock_response = {"unexpected_key": "some_value"} # Missing 'choices'
    # Configure the mock for the *base* client's method
    mock_base_make_request.return_value = (mock_response, None)

    summary = deepseek_client.generate_summary("Some input text.")

    assert summary is None
    # Check that the base method was called
    mock_base_make_request.assert_called_once()
    assert "Failed to parse summary from DeepSeek response" in caplog.text
    assert "'choices'" in caplog.text # Specific key error

def test_generate_summary_empty_input(deepseek_client, mock_base_make_request, caplog):
    """Test behavior with empty input text."""
    summary = deepseek_client.generate_summary("")

    assert summary is None
    assert "Cannot generate summary for empty text content" in caplog.text
    # Base method should not be called if input is empty
    mock_base_make_request.assert_not_called()

def test_generate_summary_custom_instruction(deepseek_client, mock_base_make_request):
    """Test that custom instructions are used in the payload passed to base request."""
    mock_response = {"choices": [{"message": {"content": " Summary"}}]}
    # Configure the mock for the *base* client's method
    mock_base_make_request.return_value = (mock_response, None)

    custom_instruction = "Summarize specifically for engineers."
    text_content = "Input text."
    deepseek_client.generate_summary(text_content, instruction=custom_instruction)

    # Check the arguments passed to the mocked base client's method
    mock_base_make_request.assert_called_once()
    _, call_kwargs = mock_base_make_request.call_args
    payload = call_kwargs.get('json_payload')
    assert payload['messages'][0]['role'] == 'system'
    assert payload['messages'][0]['content'] == custom_instruction
    # Check headers again for this case too
    headers = call_kwargs.get('headers')
    assert headers is not None
    assert 'Authorization' in headers
    assert headers['Authorization'] == 'Bearer test-deepseek-key'