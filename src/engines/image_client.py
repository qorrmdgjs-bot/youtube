"""Image generation client using Replicate API (FLUX.1 Pro)."""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path

from src.utils.logging_setup import get_logger
from src.utils.retry import with_retry

log = get_logger(__name__)


class ImageClient:
    """FLUX.1 Pro image generation via Replicate API."""

    # Approximate pricing per image
    PRICE_PER_IMAGE = 0.055  # ~$0.055 for FLUX.1 Pro

    def __init__(
        self,
        model: str = "black-forest-labs/flux-1.1-pro",
        width: int = 1440,
        height: int = 810,
    ):
        api_token = os.environ.get("REPLICATE_API_TOKEN")
        if not api_token:
            raise ValueError("REPLICATE_API_TOKEN 환경변수가 설정되지 않았습니다.")

        try:
            import replicate
        except ImportError:
            raise ImportError("replicate 패키지가 필요합니다: pip install replicate")

        self._replicate = replicate
        self.model = model
        self.width = width
        self.height = height

    @with_retry(max_attempts=3, min_wait=5.0, max_wait=60.0, retry_on=(Exception,))
    def generate(self, prompt: str, output_path: Path, seed: int | None = None) -> float:
        """Generate an image from a prompt.

        Args:
            prompt: Image generation prompt (English).
            output_path: Where to save the generated image.
            seed: Optional seed for reproducibility.

        Returns:
            Cost in USD.
        """
        input_params = {
            "prompt": prompt,
            "width": self.width,
            "height": self.height,
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
        }
        if seed is not None:
            input_params["seed"] = seed

        log.info("image_generate", prompt_len=len(prompt), model=self.model)

        output = self._replicate.run(self.model, input=input_params)

        # Output is a URL or FileOutput - download the image
        image_url = str(output) if not isinstance(output, list) else str(output[0])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(image_url, str(output_path))

        log.info("image_saved", path=str(output_path))
        return self.PRICE_PER_IMAGE


class PlaceholderImageClient:
    """Generates placeholder images using Pillow when API is unavailable."""

    def generate(self, prompt: str, output_path: Path, seed: int | None = None) -> float:
        """Generate a placeholder image with text overlay."""
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (1920, 1080), color=(40, 40, 60))
        draw = ImageDraw.Draw(img)

        # Draw scene info text
        lines = [
            "[ Placeholder Image ]",
            "",
            prompt[:80] + ("..." if len(prompt) > 80 else ""),
        ]
        y = 400
        for line in lines:
            draw.text((200, y), line, fill=(200, 200, 200))
            y += 40

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), quality=90)

        log.info("placeholder_image_saved", path=str(output_path))
        return 0.0
