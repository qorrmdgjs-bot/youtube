"""Image-to-Video generation client using Google Veo 3.1 Fast."""

from __future__ import annotations

import os
import time
from pathlib import Path

from src.utils.logging_setup import get_logger
from src.utils.retry import with_retry

log = get_logger(__name__)


class VeoVideoClient:
    """Convert a still image to a short video clip via Veo 3.1 Fast."""

    PRICE_PER_SECOND = 0.10  # Veo 3.1 Fast (audio off)
    POLL_INTERVAL_SEC = 10
    POLL_TIMEOUT_SEC = 600

    def __init__(
        self,
        model: str = "veo-3.1-fast-generate-preview",
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

    @with_retry(max_attempts=2, min_wait=10.0, max_wait=60.0, retry_on=(Exception,))
    def generate(
        self,
        image_path: Path,
        output_path: Path,
        prompt: str = "",
        duration_sec: int = 6,
        ref_images: list[Path] | None = None,
    ) -> float:
        """Convert an image to a short video clip via Veo 3.1.

        Args:
            image_path: Source PNG.
            output_path: Destination MP4.
            prompt: Motion description in English.
            duration_sec: Target duration in seconds (Veo min/max depends on model).
            ref_images: Ignored here (Veo image-to-video uses the source image only).

        Returns:
            Cost in USD.
        """
        from google.genai import types

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"

        log.info(
            "veo_generate_start",
            image=str(image_path),
            model=self.model,
            duration_sec=duration_sec,
        )

        # Note: Gemini API (generativelanguage) does not support generate_audio parameter;
        # that flag is Vertex AI only. Omit it here. Audio track is stripped in H stage anyway.
        op = self._client.models.generate_videos(
            model=self.model,
            prompt=prompt or "gentle natural motion, cinematic, emotional",
            image=types.Image(image_bytes=image_bytes, mime_type=mime),
            config=types.GenerateVideosConfig(
                duration_seconds=duration_sec,
                aspect_ratio="16:9",
            ),
        )

        elapsed = 0
        while not op.done:
            if elapsed > self.POLL_TIMEOUT_SEC:
                raise TimeoutError(
                    f"Veo 작업이 {self.POLL_TIMEOUT_SEC}초 내에 끝나지 않았습니다."
                )
            time.sleep(self.POLL_INTERVAL_SEC)
            elapsed += self.POLL_INTERVAL_SEC
            op = self._client.operations.get(op)

        response = getattr(op, "response", None) or getattr(op, "result", None)
        if response is None:
            raise RuntimeError("Veo 응답이 비어있습니다.")

        videos = getattr(response, "generated_videos", None) or []
        if not videos:
            raise RuntimeError("Veo 응답에 생성된 영상이 없습니다.")

        video_obj = videos[0].video
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Gemini Files API로 다운로드 (API 키 인증 자동 처리).
        # SDK 버전에 따라 경로가 다를 수 있어 3단계 폴백.
        saved = False
        try:
            # 최신 SDK: client.files.download + Video.save()
            self._client.files.download(file=video_obj)
            video_obj.save(str(output_path))
            saved = True
        except Exception as e1:
            log.warning("veo_download_method1_failed", error=str(e1))

        if not saved:
            try:
                # 대안: Video.save()가 내부 다운로드까지 처리하는 버전
                video_obj.save(str(output_path))
                saved = True
            except Exception as e2:
                log.warning("veo_download_method2_failed", error=str(e2))

        if not saved:
            # 최후 수단: urllib + API 키 쿼리 파라미터
            import urllib.request
            video_uri = getattr(video_obj, "uri", None) or getattr(video_obj, "url", None)
            if not video_uri:
                raise RuntimeError("Veo 영상 URI를 찾을 수 없고 save()도 실패했습니다.")
            sep = "&" if "?" in video_uri else "?"
            auth_uri = f"{video_uri}{sep}key={os.environ['GOOGLE_GENAI_API_KEY']}"
            urllib.request.urlretrieve(auth_uri, str(output_path))
            saved = True

        log.info("veo_video_saved", path=str(output_path))
        return self.PRICE_PER_SECOND * duration_sec
