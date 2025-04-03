from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Image:
    """Represents an image in an article."""
    url: str
    alt_text: Optional[str] = None
    caption: Optional[str] = None

@dataclass
class CodeBlock:
    """Represents a code block in an article."""
    code: str
    language: Optional[str] = None

@dataclass
class Paragraph:
    """Represents a paragraph in an article."""
    content: str
    is_heading: bool = False
    level: Optional[int] = None  # For headings, 1-6

@dataclass
class Article:
    """Represents a complete article."""
    title: str
    author: str
    paragraphs: List[Paragraph]
    images: List[Image]
    code_blocks: List[CodeBlock]
    
    def __post_init__(self):
        """Validate the article structure after initialization."""
        if not self.title:
            raise ValueError("Article must have a title")
        if not self.author:
            raise ValueError("Article must have an author") 