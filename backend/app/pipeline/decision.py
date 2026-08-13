"""최종 위험 판정: 모든 신호를 종합하고 XAI 근거 설명을 생성."""
from app import llm_client


def make_final_decision(case: dict) -> dict:
    """case dict(=Case 모델의 주요 필드)를 받아 위험 낮음/높음과 XAI 설명을 반환."""
    high_risk = False
    trigger = None

    if case.get("stt_result") and case["stt_result"].get("coaching_detected"):
        high_risk = True
        trigger = "stt_hard_block"
    elif case.get("freetext_analysis") and case["freetext_analysis"].get("risk_level") == "high":
        high_risk = True
        trigger = "freetext_high_risk"
    elif case.get("yesno_answers") and case["yesno_answers"].get("clearly_normal"):
        high_risk = False
        trigger = "yesno_cleared"
    elif case.get("freetext_analysis") and case["freetext_analysis"].get("risk_level") == "low":
        high_risk = False
        trigger = "freetext_low_risk"
    else:
        # 판단 근거가 부족하면 보수적으로 저위험 처리하지 않고 애매함으로 남겨 재확인 유도
        high_risk = case.get("tier2", {}).get("high_auto_signal", False)
        trigger = "fallback_auto_signal"

    case_summary = {
        "tier1": case.get("tier1"),
        "tier2": case.get("tier2"),
        "stt_result": case.get("stt_result"),
        "yesno_answers": case.get("yesno_answers"),
        "freetext_analysis": case.get("freetext_analysis"),
        "trigger": trigger,
    }
    explanation = llm_client.generate_xai_explanation(case_summary)

    return {
        "risk_level": "high" if high_risk else "low",
        "trigger": trigger,
        "explanation": explanation,
    }
