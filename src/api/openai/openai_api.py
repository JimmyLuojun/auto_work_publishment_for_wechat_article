# /Users/junluo/Documents/auto_work_publishment_for_wechat_article/src/api/openai/openai_api.py

"""
OpenAI API Client for Image Generation

Purpose:
Provides methods to interact with the OpenAI API, specifically for
generating images using DALL-E models based on text prompts.

Dependencies:
- openai (external library, >=1.0.0)
- requests (external library)
- pathlib (standard Python library)
- typing (standard Python library)
- src.core.settings
- src.utils.logger

Expected Input: Requires OpenAI API Key configured in settings.
Expected Output: Methods generate images and save them locally, returning the file path.
"""

import openai
import requests
from pathlib import Path
from typing import Optional, Literal, Tuple

from src.core import settings
from src.utils.logger import log

# Define allowed types for better type hinting, based on OpenAI documentation
ImageSize = Literal["1024x1024", "1792x1024", "1024x1792"] # DALL-E 3 sizes
ImageQuality = Literal["standard", "hd"]
ImageStyle = Literal["vivid", "natural"]

class OpenAIClient:
    """
    Client for interacting with the OpenAI API, focusing on DALL-E image generation.
    Uses the official 'openai' library.
    """

    def __init__(self):
        """Initializes the OpenAIClient."""
        if not settings.OPENAI_API_KEY:
            log.error("OpenAI API Key (OPENAI_API_KEY) not found in environment variables/settings.")
            raise ValueError("OPENAI_API_KEY must be configured to use OpenAIClient.")

        try:
            self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = settings.OPENAI_IMAGE_MODEL
            log.info(f"OpenAIClient initialized successfully for model: {self.model}")
        except Exception as e:
            log.exception(f"Failed to initialize OpenAI client: {e}")
            raise

    def generate_image(
        self,
        prompt: str,
        output_path: Path,
        size: ImageSize = "1024x1024",
        quality: ImageQuality = "standard",
        style: ImageStyle = "vivid"
    ) -> Optional[Path]:
        """
        Generates an image using OpenAI's DALL-E model based on a prompt,
        downloads it, and saves it to the specified local path.

        Args:
            prompt (str): The text description of the image to generate.
            output_path (Path): The full local path (including filename and extension, e.g., .png)
                                where the generated image should be saved.
            size (ImageSize): The desired size of the image. Defaults to "1024x1024".
            quality (ImageQuality): The quality of the image. Defaults to "standard".
                                   "hd" provides higher detail but may cost more.
            style (ImageStyle): The style of the generated image ('vivid' or 'natural').
                                Defaults to "vivid".

        Returns:
            Optional[Path]: The path to the saved image file if successful, None otherwise.
        """
        if not prompt:
            log.error("Image generation prompt cannot be empty.")
            return None
        if not output_path:
             log.error("Output path for saving the image cannot be empty.")
             return None

        # Ensure the output directory exists
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            log.error(f"Failed to create output directory {output_path.parent}: {e}")
            return None

        log.info(f"Requesting image generation from OpenAI DALL-E (model: {self.model})")
        log.debug(f"Prompt: '{prompt}', Size: {size}, Quality: {quality}, Style: {style}")

        try:
            response = self.client.images.generate(
                model=self.model,
                prompt=prompt,
                n=1,  # DALL-E 3 currently supports n=1
                size=size,
                quality=quality,
                style=style,
                response_format="url" # Get URL to download from
            )

            # Extract URL (DALL-E 3 response structure)
            if response.data and len(response.data) > 0 and response.data[0].url:
                image_url = response.data[0].url
                log.info(f"Image generated successfully. URL: {image_url}")

                # Download the image from the URL
                log.info(f"Downloading image from URL to {output_path}...")
                download_success, error_msg = self._download_image(image_url, output_path)

                if download_success:
                    log.info(f"Image successfully downloaded and saved to: {output_path}")
                    return output_path
                else:
                    log.error(f"Failed to download image: {error_msg}")
                    return None
            else:
                log.error(f"Failed to get image URL from OpenAI response: {response}")
                return None

        except openai.APIConnectionError as e:
            log.error(f"OpenAI API request failed to connect: {e}")
            return None
        except openai.RateLimitError as e:
            log.error(f"OpenAI API request exceeded rate limit: {e}")
            return None
        except openai.AuthenticationError as e:
             log.error(f"OpenAI API authentication failed (check API key): {e}")
             return None
        except openai.BadRequestError as e:
             log.error(f"OpenAI API request was invalid (check prompt, size, etc.): {e}")
             return None
        except openai.APIError as e:
            log.error(f"OpenAI API returned an API Error: {e}")
            return None
        except Exception as e:
            log.exception(f"An unexpected error occurred during image generation: {e}")
            return None

    def _download_image(self, url: str, save_path: Path) -> Tuple[bool, Optional[str]]:
        """Downloads an image from a URL and saves it."""
        try:
            response = requests.get(url, stream=True, timeout=60) # Add timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True, None
        except requests.exceptions.Timeout:
             return False, f"Request timed out while downloading from {url}"
        except requests.exceptions.RequestException as e:
            return False, f"Failed to download image from {url}: {e}"
        except IOError as e:
            return False, f"Failed to save image to {save_path}: {e}"
        except Exception as e:
             # Catch unexpected errors during download/save
             log.exception(f"Unexpected error downloading/saving image from {url} to {save_path}: {e}")
             return False, f"An unexpected error occurred: {e}"

# Example Usage (demonstration)
# Ensure settings are loaded, e.g., by running from main.py context or mocking settings
if __name__ == '__main__':
    # This example requires OPENAI_API_KEY to be set in your .env
    # and expects settings.py to load it correctly.
    try:
        log.info("--- OpenAI Client Test ---")
        client = OpenAIClient() # Assumes settings are loaded via import

        prompt = "A cute cartoon robot waving hello, digital art style"
        # Define output path relative to current execution (adjust as needed)
        output_dir = Path("./temp_openai_output")
        output_filename = "test_robot_image.png"
        output_file_path = output_dir / output_filename

        log.info(f"Attempting to generate image for prompt: '{prompt}'")
        saved_path = client.generate_image(prompt=prompt, output_path=output_file_path)

        if saved_path:
            print(f"Success! Image saved to: {saved_path.resolve()}")
        else:
            print("Image generation failed. Check logs.")

        # Clean up the generated file/dir if desired
        # if saved_path and saved_path.exists():
        #     saved_path.unlink()
        # if output_dir.exists():
        #     try:
        #         output_dir.rmdir() # Only removes if empty
        #     except OSError:
        #         pass # Directory might not be empty if something went wrong

    except ValueError as e:
        print(f"Test failed: {e}") # Likely missing API key
    except Exception as e:
        print(f"An unexpected error occurred during the test: {e}")