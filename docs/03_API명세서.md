# AntiVishing API 명세서

- Base URL(로컬): `http://localhost:8000`
- 프론트엔드는 `/api` prefix로 프록시됨 (`vite.config.js`)
- 모든 요청/응답은 JSON
- 에러 응답 공통 포맷: `{ "detail": "에러 메시지" }` (400/404/500 공통, 500도 실제 예외 메시지를 그대로 노출하도록 커스텀 처리됨)

## 공통 객체: Case

거의 모든 엔드포인트가 아래 형태의 "케이스" 객체를 반환한다.

```jsonc
{
  "id": "string",
  "status": "TIER1_LOW_RISK_COMPLETED | TIER2_ESCALATED | AWAITING_YESNO | AWAITING_FREETEXT | STT_HARD_BLOCKED | FINAL_HIGH_RISK | FINAL_LOW_RISK | GOLDEN_TIME_FREEZE_REQUESTED",
  "teller_id": "string",
  "customer_name": "이순자",
  "customer_account_number": "330-4455-667788",
  "recipient_label": "'안전계좌' 명의 계좌",
  "recipient_bank": "하나은행",
  "recipient_account_number": "110-452-889931",
  "amount": 25000000,
  "already_sent": false,

  "tier1": {
    "is_trusted_recipient": false,
    "is_first_time": true,
    "is_elderly_customer": true,
    "amount_ratio_vs_max": 125.0,
    "escalate_to_tier2": true,
    "reasons": ["미등록 수취인 + 일정 금액 이상 첫 거래(고령 금융소비자 65세 이상 보호 기준 적용, 300,000원 이상)"]
  },

  "tier2": {
    "recipient_label": "'안전계좌' 명의 계좌",
    "bank": "하나은행",
    "account_number": "110-452-889931",
    "auto_suspicion_score": 100,
    "reasons": [
      "입금 후 짧은 시간 내 92%가 인출됨(대포통장 의심 패턴)",
      "최근 72시간 내 12명으로부터 입금",
      "조기경보DB 등재 이력 있음",
      "[통계적 이상탐지] 분산입금 건수이(가) 정상계좌 표본 대비 15표준편차 이상(현저히 이례적) 벗어남(알려진 패턴에 해당하지 않는 이례적 거래 흐름)",
      "고령 금융소비자(만 80세) 대상 거래로 보수적 기준 적용"
    ],
    "high_auto_signal": true,
    "account_features": {
      "immediate_withdrawal_ratio": 0.92,
      "distinct_senders_72h": 12,
      "night_txn_ratio": 0.33,
      "txn_frequency_per_day": 9.29
    },
    "anomaly_flag": true
  }, // null이면 Tier1에서 저위험 종료된 케이스

  "stt_result": {
    "coaching_detected": true,
    "confidence": 0.95,
    "matched_scam_type": "검찰_금감원_사칭",
    "reasoning": "string",
    "raw": { /* LLM 원본 응답 */ }
  }, // null 가능

  "yesno_answers": {
    "known_recipient": false,
    "aware_of_true_purpose": false,
    "clearly_normal": false
  }, // null 가능

  "freetext_analysis": {
    "risk_level": "low | medium | high",
    "matched_pattern_id": "PROSECUTOR_IMPERSONATION | FAMILY_EMERGENCY | FAKE_INVESTMENT | LEGITIMATE_MERCHANT_DISCOUNT | null",
    "needs_followup": false,
    "followup_question": "string | null",
    "reasoning": "string"
  }, // null 가능

  "final_decision": {
    "risk_level": "low | high",
    "trigger": "stt_hard_block | freetext_high_risk | yesno_cleared | freetext_low_risk | fallback_auto_signal",
    "explanation": "LLM이 생성한 3~4문장 자연어 설명"
  }, // null 가능

  "escalation_log": [{ "action": "confirm_with_sender | escalate_fsi | notify_guardian | freeze_request" }],

  "conversation": [
    { "question": "아는 사람/사업체인가요?", "answer": "예" }
  ],

  "next_action": "none_completed | stt_optional_or_yesno | yesno | freetext | high_risk_actions | null",
  "pending_freetext_question": "string | null",
  "freetext_round": 0
}
```

## 엔드포인트

### GET /api/customer-lookup
고객 이름 + 본인 계좌번호로 고객 프로필을 조회한다. 신분증 스캐너가 없는 프로토타입에서 "신분증 스캔 후 정보 표출"을 재현하는 용도이며, 후보 목록을 미리 보여주지 않는다(일치하는 조합이 없으면 그냥 404).

**Query Params**: `name` (string), `account_number` (string)

**Response 200**
```json
{
  "name": "이순자",
  "account_number": "330-4455-667788",
  "age": 80,
  "gender": "여",
  "balance": 26140500,
  "recent_channel": "영업점 창구 방문 (본인)",
  "notable_activity": "2일 전 비대면(스마트폰 앱)으로 2,500만원 신용대출 실행 이력 있음. ...",
  "avg_monthly_tx_count": 0.1,
  "avg_amount": 0,
  "max_amount_ever": 200000,
  "trusted_recipient_account_numbers": []
}
```
**Response 404**: `{"detail": "일치하는 고객 정보를 찾을 수 없습니다. 이름과 계좌번호를 다시 확인해주세요."}`

### POST /api/cases
거래 접수. 고객·수취계좌를 이름/계좌번호로 조회해 매칭되면 즉시 Tier1/Tier2까지 자동 실행한다. 시나리오 카드/ID 선택 방식은 폐지되었다.

**Request Body**
```json
{
  "teller_id": "TELLER_001",
  "customer_name": "이순자",
  "customer_account_number": "330-4455-667788",
  "recipient_bank": "하나은행",
  "recipient_account_number": "110-452-889931",
  "amount": 25000000,
  "already_sent": false
}
```
- `recipient_bank`: 창구직원이 입력한 은행명(표시용 참고 정보). 매칭은 `recipient_account_number`만으로 이루어진다.
- **Response 200**: Case 객체
- **Response 404**: 고객 불일치 시 `{"detail": "일치하는 고객 정보를 찾을 수 없습니다. 이름과 계좌번호를 다시 확인해주세요."}` / 수취계좌 불일치 시 `{"detail": "조회할 수 없는 수취 계좌입니다."}`

### GET /api/cases/{case_id}
케이스 현재 상태 조회.

**Response 200**: Case 객체
**Response 404**: `{"detail": "케이스를 찾을 수 없습니다."}`

### POST /api/cases/{case_id}/stt
통화 중 채록(또는 음성인식 결과) 텍스트를 제출해 코칭 정황을 분석.

**Request Body**
```json
{ "transcript": "검찰청이라면서 안전계좌로 옮기라고 계속 통화중이에요" }
```
**Response 200**: Case 객체 (status가 `STT_HARD_BLOCKED` 또는 `AWAITING_YESNO`로 전이)
**Response 400**: `TIER2_ESCALATED` 상태가 아니면 거부

### POST /api/cases/{case_id}/yesno
Y/N 확인 질문 2건에 대한 답변 제출.

**Request Body**
```json
{ "known_recipient": false, "aware_of_true_purpose": false }
```
**Response 200**: Case 객체 (`FINAL_LOW_RISK` 즉시 확정 또는 `AWAITING_FREETEXT`로 전이)
**Response 400**: `TIER2_ESCALATED`/`AWAITING_YESNO` 상태가 아니면 거부

### POST /api/cases/{case_id}/freetext
자유텍스트 진술(또는 후속 질문 답변) 제출. 같은 엔드포인트를 후속질문에도 반복 사용한다.

**Request Body**
```json
{ "text": "아는 사람이 소개해준 투자처인데 리딩방에서 알려준 계좌로 입금하면..." }
```
**Response 200**: Case 객체
- `needs_followup=true`이고 `freetext_round < 3`이면 `pending_freetext_question`에 다음 질문이 담긴 채로 같은 상태 유지 (프론트가 재호출)
- 아니면 `final_decision` 확정, status가 `FINAL_HIGH_RISK`/`FINAL_LOW_RISK`로 전이
**Response 400**: `AWAITING_FREETEXT` 상태가 아니면 거부

### POST /api/cases/{case_id}/escalate-action
고위험 확정 케이스에 대한 조치 기록.

**Request Body**
```json
{ "action": "freeze_request" }
```
- `action`: `confirm_with_sender | escalate_fsi | notify_guardian | freeze_request`
- `already_sent=true`인 케이스에서 `freeze_request`를 보내면 status가 `GOLDEN_TIME_FREEZE_REQUESTED`로 전이

**Response 200**: Case 객체
**Response 400**: `FINAL_HIGH_RISK`/`STT_HARD_BLOCKED`/`GOLDEN_TIME_FREEZE_REQUESTED` 상태가 아니면 거부

### GET /api/cases/{case_id}/log
해당 케이스의 전체 이벤트 로그(내부 감사용).

**Response 200**
```json
[
  { "case_id": "string", "event": "tier2_escalated", "payload": { /* tier2 결과 dict */ } }
]
```

### POST /api/reset
인메모리 저장소 전체 초기화(로컬 데모/테스트용).

**Response 200**: `{ "ok": true }`

## 부록: 테스트 계정 안내 (평가자/시연자용 — 화면에는 절대 노출되지 않음)

프로토타입 화면에는 아래 목록이 전혀 표시되지 않는다(실제 창구처럼, 등록된 조합인지 아닌지만 알 수 있음). 시연·평가 시 아래 조합을 그대로 입력하면 의도된 6가지 케이스가 재현된다. 데이터 정의는 `backend/app/data/accounts.py`.

| 성격 | 고객 이름 / 본인 계좌번호 | 수취 은행 / 계좌번호 | 권장 송금액 | 기송금 |
|---|---|---|---|---|
| 정상 송금(신뢰 수취인) | 김영희 / 110-2233-445566 | 국민은행 / 352-1044-782211 | 400,000 | 아니오 |
| 검찰 사칭·안전계좌 | 이순자 / 330-4455-667788 | 하나은행 / 110-452-889931 | 25,000,000 | 아니오 |
| 가구점 할인(선의) | 박철수 / 220-3344-556677 | 신한은행 / 301-882-744102 | 800,000 | 아니오 |
| 대포통장 의심(투자 사기) | 정민호 / 440-5566-778899 | 우리은행 / 643-210-099871 | 9,000,000 | 아니오 |
| 자녀 사칭(고령층 첫거래) | 최영자 / 550-6677-889900 | 카카오뱅크 / 902-114-556602 | 3,000,000 | 아니오 |
| 이미 송금 완료(골든타임) | 김영희 / 110-2233-445566 | 하나은행 / 110-452-889931 | 18,000,000 | 예 |

이름/계좌번호 조합이 위 목록과 정확히 일치하지 않으면 `/api/customer-lookup`, `/api/cases` 모두 404로 응답한다(등록되지 않은 고객·계좌를 임의로 입력해 "정상적으로 조회되지 않는" 상태를 보여주는 것도 유효한 데모 시나리오다).
