# tests/api/openai/test_openai_api.py

import pytest
import requests
import openai # Import openai library itself for error types
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

# Modules to test
from src.api.openai.openai_api import OpenAIClient
from src.core import settings

# --- Fixtures ---

@pytest.fixture
def mock_settings_openai(mocker):
    """Mocks settings used by OpenAIClient."""
    mocker.patch('src.core.settings.OPENAI_API_KEY', 'test-openai-key')
    mocker.patch('src.core.settings.OPENAI_IMAGE_MODEL', 'dall-e-test')
    return settings

@pytest.fixture
def mock_openai_client_instance(mocker):
    """Mocks the openai.OpenAI() instance and its methods."""
    mock_instance = MagicMock()
    # Mock the images.generate structure
    mock_instance.images = MagicMock()
    mock_instance.images.generate = MagicMock()
    mocker.patch('openai.OpenAI', return_value=mock_instance) # Patch the class constructor
    return mock_instance

@pytest.fixture
def openai_client_fixture(mock_settings_openai, mock_openai_client_instance):
    """Provides an OpenAIClient instance with mocked underlying client."""
    client = OpenAIClient()
    # The internal self.client is already the mocked instance
    return client

# --- Test Cases ---

def test_openai_client_init_success(mock_settings_openai, mock_openai_client_instance):
    """Test successful initialization."""
    client = OpenAIClient()
    assert client.model == 'dall-e-test'
    # Check if OpenAI() constructor was called with the key
    openai.OpenAI.assert_called_once_with(api_key='test-openai-key')

def test_openai_client_init_missing_key(mocker):
    """Test initialization fails if API key is missing."""
    mocker.patch('src.core.settings.OPENAI_API_KEY', None)
    with pytest.raises(ValueError, match="OPENAI_API_KEY must be configured"):
        OpenAIClient()

@patch('requests.get') # Patch requests.get globally for download test
def test_generate_image_success(mock_requests_get, openai_client_fixture, mock_openai_client_instance, tmp_path, caplog):
    """Test successful image generation, download, and saving."""
    # Configure mock OpenAI response
    mock_image_url = "https://mock.openai.com/image.png"
    mock_openai_response = MagicMock()
    mock_openai_response.data = [MagicMock(url=mock_image_url)]
    mock_openai_client_instance.images.generate.return_value = mock_openai_response

    # Configure mock download response
    mock_download_response = MagicMock()
    mock_download_response.raise_for_status.return_value = None
    mock_download_response.iter_content.return_value = [b'mock', b'image', b'data']
    mock_requests_get.return_value = mock_download_response

    prompt = "A test prompt"
    output_file = tmp_path / "generated_image.png"

    result_path = openai_client_fixture.generate_image(prompt, output_file)

    assert result_path == output_file
    assert output_file.exists()
    assert output_file.read_bytes() == b'mockimagedata'
    # Verify OpenAI call
    mock_openai_client_instance.images.generate.assert_called_once_with(
        model='dall-e-test',
        prompt=prompt,
        n=1,
        size="1024x1024", # Default size
        quality="standard", # Default quality
        style="vivid", # Default style
        response_format="url"
    )
    # Verify download call
    mock_requests_get.assert_called_once_with(mock_image_url, stream=True, timeout=60)
    assert "Image successfully downloaded and saved" in caplog.text

@patch('requests.get')
def test_generate_image_api_error(mock_requests_get, openai_client_fixture, mock_openai_client_instance, tmp_path, caplog):
    """Test handling of OpenAI API errors during generation."""
    # Configure mock OpenAI error
    mock_openai_client_instance.images.generate.side_effect = openai.RateLimitError(
        message="Rate limit exceeded", response=MagicMock(), body=None
    )

    prompt = "A test prompt"
    output_file = tmp_path / "generated_image.png"

    result_path = openai_client_fixture.generate_image(prompt, output_file)

    assert result_path is None
    assert not output_file.exists()
    mock_requests_get.assert_not_called() # Download should not be attempted
    assert "OpenAI API request exceeded rate limit" in caplog.text

@patch('requests.get')
def test_generate_image_download_error(mock_requests_get, openai_client_fixture, mock_openai_client_instance, tmp_path, caplog):
    """Test handling of errors during image download."""
    # Configure mock OpenAI response (success)
    mock_image_url = "https://mock.openai.com/image.png"
    mock_openai_response = MagicMock()
    mock_openai_response.data = [MagicMock(url=mock_image_url)]
    mock_openai_client_instance.images.generate.return_value = mock_openai_response

    # Configure mock download error
    expected_error_msg = "Failed to connect"
    mock_requests_get.side_effect = requests.exceptions.ConnectionError(expected_error_msg)

    prompt = "A test prompt"
    output_file = tmp_path / "generated_image.png"

    result_path = openai_client_fixture.generate_image(prompt, output_file)

    assert result_path is None
    assert not output_file.exists() # Should not be created if download fails
    mock_requests_get.assert_called_once()
    # --- Start of Correction ---
    # Check that the specific error message from the exception is logged
    assert expected_error_msg in caplog.text
    # Optionally, also check for the generic log prefix
    assert "Failed to download image:" in caplog.text
    # --- End of Correction ---

@patch('requests.get')
@patch('builtins.open') # Mock the built-in open function
def test_generate_image_save_error(mock_open, mock_requests_get, openai_client_fixture, mock_openai_client_instance, tmp_path, caplog):
    """Test handling of errors during file saving."""
     # Configure mock OpenAI response (success)
    mock_image_url = "https://mock.openai.com/image.png"
    mock_openai_response = MagicMock()
    mock_openai_response.data = [MagicMock(url=mock_image_url)]
    mock_openai_client_instance.images.generate.return_value = mock_openai_response

    # Configure mock download response (success)
    mock_download_response = MagicMock()
    mock_download_response.raise_for_status.return_value = None
    mock_download_response.iter_content.return_value = [b'mock', b'image', b'data']
    mock_requests_get.return_value = mock_download_response

    # Configure mock open to raise IOError
    expected_error_msg = "Permission denied"
    mock_open.side_effect = IOError(expected_error_msg)

    prompt = "A test prompt"
    output_file = tmp_path / "generated_image.png"

    result_path = openai_client_fixture.generate_image(prompt, output_file)

    assert result_path is None
    mock_open.assert_called_once_with(output_file, 'wb')
    # Check the log message includes the specific IO error
    assert f"Failed to save image to {output_file}: {expected_error_msg}" in caplog.text

def test_generate_image_empty_prompt(openai_client_fixture, tmp_path, caplog):
    """Test generation with an empty prompt."""
    output_file = tmp_path / "image.png"
    result = openai_client_fixture.generate_image("", output_file)
    assert result is None
    assert "Image generation prompt cannot be empty" in caplog.text

def test_generate_image_empty_path(openai_client_fixture, caplog):
    """Test generation with an empty output path."""
    result = openai_client_fixture.generate_image("prompt", None) # type: ignore
    assert result is None
    assert "Output path for saving the image cannot be empty" in caplog.text