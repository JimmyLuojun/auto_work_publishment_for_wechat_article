from typing import List
from src.core.article_model import Article, Paragraph, Image, CodeBlock

class WeChatFormatter:
    """Formatter for converting Article objects to WeChat-compatible HTML."""
    
    def __init__(self):
        self.css = """
        .article {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .title {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 20px;
        }
        .author {
            color: #666;
            margin-bottom: 20px;
        }
        h1, h2, h3, h4, h5, h6 {
            margin-top: 30px;
            margin-bottom: 15px;
            font-weight: bold;
        }
        p {
            margin-bottom: 15px;
        }
        img {
            max-width: 100%;
            height: auto;
            margin: 20px 0;
        }
        pre {
            background-color: #f6f8fa;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            margin: 20px 0;
        }
        code {
            font-family: Consolas, Monaco, 'Andale Mono', monospace;
        }
        """
    
    def format_article(self, article: Article) -> str:
        """Convert an Article object to WeChat-compatible HTML."""
        html_parts = [
            '<div class="article">',
            f'<h1 class="title">{article.title}</h1>',
            f'<div class="author">作者：{article.author}</div>'
        ]
        
        # Add paragraphs
        for para in article.paragraphs:
            if para.is_heading:
                html_parts.append(f'<h{para.level}>{para.content}</h{para.level}>')
            else:
                html_parts.append(f'<p>{para.content}</p>')
        
        # Add images
        for img in article.images:
            img_html = f'<img src="{img.url}"'
            if img.alt_text:
                img_html += f' alt="{img.alt_text}"'
            if img.caption:
                img_html += f' title="{img.caption}"'
            img_html += '>'
            html_parts.append(img_html)
        
        # Add code blocks
        for code_block in article.code_blocks:
            lang_class = f' class="language-{code_block.language}"' if code_block.language else ''
            html_parts.append(f'<pre{lang_class}><code>{code_block.code}</code></pre>')
        
        html_parts.append('</div>')
        
        # Combine all parts
        html = '\n'.join(html_parts)
        
        # Add CSS
        html = f'<style>{self.css}</style>\n{html}'
        
        return html 