# ---- Stage 1: 프론트엔드(React) 빌드 ----
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: 백엔드(FastAPI) + 정적 파일 서빙 ----
FROM python:3.11-slim
WORKDIR /app

# torch는 기본 PyPI 인덱스로 설치하면 CUDA 포함판이 받아져 이미지가 불필요하게 커진다.
# 배포 서버는 GPU가 없으므로 CPU 전용 휠을 쓴다.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu

# 저장소와 동일한 상대 경로 구조(repo_root/backend, repo_root/analysis)를 그대로 유지해서
# 복사한다. account_figures.py가 "../../../analysis/account_features.csv"처럼 리포지토리
# 루트 기준 상대경로로 분석용 CSV를 찾기 때문에, 이 구조가 깨지면 "계좌 위치 분석"
# 기능(자세히 보기)이 조용히 500 에러를 낸다.
# 로컬 STT 코칭탐지 분류기(model.safetensors 약 261MB, backend/app/models/coaching_classifier)도
# 이 COPY에 포함된다 — .dockerignore에서 제외되지 않도록 유지해야 한다(git 추적 여부와 무관).
COPY backend ./backend
COPY analysis ./analysis
COPY --from=frontend-build /frontend/dist ./backend/static

WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
