"""Image generation client using Google Gemini 3 Flash Image (Nano Banana 2)."""

from __future__ import annotations

import os
from pathlib import Path

from src.utils.logging_setup import get_logger
from src.utils.retry import with_retry

log = get_logger(__name__)


class GeminiImageClient:
    """Nano Banana 2 (Gemini 3 Flash Image) image generation.

    Supports multi-image input for character consistency via reference images.
    """

    PRICE_PER_IMAGE = 0.039  # ~$0.039/image for gemini-3.1-flash-image-preview

    def __init__(
        self,
        model: str = "gemini-3.1-flash-image-preview",
    ):
        api_key = os.environ.get("GOOGLE_GENAI_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_GENAI_API_KEY 환경변수가 설정되지 않았습니다.")

        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai 패키지가 필요합니다: pip install -e '.[gemini]'"
            )

        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self.model = model

    @with_retry(max_attempts=3, min_wait=5.0, max_wait=60.0, retry_on=(Exception,))
    def generate(
        self,
        prompt: str,
        output_path: Path,
        ref_images: list[Path] | None = None,
        seed: int | None = None,
    ) -> float:
        """Generate an image, optionally conditioned on reference images.

        Args:
            prompt: English image generation prompt.
            output_path: Where to save the generated PNG.
            ref_images: Optional reference images for character consistency.
            seed: Optional seed (accepted but Gemini image API may ignore).

        Returns:
            Cost in USD.
        """
        from google.genai import types

        contents: list = [prompt]
        if ref_images:
            for ref_path in ref_images:
                if not ref_path.exists():
                    log.warning("ref_image_missing", path=str(ref_path))
                    continue
                with open(ref_path, "rb") as f:
                    image_bytes = f.read()
                mime = "image/png" if ref_path.suffix.lower() == ".png" else "image/jpeg"
                contents.append(
                    types.Part.from_bytes(data=image_bytes, mime_type=mime)
                )

        log.info(
            "gemini_image_generate",
            prompt_len=len(prompt),
            ref_count=len(ref_images) if ref_images else 0,
            model=self.model,
        )

        response = self._client.models.generate_content(
            model=self.model,
            contents=contents,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        saved = False
        for candidate in response.candidates or []:
            for part in candidate.content.parts or []:
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    with open(output_path, "wb") as f:
                        f.write(inline.data)
                    saved = True
                    break
            if saved:
                break

        if not saved:
            raise RuntimeError("Gemini 응답에 이미지 데이터가 없습니다.")

        log.info("gemini_image_saved", path=str(output_path))
        return self.PRICE_PER_IMAGE
