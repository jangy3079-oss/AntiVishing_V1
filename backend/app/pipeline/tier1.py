"""Tier 1 · 경량 실시간 필터: 개인화 임계값 · 첫거래 여부 · 신뢰 수취인 여부."""

# 금융소비자보호법 시행령 제2조 기준 "고령금융소비자"(65세 이상)는 보이스피싱 표적이 되는
# 비중이 높아, 미등록 수취인 첫 거래 확대 기준 금액을 일반 고객보다 낮춘다.
_ELDERLY_AGE_THRESHOLD = 65
_FIRST_TIME_ESCALATE_AMOUNT = 500_000
_FIRST_TIME_ESCALATE_AMOUNT_ELDERLY = 300_000


def run_tier1(customer: dict, recipient_account_number: str, amount: int) -> dict:
    is_trusted = recipient_account_number in customer.get("trusted_recipient_account_numbers", set())
    is_first_time = not is_trusted  # 이 목업에서는 신뢰수취인이 아니면 첫 거래로 간주
    is_elderly = customer.get("age", 0) >= _ELDERLY_AGE_THRESHOLD
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
        first_time_threshold = _FIRST_TIME_ESCALATE_AMOUNT_ELDERLY if is_elderly else _FIRST_TIME_ESCALATE_AMOUNT
        if is_first_time and amount >= first_time_threshold:
            escalate = True
            reason = "미등록 수취인 + 일정 금액 이상 첫 거래"
            if is_elderly:
                reason += f"(고령 금융소비자 {_ELDERLY_AGE_THRESHOLD}세 이상 보호 기준 적용, {first_time_threshold:,}원 이상)"
            reasons.append(reason)

    return {
        "is_trusted_recipient": is_trusted,
        "is_first_time": is_first_time,
        "is_elderly_customer": is_elderly,
        "amount_ratio_vs_max": round(amount_ratio_vs_max, 2),
        "escalate_to_tier2": escalate,
        "reasons": reasons,
    }
