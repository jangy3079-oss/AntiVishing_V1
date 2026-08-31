# Fly.io 배포 가이드

이 문서는 AntiVishing MVP를 Fly.io에 실제로 올릴 때 **직접** 실행해야 하는 명령어 순서다.
계정 로그인/인증은 Claude가 대신 해줄 수 없으니, 아래 단계를 터미널에서 그대로 따라가면 된다.

준비된 배포 파일: `Dockerfile`, `.dockerignore`, `fly.toml` (모두 리포지토리 루트에 있음).
백엔드(FastAPI)가 프론트(React 빌드 결과물)를 같은 서비스·같은 URL에서 정적으로 같이
서빙하는 단일 서비스 구조라, 별도 프론트 배포나 CORS 설정이 필요 없다. 로컬 STT
코칭탐지 분류기(model.safetensors, 약 261MB)도 이미지에 포함되어 실제 동작을 로컬에서
검증했다(pandas/sklearn/matplotlib 렌더링, Claude 설명 호출, 로컬 분류기 추론 모두 확인).

## 0. 사전 준비

- 리포지토리 루트(`AntiVishing_v1/`)에서 아래 명령을 실행한다.
- Fly.io 계정이 없으면 `fly auth signup`으로 새로 만들 수 있다(신용카드 등록 필요할 수 있음 —
  트라이얼 크레딧과는 별개로 상시구동은 유료이기 때문).

```bash
# macOS
curl -L https://fly.io/install.sh | sh
# 설치 후 PATH에 추가하라는 안내가 나오면 그대로 따른다 (보통 ~/.zshrc 등에 추가)

fly version   # 설치 확인
```

## 1. 로그인

```bash
fly auth login
```

브라우저가 열리면 로그인/가입을 완료한다.

## 2. 앱 생성

`fly.toml`에 앱 이름을 `antivishing-v1`로 미리 넣어뒀다. 이미 사용 중인 이름이면 아래
명령이 다른 이름을 물어보거나 에러를 낸다 — 그러면 `fly.toml`의 `app = "..."` 값을
원하는 이름으로 바꾸고 다시 실행하면 된다.

```bash
fly launch --no-deploy
```

- `--no-deploy`: 앱/설정만 생성하고 아직 배포는 하지 않음 (시크릿을 먼저 넣어야 하므로).
- 리전 등을 물어보면 이미 `fly.toml`에 적어둔 `nrt`(도쿄, 한국에서 가장 가까운 리전)를
  그대로 쓰겠다고 하면 된다.
- "기존 fly.toml을 쓸까?"라고 물으면 Yes.

## 3. 환경변수(API 키) 등록

`backend/.env`에 있는 값을 그대로 옮긴다. **이 값은 Claude에게 다시 보여주지 말고
본인 터미널에만 입력한다.**

```bash
fly secrets set ANTHROPIC_API_KEY="본인의 anthropic API 키" ANTHROPIC_MODEL="claude-sonnet-5"
```

## 4. 배포

```bash
fly deploy
```

- 첫 배포는 프론트 빌드 + torch(CPU 전용 휠) 설치 때문에 몇 분 걸릴 수 있다.
- 빌드 로그에 에러가 나면 그대로 복사해서 보여주면 같이 원인을 본다.

## 5. 확인

```bash
fly status        # 머신이 떠 있는지 확인
fly logs           # 실시간 로그
fly open           # 브라우저로 배포된 URL 열기
```

배포된 URL은 기본적으로 `https://antivishing-v1.fly.dev` 형태다(2단계에서 이름을 바꿨다면
그 이름 기준).

## 참고: 비용/동작 방식

- `fly.toml`에 `auto_stop_machines = "stop"`, `min_machines_running = 0`으로 설정해뒀다 —
  접속이 없으면 머신이 꺼져서 과금이 거의 없고, 다음 요청이 오면 자동으로 다시 켜진다.
  대회 제출용 데모처럼 상시 트래픽이 없는 경우에 예산(월 1만원 이내)을 지키기 좋은 설정이다.
- 단, 꺼져 있다가 처음 요청이 오면 머신이 새로 뜨는 데 약간의 지연(수 초)이 있고, 그 요청이
  하필 STT 확인 절차라면 로컬 분류기 모델을 처음 불러오는 시간(로컬 테스트 기준 약 2초)이
  추가로 붙는다. 심사 직전에 한 번 미리 접속해서 "깨워두는" 것을 권한다.
- 메모리는 `1gb`로 잡아뒀다(로컬 분류기 로딩 여유분 포함). 배포 후 `fly logs`에서
  OOM(메모리 부족) 관련 에러가 보이면 `fly.toml`의 `memory = "1gb"`를
  `memory = "2gb"`로 올리고 `fly deploy`를 다시 실행하면 된다.
- 실제 과금은 Fly.io 대시보드(https://fly.io/dashboard) 의 Billing에서 확인할 수 있다.

## 문제 생길 때

- `fly deploy`가 빌드 단계에서 실패하면: 에러 로그를 그대로 보여주면 원인 파악을 돕겠다.
- 배포는 됐는데 화면이 빈 화면이면: 브라우저 개발자도구 콘솔/네트워크 탭 스크린샷을 보여주면
  정적 파일 경로 문제인지 API 문제인지 구분할 수 있다.
- `/api/...` 요청이 404가 나면: 정적 파일 서빙 mount가 API 라우트보다 먼저 등록됐을 가능성
  등을 점검해야 하니 알려달라(로컬 테스트에서는 이 순서가 정상 동작하는 것을 확인했다).
