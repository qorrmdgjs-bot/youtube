"""Korean text utilities for subtitle timing and readability."""

from __future__ import annotations

import re

# Korean syllable Unicode range
HANGUL_START = 0xAC00
HANGUL_END = 0xD7A3


def is_hangul(char: str) -> bool:
    """Check if a character is a Korean syllable block."""
    return HANGUL_START <= ord(char) <= HANGUL_END


def count_syllables(text: str) -> int:
    """Count Korean syllable blocks in text.

    Each Korean character block (e.g. '가', '나') counts as one syllable.
    Non-Korean characters are ignored.
    """
    return sum(1 for c in text if is_hangul(c))


def count_characters(text: str) -> int:
    """Count visible characters (excluding whitespace)."""
    return len(re.sub(r"\s", "", text))


def estimate_reading_duration(text: str, syllables_per_sec: float = 2.5) -> float:
    """Estimate reading duration in seconds for Korean text.

    Default 2.5 syllables/sec is appropriate for senior audience (slower than
    general audience rate of 3.5-4.0).
    """
    syllable_count = count_syllables(text)
    # Also count non-Korean characters at roughly 0.3 sec each
    non_korean = len(re.sub(r"[\s]", "", re.sub(r"[\uAC00-\uD7A3]", "", text)))
    return syllable_count / syllables_per_sec + non_korean * 0.3


def split_subtitle_lines(text: str, max_chars: int = 18) -> list[str]:
    """Split text into subtitle lines at natural Korean phrase boundaries.

    Prefers breaking at:
    1. Punctuation (., !, ?, ,)
    2. Particles and postpositions (은/는/이/가/을/를/에/에서/으로)
    3. Space boundaries
    """
    if count_characters(text) <= max_chars:
        return [text.strip()]

    # Try splitting at punctuation first
    sentences = re.split(r"([.!?,])\s*", text)
    lines: list[str] = []
    current = ""

    for part in sentences:
        if not part:
            continue
        test = current + part
        if count_characters(test) <= max_chars:
            current = test
        else:
            if current:
                lines.append(current.strip())
            current = part

    if current:
        lines.append(current.strip())

    # If any line is still too long, split at spaces
    final_lines: list[str] = []
    for line in lines:
        if count_characters(line) <= max_chars:
            final_lines.append(line)
        else:
            words = line.split()
            current = ""
            for word in words:
                test = f"{current} {word}".strip()
                if count_characters(test) <= max_chars:
                    current = test
                else:
                    if current:
                        final_lines.append(current)
                    current = word
            if current:
                final_lines.append(current)

    return final_lines


def validate_subtitle_pacing(text: str, duration_sec: float, max_syllables_per_sec: float = 3.5) -> bool:
    """Check if subtitle text can be read within the given duration at senior-friendly pace."""
    syllables = count_syllables(text)
    if duration_sec <= 0:
        return False
    rate = syllables / duration_sec
    return rate <= max_syllables_per_sec
