# AntiVishing (로컬 프로토타입)

은행 창구직원용 보이스피싱 탐지 보조 도구. 고정 시나리오 6개로 Tier1(경량 필터) → Tier2(심층조사) →
STT 코칭정황 감지 / Y-N 확인 / 자유텍스트(LLM RAG 패턴대조) → 최종 위험판정(XAI) → 에스컬레이션 조치
전체 파이프라인을 로컬에서 확인할 수 있습니다.

## 사전 준비

- Python 3.10+
- Node.js 18+
- Anthropic API 키 (STT 분석, 자유텍스트 패턴대조, XAI 설명 생성에 실제 Claude API를 호출합니다. console.anthropic.com 에서 발급)

## 실행 방법 (가장 쉬운 방법)

Finder에서 `AntiVishing_v1` 폴더를 열고 **`start.command`를 더블클릭**하세요.

- 처음 실행할 때만 API 키를 물어봅니다. 붙여넣고 Enter를 누르면 `backend/.env`에 자동 저장됩니다.
- 백엔드(8000번)와 프론트엔드(5173번)를 자동으로 띄우고, 잠시 후 브라우저가 자동으로 열립니다.
- 터미널 창은 그대로 두세요 (로그가 표시됩니다). 종료하려면 그 창에서 `Ctrl + C`를 누르면 됩니다.
- 만약 "확인되지 않은 개발자" 경고가 뜨면 파일을 우클릭 → 열기를 눌러주세요.
- 다음에 다시 실행할 때는 그냥 다시 더블클릭하면 됩니다 (키는 이미 저장되어 있어 다시 묻지 않습니다).

## 수동 실행 (터미널을 직접 쓰고 싶다면)

터미널 두 개를 열어서 각각 실행합니다.

```bash
# 터미널 1 - 백엔드
cd backend
pip install -r requirements.txt
cp .env.example .env
# .env 파일을 열어 ANTHROPIC_API_KEY 값을 본인 키로 교체
uvicorn app.main:app --reload --port 8000
```

```bash
# 터미널 2 - 프론트엔드
cd frontend
npm install
npm run dev
```

브라우저에서 http://localhost:5173 접속. `/api` 요청은 vite 프록시를 통해 8000번 백엔드로 전달됩니다.

## 테스트 방법

화면에서 6개 고정 시나리오 중 하나를 골라 "거래 접수"를 누르면 파이프라인이 시작됩니다.

- **S1 정상 송금**: 신뢰 수취인이라 Tier1에서 즉시 완료됩니다.
- **S2 명백한 보이스피싱**: Tier2에서 고위험 자동신호가 뜨고, 화면에 표시된 STT 예시 문구를 붙여넣으면
  코칭 정황이 감지되어 질문 없이 바로 하드블록됩니다.
- **S3 가구점(선의)**: Tier2는 애매하게 나오고, Y/N에서 "아는 사람?"=아니오로 답해도 자유텍스트 단계로
  가서 화면의 예시 문구를 넣으면 정상으로 판정됩니다.
- **S4 대포통장 의심 / S5 자녀사칭**: Y/N에서 애매하게 답한 뒤 자유텍스트 예시 문구를 넣으면 LLM이
  알려진 사기 스크립트 패턴과 대조해 위험 높음으로 판정합니다.
- **S6 이미 송금 완료**: 위험 높음 판정 후 "골든타임 내 자동 지급정지 요청" 버튼이 추가로 나타납니다.

## 폴더 구조

```
backend/
  app/
    main.py            # FastAPI 라우트, 케이스 상태 전이
    models.py           # Pydantic 스키마
    store.py            # 인메모리 케이스 저장소 + 로그
    llm_client.py        # Claude API 래퍼 (STT분석/자유텍스트대조/XAI설명)
    data/scenarios.py    # 고객/수취계좌/조기경보DB/6개 고정 시나리오 목업
    pipeline/
      tier1.py            # 경량 실시간 필터
      tier2.py            # 심층 조사 (자동)
      stt_analysis.py     # STT 코칭정황 감지
      verification.py     # Y/N + 자유텍스트 검증
      decision.py          # 최종 위험판정 + XAI
frontend/
  src/
    App.jsx / App.css
    api.js                     # 백엔드 API 클라이언트
    components/
      TransactionForm.jsx      # 시나리오 선택 및 거래 접수
      PipelineView.jsx          # 파이프라인 단계별 결과 표시
      VerificationPanel.jsx     # STT/Y-N/자유텍스트/에스컬레이션 조작
```

## 알려진 제한사항 (로컬 프로토타입 범위)

- 조기경보DB, 통신사 신호, 코어뱅킹 거래이력은 전부 `data/scenarios.py`의 하드코딩된 목업입니다.
- 케이스는 인메모리 저장이라 백엔드를 재시작하면 초기화됩니다.
- STT는 실제 음성인식이 아니라 텍스트를 직접 입력하는 방식으로 대체했습니다 (텍스트 이후 파이프라인은 동일).
