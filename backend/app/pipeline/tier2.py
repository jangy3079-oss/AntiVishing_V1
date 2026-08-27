"""Tier 2 · 에이전트 심층 조사: 상대 계좌 입출금 내역 분석(규칙기반+통계적 이상탐지) ·
조기경보DB · 사업자등록 진위 (자동)."""
import os

from app.pipeline import account_analysis

_CSV_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "account_transactions")

_ELDERLY_AGE_THRESHOLD = 65
_ELDERLY_BONUS = 10


def run_tier2(recipient: dict, customer: dict | None = None) -> dict:
    csv_path = os.path.join(_CSV_DIR, recipient["transactions_csv"])
    analysis = account_analysis.analyze_account(csv_path)

    score = analysis["rule_score"]
    reasons = list(analysis["rule_reasons"])

    if recipient["early_warning_db_hit"]:
        score += 50
        reasons.append("조기경보DB 등재 이력 있음")
    if recipient["biz_reg_verified"] is True:
        score -= 40
        reasons.append("사업자등록 진위확인 통과(정상 사업자)")

    # 알려진 패턴(위 규칙)에는 안 걸려도, 통계적 이상탐지가 별도로 이례적 흐름을 잡아내면 가산.
    if analysis["anomaly_flag"]:
        score += 20
        reasons.append("[통계적 이상탐지] " + analysis["anomaly_reasons"][0])

    # 계좌 자체는 깨끗한데 고객이 고령이라는 이유만으로 점수를 올리지는 않는다(계좌 위험도와
    # 무관한 신호를 섞지 않기 위해). 이미 규칙/통계 신호가 하나라도 잡힌 애매~의심 계좌에 대해서만,
    # 고령 금융소비자(65세 이상) 보호 취지로 보수적 가산을 더한다.
    if customer and customer.get("age", 0) >= _ELDERLY_AGE_THRESHOLD and (analysis["rule_score"] > 0 or analysis["anomaly_flag"]):
        score += _ELDERLY_BONUS
        reasons.append(f"고령 금융소비자(만 {customer['age']}세) 대상 거래로 보수적 기준 적용")

    score = max(0, min(100, score))

    return {
        "recipient_label": recipient["label"],
        "bank": recipient["bank"],
        "account_number": recipient["account_number"],
        "auto_suspicion_score": score,
        "reasons": reasons,
        "high_auto_signal": score >= 70,
        "account_features": analysis["features"],
        "anomaly_flag": analysis["anomaly_flag"],
    }
