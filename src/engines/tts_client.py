"""TTS client supporting Google Cloud TTS with SSML for emotional pauses."""

from __future__ import annotations

import os
import re
from pathlib import Path

from src.utils.logging_setup import get_logger
from src.utils.retry import with_retry

log = get_logger(__name__)


class TTSClient:
    """Google Cloud Text-to-Speech client with SSML support."""

    # Pricing: $16 per 1M characters (WaveNet)
    PRICE_PER_CHAR = 16.0 / 1_000_000

    def __init__(
        self,
        voice_name: str = "ko-KR-Wavenet-A",
        speaking_rate: float = 0.9,
        pitch: float = 0.0,
    ):
        try:
            from google.cloud import texttospeech
        except ImportError:
            raise ImportError(
                "google-cloud-texttospeech가 필요합니다: pip install google-cloud-texttospeech"
            )

        self._tts = texttospeech
        self.client = texttospeech.TextToSpeechClient()
        self.voice_name = voice_name
        self.speaking_rate = speaking_rate
        self.pitch = pitch

    def _build_ssml(self, text: str, has_silence_before: bool = False, silence_sec: float = 0.0) -> str:
        """Convert plain text to SSML with natural pauses.

        Handles:
        - [침묵] markers → long break
        - Sentence-ending punctuation → natural breath pause
        - Commas → short pause
        - Prosody for emotional sections
        """
        ssml = "<speak>"

        if has_silence_before and silence_sec > 0:
            ms = int(silence_sec * 1000)
            ssml += f'<break time="{ms}ms"/>'

        # Replace [침묵] markers with break tags
        processed = re.sub(
            r"\[침묵\]",
            '<break time="1200ms"/>',
            text,
        )

        # Natural breath pauses after sentences (shorter = more natural)
        processed = re.sub(
            r"([.]) ",
            r'\1<break time="350ms"/> ',
            processed,
        )
        processed = re.sub(
            r"([!?]) ",
            r'\1<break time="450ms"/> ',
            processed,
        )

        # Short pause after commas (like natural speech)
        processed = re.sub(
            r",\s+",
            r',<break time="150ms"/> ',
            processed,
        )

        # Ellipsis gets a thoughtful pause
        processed = re.sub(
            r"\.\.\.",
            r'<break time="600ms"/>',
            processed,
        )

        ssml += processed
        ssml += "</speak>"
        return ssml

    @with_retry(max_attempts=3, min_wait=1.0, max_wait=30.0, retry_on=(Exception,))
    def synthesize(
        self,
        text: str,
        output_path: Path,
        has_silence_before: bool = False,
        silence_sec: float = 0.0,
    ) -> float:
        """Synthesize text to speech and save as MP3.

        Args:
            text: Korean narration text.
            output_path: Where to save the MP3 file.
            has_silence_before: Whether to add silence before speech.
            silence_sec: Duration of silence in seconds.

        Returns:
            Cost in USD.
        """
        ssml = self._build_ssml(text, has_silence_before, silence_sec)

        voice = self._tts.VoiceSelectionParams(
            language_code="ko-KR",
            name=self.voice_name,
        )
        audio_config = self._tts.AudioConfig(
            audio_encoding=self._tts.AudioEncoding.MP3,
            speaking_rate=self.speaking_rate,
            pitch=self.pitch,
        )
        synthesis_input = self._tts.SynthesisInput(ssml=ssml)

        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.audio_content)

        char_count = len(text)
        cost = char_count * self.PRICE_PER_CHAR

        log.info(
            "tts_synthesized",
            chars=char_count,
            output=str(output_path),
            cost_usd=round(cost, 4),
        )

        return cost

    def get_audio_duration(self, audio_path: Path) -> float:
        """Get duration of an audio file in seconds using ffprobe."""
        import subprocess

        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip())
