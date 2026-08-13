from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import store
from app.models import (
    TransactionCreate, SttSubmit, YesNoAnswers, FreeTextSubmit, EscalationAction,
)
from app.data.scenarios import SCENARIOS, get_scenario, CUSTOMERS, RECIPIENTS
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


def _customer_recipient_view(case: dict) -> dict:
    return {
        **case,
        "customer_name": CUSTOMERS[case["customer_id"]]["name"],
        "recipient_label": RECIPIENTS[case["recipient_id"]]["label"],
    }


@app.get("/api/scenarios")
def list_scenarios():
    return SCENARIOS


@app.post("/api/cases/from-scenario/{scenario_id}")
def create_case_from_scenario(scenario_id: str):
    scenario = get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(404, "존재하지 않는 시나리오입니다.")
    payload = TransactionCreate(
        teller_id="TELLER_DEMO",
        customer_id=scenario["customer_id"],
        recipient_id=scenario["recipient_id"],
        amount=scenario["amount"],
        already_sent=scenario["already_sent"],
    )
    return _start_case(payload)


@app.post("/api/cases")
def create_case(payload: TransactionCreate):
    return _start_case(payload)


def _start_case(payload: TransactionCreate):
    if payload.customer_id not in CUSTOMERS:
        raise HTTPException(400, f"알 수 없는 customer_id: {payload.customer_id}")
    if payload.recipient_id not in RECIPIENTS:
        raise HTTPException(400, f"알 수 없는 recipient_id: {payload.recipient_id}")

    t1 = tier1.run_tier1(payload.customer_id, payload.recipient_id, payload.amount)

    case = store.create_case({
        "teller_id": payload.teller_id,
        "customer_id": payload.customer_id,
        "recipient_id": payload.recipient_id,
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
        return _customer_recipient_view(store.get_case(case["id"]))

    t2 = tier2.run_tier2(payload.recipient_id)
    store.update_case(
        case["id"], tier2=t2, status="TIER2_ESCALATED",
        next_action="stt_optional_or_yesno",
    )
    store.log_event(case["id"], "tier2_escalated", t2)
    return _customer_recipient_view(store.get_case(case["id"]))


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "케이스를 찾을 수 없습니다.")
    return _customer_recipient_view(case)


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

    return _customer_recipient_view(store.get_case(case_id))


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

    return _customer_recipient_view(store.get_case(case_id))


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
        return _customer_recipient_view(store.get_case(case_id))

    final = decision.make_final_decision(store.get_case(case_id))
    high_risk = final["risk_level"] == "high"
    status = "FINAL_HIGH_RISK" if high_risk else "FINAL_LOW_RISK"
    store.update_case(
        case_id, status=status, final_decision=final,
        next_action="high_risk_actions" if high_risk else "none_completed",
    )
    store.log_event(case_id, "final_decision", final)
    return _customer_recipient_view(store.get_case(case_id))


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

    return _customer_recipient_view(store.get_case(case_id))


@app.get("/api/cases/{case_id}/log")
def get_case_log(case_id: str):
    return store.get_log(case_id)


@app.post("/api/reset")
def reset_all():
    store.reset()
    return {"ok": True}
