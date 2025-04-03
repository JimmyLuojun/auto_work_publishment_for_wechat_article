import argparse
from pathlib import Path
from src.core.settings import settings
from src.parsing.md_parser import MarkdownParser
from src.platforms.wechat.publisher import WeChatPublisher

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Publish articles to WeChat Official Account")
    parser.add_argument("input_file", help="Path to the input Markdown file")
    parser.add_argument("--preview", action="store_true", help="Generate preview HTML without publishing")
    args = parser.parse_args()
    
    # Initialize components
    parser = MarkdownParser()
    publisher = WeChatPublisher()
    
    # Parse the input file
    input_path = Path(args.input_file)
    article = parser.parse_file(input_path)
    
    if args.preview:
        # Generate preview HTML
        html_content = publisher.formatter.format_article(article)
        preview_path = settings.output_dir / "wechat_preview.html"
        preview_path.write_text(html_content, encoding="utf-8")
        print(f"Preview generated at: {preview_path}")
    else:
        # Publish to WeChat
        response = publisher.publish(article)
        print("Article published successfully!")
        print(f"Response: {response}")

if __name__ == "__main__":
    main() 