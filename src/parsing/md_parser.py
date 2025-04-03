import re
from pathlib import Path
from typing import List, Tuple
from src.core.article_model import Article, Paragraph, Image, CodeBlock

class MarkdownParser:
    """Parser for converting Markdown to Article model."""
    
    def __init__(self):
        self.heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
        self.image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        self.code_block_pattern = re.compile(r'```(\w*)\n([\s\S]*?)\n```')
    
    def parse_file(self, file_path: Path) -> Article:
        """Parse a Markdown file into an Article object."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract title (first heading)
        title_match = self.heading_pattern.search(content)
        if not title_match:
            raise ValueError("Markdown file must start with a heading as the title")
        
        title = title_match.group(2)
        
        # Extract images
        images = []
        for match in self.image_pattern.finditer(content):
            alt_text, url = match.groups()
            images.append(Image(url=url, alt_text=alt_text))
        
        # Extract code blocks
        code_blocks = []
        for match in self.code_block_pattern.finditer(content):
            language, code = match.groups()
            code_blocks.append(CodeBlock(code=code, language=language))
        
        # Split into paragraphs
        paragraphs = []
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Check if it's a heading
            heading_match = self.heading_pattern.match(line)
            if heading_match:
                level = len(heading_match.group(1))
                content = heading_match.group(2)
                paragraphs.append(Paragraph(
                    content=content,
                    is_heading=True,
                    level=level
                ))
            else:
                paragraphs.append(Paragraph(content=line))
        
        return Article(
            title=title,
            author="",  # This should be set from config or metadata
            paragraphs=paragraphs,
            images=images,
            code_blocks=code_blocks
        ) 