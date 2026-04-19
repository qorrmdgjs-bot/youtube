# YouTube 장편 자동화 시스템

한국 시니어(50-70세) 대상 감성 가족 이야기 유튜브 채널의 완전 자동화 콘텐츠 파이프라인.

## YouTube 채널 정보

- 채널명: **부모님께 드리는 이야기**
- 핸들: **@loveu-fam**
- 채널 ID: `UCklS5vu3fPwRCWajfj0HYjg`
- 카테고리: 인물 및 블로그 (category_id: 22)
- 브랜딩 에셋: `assets/branding/` (아이콘, 배너, 워터마크)
- 첫 영상 업로드 완료 (2026-04-19)

## 개발 환경

- Python 3.11.15 (pyenv로 설치, `.python-version` 참조)
- 가상환경: `.venv/` (`source .venv/bin/activate`)
- 패키지 관리: pip + hatchling (`pyproject.toml`)
- OS: macOS (Apple M3, 8GB RAM)
- FFmpeg 8.1 (`homebrew-ffmpeg/ffmpeg` 탭, libass/drawtext 포함)
- GitHub CLI: `gh` (brew로 설치됨, `qorrmdgjs-bot` 계정 인증 완료)

### 환경 활성화 명령
```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
source .venv/bin/activate
```

### 환경변수 (.env)
```
ANTHROPIC_API_KEY=sk-ant-xxxxx          # 필수 - Claude API (설정 완료)
GOOGLE_APPLICATION_CREDENTIALS=credentials/tts-service-account.json  # 설정 완료 - Google Cloud TTS (폴백)
REPLICATE_API_TOKEN=r8_xxxxx            # 설정 완료 - FLUX.1 이미지 + Wan 2.1 영상
ELEVENLABS_API_KEY=sk_xxxxx             # 설정 완료 - 고품질 한국어 TTS (유료 Starter 플랜)
```

## 다른 기기에서 셋업

GitHub repo: https://github.com/qorrmdgjs-bot/youtube (public)

### 새 Mac에서 처음 셋업할 때

```bash
# 1. 레포 클론
gh repo clone qorrmdgjs-bot/youtube
cd youtube

# 2. Python 환경 (3.11)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

# 3. FFmpeg (libass/drawtext 필수)
brew tap homebrew-ffmpeg/ffmpeg
brew install homebrew-ffmpeg/ffmpeg/ffmpeg

# 4. 비밀 파일 수동 전달 (git에 없음)
#    - .env (API 키 4개)
#    - credentials/tts-service-account.json (Google TTS)
#    → AirDrop, 1Password, 암호화 USB 등으로 안전하게 전달
```

### 일상 작업 흐름

```bash
# 작업 시작 시
git pull

# 작업 종료 시
git add . && git commit -m "..." && git push
```

### iPhone / iPad에서

- **Working Copy** 앱 — git clone, 코드 열람·간단 편집·커밋·푸시 (파이프라인 실행은 불가)
- **GitHub 모바일 앱** — 코드 열람, 이슈 관리

### git에서 제외되는 것 (수동 동기화 필요)

| 경로 | 처리 방법 |
|------|----------|
| `.env`, `credentials/` | 수동 전달 (보안) |
| `.venv/` | 기기마다 새로 생성 |
| `projects/` | 생성된 영상 — 필요시 별도 백업 |
| `logs/` | 기기별 로컬 로그 |
| `assets/fonts/`, `assets/bgm/*.mp3`, `assets/sfx/`, `assets/overlays/` | 라이선스 이슈 → 수동 동기화 |

## 프로젝트 구조

```
youtube/
├── pyproject.toml          # 의존성 및 빌드 설정
├── Makefile                # 자주 쓰는 명령 단축
├── dashboard.py            # Streamlit 웹 대시보드 (http://localhost:8501)
├── .env / .env.example     # API 키 설정
├── .gitignore
│
├── config/                 # YAML 설정 파일 (8개)
│   ├── settings.yaml         # 전역 설정 (24fps/BGM -3dB/자막 22px)
│   ├── emotional_arcs.yaml   # 12가지 감정 아크 템플릿
│   ├── safety_rules.yaml     # 금지 문구, 페이싱 제한, 중복 임계값
│   ├── bgm_library.yaml      # BGM 설정 (단일곡: Lullaby for the Lost)
│   ├── timing_curves.yaml    # BGM 볼륨/장면별 내레이션 속도/가변 침묵/줌 곡선
│   ├── font_config.yaml      # 시니어 친화 폰트 설정
│   ├── cta_templates.yaml    # 가족유형별 CTA + 멤버십 3티어 + 고전환 제휴
│   └── monetization_blocks.yaml  # 수익화 설명문 블록 구성
│
├── src/
│   ├── cli.py                # typer CLI (new/run/status/resume/batch/cost), 기본 음성: male
│   ├── models.py             # Pydantic v2 데이터 모델 (12 FamilyType)
│   ├── orchestrator.py       # 파이프라인 DAG 컨트롤러
│   ├── project_manager.py    # 프로젝트 디렉토리 CRUD
│   │
│   ├── pipeline/             # 14개 파이프라인 스테이지 (A~M + G2)
│   │   ├── a_script_gen.py     # LLM 스크립트 생성
│   │   ├── b_scene_segment.py  # 장면 분할 + 서브씬 자동 분할 (15초 초과 시)
│   │   ├── c_visual_prompt.py  # 이미지 프롬프트 추출 (웹툰 스타일 + 캐릭터 일관성 템플릿)
│   │   ├── d_tts_gen.py        # TTS (ElevenLabs > Google > gTTS) + 오디오 후처리
│   │   ├── e_bgm_select.py     # 감정 구간별 BGM 매칭 (단일곡 루프)
│   │   ├── f_subtitle_split.py # SRT 자막 생성 (실제 TTS 오디오 길이 기반 동기화)
│   │   ├── g_image_gen.py      # 이미지 생성 (FLUX.1 Pro, 1440x810)
│   │   ├── g2_image_to_video.py # 이미지→영상 변환 (Wan 2.1, 5초 클립)
│   │   ├── h_video_compose.py  # FFmpeg 합성 (AI 영상 클립 우선, Ken Burns 폴백)
│   │   ├── i_thumbnail_gen.py  # 썸네일 (96px, 따뜻한 색보정, 이모지)
│   │   ├── j_metadata_gen.py   # YouTube 메타데이터 (60-90자 이모지 제목)
│   │   ├── k_monetization_desc.py  # 수익화 설명문 (가족유형별 CTA)
│   │   ├── l_shorts_teaser.py  # 쇼츠 멀티클립 (2-5개, 15-30초, 9:16)
│   │   └── m_export_package.py # 최종 패키징 + 검증
│   │
│   ├── engines/              # 외부 API 클라이언트
│   │   ├── llm_client.py       # Claude API (프롬프트 캐싱, API 에러만 재시도)
│   │   ├── elevenlabs_client.py # ElevenLabs TTS (한국어 네이티브 음성)
│   │   ├── tts_client.py       # Google Cloud TTS (SSML, Neural2 폴백)
│   │   ├── image_client.py     # Replicate FLUX.1 (1440x810) + Placeholder 폴백
│   │   ├── video_gen_client.py  # Replicate Wan 2.1 Image-to-Video
│   │   └── ffmpeg_wrapper.py   # FFmpeg (AI클립/Ken Burns, xfade, 자막 번인, 44.1kHz)
│   │
│   └── utils/                # 로깅, 재시도, 캐시, 한글 유틸리티
│
├── credentials/              # Google Cloud 서비스 계정 키 (gitignored)
├── templates/prompts/        # LLM 프롬프트 템플릿 (Jinja2)
├── assets/
│   ├── fonts/                # 한글 폰트 3개 (gitignored)
│   ├── bgm/                  # BGM: lullaby_for_the_lost.mp3 (단일곡)
│   ├── branding/             # 채널 아이콘, 배너, 워터마크
│   └── tts_samples/          # ElevenLabs 음성 샘플 (테스트용)
├── projects/                 # 비디오별 작업 디렉토리 (gitignored)
├── tests/                    # pytest 테스트
└── scripts/                  # setup_env.sh, cost_report.py
```

## CLI 사용법

```bash
python -m src.cli new --title "제목" --synopsis "줄거리" --type parent_sacrifice --arc parent_sacrifice
python -m src.cli run projects/{project_id}
python -m src.cli status
python -m src.cli resume projects/{project_id}
python -m src.cli batch batch/queue.json
python -m src.cli cost
```

## 웹 대시보드

```bash
streamlit run dashboard.py --server.headless true   # → http://localhost:8501
```
| 페이지 | 기능 |
|--------|------|
| 새 영상 만들기 | 제목/줄거리 입력 → 12가지 유형 선택 → 실시간 진행 → 결과물 확인 + 다운로드 |
| 프로젝트 현황 | 전체 목록, 진행률, 영상/썸네일 미리보기, 다운로드, 실패 재시도 |
| 비용 리포트 | 총 비용, 월 예산, 프로젝트별 비용 분석 |

## 파이프라인 DAG (A~M + G2, 14단계)

```
A) 스크립트 → B) 장면 분할 (서브씬 자동 분할, 20+ 장면)
  → C) 시각 프롬프트 (웹툰 스타일 + 캐릭터 일관성) → G) 이미지 (FLUX.1) → G2) 이미지→영상 (Wan 2.1) ─┐
  → D) TTS (ElevenLabs Haechan 남성) → F) 자막 (TTS 오디오 동기화)                        ┤
  → E) BGM (Lullaby for the Lost, 구간별 루프)                                             ┘
    → H) 영상 합성 (AI 영상 클립 + BGM 처음~끝 재생 + 페이드아웃)
      → I) 썸네일 / J) 메타 / K) 수익화 / L) 쇼츠 멀티클립
        → M) 최종 패키징
```

## 영상 스타일 - 한국 웹툰(만화) 스타일

- **스타일**: 한국 웹툰(만화) 스타일 일러스트 (Korean manhwa webtoon style)
- **프롬프트 키워드**: `Korean manhwa webtoon style illustration, detailed clean line art, warm earthy color palette, realistic proportions, expressive character faces, detailed Korean background setting`
- **라인**: 깔끔한 디지털 라인 아트 (수채화가 아님)
- **색감**: 따뜻한 어스톤 (warm earthy tones) - 브라운, 베이지, 크림 계열
- **배경**: 한국적 배경 상세 묘사 (한국 가정집, 시장, 사무실, 식당, 학교 등)
- **참고 채널**: 한국 감성 사연 웹툰 채널 스타일

### 캐릭터 일관성 (c_visual_prompt.py)
모든 장면에서 동일 캐릭터가 일관된 외모로 등장하도록 고정 설명 사용:

**parent_sacrifice 유형 기본 캐릭터:**
| 역할 | 외모 설명 |
|------|----------|
| 어머니 | 50대, 짧은 파마 다크브라운 머리, 따뜻한 눈, 앞치마, 소박한 옷 |
| 아버지 | 50대, 짧은 검은 머리(약간 흰머리), 사각턱, 낡은 셔츠, 강인하지만 피곤한 눈 |
| 아들 | 20대 후반, 깔끔한 다크헤어 옆가르마, 그레이 크루넥 스웨터, 감성적인 눈 |
| 딸 | 20대 후반, 긴 생머리, 심플한 블라우스, 부드러운 이목구비 |

가족 유형별 캐릭터 템플릿은 `c_visual_prompt.py`의 `CHARACTER_TEMPLATES` 딕셔너리에 정의됨.
새로운 가족 유형 추가 시 여기에 캐릭터 설명을 추가해야 인물 일관성 유지됨.

## TTS 음성 설정

### 우선순위: ElevenLabs > Google Cloud TTS > gTTS (무료)

### ElevenLabs (현재 사용, 유료 Starter 플랜)
| 성별 | 음성 | Voice ID | 특징 |
|------|------|----------|------|
| 여성 | **Kanna** | `5I7B1di44aCL15NkP0jn` | 차분하고 친근한 서울 여성 |
| 남성 | **Haechan** | `prgs92xTdxeczorJi7ez` | 품위 있고 신뢰감 있는 남성 |

- 모델: `eleven_multilingual_v2`
- 한국어 네이티브 음성, 감정 표현력 높음
- 기본 음성: **남성 (Haechan)** (`src/cli.py` 기본값 `--voice male`)

### Google Cloud TTS (폴백)
| 항목 | 값 |
|------|------|
| 여성 음성 | ko-KR-Neural2-A |
| 남성 음성 | ko-KR-Neural2-C |
| 속도 | 0.92 |
| 피치 | -0.5 |

## BGM 설정

- **단일곡 사용**: Lullaby for the Lost (`assets/bgm/lullaby_for_the_lost.mp3`)
- 영상 처음부터 끝까지 재생, 내레이션 끝난 후 5초간 BGM만 남음
- 마지막에 페이드 아웃으로 자연스럽게 종료
- BGM 볼륨: **-3dB** (내레이션과 비슷한 수준)
- 모든 감정 구간에 동일 곡 적용 (`bgm_library.yaml` 단일 트랙 설정)

## 영상 품질 설정

| 항목 | 값 |
|------|------|
| 해상도 | 1920x1080 (본편) / 1080x1920 (쇼츠) |
| FPS | 24 (시네마틱) |
| 기본 길이 | 5분 |
| 이미지 스타일 | 한국 웹툰(만화) 스타일, 깔끔한 라인아트, 어스톤 색감 |
| 이미지 생성 | FLUX.1 Pro, 1440x810 (API 제한) |
| 영상 변환 | Wan 2.1 Image-to-Video (5초 클립, 슬로모션 확장) |
| 장면 분할 | 15초 초과 시 서브씬 자동 분할 (장면당 1이미지) |
| 오디오 | 44.1kHz 스테레오, EQ (250Hz 웜 부스트 + 4kHz 컷), -16 LUFS |
| BGM | -3dB, 처음~끝 재생 + 페이드 아웃 |
| 장면 전환 | 크로스페이드 (xfade, 폴백: fade-in/out) |
| Ken Burns | 6방향 순환 (AI 영상 실패 시 폴백) |
| 장면간 호흡 | 0.8초 무음 갭 삽입 |
| 인코딩 | H.264 CRF 23, medium preset |
| 자막 | 22px, 반투명 검정 배경 박스 (BorderStyle=4), NanumSquareRoundEB, TTS 오디오 동기화 |
| 쇼츠 | 2-5개/영상, 15-30초, 9:16 센터크롭 |
| 썸네일 | 96px 폰트, 따뜻한 색보정, 이모지, 프리클라이맥스 장면 |

## 감정 아크 (12종)

| 키 | 이름 |
|----|------|
| `parent_sacrifice` | 부모의 희생 |
| `sibling_reconciliation` | 형제 화해 |
| `grandparent_memory` | 할머니의 기억 |
| `father_daughter_wedding` | 아버지와 딸의 결혼식 |
| `late_realization` | 늦은 깨달음 |
| `remarriage_parent` | 재혼 부모의 사랑 |
| `inlaw_relationship` | 며느리와 시어머니 |
| `grandchild_love` | 손주와 할아버지 |
| `holiday_reunion` | 명절의 재회 |
| `career_sacrifice_parent` | 일하는 부모의 미안함 |
| `immigrant_parent` | 이민 부모의 눈물 |
| `couple_growing_old` | 함께 늙어가는 부부 |

## 비용 관리

### 영상당 비용 (풀 API 기준)
| 항목 | 비용 |
|------|------|
| Claude API (스크립트+메타) | ~$0.15 |
| ElevenLabs TTS | ~$0.23 |
| FLUX.1 이미지 (22장) | ~$1.21 |
| Wan 2.1 영상 변환 (22개) | ~$2.20 |
| **영상당 합계** | **~$3.80** |

### 월간 비용
| 항목 | 비용 |
|------|------|
| 영상 30편/월 | ~$114 |
| ElevenLabs 구독 | $5~22/월 |
| Replicate | 사용량 과금 |
| **월 합계** | **~$120-140** |

## 수익 전망 (현실적 분석)

### AI 자동화 채널 현실적 수익 예측
| 시기 | 구독자 | 월 수익 | 월 비용 | 순이익 |
|------|--------|---------|---------|--------|
| 1-3개월 | ~500 | $0 (YPP 미승인) | ~$140 | -$140 |
| 4-6개월 | ~2,000 | $20-50 | ~$140 | -$90 |
| 7-12개월 | ~5,000 | $100-300 | ~$140 | +$160 |
| 13-24개월 | ~15,000 | $300-800 | ~$140 | +$660 |

### 수익화 조건 (YPP)
- 구독자 1,000명 이상
- 최근 12개월 시청 4,000시간 또는 쇼츠 조회 1,000만회
- AdSense 계정 연동

## 구현 진행 상황

- [x] Phase 1-6: 전체 파이프라인 구현 (14단계)
- [x] 웹 대시보드 (Streamlit)
- [x] 코드 리뷰 및 최적화
- [x] API 연동 완료 (Claude, Google TTS, Replicate, ElevenLabs)
- [x] YouTube 채널 생성 + 브랜딩 (아이콘/배너/워터마크)
- [x] 장면 세분화 (15초 초과 → 서브씬 분할, 이미지 수 증가)
- [x] Image-to-Video 파이프라인 (Wan 2.1)
- [x] ElevenLabs 한국어 네이티브 TTS (Kanna 여성 / Haechan 남성)
- [x] 자막 개선 (TTS 오디오 동기화, 반투명 배경 박스, 22px)
- [x] FFmpeg libass 재설치 (homebrew-ffmpeg 탭, 자막 번인 정상 동작)
- [x] 이미지 스타일 변경 (사실적 사진 → 수채화 → 한국 웹툰 스타일 + 캐릭터 일관성)
- [x] BGM 교체 (Lullaby for the Lost 단일곡, 처음~끝 재생 + 페이드아웃)
- [x] 첫 영상 업로드 (2026-04-19, "어머니의 조건 없는 사랑")
- [x] 두번째 영상 제작 (2026-04-19, "택시 기사 아버지의 새벽")
- [ ] YouTube 자동 업로드 (YouTube Data API v3)
- [ ] 매일 자동 실행 스케줄러 (cron/launchd)
- [ ] 주제 자동 생성 (AI가 매일 새 줄거리 생성)

## 실행 검증 결과

### 5차: "어머니의 조건 없는 사랑" (최종 버전 - 첫 업로드 영상)
- 14/14 완료, $3.74
- 제목: "새벽 시장에서 30년간 숨겨온 어머니의 가계부 😭 아들을 위해 포기한 것들의 목록을 보는 순간 눈물이 멈추지 않았습니다"
- 장면 23개 (서브씬 분할)
- 수채화 일러스트 스타일
- ElevenLabs Haechan 남성 음성
- AI 영상 클립 21/23개 성공 (Wan 2.1)
- BGM: Lullaby for the Lost (처음~끝 + 페이드아웃)
- 자막: 22px 반투명 배경 박스, TTS 오디오 동기화
- 쇼츠 3개 (hook, reveal, memory)

### 6차: "택시 기사 아버지의 새벽" (웹툰 스타일 첫 적용)
- 14/14 완료, $3.18
- 제목: "30년 택시기사 아버지가 쓰러진 날 발견한 낡은 수첩 😭 매일 적힌 아들을 위한 기도에 눈물이 멈추지 않았습니다"
- 장면 27개 (서브씬 분할)
- 한국 웹툰 스타일 + 캐릭터 일관성 적용
- ElevenLabs Haechan 남성 음성
- BGM: Lullaby for the Lost
- 쇼츠 3개 (hook, reveal, memory)

## 업로드 워크플로우

### 업로드 파일 준비
파이프라인 완료 후 `Desktop/youtube_upload/` 폴더에 복사:
- `본편.mp4` - 본편 영상
- `썸네일.png` - 썸네일
- `설명문.txt` - 설명/태그
- `쇼츠_01_hook.mp4` - 쇼츠 #1
- `쇼츠_02_reveal.mp4` - 쇼츠 #2
- `쇼츠_03_memory.mp4` - 쇼츠 #3

### 업로드 순서
1. 본편 → 바로 업로드
2. 쇼츠 #1 (hook) → 본편 3-4시간 후
3. 쇼츠 #3 (memory) → 다음 날 오전
4. 쇼츠 #2 (reveal) → 다음 날 오후

### 쇼츠 업로드 방법
- YouTube Studio → "만들기" → "동영상 업로드" (일반 영상과 동일)
- 세로 영상(9:16)이면 자동으로 쇼츠로 인식
- 제목에 `#Shorts` 포함 필수

## 설치된 에셋

### BGM (assets/bgm/) - 1곡
| 파일 | 용도 |
|------|------|
| lullaby_for_the_lost.mp3 | 전 영상 공통 BGM (처음~끝 재생 + 페이드아웃) |

### 폰트 (assets/fonts/) - 3개
| 파일 | 용도 |
|------|------|
| NanumSquareRoundExtraBold.ttf | 자막 (22px, 반투명 배경 박스) |
| NanumMyeongjo.ttf | 썸네일 제목 (96px) |
| NanumGothicBold.ttf | 폴백 폰트 |

### 브랜딩 (assets/branding/)
| 파일 | 용도 |
|------|------|
| channel_icon.png | 채널 프로필 아이콘 (800x800) |
| channel_banner.png | 채널 배너 (2560x1440) |
| watermark.png | 동영상 워터마크 (150x150) |

## 폴백 동작

| 상황 | 폴백 |
|------|------|
| ElevenLabs 미설정 | Google Cloud TTS (Neural2) |
| Google Cloud TTS 미설정 | gTTS (무료) |
| Replicate 미설정 | Pillow placeholder 이미지 |
| Image-to-Video 실패 | Ken Burns 6방향 효과 |
| BGM 파일 미존재 | ffmpeg 무음 파일 |
| 오디오 믹싱 실패 | 내레이션만 사용 |
| 자막 번인 실패 | 자막 없이 영상 |
| HW 가속 실패 | libx264 소프트웨어 인코딩 |
| xfade 전환 실패 | fade-in/out 개별 폴백 |

## GitHub

- 저장소: `qorrmdgjs-bot/youtube`
- 브랜치: `main`
- gh CLI 인증 완료 (`qorrmdgjs-bot` 계정)
