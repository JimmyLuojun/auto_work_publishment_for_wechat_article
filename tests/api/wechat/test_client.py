import pytest
import time
from unittest.mock import MagicMock, patch, call
from pathlib import Path

# Modules to test
from src.api.wechat.client import WeChatClient, ENDPOINT_ACCESS_TOKEN, ENDPOINT_UPLOAD_MEDIA, ENDPOINT_ADD_DRAFT, ENDPOINT_UPDATE_DRAFT, ENDPOINT_BATCHGET_DRAFT
from src.core import settings

# --- Fixtures ---

@pytest.fixture
def mock_settings_wechat(mocker):
    """Mocks settings used by WeChatClient."""
    mocker.patch('src.core.settings.WECHAT_APP_ID', 'test-app-id')
    mocker.patch('src.core.settings.WECHAT_APP_SECRET', 'test-app-secret')
    mocker.patch('src.core.settings.WECHAT_API_BASE_URL', 'https://mock.weixin.qq.com')
    return settings

@pytest.fixture
def wechat_client_fixture(mock_settings_wechat, mocker):
    """Provides a WeChatClient instance with mocked base request."""
    # Mock the parent class's _make_request directly
    mocker.patch('src.api.base_client.BaseApiClient._make_request', return_value=(None, None)) # Default mock
    client = WeChatClient()
    # Mock _make_request on the instance after super().__init__
    client._make_request = MagicMock(return_value=(None, None))
    # Reset token state for clean tests
    client._access_token = None
    client._token_expiry_time = 0.0
    return client

# --- Test Cases ---

def test_wechat_client_init_success(mock_settings_wechat):
    """Test successful initialization."""
    client = WeChatClient()
    assert client.app_id == 'test-app-id'
    assert client.app_secret == 'test-app-secret'
    assert client.base_url == 'https://mock.weixin.qq.com'

def test_wechat_client_init_missing_creds(mocker):
    """Test initialization fails if App ID or Secret is missing."""
    mocker.patch('src.core.settings.WECHAT_APP_ID', None)
    mocker.patch('src.core.settings.WECHAT_APP_SECRET', 'secret')
    with pytest.raises(ValueError, match="WECHAT_APP_ID and WECHAT_APP_SECRET must be configured"):
        WeChatClient()

    mocker.patch('src.core.settings.WECHAT_APP_ID', 'id')
    mocker.patch('src.core.settings.WECHAT_APP_SECRET', None)
    with pytest.raises(ValueError, match="WECHAT_APP_ID and WECHAT_APP_SECRET must be configured"):
        WeChatClient()

def test_fetch_access_token_success(wechat_client_fixture):
    """Test successful fetching of access token."""
    mock_response = {"access_token": "mock_token_123", "expires_in": 7200}
    wechat_client_fixture._make_request.return_value = (mock_response, None)
    current_time = time.time()

    success = wechat_client_fixture._fetch_access_token()

    assert success is True
    assert wechat_client_fixture._access_token == "mock_token_123"
    assert wechat_client_fixture._token_expiry_time > current_time + 6800 # 7200 - 300 buffer, allow slight timing diff
    assert wechat_client_fixture._token_expiry_time < current_time + 7000
    wechat_client_fixture._make_request.assert_called_once_with(
        'GET',
        ENDPOINT_ACCESS_TOKEN,
        params={'grant_type': 'client_credential', 'appid': 'test-app-id', 'secret': 'test-app-secret'}
    )

def test_fetch_access_token_api_error(wechat_client_fixture, caplog):
    """Test failure during access token fetching due to API error."""
    wechat_client_fixture._make_request.return_value = (None, "Network Error")

    success = wechat_client_fixture._fetch_access_token()

    assert success is False
    assert wechat_client_fixture._access_token is None
    assert "Failed to fetch access token. Error: Network Error" in caplog.text

def test_fetch_access_token_invalid_response(wechat_client_fixture, caplog):
    """Test failure due to invalid JSON response from API."""
    mock_response = {"error": "invalid credential"} # Missing access_token
    wechat_client_fixture._make_request.return_value = (mock_response, None)

    success = wechat_client_fixture._fetch_access_token()

    assert success is False
    assert wechat_client_fixture._access_token is None
    assert "Error fetching access token: WeChat API response missing token or expiry" in caplog.text

@patch('time.time') # Mock time.time
def test_get_valid_access_token_refresh(mock_time, wechat_client_fixture):
    """Test that token is refreshed when expired."""
    # 1. Initial state: No token
    mock_time.return_value = 10000.0
    mock_response = {"access_token": "token_1", "expires_in": 7200}
    wechat_client_fixture._make_request.return_value = (mock_response, None)
    token1 = wechat_client_fixture._get_valid_access_token()
    assert token1 == "token_1"
    assert wechat_client_fixture._token_expiry_time > 10000.0 + 6800
    first_call = call('GET', ENDPOINT_ACCESS_TOKEN, params={'grant_type': 'client_credential', 'appid': 'test-app-id', 'secret': 'test-app-secret'})
    wechat_client_fixture._make_request.assert_has_calls([first_call])
    assert wechat_client_fixture._make_request.call_count == 1

    # 2. Token is valid, should not refresh
    mock_time.return_value = 11000.0 # Still valid
    token2 = wechat_client_fixture._get_valid_access_token()
    assert token2 == "token_1"
    assert wechat_client_fixture._make_request.call_count == 1 # No new call

    # 3. Token expired, should refresh
    mock_time.return_value = 18000.0 # More than 7200-300 seconds later
    mock_response_2 = {"access_token": "token_2", "expires_in": 7200}
    wechat_client_fixture._make_request.return_value = (mock_response_2, None) # Set new return value
    token3 = wechat_client_fixture._get_valid_access_token()
    assert token3 == "token_2"
    assert wechat_client_fixture._make_request.call_count == 2 # Fetched again
    second_call = call('GET', ENDPOINT_ACCESS_TOKEN, params={'grant_type': 'client_credential', 'appid': 'test-app-id', 'secret': 'test-app-secret'})
    wechat_client_fixture._make_request.assert_has_calls([first_call, second_call]) # Check both calls happened

def test_get_valid_access_token_fetch_fails(wechat_client_fixture, caplog):
    """Test that ConnectionError is raised if token fetch fails during _authenticate."""
    wechat_client_fixture._make_request.return_value = (None, "Fetch Failed") # Mock token fetch failure
    with pytest.raises(ConnectionError, match="Failed to retrieve WeChat access token"):
        wechat_client_fixture._get_valid_access_token()
    assert "Failed to fetch access token. Error: Fetch Failed" in caplog.text


@patch('builtins.open', new_callable=MagicMock) # Mock the open builtin
def test_upload_media_success(mock_open, wechat_client_fixture, tmp_path):
    """Test successful media upload."""
    # Mock token
    wechat_client_fixture._access_token = "valid_token"
    wechat_client_fixture._token_expiry_time = time.time() + 1000

    # Mock API response
    mock_media_id = "media_id_xyz"
    mock_url = "http://mmbiz.qpic.cn/..."
    mock_api_response = {"media_id": mock_media_id, "url": mock_url}
    wechat_client_fixture._make_request.return_value = (mock_api_response, None)

    # Create dummy file
    file_path = tmp_path / "test_image.jpg"
    file_path.touch()
    # Configure mock_open context manager
    mock_file_handle = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file_handle

    result = wechat_client_fixture.upload_media(str(file_path), media_type='image', is_permanent=True)

    assert result == mock_api_response
    mock_open.assert_called_once_with(str(file_path), 'rb')
    wechat_client_fixture._make_request.assert_called_once()
    args, kwargs = wechat_client_fixture._make_request.call_args
    assert args[0] == 'POST'
    assert args[1] == ENDPOINT_UPLOAD_MEDIA # Permanent upload endpoint
    assert kwargs['params'] == {'access_token': 'valid_token', 'type': 'image'}
    assert 'media' in kwargs['files']
    assert kwargs['files']['media'][0] == str(file_path) # Check filename passed to requests

def test_upload_media_file_not_found(wechat_client_fixture, tmp_path, caplog):
    """Test upload when the media file does not exist."""
    wechat_client_fixture._access_token = "valid_token"
    wechat_client_fixture._token_expiry_time = time.time() + 1000

    non_existent_file = tmp_path / "not_a_file.jpg"
    result = wechat_client_fixture.upload_media(str(non_existent_file), media_type='image')

    assert result is None
    assert f"Media file not found: {non_existent_file}" in caplog.text
    wechat_client_fixture._make_request.assert_not_called() # Should fail before API call

@patch('builtins.open', new_callable=MagicMock)
def test_upload_media_api_error(mock_open, wechat_client_fixture, tmp_path, caplog):
    """Test upload failure due to WeChat API error response."""
    wechat_client_fixture._access_token = "valid_token"
    wechat_client_fixture._token_expiry_time = time.time() + 1000
    mock_api_error = {"errcode": 40004, "errmsg": "invalid media type"}
    wechat_client_fixture._make_request.return_value = (mock_api_error, None)

    file_path = tmp_path / "test_image.jpg"
    file_path.touch()
    mock_file_handle = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file_handle

    result = wechat_client_fixture.upload_media(str(file_path), media_type='invalid_type')

    assert result is None
    assert f"WeChat API error during media upload: {mock_api_error['errmsg']} (Code: {mock_api_error['errcode']})" in caplog.text

def test_add_draft_success(wechat_client_fixture):
    """Test successfully adding a draft."""
    wechat_client_fixture._access_token = "valid_token"
    wechat_client_fixture._token_expiry_time = time.time() + 1000
    mock_draft_id = "draft_media_id_123"
    mock_api_response = {"media_id": mock_draft_id}
    wechat_client_fixture._make_request.return_value = (mock_api_response, None)

    article_data = {"title": "Test Title", "content": "<p>Hello</p>", "thumb_media_id": "thumb1"}
    result = wechat_client_fixture.add_draft(article_data)

    assert result == mock_draft_id
    wechat_client_fixture._make_request.assert_called_once()
    args, kwargs = wechat_client_fixture._make_request.call_args
    assert args[0] == 'POST'
    assert args[1] == ENDPOINT_ADD_DRAFT
    assert kwargs['params'] == {'access_token': 'valid_token'}
    assert kwargs['json_payload'] == {'articles': [article_data]}

def test_add_draft_api_error(wechat_client_fixture, caplog):
    """Test adding draft failure due to API error."""
    wechat_client_fixture._access_token = "valid_token"
    wechat_client_fixture._token_expiry_time = time.time() + 1000
    mock_api_error = {"errcode": 45009, "errmsg": "reach max api call limit"}
    wechat_client_fixture._make_request.return_value = (mock_api_error, None)

    article_data = {"title": "Test Title", "content": "<p>Hello</p>", "thumb_media_id": "thumb1"}
    result = wechat_client_fixture.add_draft(article_data)

    assert result is None
    assert f"WeChat API error adding draft: {mock_api_error['errmsg']} (Code: {mock_api_error['errcode']})" in caplog.text


def test_update_draft_success(wechat_client_fixture):
    """Test successfully updating a draft."""
    wechat_client_fixture._access_token = "valid_token"
    wechat_client_fixture._token_expiry_time = time.time() + 1000
    mock_api_response = {"errcode": 0, "errmsg": "ok"}
    wechat_client_fixture._make_request.return_value = (mock_api_response, None)

    draft_media_id = "draft_media_id_123"
    article_data = {"title": "Updated Title", "content": "<p>Updated</p>", "thumb_media_id": "thumb2"}
    result = wechat_client_fixture.update_draft(draft_media_id, 0, article_data)

    assert result is True
    wechat_client_fixture._make_request.assert_called_once()
    args, kwargs = wechat_client_fixture._make_request.call_args
    assert args[0] == 'POST'
    assert args[1] == ENDPOINT_UPDATE_DRAFT
    assert kwargs['params'] == {'access_token': 'valid_token'}
    assert kwargs['json_payload'] == {"media_id": draft_media_id, "index": 0, "articles": article_data}


def test_update_draft_api_error(wechat_client_fixture, caplog):
    """Test updating draft failure due to API error."""
    wechat_client_fixture._access_token = "valid_token"
    wechat_client_fixture._token_expiry_time = time.time() + 1000
    mock_api_error = {"errcode": 40007, "errmsg": "invalid media_id"}
    wechat_client_fixture._make_request.return_value = (mock_api_error, None)

    draft_media_id = "invalid_draft_id"
    article_data = {"title": "Updated Title"}
    result = wechat_client_fixture.update_draft(draft_media_id, 0, article_data)

    assert result is False
    assert f"WeChat API error updating draft {draft_media_id}: {mock_api_error['errmsg']} (Code: {mock_api_error['errcode']})" in caplog.text


def test_find_draft_by_title_found(wechat_client_fixture):
    """Test finding an existing draft by title."""
    wechat_client_fixture._access_token = "valid_token"
    wechat_client_fixture._token_expiry_time = time.time() + 1000
    target_title = "My Draft Title"
    target_media_id = "draft_abc"
    mock_api_response = {
        "total_count": 2,
        "item_count": 2,
        "item": [
            {"media_id": "draft_xyz", "content": {"news_item": [{"title": "Another Title"}]}},
            {"media_id": target_media_id, "content": {"news_item": [{"title": target_title}]}},
        ]
    }
    wechat_client_fixture._make_request.return_value = (mock_api_response, None)

    result = wechat_client_fixture.find_draft_by_title(target_title)

    assert result == target_media_id
    wechat_client_fixture._make_request.assert_called_once()
    args, kwargs = wechat_client_fixture._make_request.call_args
    assert args[0] == 'POST'
    assert args[1] == ENDPOINT_BATCHGET_DRAFT
    assert kwargs['params'] == {'access_token': 'valid_token'}
    assert kwargs['json_payload'] == {"offset": 0, "count": 20, "no_content": 1}

def test_find_draft_by_title_not_found(wechat_client_fixture):
    """Test finding a draft when the title doesn't match."""
    wechat_client_fixture._access_token = "valid_token"
    wechat_client_fixture._token_expiry_time = time.time() + 1000
    target_title = "NonExistent Title"
    mock_api_response = {
        "total_count": 1,
        "item_count": 1,
        "item": [
            {"media_id": "draft_xyz", "content": {"news_item": [{"title": "Another Title"}]}},
        ]
    }
    wechat_client_fixture._make_request.return_value = (mock_api_response, None)

    result = wechat_client_fixture.find_draft_by_title(target_title)

    assert result is None

def test_find_draft_by_title_api_error(wechat_client_fixture, caplog):
    """Test finding draft failure due to API error."""
    wechat_client_fixture._access_token = "valid_token"
    wechat_client_fixture._token_expiry_time = time.time() + 1000
    wechat_client_fixture._make_request.return_value = (None, "Listing failed")

    result = wechat_client_fixture.find_draft_by_title("Some Title")

    assert result is None
    assert "Failed to list drafts. Error: Listing failed" in caplog.text 