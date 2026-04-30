"""Factory for image/video engine selection with automatic fallback."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol

from src.utils.logging_setup import get_logger

log = get_logger(__name__)


class ImageClientProtocol(Protocol):
    def generate(
        self,
        prompt: str,
        output_path: Path,
        ref_images: list[Path] | None = None,
        seed: int | None = None,
    ) -> float: ...


class VideoClientProtocol(Protocol):
    def generate(
        self,
        image_path: Path,
        output_path: Path,
        prompt: str = "",
        duration_sec: int = 6,
        ref_images: list[Path] | None = None,
    ) -> float: ...


class _ImageClientWithFallback:
    """Wraps a primary image client with an ordered list of fallbacks."""

    def __init__(self, clients: list[Any]):
        if not clients:
            raise ValueError("적어도 하나의 이미지 클라이언트가 필요합니다.")
        self._clients = clients

    def generate(
        self,
        prompt: str,
        output_path: Path,
        ref_images: list[Path] | None = None,
        seed: int | None = None,
    ) -> float:
        last_error: Exception | None = None
        for idx, client in enumerate(self._clients):
            try:
                try:
                    return client.generate(
                        prompt=prompt,
                        output_path=output_path,
                        ref_images=ref_images,
                        seed=seed,
                    )
                except TypeError:
                    return client.generate(
                        prompt=prompt, output_path=output_path, seed=seed
                    )
            except Exception as e:
                last_error = e
                log.warning(
                    "image_client_failed_fallback",
                    client=client.__class__.__name__,
                    index=idx,
                    error=str(e),
                )
        assert last_error is not None
        raise last_error


def get_image_client(settings: dict | None = None) -> Any:
    """Return an image client according to settings, with fallbacks.

    settings["image_engine"] = "gemini" | "flux" (default: "gemini")
    """
    engine = "gemini"
    if settings:
        engine = settings.get("image", {}).get("engine", engine)

    clients: list[Any] = []

    if engine == "gemini" and os.environ.get("GOOGLE_GENAI_API_KEY"):
        try:
            from src.engines.gemini_image_client import GeminiImageClient
            clients.append(GeminiImageClient())
        except Exception as e:
            log.warning("gemini_client_init_failed", error=str(e))

    if os.environ.get("REPLICATE_API_TOKEN"):
        try:
            from src.engines.image_client import ImageClient
            clients.append(ImageClient())
        except Exception as e:
            log.warning("flux_client_init_failed", error=str(e))

    if not clients:
        from src.engines.image_client import PlaceholderImageClient
        log.warning("no_image_api_keys, using placeholder")
        return PlaceholderImageClient()

    if len(clients) == 1:
        return clients[0]
    return _ImageClientWithFallback(clients)


def get_video_client(settings: dict | None = None) -> Any | None:
    """Return a video client according to settings, or None for Ken Burns only.

    settings["video_engine"] = "veo_selective" | "veo_all" | "ken_burns" (default: "ken_burns")
    Returns None if ken_burns mode (no AI video client needed).
    """
    engine = "ken_burns"
    if settings:
        engine = settings.get("video_engine", {}).get("engine", engine)

    if engine == "ken_burns":
        return None

    if engine in ("veo_selective", "veo_all") and os.environ.get("GOOGLE_GENAI_API_KEY"):
        try:
            from src.engines.veo_video_client import VeoVideoClient
            return VeoVideoClient()
        except Exception as e:
            log.warning("veo_client_init_failed_fallback_wan", error=str(e))

    if os.environ.get("REPLICATE_API_TOKEN"):
        try:
            from src.engines.video_gen_client import ImageToVideoClient
            return ImageToVideoClient()
        except Exception as e:
            log.warning("wan_client_init_failed", error=str(e))

    log.warning("no_video_api_keys, video engine disabled (ken_burns only)")
    return None
