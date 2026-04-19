"""Tests for Korean text utilities."""

from src.utils.hangul_utils import (
    count_syllables,
    estimate_reading_duration,
    is_hangul,
    split_subtitle_lines,
    validate_subtitle_pacing,
)


def test_is_hangul():
    assert is_hangul("가")
    assert is_hangul("힣")
    assert not is_hangul("a")
    assert not is_hangul("1")
    assert not is_hangul(" ")


def test_count_syllables():
    assert count_syllables("안녕하세요") == 5
    assert count_syllables("Hello 세상") == 2
    assert count_syllables("") == 0
    assert count_syllables("abc 123") == 0


def test_estimate_reading_duration():
    # 5 syllables at 2.5 syl/sec = 2.0 seconds
    duration = estimate_reading_duration("안녕하세요")
    assert 1.9 <= duration <= 2.1

    # With non-Korean characters
    duration = estimate_reading_duration("Hello 세상")
    assert duration > 0


def test_split_subtitle_lines_short():
    lines = split_subtitle_lines("짧은 문장")
    assert lines == ["짧은 문장"]


def test_split_subtitle_lines_long():
    text = "아버지는 매일 새벽 네 시에 일어나 도시락을 싸셨습니다"
    lines = split_subtitle_lines(text, max_chars=18)
    assert len(lines) >= 2
    for line in lines:
        assert len(line.replace(" ", "")) <= 18


def test_validate_subtitle_pacing_ok():
    # 5 syllables in 3 seconds = 1.67 syl/sec (under 3.5 limit)
    assert validate_subtitle_pacing("안녕하세요", 3.0)


def test_validate_subtitle_pacing_too_fast():
    # 10 syllables in 1 second = 10 syl/sec (over 3.5 limit)
    assert not validate_subtitle_pacing("가나다라마바사아자차", 1.0)


def test_validate_subtitle_pacing_zero_duration():
    assert not validate_subtitle_pacing("테스트", 0.0)
