"""Tier 2 · 에이전트 심층 조사: 상대 계좌 입출금 내역 분석(규칙기반+통계적 이상탐지) ·
조기경보DB · 사업자등록 진위 (자동)."""
import os

from app.data.scenarios import RECIPIENTS
from app.pipeline import account_analysis

_CSV_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "account_transactions")


def run_tier2(recipient_id: str) -> dict:
    r = RECIPIENTS[recipient_id]
    csv_path = os.path.join(_CSV_DIR, r["transactions_csv"])
    analysis = account_analysis.analyze_account(csv_path)

    score = analysis["rule_score"]
    reasons = list(analysis["rule_reasons"])

    if r["early_warning_db_hit"]:
        score += 50
        reasons.append("조기경보DB 등재 이력 있음")
    if r["biz_reg_verified"] is True:
        score -= 40
        reasons.append("사업자등록 진위확인 통과(정상 사업자)")

    # 알려진 패턴(위 규칙)에는 안 걸려도, 통계적 이상탐지가 별도로 이례적 흐름을 잡아내면 가산.
    if analysis["anomaly_flag"]:
        score += 20
        reasons.append("[통계적 이상탐지] " + analysis["anomaly_reasons"][0])

    score = max(0, min(100, score))

    return {
        "recipient_label": r["label"],
        "account_number": r["account_number"],
        "auto_suspicion_score": score,
        "reasons": reasons,
        "high_auto_signal": score >= 70,
        "account_features": analysis["features"],
        "anomaly_flag": analysis["anomaly_flag"],
    }
