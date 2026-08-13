"""Tier 1 · 경량 실시간 필터: 개인화 임계값 · 첫거래 여부 · 신뢰 수취인 여부."""
from app.data.scenarios import CUSTOMERS, TRUSTED_RECIPIENTS


def run_tier1(customer_id: str, recipient_id: str, amount: int) -> dict:
    customer = CUSTOMERS[customer_id]
    is_trusted = recipient_id in TRUSTED_RECIPIENTS.get(customer_id, set())
    is_first_time = not is_trusted  # 이 목업에서는 신뢰수취인이 아니면 첫 거래로 간주
    max_ever = max(customer["max_amount_ever"], 1)
    amount_ratio_vs_max = amount / max_ever

    escalate = False
    reasons = []

    if is_trusted:
        reasons.append("등록된 신뢰 수취인")
    else:
        if amount_ratio_vs_max >= 1.5:
            escalate = True
            reasons.append(f"평소 최대 거래액 대비 {amount_ratio_vs_max:.1f}배 이상")
        if is_first_time and amount >= 500_000:
            escalate = True
            reasons.append("미등록 수취인 + 일정 금액 이상 첫 거래")

    return {
        "is_trusted_recipient": is_trusted,
        "is_first_time": is_first_time,
        "amount_ratio_vs_max": round(amount_ratio_vs_max, 2),
        "escalate_to_tier2": escalate,
        "reasons": reasons,
    }
