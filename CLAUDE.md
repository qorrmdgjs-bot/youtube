# YouTube 가족 드라마 시리즈 자동화 파이프라인

한 가족의 30년 일대기를 **다중시점 30화 시리즈**로 풀어내는 한국 시니어 대상 유튜브 채널.

## 채널

- 채널명: **부모님께 드리는 이야기**
- 핸들: **@loveu-fam**
- 채널 ID: `UCklS5vu3fPwRCWajfj0HYjg`
- 카테고리: 인물 및 블로그 (category_id: 22)
- 브랜딩 에셋: `assets/branding/`

## 시리즈 비전 (2026-04-25 확정)

**한 가족(parent_sacrifice 5인) × 10개 핵심 사건 × 3시점 = 30화**

- 5분/편, 주 5회 발행, 총 6주 분량
- 시간 스팬: 1980s 어린 시절 → 1990s IMF → 2000s 회복기 → 2020s 현재
- 발행 순서: **사건별 교차** — ep1 아들·사건1 → ep2 아빠·사건1 → ep3 엄마·사건1 → ep4 아들·사건2…

### 에피소드 ↔ 사건/시점 매핑
```
event_idx   = ((episode_number - 1) // 3) + 1     → 1, 1, 1, 2, 2, 2, …
perspective = ["son", "father", "mother"][(episode_number - 1) % 3]
```

### 가족 구성 (parent_sacrifice 단일)
| 인물 | 출생 | 핵심 설정 |
|------|------|----------|
| 아버지 | 1949 | 금융직 → IMF(1997) 후 택시기사 |
| 어머니 | 1957 | 헌신적 주부 |
| 큰누나 | 1972 | IMF 때 대학 포기, 장녀 |
| 아들 (주인공/화자) | 1975 | 둘째 |
| 막내 여동생 | 1978 | 천진난만 |

### 캐릭터 4단계 stage (인물별)
| 인물 | s1 (어린/청년) | s2 (anchor) | s3 | s4 (노년/중년) |
|---|---|---|---|---|
| father | `father_young_30s` | `father_middle_40s` ✅ | `father_elder_60s` | `father_elder_70s` |
| mother | `mother_young_20s` | `mother_middle_40s` ✅ | `mother_elder_60s` | `mother_elder_70s` |
| son | `son_child` | `son_teen` ✅ | `son_young_adult` | `son_middle_40s` |
| older_sister | `older_sister_teen` | `older_sister_young_adult` ✅ | `older_sister_middle_30s` | `older_sister_middle_50s` |
| younger_sister | `younger_sister_child` ✅ | `younger_sister_teen` | `younger_sister_young_adult` | `younger_sister_middle_40s` |

✅ = 현재 생성된 anchor (Nano Banana 2 image_input의 reference로 사용)

## 진행 상황 (Phase별)

- ✅ **Phase 1** — 캐릭터 anchor 13장 생성 ([assets/characters/](assets/characters/))
- 🟡 **Phase 1.5** — parent_sacrifice 4단계 variant 15장 신규 (생성기 준비됨)
- ⏳ **Phase 2** — 시리즈 바이블 작성 (사용자 큰 줄거리 → Claude 10개 사건 도출)
- ⏳ **Phase 3** — 데이터 모델 + 시리즈 모드 + Nano Banana 2 통합
- ⏳ **Phase 4** — Veo 3.1 key scene 단계 (climax만)
- ⏳ **Phase 5** — 침묵 2초 표준화
- ⏳ **Phase 6** — 사건1 3편 검증 제작
- ⏳ **Phase 7** — 30화 본격 제작 + 발행

상세 계획서: [/Users/seunghun/.claude/plans/recursive-wibbling-mist.md](/Users/seunghun/.claude/plans/recursive-wibbling-mist.md)

## 개발 환경

- Python 3.11.15 (pyenv, [.python-version](.python-version))
- 가상환경: `.venv/`
- 패키지 관리: pip + hatchling ([pyproject.toml](pyproject.toml))
- OS: macOS (Apple M3, 8GB RAM) / Windows 호환
- FFmpeg 8.1 (`homebrew-ffmpeg/ffmpeg` 탭, libass/drawtext 포함)
- GitHub CLI: `gh` (`qorrmdgjs-bot` 인증 완료)

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
git pull         # 시작
git add . && git commit -m "..." && git push   # 종료
```

## 프로젝트 구조

```
youtube/
├── pyproject.toml          # 의존성
├── Makefile                # 자주 쓰는 명령
├── dashboard.py            # Streamlit 대시보드 (http://localhost:8501)
├── .env / .env.example
│
├── config/                 # YAML 설정
│   ├── settings.yaml         # 전역 (24fps/BGM/자막)
│   ├── emotional_arcs.yaml   # 12 감정 아크 (시리즈에서 사건별 선택)
│   ├── character_templates.yaml  # 가족 유형 → 인물 → 이미지 (Phase 1 완료, 1.5 확장 예정)
│   ├── safety_rules.yaml
│   ├── bgm_library.yaml      # Lullaby for the Lost (단일곡)
│   ├── timing_curves.yaml
│   ├── font_config.yaml
│   ├── cta_templates.yaml
│   └── monetization_blocks.yaml
│
├── series/                 # 시리즈 자산 (Phase 2에서 생성)
│   ├── synopsis.txt          # 사용자가 작성할 큰 줄거리
│   └── our_family.yaml       # 시리즈 바이블 (10 사건 × 3 POV)
│
├── src/
│   ├── cli.py                # typer CLI (`series episode` 서브커맨드 Phase 3에서 추가)
│   ├── models.py             # Pydantic 모델
│   ├── orchestrator.py       # 파이프라인 DAG
│   ├── project_manager.py
│   ├── pipeline/             # A~M 13단계
│   ├── engines/              # Claude/ElevenLabs/Replicate 클라이언트
│   └── utils/
│
├── credentials/              # Google TTS 키 (gitignored)
├── templates/prompts/        # Jinja2 프롬프트 템플릿
├── assets/
│   ├── characters/           # 캐릭터 시트 (Phase 1: anchor 13장)
│   │   ├── parent_sacrifice/
│   │   ├── grandparent_memory/
│   │   ├── couple_growing_old/
│   │   └── late_realization/
│   ├── fonts/, bgm/, branding/
│
├── projects/                 # 영상별 작업 디렉토리 (gitignored)
├── tests/, scripts/, logs/
```

## 파이프라인 DAG (현재 13단계, Phase 3-5에서 보강 예정)

```
A) 스크립트 (Claude API, Phase 3에서 시리즈 컨텍스트 + POV 가이드 주입)
  → B) 장면 분할 (Phase 5에서 climax 침묵 1.5→2.0초)
    ├─→ C) 시각 프롬프트 (Phase 3에서 등장 인물 role 추출)
    ├─→ D) TTS (ElevenLabs Haechan)
    ├─→ E) BGM (Lullaby for the Lost)
    └─→ F) 자막 (TTS 동기화)
  → G) 이미지 (Phase 3에서 FLUX → Nano Banana 2 + 캐릭터 image_input)
    → G2) Veo 3.1 영상 (Phase 4에서 부활, climax만)
      → H) FFmpeg 합성 (Veo 클립 우선 + Ken Burns 폴백)
        → I/J/K/L (썸네일/메타/수익화/쇼츠)
          → M) 패키징
```

## 시리즈 모드 사용법 (Phase 3 완료 후)

```bash
# 캐릭터 시트 생성/확장 (현재)
python scripts/generate_characters.py --family-type parent_sacrifice --dry-run
python scripts/generate_characters.py --family-type parent_sacrifice --yes

# 시리즈 바이블 작성 (Phase 2)
python scripts/generate_series_bible.py --synopsis series/synopsis.txt

# 에피소드 제작 (Phase 3 이후)
python -m src.cli series episode --bible series/our_family.yaml --episode 1
# 자동 추론: event_idx=1, perspective="son"
```

## 영상 품질 설정

| 항목 | 값 |
|------|------|
| 해상도 | 1920×1080 (본편) / 1080×1920 (쇼츠) |
| FPS | 24 |
| 기본 길이 | 5분 (시리즈 표준) |
| 이미지 | Nano Banana 2 (Phase 3 적용 예정), 한국 웹툰 스타일, 어스톤 + 파스텔 + 골든 |
| 캐릭터 일관성 | Nano Banana 2 image_input (각 장면에 등장 인물의 stage 시트 첨부) |
| Key scene 영상 | Veo 3.1 (Phase 4 적용 예정), climax phase만 |
| 일반 장면 | Ken Burns 6방향 폴백 |
| 오디오 | 44.1kHz, EQ (250Hz 부스트 + 4kHz 컷), -16 LUFS |
| BGM | -3dB, 처음~끝 + 페이드아웃, 단일곡 (Lullaby for the Lost) |
| 침묵 | climax 직전 **2.0초** (Phase 5에서 표준화) |
| 자막 | 17px, 반투명 검정 배경 (BorderStyle=4), NanumSquareRoundEB |
| 인코딩 | H.264 CRF 23, medium |
| 쇼츠 | 2-3개/편, 15-30초, 9:16 |

## TTS 음성 (ElevenLabs Starter)

| 성별 | 음성 | Voice ID |
|------|------|----------|
| 남성 (기본) | Haechan | `prgs92xTdxeczorJi7ez` |
| 여성 | Kanna | `5I7B1di44aCL15NkP0jn` |

- 모델: `eleven_multilingual_v2`, 한국어 네이티브
- 폴백: Google Cloud TTS (Neural2) → gTTS

## 폴백 동작

| 상황 | 폴백 |
|------|------|
| ElevenLabs 미설정 | Google Cloud TTS (Neural2) |
| Google Cloud TTS 미설정 | gTTS (무료) |
| Replicate 미설정 | Pillow placeholder |
| Veo 3.1 클립 없음 (key scene 외) | Ken Burns 효과 |
| Veo 3.1 실패 (key scene) | Ken Burns 효과 |
| BGM 파일 미존재 | ffmpeg 무음 |
| 자막 번인 실패 | 자막 없이 영상 |
| HW 가속 실패 | libx264 소프트웨어 인코딩 |

## 비용 추정

### 캐릭터 자산 (1회성)
| 항목 | 비용 |
|---|---|
| Phase 1 — anchor 13장 | $0.51 (발생 완료) |
| Phase 1.5 — parent_sacrifice 4단계 variant 15장 | ~$0.60 |

### 영상 1편당 (30화 동일)
| 항목 | 비용 |
|---|---|
| Claude API | $0.15 |
| Nano Banana 2 (~23장) | ~$0.92 |
| Veo 3.1 (climax 1-2개) | ~$0.50 |
| ElevenLabs TTS | $0.23 |
| **합계** | **~$1.80/편** |

### 시리즈 30화 총합
- 캐릭터 자산 + 시리즈 바이블: ~$3.6
- 30화 제작: ~$54
- ElevenLabs 구독 (1.5개월): ~$33
- **시리즈 총 비용: ~$91**

## 업로드 워크플로우

파이프라인 완료 후 `Desktop/youtube_upload/`에:
- `본편.mp4`
- `썸네일.png`
- `설명문.txt`
- `쇼츠_*.mp4`

순서: 본편 → (3-4시간 후) 쇼츠 #1 hook → (다음 날) 쇼츠 #2 reveal/memory.
- 쇼츠는 9:16이면 자동 인식, 제목에 `#Shorts` 필수.

## GitHub

- 저장소: `qorrmdgjs-bot/youtube`
- 브랜치: `main`
- 작업 시작 `git pull`, 종료 `git push`
- iPhone/iPad: Working Copy 앱 (코드 열람·간단 편집·커밋·푸시 가능)
