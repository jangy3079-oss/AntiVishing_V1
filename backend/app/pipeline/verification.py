"""저마찰 확인 절차: ① 예/아니오 1~2문항 -> ② 자유텍스트(LLM RAG 패턴대조)."""
from app import llm_client
from app.data.scenarios import KNOWN_SCAM_PATTERNS


def evaluate_yesno(known_recipient: bool, aware_of_true_purpose: bool) -> dict:
    clearly_normal = known_recipient and aware_of_true_purpose
    return {
        "known_recipient": known_recipient,
        "aware_of_true_purpose": aware_of_true_purpose,
        "clearly_normal": clearly_normal,
    }


def evaluate_freetext(text: str, tier2_context: dict, conversation_history: list[dict] | None = None) -> dict:
    result = llm_client.analyze_freetext(text, KNOWN_SCAM_PATTERNS, tier2_context, conversation_history or [])
    return {
        "risk_level": result.get("risk_level"),
        "matched_pattern_id": result.get("matched_pattern_id"),
        "needs_followup": bool(result.get("needs_followup")),
        "followup_question": result.get("followup_question"),
        "reasoning": result.get("reasoning"),
    }
