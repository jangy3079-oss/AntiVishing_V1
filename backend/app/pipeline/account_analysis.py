"""상대 계좌 입출금 내역(CSV)을 분석해 대포통장/이상거래 신호를 계산한다.

① 규칙기반 스코어링 (메인)
   대포통장/보이스피싱 수취계좌의 전형적 특징(즉시인출·분산입금·심야거래)에
   점수를 매긴다. 결과가 항상 재현 가능하고 각 점수의 근거를 그대로 설명할 수 있다.

② 통계적 이상탐지 (보조)
   ①의 규칙에 없는 패턴도 놓치지 않기 위해, 정상계좌 표본 대비 각 지표가 통계적으로
   얼마나 벗어났는지(z-score)를 계산한다. 특히 '일평균 거래빈도'는 ①에는 없는 지표라서,
   규칙으로 정의해두지 않은 이상 패턴(예: 소액 분할 거래 반복=구조화 의심)도 잡아낼 수 있다.
"""
import csv
from datetime import datetime, timedelta

_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"

# 정상계좌 표본 평균/표준편차.
# distinct_senders_72h는 AI-Hub 실제 금융거래 데이터(analysis/account_cluster.py)를 이 함수와
# "동일한 정의"(최근 거래시각 기준 72시간 롤링 윈도우)로 재계산해 얻은 정상계좌 실측치다.
# 주의: analysis/comparison_figures.py의 "분산입금 상대방 수 약 5배" 결과는 계좌가 관측된 전체 기간의
# 누적 상대방 수를 쓴 것이라 정의가 다르다. 이 72시간 윈도우 버전으로 다시 계산해보면 정상(0.53)과
# 이상연루(0.61) 계좌의 차이가 크지 않아 판별력은 약하지만, 그래도 이 함수의 정의와 정확히 일치하는
# 실측치이므로 임의의 가정치보다는 이 값을 쓴다.
# txn_frequency_per_day는 실측 데이터에서 이상연루 계좌가 정상 대비 약 4배 높다는 유효한 결과를
# 얻었지만(comparison_figures.py fig1), 그 절대값(정상 평균 0.017/일)은 실제 계좌가 수개월 단위로
# 관측된 데이터라서 나온 것이다. 반면 우리 데모 CSV는 며칠짜리 짧은 구간만 담고 있어 정상 계좌도
# 하루 1건 안팎(수십 배 더 높은 값)으로 나온다. 이 절대값을 그대로 baseline에 쓰면 정상 데모 계좌
# (가구점 등)까지 통계적 이상탐지에 오탐지되는 것을 실제로 확인했다. 그래서 이 지표는 "관측 기간이
# 짧은 프로토타입 데모"에 맞춘 가정치를 유지하고, 실측에서 확인한 "약 4배 차이"라는 정성적 결론만
# 참고한다(distinct_senders_72h처럼 실측 절대값을 그대로 옮기지 않음).
# immediate_withdrawal_ratio / night_txn_ratio는 실측 데이터에서 정상계좌 평균이 거의 0(노이즈 수준,
# std도 극히 작음)이라, 마찬가지로 실측 절대값을 쓰지 않고 프로토타입 가정치(도메인 지식 기반)를 유지한다.
_NORMAL_BASELINE = {
    "immediate_withdrawal_ratio": {"mean": 0.15, "std": 0.12},  # 프로토타입 가정치 (실측 미검증)
    "distinct_senders_72h": {"mean": 0.53, "std": 0.54},  # AI-Hub 실측(72h 윈도우 재계산)
    "night_txn_ratio": {"mean": 0.05, "std": 0.05},  # 프로토타입 가정치 (실측 미검증)
    "txn_frequency_per_day": {"mean": 2.0, "std": 1.5},  # 프로토타입 가정치 (관측기간 스케일 불일치로 실측값 미적용)
}

# z-score 표시용 상한. 위 실측 baseline 중 std가 매우 작은 지표(txn_frequency_per_day)는
# 관측 기간이 짧은 데모 CSV에 적용하면 수백 표준편차처럼 비현실적인 숫자가 나올 수 있어,
# 판정 로직(>=3.0)은 원래 z-score 그대로 쓰되 "표시 문구"만 이 값으로 상한을 둔다.
_Z_DISPLAY_CAP = 15.0

_FEATURE_LABELS = {
    "immediate_withdrawal_ratio": "즉시인출비율",
    "distinct_senders_72h": "분산입금 건수",
    "night_txn_ratio": "심야거래 비중",
    "txn_frequency_per_day": "일평균 거래빈도",
}


def _load_transactions(csv_path: str) -> list[dict]:
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "dt": datetime.strptime(row["거래일시"], _DATETIME_FMT),
                "type": row["구분"],
                "amount": int(row["금액"]),
                "counterparty": row.get("상대방", ""),
            })
    rows.sort(key=lambda r: r["dt"])
    return rows


def _immediate_withdrawal_ratio(txns: list[dict], window_hours: int = 6) -> float:
    """입금 각 건에 대해, 이후 window_hours 이내에 얼마나 인출되었는지의 입금액 가중평균."""
    inflows = [t for t in txns if t["type"] == "입금"]
    if not inflows:
        return 0.0
    weighted_ratio_sum = 0.0
    total_amount = 0
    for inflow in inflows:
        window_end = inflow["dt"] + timedelta(hours=window_hours)
        withdrawn = sum(
            t["amount"] for t in txns
            if t["type"] == "출금" and inflow["dt"] < t["dt"] <= window_end
        )
        ratio = min(1.0, withdrawn / inflow["amount"]) if inflow["amount"] else 0.0
        weighted_ratio_sum += ratio * inflow["amount"]
        total_amount += inflow["amount"]
    return weighted_ratio_sum / total_amount if total_amount else 0.0


def _distinct_senders_72h(txns: list[dict]) -> int:
    """가장 최근 거래 시각 기준 직전 72시간 내 서로 다른 입금 상대방 수."""
    inflows = [t for t in txns if t["type"] == "입금"]
    if not inflows:
        return 0
    now = max(t["dt"] for t in txns)
    window_start = now - timedelta(hours=72)
    senders = {t["counterparty"] for t in inflows if t["dt"] >= window_start}
    return len(senders)


def _night_txn_ratio(txns: list[dict]) -> float:
    if not txns:
        return 0.0
    night = sum(1 for t in txns if t["dt"].hour >= 23 or t["dt"].hour < 6)
    return night / len(txns)


def _txn_frequency_per_day(txns: list[dict]) -> float:
    if not txns:
        return 0.0
    span_days = max(
        1.0, (max(t["dt"] for t in txns) - min(t["dt"] for t in txns)).total_seconds() / 86400
    )
    return len(txns) / span_days


def _zscore(value: float, key: str) -> float:
    base = _NORMAL_BASELINE[key]
    return (value - base["mean"]) / base["std"]


def analyze_account(csv_path: str) -> dict:
    txns = _load_transactions(csv_path)

    features = {
        "immediate_withdrawal_ratio": round(_immediate_withdrawal_ratio(txns), 2),
        "distinct_senders_72h": _distinct_senders_72h(txns),
        "night_txn_ratio": round(_night_txn_ratio(txns), 2),
        "txn_frequency_per_day": round(_txn_frequency_per_day(txns), 2),
    }

    # ① 규칙기반 스코어링
    rule_score = 0
    rule_reasons = []
    if features["immediate_withdrawal_ratio"] >= 0.8:
        rule_score += 30
        rule_reasons.append(
            f"입금 후 짧은 시간 내 {features['immediate_withdrawal_ratio'] * 100:.0f}%가 인출됨"
            "(대포통장 의심 패턴)"
        )
    if features["distinct_senders_72h"] >= 5:
        rule_score += 15
        rule_reasons.append(f"최근 72시간 내 {features['distinct_senders_72h']}명으로부터 입금")
    if features["night_txn_ratio"] >= 0.4:
        rule_score += 10
        rule_reasons.append(f"심야(23시~06시) 거래 비중이 {features['night_txn_ratio'] * 100:.0f}%로 높음")

    # ② 통계적 이상탐지 (규칙에 없는 패턴도 탐지하기 위한 보조 레이어)
    z_scores = {k: round(_zscore(features[k], k), 2) for k in features}
    max_key = max(z_scores, key=lambda k: z_scores[k])
    max_z = z_scores[max_key]
    anomaly_flag = max_z >= 3.0
    anomaly_reasons = []
    if anomaly_flag:
        if max_z > _Z_DISPLAY_CAP:
            deviation_text = f"{_Z_DISPLAY_CAP:.0f}표준편차 이상(현저히 이례적)"
        else:
            deviation_text = f"{max_z:.1f}표준편차"
        anomaly_reasons.append(
            f"{_FEATURE_LABELS[max_key]}이(가) 정상계좌 표본 대비 {deviation_text} 벗어남"
            "(알려진 패턴에 해당하지 않는 이례적 거래 흐름)"
        )

    return {
        "features": features,
        "rule_score": min(rule_score, 100),
        "rule_reasons": rule_reasons,
        "anomaly_flag": anomaly_flag,
        "anomaly_score": max_z,
        "anomaly_reasons": anomaly_reasons,
        "txn_count": len(txns),
    }
