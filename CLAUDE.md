# YouTube 가족 드라마 시리즈 자동화 파이프라인

한 가족의 30년 일대기를 **다중시점 시리즈**로 풀어내는 한국 시니어 대상 유튜브 채널.

## 채널

- 채널명: **부모님께 드리는 이야기**
- 핸들: **@loveu-fam**
- 채널 ID: `UCklS5vu3fPwRCWajfj0HYjg`
- 카테고리: 인물 및 블로그 (category_id: 22)
- 브랜딩: `assets/branding/`

## 오늘까지 (2026-04-25)

### 완료된 작업

1. **시리즈 비전 확정** — 한 가족 일대기 × 10개 핵심 사건 × 시점별 deep-dive = **22화** (당초 30화에서 조정. 시점은 dramatic peak에만 추가)
2. **Phase 1 캐릭터 anchor 13장 생성** — Nano Banana 2로 4종 가족 유형 ([assets/characters/](assets/characters/), $0.51)
3. **스토리 초안 3 POV 확정** — 사용자가 직접 작성. 이 시리즈의 north star
4. **계획서·메모리·CLAUDE.md 정합성 정리**
5. **GitHub 동기화** — `qorrmdgjs-bot/youtube` main 브랜치

### 스토리 자산 (영상 제작의 기준)

| 파일 | 내용 |
|------|------|
| [series/drafts/son_pov_stories.md](series/drafts/son_pov_stories.md) | 아들 시점 10편 (시리즈의 척추) |
| [series/drafts/father_pov_stories.md](series/drafts/father_pov_stories.md) | 아버지 시점 4편 (사건 1·4·6·8) |
| [series/drafts/mother_pov_stories.md](series/drafts/mother_pov_stories.md) | 어머니 시점 4편 (사건 1·3·5·7) |
| [series/drafts/series_overview.md](series/drafts/series_overview.md) | 시리즈 메시지·톤·POV 매트릭스 |
| [series/prompts/son_pov_story_drafts.md](series/prompts/son_pov_story_drafts.md) | 외부 AI용 프롬프트 (아카이브) |

**모든 스크립트(LLM 생성) 작업은 위 4개 마크다운 파일을 source-of-truth로 참조해야 함.**

### 사건별 POV 커버리지 (확정 22화)

| 사건 | 시기 | 아들 ep | 아빠 ep | 엄마 ep |
|---|---|:---:|:---:|:---:|
| 1 — 어머니의 도시락 | 1985 봄 | ep1 | ep2 | ep3 |
| 2 — 88올림픽 컬러 TV | 1988 여름 | ep4 | — | — |
| 3 — 누나의 운동화 | 1991 가을 | ep5 | — | ep6 |
| 4 — 비 오는 날 마중 | 1994 여름 | ep7 | ep8 | — |
| 5 — IMF 거실의 어둠 | 1997 겨울 | ep9 | ep10 | ep11 |
| 6 — 택시 운전석의 아버지 | 1999 가을 | ep12 | ep13 | — |
| 7 — 첫 월급 봉투 | 2005 겨울 | ep14 | — | ep15 |
| 8 — 결혼식 떨리는 손 | 2010 가을 | ep16 | ep17 | ep18 |
| 9 — 스마트폰 묻는 아버지 | 2019 명절 | ep19 | ep20 | — |
| 10 — 아버지의 택시 장부 | 2025 봄 | ep21 | — | ep22 |

발행 순서: 사건 순(1→10), 시점 순(아들→아빠→엄마, 존재하는 것만). 주 5회 = 약 4-5주 분량.

**소품 callback 원칙** (영상 제작 핵심): 각 사건마다 시그니처 소품이 시점 사이를 연결. 시청자가 "아! 저 장면이 이런 뜻이었구나" 무릎 치는 효과. 매트릭스 전문은 [series/drafts/series_overview.md](series/drafts/series_overview.md) 참조.

## 시리즈 비전 (변경 불가)

- 한 가족(parent_sacrifice 5인) 30년 일대기를 22화 시리즈로
- 5분/편, 주 5회 발행
- 시간 스팬: 1985(아들 10세) → 1997 IMF → 2010 결혼 → 2025 노년 회상
- 핵심 메시지: **"우리가 미처 보지 못한 부모님의 뒷모습엔, 우리를 향한 지독한 사랑이 적혀 있었다."**
- 클라이맥스: 사건 6(택시 조우)·사건 10(택시 장부) — 모든 퍼즐이 맞춰지는 마지막 화

### 가족 구성 (parent_sacrifice 단일)
| 인물 | 출생 | 핵심 |
|------|------|------|
| 아버지 | 1949 | 금융직 → IMF(1997) 후 택시기사 |
| 어머니 | 1957 | 헌신적 주부 |
| 큰누나 | 1972 | IMF 때 대학 포기, 장녀 |
| 아들 (주인공/화자) | 1975 | 둘째 |
| 막내 여동생 | 1978 | 천진난만 |

### 캐릭터 4단계 stage (인물별)
| 인물 | s1 | s2 anchor ✅ | s3 | s4 |
|---|---|---|---|---|
| father | young_30s | middle_40s | elder_60s | elder_70s |
| mother | young_20s | middle_40s | elder_60s | elder_70s |
| son | child | teen | young_adult | middle_40s |
| older_sister | teen | young_adult | middle_30s | middle_50s |
| younger_sister | child | teen | young_adult | middle_40s |

s2 anchor 13장 생성 완료. s1·s3·s4 변형 15장은 Phase 1.5에서 image_input reference로 생성 예정.

## 앞으로 진행할 작업 (Phase별)

### ✅ Phase 1 — 캐릭터 anchor (완료)

13장 anchor (parent_sacrifice 5 + grandparent_memory 3 + couple_growing_old 2 + late_realization 3).

### 🟡 Phase 1.5 — parent_sacrifice 4단계 variant (다음 작업)

**목표**: parent_sacrifice 5명 × 3 추가 단계 = 15장 신규 (s2 anchor를 image_input으로 첨부 → 동일 인물 일관성 강화).

**실행**:
```bash
python scripts/generate_characters.py --family-type parent_sacrifice --dry-run
python scripts/generate_characters.py --family-type parent_sacrifice --yes
```

**비용**: ~$0.60 (15장 × $0.04). 결과는 `assets/characters/parent_sacrifice/` 에 추가.

### ✅ Phase 2 — 에피소드 매핑 YAML (간소화 + 완료)

당초 계획은 풀 시리즈 바이블 YAML이었으나, 마크다운이 이미 강한 source-of-truth라 **매핑 YAML만** 만드는 방향으로 축소.

**산출물**: [series/our_family.yaml](series/our_family.yaml) — 22 에피소드 매핑 표 (스토리 본문 X, episode → event/POV/characters/age 매핑만)

**파이프라인 동작 흐름**:
1. CLI에서 `--episode N` 받으면 `our_family.yaml`에서 metadata 룩업
2. `pov_files[perspective]` 마크다운 파일 열기
3. "## 사건 {event_idx}" 헤딩 섹션 추출
4. 마크다운 + `series_overview.md` 글로벌 컨텍스트로 LLM에 그대로 주입
5. `characters` 매핑은 `character_templates.yaml`에서 이미지 경로 룩업 → Nano Banana 2 image_input

### ⏳ Phase 3 — 데이터 모델 + 시리즈 모드 + Nano Banana 통합

- [src/models.py](src/models.py): `ProjectBrief`에 `series_id`/`episode_number`/`event_idx`/`perspective`/`series_bible_path` 추가, `Scene`에 `is_key_scene`/`characters_in_scene` 추가
- [src/cli.py](src/cli.py): `series episode --bible <path> --episode <N>` 서브커맨드 — bible에서 자동으로 ProjectBrief 채움
- [src/engines/image_client.py](src/engines/image_client.py): `NanoBananaClient` 추가
- [src/pipeline/a_script_gen.py](src/pipeline/a_script_gen.py) + [templates/prompts/script_gen_user.txt](templates/prompts/script_gen_user.txt): 시리즈 컨텍스트 + POV 가이드 + core_facts 주입
- [src/pipeline/c_visual_prompt.py](src/pipeline/c_visual_prompt.py): 등장 인물 role 추출 + 나이대 stage 매칭
- [src/pipeline/g_image_gen.py](src/pipeline/g_image_gen.py): scene.characters_in_scene → character_templates.yaml 룩업 → image_input 첨부

### ⏳ Phase 4 — Veo 3.1 key scene 단계

climax 1-2개 장면만 Veo 3.1로 영상화 (나머지는 Ken Burns 폴백). `g2_key_scene_video.py` 부활/재작성.

### ⏳ Phase 5 — 침묵 2초 표준화

[config/emotional_arcs.yaml](config/emotional_arcs.yaml) `silence_before_climax_sec: 1.5` → `2.0`.
[src/pipeline/b_scene_segment.py](src/pipeline/b_scene_segment.py) climax 자동 마킹 갱신.

### ⏳ Phase 6 — 사건1 3편 검증 제작

ep1·ep2·ep3 (사건1 3 POV) 풀 파이프라인 실행 → 정합성·일관성·POV 차이 검증. 필요 시 Phase 2-5 보정.

### ⏳ Phase 7 — 22화 본격 제작 + 발행

22화 순차 제작, [@loveu-fam](https://www.youtube.com/@loveu-fam) 채널. 시청 지속 시간 + POV 묶음 시청 비율 모니터링.

상세 계획서: [/Users/seunghun/.claude/plans/recursive-wibbling-mist.md](/Users/seunghun/.claude/plans/recursive-wibbling-mist.md)

## 개발 환경

- Python 3.11.15 (pyenv, [.python-version](.python-version))
- 가상환경: `.venv/`
- 패키지 관리: pip + hatchling ([pyproject.toml](pyproject.toml))
- OS: macOS (Apple M3) / Windows 호환
- FFmpeg 8.1 (`homebrew-ffmpeg/ffmpeg` 탭)
- GitHub CLI: `gh` (`qorrmdgjs-bot` 인증)

### 환경 활성화
```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
source .venv/bin/activate
```

### 환경변수 (.env)
```
ANTHROPIC_API_KEY=sk-ant-xxxxx          # Claude API (스크립트 + 시리즈 바이블)
GOOGLE_APPLICATION_CREDENTIALS=credentials/tts-service-account.json  # TTS 폴백
REPLICATE_API_TOKEN=r8_xxxxx            # Nano Banana 2 + Veo 3.1
ELEVENLABS_API_KEY=sk_xxxxx             # 한국어 TTS (Haechan 남성)
```

## 다른 기기 셋업

```bash
gh repo clone qorrmdgjs-bot/youtube
cd youtube
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .
brew tap homebrew-ffmpeg/ffmpeg
brew install homebrew-ffmpeg/ffmpeg/ffmpeg
# 비밀 파일 수동 전달: .env, credentials/tts-service-account.json
```

### 일상 작업 흐름
```bash
git pull   # 시작
git add . && git commit -m "..." && git push   # 종료
```

## 프로젝트 구조

```
youtube/
├── pyproject.toml
├── Makefile
├── dashboard.py            # Streamlit (http://localhost:8501)
├── .env
│
├── series/                 # 시리즈 자산 (north star)
│   ├── prompts/            # 외부 AI 프롬프트 (아카이브)
│   ├── drafts/             # 3 POV 스토리 정본 + overview ⭐
│   └── our_family.yaml     # 22 에피소드 매핑 (스토리 본문 X, 매핑만)
│
├── config/                 # YAML 설정
│   ├── settings.yaml
│   ├── emotional_arcs.yaml
│   ├── character_templates.yaml  # 가족 유형 → 인물 → 이미지 (멀티 stage 스키마)
│   ├── safety_rules.yaml, bgm_library.yaml, timing_curves.yaml,
│   ├── font_config.yaml, cta_templates.yaml, monetization_blocks.yaml
│
├── src/
│   ├── cli.py              # `series episode` 서브커맨드 Phase 3에서 추가
│   ├── models.py
│   ├── orchestrator.py
│   ├── project_manager.py
│   ├── pipeline/           # A~M 13단계
│   ├── engines/            # Claude/ElevenLabs/Replicate
│   └── utils/
│
├── credentials/            # gitignored
├── templates/prompts/      # Jinja2 LLM 프롬프트
├── assets/
│   ├── characters/         # 캐릭터 시트 (Phase 1: 13장)
│   ├── fonts/, bgm/, branding/
│
├── projects/               # gitignored
├── scripts/
│   ├── generate_characters.py      # Nano Banana 2로 캐릭터 시트 생성
│   ├── build_series_bible.py       # Phase 2에서 생성 예정
│   ├── cost_report.py
│   └── setup_env.sh
└── tests/, logs/
```

## 파이프라인 DAG (현재 13단계, Phase 3-5에서 보강)

```
A) 스크립트 (Claude API; 시리즈 모드: POV 가이드 + 마크다운 컨텍스트 주입)
  → B) 장면 분할 (climax 직전 2.0초 침묵 자동 마킹)
    ├─→ C) 시각 프롬프트 (영문, 한국 웹툰 스타일)
    ├─→ D) TTS (ElevenLabs Haechan, 한글)
    └─→ F) 자막 (TTS 동기화, 한글)
  → G) 이미지 (Nano Banana 2 + 캐릭터 시트 image_input — 시리즈 모드)
    → G2) Veo 3.1 영상 (Phase 4에서 부활, climax만)
      → H) FFmpeg 합성 (Ken Burns + 내레이션 + 자막 번인, BGM 없음)
        → I/J/K/L (썸네일/메타/수익화/쇼츠)
          → M) 패키징

> **E 단계 (BGM 선택) 제거** (2026-04-26): BGM을 영구적으로 사용하지 않음. 내레이션과 자연 소리만으로 정서 전달. 12단계 파이프라인.
```

## 시리즈 모드 사용법 (Phase 3 완료 후)

```bash
python -m src.cli series episode --bible series/our_family.yaml --episode 1
# 자동 추론: event_idx=1, perspective="son" (사건1·아들·1985 봄·도시락)
# core_facts·son_pov·characters_present 자동 주입
```

## 영상 품질 설정

| 항목 | 값 |
|------|------|
| 해상도 | 1920×1080 (본편) / 1080×1920 (쇼츠) |
| FPS | 24 |
| 기본 길이 | 5분 |
| 이미지 | Nano Banana 2 (Phase 3 적용 예정), 한국 웹툰, 어스톤 + 파스텔 + 골든 |
| 캐릭터 일관성 | image_input reference (장면별 등장 인물 stage 시트 첨부) |
| 이미지 그룹화 | 1개 LLM 장면 = 1장 이미지 (서브씬 공유). Ken Burns 6방향으로 변주 — 비슷한 이미지 연속 절사 방지 |
| Key scene 영상 | Veo 3.1 (Phase 4), climax phase만 |
| 일반 장면 | Ken Burns 6방향 폴백 |
| 오디오 | 44.1kHz, EQ (250Hz 부스트 + 4kHz 컷), -16 LUFS |
| BGM | **사용 안 함** (2026-04-26 영구 제거) — 내레이션 단독 |
| 침묵 | climax 직전 **2.0초** (Phase 5) |
| 자막 | 17px, 반투명 검정 배경, NanumSquareRoundEB |
| 인코딩 | H.264 CRF 23, medium |
| 쇼츠 | 2-3개/편, 15-30초, 9:16 |

## TTS 음성 (ElevenLabs Starter)

| 성별 | 음성 | Voice ID |
|------|------|----------|
| 남성 (기본) | Haechan | `prgs92xTdxeczorJi7ez` |
| 여성 | Kanna | `5I7B1di44aCL15NkP0jn` |

폴백: Google Cloud TTS (Neural2) → gTTS

## 폴백 동작

| 상황 | 폴백 |
|------|------|
| ElevenLabs 미설정 | Google Cloud TTS (Neural2) |
| Google Cloud TTS 미설정 | gTTS |
| Replicate 미설정 | Pillow placeholder |
| Veo 3.1 클립 없음 | Ken Burns |
| BGM 파일 미존재 | ffmpeg 무음 |
| 자막 번인 실패 | 자막 없이 영상 |
| HW 가속 실패 | libx264 소프트웨어 인코딩 |

## 비용 추정

### 캐릭터 자산 (1회성)
| 항목 | 비용 |
|---|---|
| Phase 1 anchor 13장 | $0.51 (발생 완료) |
| Phase 1.5 parent_sacrifice 4단계 variant 15장 | ~$0.60 |

### 영상 1편당
| 항목 | 비용 |
|---|---|
| Claude API | $0.15 |
| Nano Banana 2 (~23장) | ~$0.92 |
| Veo 3.1 (climax 1-2개) | ~$0.50 |
| ElevenLabs TTS | $0.23 |
| **합계** | **~$1.80/편** |

### 시리즈 22화 총합
- 캐릭터 자산: ~$1.11
- 22화 제작: ~$40
- ElevenLabs 구독 (1.5개월): ~$33
- **시리즈 총 비용: ~$74**

## 업로드 워크플로우

파이프라인 완료 후 `Desktop/youtube_upload/`에:
- `본편.mp4`
- `썸네일.png`
- `설명문.txt`
- `쇼츠_*.mp4`

순서: 본편 → (3-4시간 후) 쇼츠 #1 → (다음 날) 쇼츠 #2.
- 쇼츠는 9:16이면 자동 인식, 제목에 `#Shorts` 필수.

## GitHub

- 저장소: `qorrmdgjs-bot/youtube`
- 브랜치: `main`
- 시작 `git pull`, 종료 `git push`
- iPhone/iPad: Working Copy 앱 (코드 열람·간단 편집·커밋·푸시)
