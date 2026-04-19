"""ElevenLabs TTS client for high-quality Korean narration."""

from __future__ import annotations

import os
from pathlib import Path

import requests

from src.utils.logging_setup import get_logger
from src.utils.retry import with_retry

log = get_logger(__name__)


class ElevenLabsTTSClient:
    """ElevenLabs Text-to-Speech with Korean native voices."""

    # Pricing: ~$0.30 per 1000 characters (Starter plan)
    PRICE_PER_CHAR = 0.30 / 1000

    # Korean native voices
    VOICES = {
        "female": "5I7B1di44aCL15NkP0jn",  # Kanna - Calm & Friendly
        "male": "prgs92xTdxeczorJi7ez",      # Haechan - Dignified
    }

    def __init__(
        self,
        voice_gender: str = "female",
        model_id: str = "eleven_multilingual_v2",
    ):
        self.api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY 환경변수가 설정되지 않았습니다.")

        self.voice_id = self.VOICES.get(voice_gender, self.VOICES["female"])
        self.model_id = model_id

    @with_retry(max_attempts=3, min_wait=2.0, max_wait=30.0, retry_on=(Exception,))
    def synthesize(
        self,
        text: str,
        output_path: Path,
        **kwargs,
    ) -> float:
        """Synthesize Korean text to speech.

        Args:
            text: Korean narration text.
            output_path: Where to save the MP3 file.

        Returns:
            Cost in USD.
        """
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.55,
                "similarity_boost": 0.80,
                "style": 0.25,
                "use_speaker_boost": True,
            },
        }

        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
            headers=headers,
            json=payload,
            timeout=60,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"ElevenLabs API error: {response.status_code} {response.text[:200]}"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)

        char_count = len(text)
        cost = char_count * self.PRICE_PER_CHAR

        log.info(
            "elevenlabs_tts_synthesized",
            chars=char_count,
            output=str(output_path),
            cost_usd=round(cost, 4),
        )

        return cost
