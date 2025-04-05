import pytest
from pathlib import Path
from unittest.mock import MagicMock, call  # Use MagicMock for flexible mocking

from src.core.article_model import Article, MediaPlaceholder
from src.platforms.wechat.media_uploader import WeChatMediaUploader


# --- Fixtures ---

@pytest.fixture
def mock_wechat_client(mocker):
    """Fixture to create a mocked WeChatClient."""
    mock_client = MagicMock(spec=['upload_media'])  # Mock only needed methods

    # Default success behavior for upload_media
    def mock_upload_success(file_path, media_type, is_permanent):
        # Simulate different IDs/URLs based on type/path
        file_name = Path(file_path).name
        if media_type == 'thumb':
            return {'media_id': f'thumb_id_for_{file_name}', 'url': None}  # Thumbs often don't return URL
        else:
            return {'media_id': f'perm_id_for_{file_name}', 'url': f'http://wechat.example.com/{file_name}'}

    mock_client.upload_media.side_effect = mock_upload_success
    return mock_client

@pytest.fixture
def mock_settings(monkeypatch, tmp_path):
    """Fixture to mock settings, creating necessary dummy dirs."""
    cover_dir = tmp_path / "input" / "cover_images"
    content_dir = tmp_path / "input" / "content_images"
    input_dir = tmp_path / "input"  # General input dir for relative paths
    cover_dir.mkdir(parents=True, exist_ok=True)
    content_dir.mkdir(parents=True, exist_ok=True)

    class MockSettings:
        INPUT_COVER_IMAGE_DIR = cover_dir
        INPUT_CONTENT_IMAGE_DIR = content_dir
        INPUT_DIR = input_dir  # Base dir for resolving MD paths

    monkeypatch.setattr('src.platforms.wechat.media_uploader.settings', MockSettings)
    return MockSettings

@pytest.fixture
def sample_article_for_upload(mock_settings):
    """Creates an Article object ready for upload testing."""
    # Create dummy files that should be found
    (mock_settings.INPUT_COVER_IMAGE_DIR / "cover_by_id.jpg").touch()
    
    # Ensure the 'rel_content' directory exists before touching files
    rel_content_dir = mock_settings.INPUT_DIR / "rel_content"
    rel_content_dir.mkdir(parents=True, exist_ok=True)

    (rel_content_dir / "standard_img.png").touch()  # Relative to INPUT_DIR
    (mock_settings.INPUT_CONTENT_IMAGE_DIR / "content_by_id.gif").touch()
    (mock_settings.INPUT_COVER_IMAGE_DIR / "cover_by_path.webp").touch()  # For cover_image_path
    
    # Provide the `original_tag` for the MediaPlaceholder initialization
    cover_placeholder_by_id = MediaPlaceholder(placeholder_id="cover_by_id.jpg", media_type="thumb", 
                                               alt_text="Cover", original_tag="![Cover](cover_by_id.jpg)")

    # Standard MD link placeholder (path relative to INPUT_DIR)
    content_placeholder_std = MediaPlaceholder(placeholder_id="standard_img.png", media_type="image", 
                                               alt_text="Standard", file_path="rel_content/standard_img.png", 
                                               original_tag="![Standard](rel_content/standard_img.png)")

    # Custom placeholder ID (found in INPUT_CONTENT_IMAGE_DIR)
    content_placeholder_custom = MediaPlaceholder(placeholder_id="content_by_id.gif", media_type="image", 
                                                  alt_text="Custom", original_tag="![Custom](content_by_id.gif)")

    # Placeholder for a file that won't be found
    content_placeholder_missing = MediaPlaceholder(placeholder_id="missing_file.bmp", media_type="image", 
                                                  alt_text="Missing", original_tag="![Missing](missing_file.bmp)")

    # Placeholder for cover specified by path
    cover_placeholder_by_path = MediaPlaceholder(placeholder_id="cover_by_path.webp", media_type="thumb", 
                                                file_path="cover_by_path.webp", alt_text="Cover Path", 
                                                original_tag="![Cover Path](cover_by_path.webp)")


    article = Article(
        title="Upload Test Article",
        # Start with cover defined by ID
        cover_image_placeholder=cover_placeholder_by_id,
        cover_image_file_path=None,  # Explicitly None initially
        content_elements=[],  # Not needed for media upload test
        media_placeholders=[
            content_placeholder_std,
            content_placeholder_custom,
            content_placeholder_missing,
        ],
        metadata={'author': 'Test'}
    )
    return article

@pytest.fixture
def sample_article_cover_path(sample_article_for_upload):
    """Modifies sample article to use cover_image_path."""
    # Get the placeholder created for cover_by_path.webp
    cover_p = MediaPlaceholder(placeholder_id="cover_by_path.webp", media_type="thumb", file_path="cover_by_path.webp", 
                               alt_text="Cover Path", original_tag="![Cover Path](cover_by_path.webp)")

    sample_article_for_upload.cover_image_placeholder = cover_p  # Assign placeholder derived from path
    sample_article_for_upload.cover_image_file_path = "cover_by_path.webp"  # Set the explicit path
    return sample_article_for_upload

@pytest.fixture
def sample_article_no_cover_ref(sample_article_for_upload):
     """Modifies article to have no explicit cover reference initially."""
     sample_article_for_upload.cover_image_placeholder = None
     sample_article_for_upload.cover_image_file_path = None
     return sample_article_for_upload


# --- Test Class ---

class TestWeChatMediaUploader:

    def test_upload_success_cover_id_and_content(self, mock_wechat_client, mock_settings, sample_article_for_upload):
        """Test successful upload of cover (by ID) and content media."""
        uploader = WeChatMediaUploader(mock_wechat_client)
        article = sample_article_for_upload  # Uses cover_by_id.jpg initially

        result = uploader.upload_article_media(article)

        assert result is True  # Cover upload succeeded

        # Check cover placeholder updated
        assert article.cover_image_placeholder is not None
        assert article.cover_image_placeholder.uploaded_media_id == "thumb_id_for_cover_by_id.jpg"
        assert article.cover_image_placeholder.uploaded_url is None

        # Check content placeholders
        p_std = article.get_placeholder_by_id("standard_img.png")
        assert p_std.uploaded_media_id == "perm_id_for_standard_img.png"
        assert p_std.uploaded_url == "http://wechat.example.com/standard_img.png"

        p_custom = article.get_placeholder_by_id("content_by_id.gif")
        assert p_custom.uploaded_media_id == "perm_id_for_content_by_id.gif"
        assert p_custom.uploaded_url == "http://wechat.example.com/content_by_id.gif"

        p_missing = article.get_placeholder_by_id("missing_file.bmp")
        assert p_missing.uploaded_media_id is None  # Should not have been uploaded
        assert p_missing.uploaded_url is None

        # Verify client calls
        expected_calls = [
            # Cover call (thumb type, permanent often needed)
            call(file_path=str(mock_settings.INPUT_COVER_IMAGE_DIR / "cover_by_id.jpg"), media_type='thumb', is_permanent=True),
            # Content call 1 (std link resolved relative to INPUT_DIR)
            call(file_path=str(mock_settings.INPUT_DIR / "rel_content" / "standard_img.png"), media_type='image', is_permanent=True),
            # Content call 2 (custom ID found in content dir)
            call(file_path=str(mock_settings.INPUT_CONTENT_IMAGE_DIR / "content_by_id.gif"), media_type='image', is_permanent=True),
            # Missing file placeholder is not uploaded, so no call for it
        ]
        mock_wechat_client.upload_media.assert_has_calls(expected_calls, any_order=True)  # Order might vary slightly
        assert mock_wechat_client.upload_media.call_count == 3
