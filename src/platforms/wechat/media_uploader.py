from pathlib import Path
from typing import List, Dict
from src.api.wechat.client import WeChatClient
from src.core.article_model import Image

class WeChatMediaUploader:
    """Handles uploading media files to WeChat servers."""
    
    def __init__(self, client: WeChatClient):
        self.client = client
    
    def upload_images(self, images: List[Image]) -> List[Dict]:
        """Upload a list of images to WeChat servers."""
        uploaded_media = []
        
        for img in images:
            # Skip if image is already a WeChat URL
            if "wx.qq.com" in img.url:
                uploaded_media.append({"url": img.url})
                continue
            
            # Download image if it's a URL
            if img.url.startswith(("http://", "https://")):
                # TODO: Implement image downloading
                raise NotImplementedError("Image downloading from URLs not implemented yet")
            
            # Upload local image
            file_path = Path(img.url)
            if not file_path.exists():
                raise FileNotFoundError(f"Image file not found: {img.url}")
            
            # Upload to WeChat
            response = self.client.upload_media("image", str(file_path))
            uploaded_media.append(response)
        
        return uploaded_media 