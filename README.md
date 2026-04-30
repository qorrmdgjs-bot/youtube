# YouTube 가족 드라마 시리즈 자동화

한 가족의 30년 일대기를 다중시점 22화 시리즈로 풀어내는 한국 시니어 대상 유튜브 채널 [`@loveu-fam`](https://www.youtube.com/@loveu-fam)의 콘텐츠 자동화 파이프라인.

## 파이프라인 (12단계)

스크립트 생성(Claude) → 장면 분할 → 시각 프롬프트 → TTS(ElevenLabs) → 자막 → 이미지(Nano Banana 2 + 캐릭터 시트 reference) → FFmpeg 합성 → 썸네일/메타/수익화/쇼츠 → 패키징.

## 빠른 시작

```bash
# 환경 셋업
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .

# 시리즈 에피소드 생성 (기본)
python -m src.cli series episode --episode 1
```

## 자세한 문서

전체 비전, 가족 구성, 캐릭터 4단계 stage, 사건별 POV 매트릭스, 환경변수, 비용 추정 등은 **[CLAUDE.md](CLAUDE.md)** 참고.

스토리 자산:
- [series/drafts/](series/drafts/) — 3시점 마크다운 정본
- [series/our_family.yaml](series/our_family.yaml) — 22화 매핑
- [config/character_templates.yaml](config/character_templates.yaml) — 캐릭터 시트 레지스트리
