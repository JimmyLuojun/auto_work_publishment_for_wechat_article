# /Users/junluo/Documents/auto_work_publishment_for_wechat_article/tests/platforms/wechat/test_publisher.py

import pytest
from unittest.mock import MagicMock, call, ANY # ANY can match arguments flexibly

from src.core.article_model import Article, MediaPlaceholder, ContentElement
from src.platforms.wechat.publisher import WeChatPublisher
# Assuming WeChatClient/DeepSeekClient are accessible for type hinting/mocking
# from src.api.wechat.client import WeChatClient
# from src.api.deepseek.deepseek_api import DeepSeekClient

# --- Fixtures ---

@pytest.fixture
def mock_wechat_client(mocker):
    """Fixture for a mocked WeChatClient for publishing."""
    mock_client = MagicMock(spec=['add_draft', 'update_draft', 'find_draft_by_title'])

    # Default behaviors
    mock_client.add_draft.return_value = "new_draft_media_id_123" # Simulate successful creation
    mock_client.update_draft.return_value = True # Simulate successful update
    mock_client.find_draft_by_title.return_value = None # Default: no existing draft found

    return mock_client

@pytest.fixture
def mock_deepseek_client(mocker):
    """Fixture for a mocked DeepSeekClient."""
    mock_client = MagicMock(spec=['generate_summary', 'get_content_as_text']) # Added get_content_as_text to spec if needed for mocking
    mock_client.generate_summary.return_value = "Generated test summary."
    # If you need to mock Article.get_content_as_text behavior you might do it here or on the article object directly
    return mock_client


@pytest.fixture
def mock_settings(monkeypatch):
    """Fixture to mock settings relevant to the publisher."""
    class MockSettings:
        ARTICLE_AUTHOR = "Publisher Default Author"
        MARK_AS_ORIGINAL = True
        # *** CORRECTED SECTION ***
        # Use the setting name expected by the publisher code
        ENABLE_COMMENTS = False
        # Keep ENABLE_APPRECIATION if it's used elsewhere or remove if redundant
        # ENABLE_APPRECIATION = False
        # *** END CORRECTION ***
        # Add other settings used in payload construction if necessary, e.g.:
        # ARTICLE_CREATION_SOURCE = "Test Source"

    # Patch the settings module used by the publisher
    monkeypatch.setattr('src.platforms.wechat.publisher.settings', MockSettings)
    # Patch the regex used for HTML replacement if it causes issues finding placeholders
    # For now, assume it works with basic HTML structures
    return MockSettings


@pytest.fixture
def processed_article(mocker): # Add mocker fixture if mocking methods on article
    """Creates an Article object as if processed and media uploaded."""
    cover_p = MediaPlaceholder(placeholder_id="cover.jpg", media_type="thumb",
                               uploaded_media_id="cover_media_id_abc", original_tag="![Cover](cover.jpg)")

    content_p1 = MediaPlaceholder(placeholder_id="img1.png", media_type="image",
                                  uploaded_media_id="content_media_id_1", uploaded_url="http://wx.com/img1.png",
                                  original_tag="![Image 1](img1.png)")

    content_p2 = MediaPlaceholder(placeholder_id="vid1.mp4", media_type="video",
                                  uploaded_media_id="content_media_id_2", uploaded_url="http://wx.com/vid1.mp4",
                                  original_tag="![Video](vid1.mp4)")

    content_p_missing_url = MediaPlaceholder(placeholder_id="img_no_url.gif", media_type="image",
                                             uploaded_media_id="content_media_id_3", uploaded_url=None,
                                             original_tag="![Image no URL](img_no_url.gif)")

    # Simulate HTML generated by markdown parser, including placeholder references
    html_content = """
    <p>This is the intro.</p>
    <p><img alt="Image 1" src="placeholder:img1.png" /></p>
    <p>Some more text.</p>
    <p><img alt="Video Placeholder" src="placeholder:vid1.mp4" /></p>
    <p>Text mentioning <img src="placeholder:img_no_url.gif"> which failed.</p>
    """

    # Create ContentElement with 'content' argument passed
    content_elements = [ContentElement(type='html', content=html_content)] # Using 'content' as established

    raw_markdown_content = "# Publish Test Article\nIntro\n![Image 1](img1.png)\nMore text\n![Video](vid1.mp4)\n![Image no URL](img_no_url.gif)"

    article = Article(
        title="Publish Test Article",
        content_elements=content_elements,
        media_placeholders=[content_p1, content_p2, content_p_missing_url],
        cover_image_placeholder=cover_p,
        metadata={'author': 'Override Author'}, # Example metadata
        raw_markdown=raw_markdown_content # Provide raw markdown for summary test
    )

    # Mock the get_content_as_text method to return the raw markdown for summary generation testing
    # This makes the test less dependent on the actual implementation of get_content_as_text
    mocker.patch.object(article, 'get_content_as_text', return_value=raw_markdown_content)

    return article


# --- Test Class ---

class TestWeChatPublisher:

    def test_publish_create_new_draft_success(self, mock_wechat_client, mock_deepseek_client, mock_settings, processed_article):
        """Test creating a new draft successfully."""
        publisher = WeChatPublisher(mock_wechat_client, mock_deepseek_client)

        # Ensure find_draft returns None initially
        mock_wechat_client.find_draft_by_title.return_value = None

        draft_media_id = publisher.publish_draft(processed_article, check_existing=True)

        assert draft_media_id == "new_draft_media_id_123"
        mock_wechat_client.find_draft_by_title.assert_called_once_with(processed_article.title)
        mock_wechat_client.add_draft.assert_called_once()
        mock_wechat_client.update_draft.assert_not_called()

        # Verify payload passed to add_draft
        call_args = mock_wechat_client.add_draft.call_args
        assert call_args is not None, "add_draft was not called"
        payload = call_args[0][0] # First positional argument
        assert payload['title'] == processed_article.title
        assert payload['author'] == mock_settings.ARTICLE_AUTHOR # Uses settings author
        assert payload['digest'] == "Generated test summary." # From deepseek mock
        assert payload['thumb_media_id'] == "cover_media_id_abc"
        assert 'src="http://wx.com/img1.png"' in payload['content'] # Check replacement
        assert 'src="http://wx.com/vid1.mp4"' in payload['content']
        # Check placeholder with missing URL was handled (removed in corrected publisher)
        assert 'src="placeholder:img_no_url.gif"' not in payload['content']
        assert 'img_no_url.gif' not in payload['content'] # Ensure the tag or reference is gone
        assert payload['is_original'] == (1 if mock_settings.MARK_AS_ORIGINAL else 0)
        assert payload['need_open_comment'] == (1 if mock_settings.ENABLE_COMMENTS else 0)

        # Verify summary generation was called with the correct content
        # Uses the mocked return value of get_content_as_text (raw_markdown in this setup)
        processed_article.get_content_as_text.assert_called_once()
        mock_deepseek_client.generate_summary.assert_called_once_with(processed_article.raw_markdown)


    def test_publish_update_existing_draft_success(self, mock_wechat_client, mock_deepseek_client, mock_settings, processed_article):
        """Test updating an existing draft successfully."""
        publisher = WeChatPublisher(mock_wechat_client, mock_deepseek_client)

        # Simulate finding an existing draft
        existing_id = "existing_media_id_456"
        mock_wechat_client.find_draft_by_title.return_value = existing_id

        draft_media_id = publisher.publish_draft(processed_article, check_existing=True)

        assert draft_media_id == existing_id # Should return the existing ID on successful update
        mock_wechat_client.find_draft_by_title.assert_called_once_with(processed_article.title)
        mock_wechat_client.update_draft.assert_called_once()
        mock_wechat_client.add_draft.assert_not_called()

        # Verify payload passed to update_draft
        call_args = mock_wechat_client.update_draft.call_args
        assert call_args is not None, "update_draft was not called"
        assert call_args.kwargs['draft_media_id'] == existing_id
        assert call_args.kwargs['article_index'] == 0
        payload = call_args.kwargs['article_data']
        # Check some key fields in payload (same checks as add_draft basically)
        assert payload['title'] == processed_article.title
        assert payload['thumb_media_id'] == "cover_media_id_abc"
        assert 'src="http://wx.com/img1.png"' in payload['content']
        assert payload['need_open_comment'] == (1 if mock_settings.ENABLE_COMMENTS else 0)


    def test_publish_no_deepseek_client(self, mock_wechat_client, mock_settings, processed_article):
        """Test publishing without a DeepSeek client (no summary generated)."""
        publisher = WeChatPublisher(mock_wechat_client, deepseek_client=None) # No deepseek client

        # Mock find_draft to return None for this specific test scenario if needed
        mock_wechat_client.find_draft_by_title.return_value = None

        draft_media_id = publisher.publish_draft(processed_article, check_existing=False) # Set check_existing=False for simplicity

        assert draft_media_id is not None # Should still succeed in creating draft
        mock_wechat_client.add_draft.assert_called_once()
        payload = mock_wechat_client.add_draft.call_args[0][0]
        assert payload['digest'] == "" # Summary should be empty
        assert payload['need_open_comment'] == (1 if mock_settings.ENABLE_COMMENTS else 0)


    def test_publish_use_existing_summary(self, mock_wechat_client, mock_deepseek_client, mock_settings, processed_article):
         """Test that an existing summary on the article is used."""
         processed_article.summary = "Pre-existing summary from metadata."
         publisher = WeChatPublisher(mock_wechat_client, mock_deepseek_client)

         # Mock find_draft to return None for this specific test scenario if needed
         mock_wechat_client.find_draft_by_title.return_value = None

         draft_media_id = publisher.publish_draft(processed_article, check_existing=False) # Set check_existing=False

         assert draft_media_id is not None
         mock_deepseek_client.generate_summary.assert_not_called() # Should not call deepseek
         # Ensure get_content_as_text was not called because summary existed
         processed_article.get_content_as_text.assert_not_called()
         mock_wechat_client.add_draft.assert_called_once()
         payload = mock_wechat_client.add_draft.call_args[0][0]
         assert payload['digest'] == "Pre-existing summary from metadata."
         assert payload['need_open_comment'] == (1 if mock_settings.ENABLE_COMMENTS else 0)


    def test_publish_fail_no_cover_media_id(self, mock_wechat_client, mock_deepseek_client, mock_settings, processed_article):
        """Test failure if the cover image media ID is missing."""
        processed_article.cover_image_placeholder.uploaded_media_id = None # Simulate missing ID
        publisher = WeChatPublisher(mock_wechat_client, mock_deepseek_client)

        draft_media_id = publisher.publish_draft(processed_article)

        assert draft_media_id is None
        # Ensure API calls are not made if pre-check fails
        mock_wechat_client.find_draft_by_title.assert_not_called()
        mock_wechat_client.add_draft.assert_not_called()
        mock_wechat_client.update_draft.assert_not_called()
        mock_deepseek_client.generate_summary.assert_not_called()


    def test_publish_fail_add_draft_api_error(self, mock_wechat_client, mock_deepseek_client, mock_settings, processed_article):
        """Test failure when add_draft API call fails."""
        # Setup mocks for this specific scenario
        mock_wechat_client.find_draft_by_title.return_value = None # Ensure it tries to add
        mock_wechat_client.add_draft.return_value = None # Simulate API failure

        publisher = WeChatPublisher(mock_wechat_client, mock_deepseek_client)

        draft_media_id = publisher.publish_draft(processed_article, check_existing=True)

        assert draft_media_id is None
        mock_wechat_client.find_draft_by_title.assert_called_once()
        mock_wechat_client.add_draft.assert_called_once() # Verify it was called
        mock_wechat_client.update_draft.assert_not_called()


    def test_publish_fail_update_draft_api_error(self, mock_wechat_client, mock_deepseek_client, mock_settings, processed_article):
         """Test failure when update_draft API call fails."""
         existing_id = "existing_media_id_456"
         # Setup mocks for this specific scenario
         mock_wechat_client.find_draft_by_title.return_value = existing_id # Ensure it finds one
         mock_wechat_client.update_draft.return_value = False # Simulate update failure

         publisher = WeChatPublisher(mock_wechat_client, mock_deepseek_client)

         draft_media_id = publisher.publish_draft(processed_article, check_existing=True)

         assert draft_media_id is None # Should fail if update fails
         mock_wechat_client.find_draft_by_title.assert_called_once()
         mock_wechat_client.update_draft.assert_called_once() # Verify it was called
         mock_wechat_client.add_draft.assert_not_called()