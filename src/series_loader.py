"""Helpers for loading series episode metadata + extracting story drafts.

The series bible (`series/our_family.yaml`) is intentionally minimal: it only
maps episode_number → (event_idx, perspective, characters, ages). Story bodies
live in markdown drafts (series/drafts/{son,father,mother}_pov_stories.md) and
are pulled in on demand by `extract_event_section`.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.models import EndingType, FamilyType, ProjectBrief

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Korean labels for the perspective field — used in the project title
PERSPECTIVE_LABELS = {
    "son": "아들 시점",
    "father": "아빠 시점",
    "mother": "엄마 시점",
}


def load_series_yaml(bible_path: Path) -> dict:
    with open(bible_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_episode_entry(series_data: dict, episode_number: int) -> dict:
    for ep in series_data.get("episodes", []):
        if ep.get("ep") == episode_number:
            return ep
    raise ValueError(f"에피소드 {episode_number} 가 시리즈 바이블에 없습니다.")


def extract_event_section(markdown_path: Path, event_idx: int) -> str:
    """Return the markdown block under '## 사건 {event_idx}: …' until the next '## 사건' heading.

    Used for the legacy 1차 정본 POV files (son/father/mother_pov_stories.md).
    """
    text = markdown_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    start: int | None = None
    end = len(lines)
    target_pattern = re.compile(rf"^##\s+사건\s+{event_idx}\s*:")
    next_event_pattern = re.compile(r"^##\s+사건\s+\d+\s*:")
    next_section_pattern = re.compile(r"^##\s+(?!사건\s)")

    for i, line in enumerate(lines):
        if start is None and target_pattern.match(line):
            start = i
            continue
        if start is not None and (next_event_pattern.match(line) or next_section_pattern.match(line)):
            end = i
            break

    if start is None:
        raise ValueError(f"'사건 {event_idx}' 섹션을 {markdown_path.name} 에서 찾을 수 없습니다.")

    return "\n".join(lines[start:end]).rstrip()


def extract_episode_section_v4(scenario_path: Path, episode_number: int) -> str:
    """Return the markdown block under '### EP{n}. …' until the next '### EP' or '## ' heading.

    Used for the v4 unified scenario (full_scenario_v4.md), which has per-episode sections.
    """
    text = scenario_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    start: int | None = None
    end = len(lines)
    target_pattern = re.compile(rf"^###\s+EP{episode_number}\.\s")
    next_episode_pattern = re.compile(r"^###\s+EP\d+\.\s")
    next_section_pattern = re.compile(r"^##\s+")

    for i, line in enumerate(lines):
        if start is None and target_pattern.match(line):
            start = i
            continue
        if start is not None and (next_episode_pattern.match(line) or next_section_pattern.match(line)):
            end = i
            break

    if start is None:
        raise ValueError(f"'EP{episode_number}' 섹션을 {scenario_path.name} 에서 찾을 수 없습니다.")

    return "\n".join(lines[start:end]).rstrip()


def _extract_story_summary(markdown_section: str) -> str:
    """Pull a synopsis (≤1000 chars) from either the v4 후킹 block or the legacy 줄거리 bullet."""
    # v4 format: "**🎞️ 후킹**\n> ..." blockquote paragraph
    hook_match = re.search(
        r"\*\*🎞️\s*후킹\*\*\s*\n((?:>.*\n?)+)",
        markdown_section,
    )
    if hook_match:
        hook_lines = hook_match.group(1).strip().split("\n")
        cleaned = " ".join(line.lstrip("> ").strip() for line in hook_lines if line.strip())
        return cleaned[:1000]

    # Legacy format: "**줄거리**: ..."
    match = re.search(
        r"\*\*줄거리[^*]*\*\*\s*:\s*(.+?)(?=\n\s*-\s+\*\*|\n\n##|\Z)",
        markdown_section,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()[:1000]

    # Fallback: first non-heading paragraph
    for line in markdown_section.split("\n"):
        clean = line.strip()
        if clean and not clean.startswith(("#", "**", ">")):
            return clean[:1000]
    return markdown_section[:1000]


def build_episode_brief(
    bible_path: Path,
    episode_number: int,
    target_duration_sec: int = 300,
    voice_gender: str = "male",
    emotional_arc_override: str | None = None,
) -> ProjectBrief:
    """Build a ProjectBrief from the series bible + the corresponding markdown section."""
    series_data = load_series_yaml(bible_path)
    episode = get_episode_entry(series_data, episode_number)
    series_meta = series_data["series"]

    drafts_dir = PROJECT_ROOT / series_meta["drafts_dir"]
    perspective: str = episode["perspective"]
    overview_file = drafts_dir / series_meta["overview"]
    event_idx: int = episode["event_idx"]

    # Prefer v4 unified scenario when configured (per-episode section).
    # Fall back to legacy POV files (per-event section) if scenario field is absent.
    scenario_filename = series_meta.get("scenario")
    if scenario_filename:
        scenario_file = drafts_dir / scenario_filename
        series_context_md = extract_episode_section_v4(scenario_file, episode_number)
    else:
        pov_file = drafts_dir / series_meta["pov_files"][perspective]
        series_context_md = extract_event_section(pov_file, event_idx)

    series_overview_md = overview_file.read_text(encoding="utf-8")

    pov_label = PERSPECTIVE_LABELS[perspective]
    full_title = f"ep{episode_number}. {episode['title']} ({pov_label})"
    if len(full_title) > 100:
        full_title = full_title[:97] + "…"

    return ProjectBrief(
        title=full_title,
        synopsis=_extract_story_summary(series_context_md),
        family_type=FamilyType(series_meta["family_type"]),
        emotional_arc=emotional_arc_override or series_meta["family_type"],
        ending_type=EndingType.HEALING,
        target_duration_sec=target_duration_sec,
        voice_gender=voice_gender,  # type: ignore[arg-type]
        # Series fields
        series_id=series_meta["id"],
        episode_number=episode["ep"],
        event_idx=event_idx,
        perspective=perspective,  # type: ignore[arg-type]
        series_context_md=series_context_md,
        series_overview_md=series_overview_md,
        characters_in_episode=dict(episode.get("characters", {})),
    )
