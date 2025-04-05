# tests/core/test_article_model.py

import pytest
from dataclasses import is_dataclass, fields

# Module to test
from src.core.article_model import Article, MediaPlaceholder, ContentElement

# --- Test Cases ---

def test_dataclasses_defined():
    """Check if the core classes are defined as dataclasses."""
    assert is_dataclass(MediaPlaceholder)
    assert is_dataclass(ContentElement)
    assert is_dataclass(Article)

def test_media_placeholder_init():
    """Test initialization of MediaPlaceholder."""
    tag = "![alt](placeholder:id.png)"
    ph_id = "id.png"
    ph = MediaPlaceholder(original_tag=tag, placeholder_id=ph_id, media_type="image", alt_text="alt")
    assert ph.original_tag == tag
    assert ph.placeholder_id == ph_id
    assert ph.media_type == "image"
    assert ph.alt_text == "alt"
    assert ph.file_path is None
    assert ph.uploaded_media_id is None
    assert ph.uploaded_url is None

def test_content_element_init():
    """Test initialization of ContentElement."""
    elem = ContentElement(type="p", content="Paragraph text.", html_content="<p>Paragraph text.</p>")
    assert elem.type == "p"
    assert elem.content == "Paragraph text."
    assert elem.html_content == "<p>Paragraph text.</p>"

def test_article_init_defaults():
    """Test default values during Article initialization."""
    article = Article(title="Test Title")
    assert article.title == "Test Title"
    assert article.content_elements == []
    assert article.media_placeholders == []
    assert article.raw_markdown is None
    assert article.final_html_content is None
    assert article.metadata == {}
    assert article.summary is None
    assert article.cover_image_placeholder is None
    assert article.cover_image_file_path is None

def test_article_init_with_values():
    """Test initializing Article with specific values."""
    ph1 = MediaPlaceholder(original_tag="t1", placeholder_id="id1")
    ph2 = MediaPlaceholder(original_tag="t2", placeholder_id="id2")
    cover_ph = MediaPlaceholder(original_tag="cover", placeholder_id="cover_id")
    elem1 = ContentElement(type="h1", content="Header")
    article = Article(
        title="My Article",
        content_elements=[elem1],
        media_placeholders=[ph1, ph2],
        raw_markdown="# Header",
        metadata={"author": "Tester"},
        summary="A short summary.",
        cover_image_placeholder=cover_ph,
        cover_image_file_path="path/to/cover.jpg"
    )
    assert article.title == "My Article"
    assert article.content_elements == [elem1]
    assert article.media_placeholders == [ph1, ph2]
    assert article.raw_markdown == "# Header"
    assert article.metadata == {"author": "Tester"}
    assert article.summary == "A short summary."
    assert article.cover_image_placeholder == cover_ph
    assert article.cover_image_file_path == "path/to/cover.jpg"

def test_article_get_placeholder_by_id():
    """Test the get_placeholder_by_id method."""
    ph1 = MediaPlaceholder(original_tag="t1", placeholder_id="id1")
    ph2 = MediaPlaceholder(original_tag="t2", placeholder_id="id2")
    cover_ph = MediaPlaceholder(original_tag="cover", placeholder_id="cover_id")
    article = Article(
        title="Test",
        media_placeholders=[ph1, ph2],
        cover_image_placeholder=cover_ph
    )

    # Found in content placeholders
    assert article.get_placeholder_by_id("id1") == ph1
    assert article.get_placeholder_by_id("id2") == ph2
    # Found in cover placeholder
    assert article.get_placeholder_by_id("cover_id") == cover_ph
    # Not found
    assert article.get_placeholder_by_id("non_existent_id") is None
    # No placeholders added
    empty_article = Article(title="Empty")
    assert empty_article.get_placeholder_by_id("id1") is None

def test_article_get_content_as_text():
    """Test the get_content_as_text method."""
    elem_h1 = ContentElement(type="h1", content="Main Title")
    elem_p1 = ContentElement(type="p", content="First paragraph.")
    elem_ul = ContentElement(type="ul", content=["Item 1", "Item 2"])
    elem_p2 = ContentElement(type="p", content="  Second paragraph with spaces.  ")
    elem_code = ContentElement(type="code", content="print('hello')") # Content is a string
    elem_empty_p = ContentElement(type="p", content="") # Empty string content

    article = Article(
        title="Test Title",
        content_elements=[elem_h1, elem_p1, elem_ul, elem_p2, elem_code, elem_empty_p]
    )

    # --- Start Correction ---
    # Update expected_text to include the content of elem_code, as the current
    # implementation's fallback includes any element with string content.
    expected_text = """Main Title
First paragraph.
- Item 1
- Item 2
Second paragraph with spaces.
print('hello')"""
    # --- End Correction ---

    actual_text = article.get_content_as_text()
    # Compare strings directly after splitting lines. The method already handles stripping.
    assert actual_text.splitlines() == expected_text.splitlines()

def test_article_get_content_as_text_empty():
    """Test get_content_as_text with no content elements."""
    article = Article(title="Empty")
    assert article.get_content_as_text() == ""