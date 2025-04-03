from typing import Dict
from src.core.article_model import Article
from src.api.wechat.client import WeChatClient
from .formatter import WeChatFormatter
from .media_uploader import WeChatMediaUploader

class WeChatPublisher:
    """Handles the complete workflow for publishing articles to WeChat."""
    
    def __init__(self):
        self.client = WeChatClient()
        self.formatter = WeChatFormatter()
        self.media_uploader = WeChatMediaUploader(self.client)
    
    def publish(self, article: Article) -> Dict:
        """Publish an article to WeChat."""
        # 1. Upload images
        uploaded_media = self.media_uploader.upload_images(article.images)
        
        # 2. Format article with WeChat-compatible HTML
        html_content = self.formatter.format_article(article)
        
        # 3. Create draft article
        draft_article = {
            "title": article.title,
            "author": article.author,
            "content": html_content,
            "digest": "",  # TODO: Generate digest from content
            "content_source_url": "",  # TODO: Add source URL if available
            "thumb_media_id": "",  # TODO: Add thumbnail if needed
        }
        
        # 4. Add to draft
        draft_response = self.client.add_draft([draft_article])
        
        # 5. Publish the draft
        publish_response = self.client.publish(draft_response["media_id"])
        
        return publish_response 