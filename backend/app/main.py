from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import store
from app.models import (
    TransactionCreate, SttSubmit, YesNoAnswers, FreeTextSubmit, EscalationAction,
)
from app.data import accounts
from app.pipeline import tier1, tier2, stt_analysis, verification, decision

app = FastAPI(title="AntiVishing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def show_real_error(request: Request, exc: Exception):
    # 기본 FastAPI 500 응답은 "Internal Server Error"만 보여줘서 원인을 알 수 없다.
    # (예: API 키 미설정, LLM 응답 파싱 실패 등) 실제 에러 메시지를 프론트에 그대로 전달한다.
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/api/customer-lookup")
def lookup_customer(name: str, account_number: str):
    """신분증 스캐너 대신, 고객 이름+본인 계좌번호로 조회한다(창구 UI에는 후보 목록을 노출하지 않는다)."""
    customer = accounts.find_customer(name, account_number)
    if not customer:
        raise HTTPException(404, "일치하는 고객 정보를 찾을 수 없습니다. 이름과 계좌번호를 다시 확인해주세요.")
    return customer


@app.get("/api/test-accounts")
def list_test_accounts():
    """프론트 거래 접수 화면의 '테스트 계정 빠른 선택' 드롭다운용 (프로토타입 전용 편의 기능).
    실제 창구 흐름(이름+계좌번호로 blind lookup)은 /api/customer-lookup, /api/cases 그대로 유지되며,
    이 엔드포인트는 시연·테스트 시 값을 빠르게 채워 넣기 위한 목록 제공용일 뿐이다."""
    return {
        "customers": [
            {
                "name": c["name"],
                "account_number": c["account_number"],
                "age": c["age"],
                "gender": c["gender"],
            }
            for c in accounts.CUSTOMERS
        ],
        "recipients": [
            {
                "label": r["label"],
                "bank": r["bank"],
                "account_number": r["account_number"],
            }
            for r in accounts.RECIPIENTS
        ],
    }


@app.post("/api/dev/regenerate-test-accounts")
def regenerate_test_accounts(n_per_archetype: int = 5):
    """개발자 도구 전용: 대량 테스트 계좌 풀을 새로 생성해 즉시 반영한다(서버 재시작 불필요).
    손으로 만든 데모 시나리오 계좌는 유지되고, 생성 계좌 풀만 새로 교체된다."""
    return accounts.regenerate_generated_pool(n_per_archetype)


@app.post("/api/cases")
def create_case(payload: TransactionCreate):
    return _start_case(payload)


def _start_case(payload: TransactionCreate):
    customer = accounts.find_customer(payload.customer_name, payload.customer_account_number)
    if not customer:
        raise HTTPException(404, "일치하는 고객 정보를 찾을 수 없습니다. 이름과 계좌번호를 다시 확인해주세요.")

    recipient = accounts.find_recipient(payload.recipient_account_number)
    if not recipient:
        raise HTTPException(404, "조회할 수 없는 수취 계좌입니다.")

    t1 = tier1.run_tier1(customer, recipient["account_number"], payload.amount)

    case = store.create_case({
        "teller_id": payload.teller_id,
        "customer_name": customer["name"],
        "customer_account_number": customer["account_number"],
        "recipient_label": recipient["label"],
        "recipient_bank": payload.recipient_bank or recipient["bank"],
        "recipient_account_number": recipient["account_number"],
        "amount": payload.amount,
        "already_sent": payload.already_sent,
        "tier1": t1,
        "tier2": None,
        "stt_result": None,
        "yesno_answers": None,
        "freetext_analysis": None,
        "final_decision": None,
        "escalation_log": [],
        "conversation": [],
        "pending_freetext_question": None,
        "freetext_round": 0,
    })

    if not t1["escalate_to_tier2"]:
        store.update_case(case["id"], status="TIER1_LOW_RISK_COMPLETED", next_action="none_completed")
        store.log_event(case["id"], "tier1_low_risk", t1)
        return store.get_case(case["id"])

    t2 = tier2.run_tier2(recipient, customer)
    store.update_case(
        case["id"], tier2=t2, status="TIER2_ESCALATED",
        next_action="stt_optional_or_yesno",
    )
    store.log_event(case["id"], "tier2_escalated", t2)
    return store.get_case(case["id"])


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "케이스를 찾을 수 없습니다.")
    return case


@app.post("/api/cases/{case_id}/stt")
def submit_stt(case_id: str, payload: SttSubmit):
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "케이스를 찾을 수 없습니다.")
    if case["status"] != "TIER2_ESCALATED":
        raise HTTPException(400, "STT 분석은 Tier2로 확대된 케이스에서만 가능합니다.")

    result = stt_analysis.analyze_stt(payload.transcript)
    store.update_case(case_id, stt_result=result)
    store.add_conversation(case_id, "(고객이 통화 중인 것으로 보여 창구 대화를 채록함)", payload.transcript)
    store.log_event(case_id, "stt_analyzed", result)

    if result["coaching_detected"]:
        final = decision.make_final_decision(store.get_case(case_id))
        store.update_case(case_id, status="STT_HARD_BLOCKED", final_decision=final, next_action="high_risk_actions")
        store.log_event(case_id, "final_decision", final)
    else:
        store.update_case(case_id, status="AWAITING_YESNO", next_action="yesno")

    return store.get_case(case_id)


@app.post("/api/cases/{case_id}/yesno")
def submit_yesno(case_id: str, payload: YesNoAnswers):
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "케이스를 찾을 수 없습니다.")
    if case["status"] not in ("TIER2_ESCALATED", "AWAITING_YESNO"):
        raise HTTPException(400, "지금 단계에서는 Y/N 답변을 받을 수 없습니다.")

    result = verification.evaluate_yesno(payload.known_recipient, payload.aware_of_true_purpose)
    store.update_case(case_id, yesno_answers=result)
    store.add_conversation(case_id, "아는 사람/사업체인가요?", "예" if payload.known_recipient else "아니오")
    store.add_conversation(
        case_id, "이 돈의 정확한 용도를 알고 계신가요?", "예" if payload.aware_of_true_purpose else "아니오"
    )
    store.log_event(case_id, "yesno_evaluated", result)

    if result["clearly_normal"]:
        final = decision.make_final_decision(store.get_case(case_id))
        store.update_case(case_id, status="FINAL_LOW_RISK", final_decision=final, next_action="none_completed")
        store.log_event(case_id, "final_decision", final)
    else:
        store.update_case(case_id, status="AWAITING_FREETEXT", next_action="freetext")

    return store.get_case(case_id)


@app.post("/api/cases/{case_id}/freetext")
def submit_freetext(case_id: str, payload: FreeTextSubmit):
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "케이스를 찾을 수 없습니다.")
    if case["status"] != "AWAITING_FREETEXT":
        raise HTTPException(400, "지금 단계에서는 자유텍스트를 받을 수 없습니다.")

    question_asked = case.get("pending_freetext_question") or "상황을 간단히 말씀해주세요"
    case["freetext_round"] = case.get("freetext_round", 0) + 1
    prior_conversation = list(case.get("conversation", []))  # 이번 턴 추가 전 스냅샷 (중복질문 방지용)
    result = verification.evaluate_freetext(payload.text, case["tier2"], prior_conversation)
    store.update_case(case_id, freetext_analysis=result)
    store.add_conversation(case_id, question_asked, payload.text)
    store.log_event(case_id, "freetext_analyzed", result)

    # 설계상 후속질문은 최초 답변 이후 최대 2회까지만 허용한다 (끝없이 심문식으로 반복되는 것 방지).
    followup_allowed = case["freetext_round"] < 3
    if result["needs_followup"] and followup_allowed:
        store.update_case(
            case_id, next_action="freetext", pending_freetext_question=result["followup_question"]
        )  # 후속질문도 같은 엔드포인트로 재제출
        return store.get_case(case_id)

    final = decision.make_final_decision(store.get_case(case_id))
    high_risk = final["risk_level"] == "high"
    status = "FINAL_HIGH_RISK" if high_risk else "FINAL_LOW_RISK"
    store.update_case(
        case_id, status=status, final_decision=final,
        next_action="high_risk_actions" if high_risk else "none_completed",
    )
    store.log_event(case_id, "final_decision", final)
    return store.get_case(case_id)


@app.post("/api/cases/{case_id}/escalate-action")
def submit_escalation_action(case_id: str, payload: EscalationAction):
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "케이스를 찾을 수 없습니다.")
    if case["status"] not in ("FINAL_HIGH_RISK", "STT_HARD_BLOCKED", "GOLDEN_TIME_FREEZE_REQUESTED"):
        raise HTTPException(400, "고위험 판정 케이스에서만 에스컬레이션 조치를 기록할 수 있습니다.")

    entry = {"action": payload.action}
    case["escalation_log"].append(entry)
    store.log_event(case_id, "escalation_action", entry)

    if payload.action == "freeze_request" and case.get("already_sent"):
        store.update_case(case_id, status="GOLDEN_TIME_FREEZE_REQUESTED")

    return store.get_case(case_id)


@app.get("/api/cases/{case_id}/log")
def get_case_log(case_id: str):
    return store.get_log(case_id)


@app.post("/api/reset")
def reset_all():
    store.reset()
    return {"ok": True}
