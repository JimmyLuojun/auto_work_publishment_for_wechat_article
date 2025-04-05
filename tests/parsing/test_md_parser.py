import pytest
from pathlib import Path
import frontmatter  # Import to potentially mock

# Assuming Article, MediaPlaceholder etc. are accessible
from src.core.article_model import Article, MediaPlaceholder
from src.parsing.md_parser import MarkdownParser


# --- Fixtures ---

@pytest.fixture
def mock_settings(monkeypatch):
    """Fixture to mock settings used by the parser."""
    class MockSettings:
        ARTICLE_AUTHOR = "Mock Default Author"
        INPUT_DIR = Path("/fake/input/dir")  # Path doesn't need to exist for some tests

    # Use the actual path where settings is expected within md_parser.py
    monkeypatch.setattr('src.parsing.md_parser.settings', MockSettings)
    return MockSettings


@pytest.fixture
def md_parser():
    """Fixture to provide a MarkdownParser instance."""
    return MarkdownParser()

@pytest.fixture
def sample_md_no_title_or_author(tmp_path):
    """Creates a sample MD file with no title and no author in frontmatter."""
    content = """---
some_other_field: value
---

Just some paragraph content.
"""
    md_file = tmp_path / "no_title_no_author_article.md"
    md_file.write_text(content, encoding='utf-8')
    return md_file

@pytest.fixture
def sample_md_with_frontmatter_author(tmp_path):
    """Creates a sample MD file with no title but with an author in frontmatter."""
    content = """---
author: Explicit Author From Frontmatter
---

Paragraph content here.
"""
    md_file = tmp_path / "frontmatter_author_article.md"
    md_file.write_text(content, encoding='utf-8')
    return md_file


# --- Test Class ---

class TestMarkdownParser:

    def test_parse_filename_title_default_author_when_no_frontmatter_author(self, md_parser, sample_md_no_title_or_author, mock_settings):
        """
        Test fallback to filename title AND fallback to default author
        when author is NOT specified in frontmatter.
        """
        article = md_parser.parse_file(sample_md_no_title_or_author)

        assert isinstance(article, Article)
        # Title should fallback to filename stem
        assert article.title == "no_title_no_author_article"
        # Author SHOULD fallback to the default from mocked settings
        assert 'author' in article.metadata, "Author key should be in metadata"
        assert article.metadata['author'] == "Mock Default Author"

    def test_parse_filename_title_uses_frontmatter_author_when_present(self, md_parser, sample_md_with_frontmatter_author, mock_settings):
        """
        Test fallback to filename title BUT uses author from frontmatter
        when author IS specified in frontmatter (overriding default).
        """
        article = md_parser.parse_file(sample_md_with_frontmatter_author)

        assert isinstance(article, Article)
        # Title should fallback to filename stem
        assert article.title == "frontmatter_author_article"
        # Author SHOULD come from the frontmatter, NOT the default settings
        assert 'author' in article.metadata, "Author key should be in metadata"
        assert article.metadata['author'] == "Explicit Author From Frontmatter"

    # Add more tests here for other scenarios (H1 title, cover images, placeholders etc.)