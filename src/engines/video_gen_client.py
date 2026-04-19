"""Image-to-Video generation client using Replicate API (Wan 2.1)."""

from __future__ import annotations

import os
import time
import urllib.request
from pathlib import Path

from src.utils.logging_setup import get_logger
from src.utils.retry import with_retry

log = get_logger(__name__)


class ImageToVideoClient:
    """Convert static images to short video clips via Replicate (Wan 2.1)."""

    PRICE_PER_CLIP = 0.10  # ~$0.10 per clip for wan-2.1

    def __init__(
        self,
        model: str = "wavespeedai/wan-2.1-i2v-480p",
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

    @with_retry(max_attempts=2, min_wait=10.0, max_wait=60.0, retry_on=(Exception,))
    def generate(
        self,
        image_path: Path,
        output_path: Path,
        prompt: str = "",
        duration_sec: int = 5,
        fps: int = 16,
    ) -> float:
        """Convert an image to a short video clip.

        Args:
            image_path: Path to the source image.
            output_path: Where to save the generated video (mp4).
            prompt: Optional text prompt to guide the motion.
            duration_sec: Target video duration.
            fps: Frames per second.

        Returns:
            Cost in USD.
        """
        log.info(
            "image_to_video_generate",
            image=str(image_path),
            model=self.model,
        )

        with open(image_path, "rb") as f:
            input_params = {
                "image": f,
                "prompt": prompt or "gentle, subtle natural motion, cinematic, emotional",
                "negative_prompt": "fast motion, shaking, distortion, blurry, artifacts",
                "aspect_ratio": "16:9",
                "fast_mode": "Balanced",
                "sample_steps": 25,
                "sample_guide_scale": 5,
            }

            output = self._replicate.run(self.model, input=input_params)

        # Output is a URL or FileOutput
        video_url = str(output) if not isinstance(output, list) else str(output[0])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(video_url, str(output_path))

        log.info("image_to_video_saved", path=str(output_path))
        return self.PRICE_PER_CLIP


class PlaceholderVideoClient:
    """Fallback: skip video generation so Ken Burns is used instead."""

    def generate(self, image_path: Path, output_path: Path, **kwargs) -> float:
        log.info("placeholder_video_skip", image=str(image_path))
        return 0.0
