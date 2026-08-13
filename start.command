#!/bin/bash
# AntiVishing 로컬 실행 스크립트 (더블클릭으로 실행)
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== AntiVishing 로컬 서버 시작 ==="

# 이전에 떠 있던 서버가 있으면 정리 (포트 충돌 방지)
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true

# --- 백엔드 준비 ---
cd "$ROOT/backend"
echo "[백엔드] 의존성 확인 중..."
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "Anthropic API 키가 아직 설정되지 않았습니다. (console.anthropic.com 에서 발급)"
  read -s -p "API 키를 붙여넣고 Enter (나중에 넣으려면 그냥 Enter): " API_KEY
  echo ""
  if [ -n "$API_KEY" ]; then
    API_KEY="$API_KEY" python3 -c "
import os
path = '.env'
with open(path) as f:
    content = f.read()
content = content.replace('sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', os.environ['API_KEY'])
with open(path, 'w') as f:
    f.write(content)
"
    echo "API 키를 backend/.env 에 저장했습니다."
  else
    echo "키를 나중에 backend/.env 파일에 직접 넣어주세요."
  fi
fi

echo "[백엔드] 서버 시작 (http://localhost:8000)"
uvicorn app.main:app --port 8000 > "$ROOT/backend.log" 2>&1 &
BACK_PID=$!

# --- 프론트엔드 준비 ---
cd "$ROOT/frontend"
if [ ! -d "node_modules" ]; then
  echo "[프론트엔드] 의존성 설치 중... (처음 한 번만, 1~2분 소요)"
  npm install --silent
fi

echo "[프론트엔드] 서버 시작 (http://localhost:5173)"
npm run dev > "$ROOT/frontend.log" 2>&1 &
FRONT_PID=$!

cd "$ROOT"
trap "echo ''; echo '종료 중...'; kill $BACK_PID $FRONT_PID 2>/dev/null; exit" INT TERM

sleep 3
echo ""
echo "준비 완료. 브라우저를 엽니다: http://localhost:5173"
echo "이 창을 닫지 말고 그대로 두세요. 종료하려면 이 창에서 Ctrl+C 를 누르세요."
open http://localhost:5173 2>/dev/null || true

echo ""
echo "--- 실시간 로그 (문제가 생기면 여기서 원인을 확인하세요) ---"
tail -f "$ROOT/backend.log" "$ROOT/frontend.log"
