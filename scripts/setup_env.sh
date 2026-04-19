
#!/bin/bash
# Environment setup script for YouTube automation pipeline
# Run: bash scripts/setup_env.sh

set -e

echo "=== YouTube 자동화 파이프라인 환경 설정 ==="

# 1. Check/install Homebrew
if ! command -v brew &>/dev/null; then
    echo "[1/5] Homebrew 설치 중..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    echo "[1/5] Homebrew 이미 설치됨"
fi

# 2. Install system dependencies
echo "[2/5] 시스템 의존성 설치 중..."
brew install ffmpeg pyenv 2>/dev/null || true

# 3. Install Python 3.11
echo "[3/5] Python 3.11 설치 중..."
if ! pyenv versions | grep -q "3.11"; then
    pyenv install 3.11
fi
pyenv local 3.11

# 4. Create virtual environment and install
echo "[4/5] 가상환경 생성 및 패키지 설치 중..."
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

# 5. Setup .env
echo "[5/5] 환경변수 파일 설정..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ".env 파일이 생성되었습니다. API 키를 입력해주세요."
fi

echo ""
echo "=== 설정 완료! ==="
echo "가상환경 활성화: source .venv/bin/activate"
echo "CLI 테스트: python -m src.cli --help"
