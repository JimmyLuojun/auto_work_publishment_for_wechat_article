# -*- coding: utf-8 -*-
"""
article_model.py - Defines the internal data structure for articles.

Responsibilities:
- Define Python classes representing the components of an article (paragraphs,
  headings, images, etc.) after parsing and before platform-specific formatting.
- Provide a standardized, platform-agnostic way to represent article content
  within the application.

Dependencies:
- dataclasses: For concise data class definitions.
- typing: For type hinting.

Expected Input: None (Defines structures used by other modules).
Expected Output: Class definitions (`Article`, `ContentBlock` subclasses).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Protocol # Protocol for structural subtyping

# --- Content Block Definitions ---

@dataclass
class ContentBlock(Protocol):
    """Base protocol for all content block types."""
    # Protocols define structure, not implementation. Useful for type checking.
    pass

@dataclass
class Paragraph(ContentBlock):
    """Represents a standard paragraph of text."""
    text: str

@dataclass
class Heading(ContentBlock):
    """Represents a heading element."""
    level: int  # e.g., 1 for H1, 2 for H2
    text: str

@dataclass
class ImagePlaceholder(ContentBlock):
    """
    Represents an image placeholder identified during parsing.
    Will be updated with media_id after upload.
    """
    alt_text: Optional[str]
    local_path: str # Path relative to input file or absolute path
    wechat_media_id: Optional[str] = None # To be filled after upload

@dataclass
class VideoPlaceholder(ContentBlock):
    """
    Represents a video placeholder identified during parsing.
    Will be updated with media_id after upload.
    """
    local_path: str # Path relative to input file or absolute path
    wechat_media_id: Optional[str] = None # To be filled after upload
    # Add title or other video attributes if needed

@dataclass
class CodeBlock(ContentBlock):
    """Represents a block of preformatted code."""
    language: Optional[str] # Programming language hint (e.g., 'python')
    code: str

@dataclass
class UnparsedBlock(ContentBlock):
    """Represents a block that couldn't be specifically parsed (fallback)."""
    raw_content: str

# --- Article Definition ---

@dataclass
class Article:
    """
    Represents the entire article structure after parsing.
    This is the central data object passed between modules.
    """
    title: str
    # Optional: Add author if parsed from Markdown frontmatter
    # author: Optional[str] = None
    content_blocks: List[ContentBlock] = field(default_factory=list)
    # Optional: Store original markdown path
    source_path: Optional[str] = None
    # Optional: Store frontmatter metadata if parsed
    metadata: dict = field(default_factory=dict)

# --- Explanation ---
# Purpose: Defines a clear, structured, in-memory representation of an article.
#          This decouples the parsing logic from the formatting/publishing logic.
# Design Choices:
# - Uses `dataclasses` for simplicity and boilerplate reduction.
# - Defines a base `ContentBlock` protocol and specific subclasses for different
#   content types (Paragraph, Heading, ImagePlaceholder, etc.). This allows for
#   easy type checking and handling in the formatter.
# - `ImagePlaceholder` and `VideoPlaceholder` include a `wechat_media_id` field,
#   initially None, to be populated after media upload. This keeps related data together.
# - The main `Article` class aggregates the title and a list of `ContentBlock` objects.
# Improvements/Alternatives:
# - Could add more block types (Lists, Blockquotes, Tables) as needed.
# - Could use a library like Pydantic for more advanced validation if required.
# - The `ContentBlock` could be an abstract base class (`abc.ABC`) instead of a
#   protocol if common implementation logic was needed, but protocol is fine for structure.