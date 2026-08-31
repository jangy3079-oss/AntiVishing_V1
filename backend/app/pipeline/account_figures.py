"""수취계좌 위치 시각화: analysis/account_features.csv(AI-Hub 실측 데이터, 정상 vs 이상거래
연루 계좌 47,754건)를 모집단 기준선으로 삼아, 지금 이 케이스의 수취계좌가 그 모집단 안에서
어디쯤 위치하는지 2개의 그래프로 보여준다.

- 극단치 쏠림 비교(초과비율): 실제로 신호가 있는 2개 지표(분산입금 상대방 수/일평균 거래빈도)만
  써서, 정상계좌 기준 상위 P% 구간을 이상연루 계좌가 얼마나 더 많이 초과하는지 보여준다.
- 정상군 중심 이탈 거리: 4개 지표를 표준화한 공간에서 정상군 중심으로부터의 거리 분포.

PCA 2D 산점도는 폐기했다: 정상/이상연루 두 그룹의 중심이 거의 겹치고 점도 완전히 섞여 있어
"어디가 정상 구역인지" 답이 안 되는 그래프였다(로지스틱회귀 AUC 0.667 수준 — 이 4개 지표로는
원래 뚜렷이 안 갈린다는 걸 보여줄 뿐, 위치 판단 기준으로 쓰기엔 오히려 헷갈림만 준다).

주의 — 지표 정의 일치 여부:
- immediate_withdrawal_ratio / night_txn_ratio / txn_frequency_per_day는 account_analysis.py가
  런타임에 쓰는 정의를 그대로 쓴다(이미 화면에 노출 중인 값과 일치시키기 위해).
- distinct_senders만은 다르다. account_analysis.py는 운영 관점에서 "최근 72시간" 윈도우 버전
  (distinct_senders_72h)을 쓰지만, 모집단 figure의 distinct_senders는 "계좌가 관측된 전체 기간"
  기준이다(account_cluster.py 참고). 두 정의를 섞으면 축이 안 맞으므로, 이 모듈에서는 모집단과
  같은 정의(전체 기간 고유 입금 상대방 수)로 별도 계산한다.
"""
import base64
import io
import os

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from sklearn.preprocessing import StandardScaler

from app.pipeline import account_analysis

# "Noto Sans CJK JP"라는 이름만 지정했었는데, 이 폰트가 시스템에 실제로 설치되어 있지 않으면
# matplotlib이 기본 폰트(한글 미지원)로 조용히 폴백해서 한글이 전부 네모(tofu)로 깨진다 —
# 실제로 로컬 환경에서 이렇게 깨지는 게 확인됐다. 폰트 파일을 프로젝트에 직접 번들해서, 어떤
# 환경에서 실행하든(개발자 PC마다 설치된 폰트가 달라도) 항상 같은 폰트로 렌더링되게 한다.
_KOREAN_FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "NanumGothic-Regular.ttf")
if os.path.exists(_KOREAN_FONT_PATH):
    fm.fontManager.addfont(_KOREAN_FONT_PATH)
    plt.rcParams["font.family"] = fm.FontProperties(fname=_KOREAN_FONT_PATH).get_name()
else:
    plt.rcParams["font.family"] = "Noto Sans CJK JP"  # 폰트 파일이 없으면 예전 방식으로 폴백
plt.rcParams["axes.unicode_minus"] = False

_FEATURES_CSV = os.path.join(os.path.dirname(__file__), "..", "..", "..", "analysis", "account_features.csv")

_COLS = ["immediate_withdrawal_ratio", "distinct_senders", "night_txn_ratio", "txn_frequency_per_day"]
_LABELS = {
    "immediate_withdrawal_ratio": "즉시인출비율",
    "distinct_senders": "분산입금 상대방 수(전체기간)",
    "night_txn_ratio": "심야거래 비중",
    "txn_frequency_per_day": "일평균 거래빈도",
}
_COLOR_NORMAL = "#4C72B0"
_COLOR_ANOMALY = "#C0392B"
_COLOR_CASE = "#E8A33D"

_state = {}


def _ensure_loaded():
    """모집단 데이터 로드 + 스케일러 적합을 1회만 수행하고 캐시한다(요청마다 반복 X)."""
    if _state:
        return
    feat = pd.read_csv(_FEATURES_CSV, index_col=0)
    feat["is_anomaly_account"] = feat["is_anomaly_account"].astype(bool)
    normal = feat[~feat["is_anomaly_account"]]
    anomaly = feat[feat["is_anomaly_account"]]

    X = feat[_COLS].values
    scaler = StandardScaler().fit(np.log1p(X))
    Xs = scaler.transform(np.log1p(X))

    centroid_4d = Xs[~feat["is_anomaly_account"].values].mean(axis=0)
    dist_4d_all = np.linalg.norm(Xs - centroid_4d, axis=1)

    _state.update(
        feat=feat, normal=normal, anomaly=anomaly, scaler=scaler,
        centroid_4d=centroid_4d,
        dist_normal=dist_4d_all[~feat["is_anomaly_account"].values],
        dist_anomaly=dist_4d_all[feat["is_anomaly_account"].values],
    )


def _full_period_distinct_senders(csv_path: str) -> int:
    """모집단 figure와 같은 정의(전체 관측 기간 동안의 고유 입금 상대방 수)로 계산."""
    txns = account_analysis._load_transactions(csv_path)
    senders = {t["counterparty"] for t in txns if t["type"] == "입금"}
    return len(senders)


def compute_case_position(csv_path: str) -> dict:
    """이번 케이스 수취계좌를 모집단과 같은 4개 지표 표준화 공간에 위치시킨다."""
    _ensure_loaded()
    s = _state
    analysis = account_analysis.analyze_account(csv_path)
    f = analysis["features"]
    x = np.array([[
        f["immediate_withdrawal_ratio"],
        _full_period_distinct_senders(csv_path),
        f["night_txn_ratio"],
        f["txn_frequency_per_day"],
    ]])
    xs = s["scaler"].transform(np.log1p(x))
    dist_from_normal = float(np.linalg.norm(xs[0] - s["centroid_4d"]))

    per_feature = {}
    for i, col in enumerate(_COLS):
        m_normal = s["normal"][col].mean()
        m_anomaly = s["anomaly"][col].mean()
        per_feature[col] = {
            "label": _LABELS[col],
            "case_value": round(float(x[0][i]), 4),
            "normal_mean": round(float(m_normal), 4),
            "anomaly_mean": round(float(m_anomaly), 4),
            "ratio_vs_normal": round(float(x[0][i] / m_normal), 2) if m_normal > 0 else None,
        }

    return {
        "raw_vector": x[0].tolist(),
        "dist_from_normal": dist_from_normal,
        "dist_normal_mean": float(s["dist_normal"].mean()),
        "dist_anomaly_mean": float(s["dist_anomaly"].mean()),
        "per_feature": per_feature,
        "tier2_rule_reasons": analysis["rule_reasons"],
        "tier2_anomaly_flag": analysis["anomaly_flag"],
        # 데모 계좌 CSV는 며칠짜리 짧은 관측 구간만 담고 있어(모집단은 AI-Hub 실제 계좌를 수개월
        # 관측), txn_frequency_per_day 같은 지표는 배율이 수십~수백 배로 과장되어 보일 수 있다
        # (account_analysis.py의 _NORMAL_BASELINE 주석과 같은 한계). LLM 설명 생성 시 이 점을
        # 반드시 감안하도록 넘겨준다.
        "caveat": (
            "이 케이스의 계좌 CSV는 며칠 안의 짧은 기간만 담고 있어 txn_frequency_per_day 같은 "
            "지표는 모집단(수개월 관측)보다 수십~수백 배 높게 나올 수 있다. 배율의 절대값보다는 "
            "정상군/이상연루군 중 어느 쪽 패턴에 더 가까운지(방향성)를 중심으로 해석해야 한다."
        ),
    }


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# 지표별 평균 막대 비교는 폐기했다: 실측 검증 결과(로지스틱회귀 AUC 0.667, distinct_senders
# 중앙값이 정상·이상연루 둘 다 1.0으로 동일) 평균 기준 "5배/4배" 차이는 극소수 극단치 계좌가
# 끌어올린 수치일 뿐, 이상연루 계좌의 80% 이상은 이 지표들만 보면 정상 계좌와 통계적으로 구분이
# 안 된다. 막대그래프는 이 사실을 왜곡해서 "뚜렷이 갈리는 것처럼" 보이게 하므로 정직하지 않다.
# 대신 실제로 존재하는 신호 — "평소엔 비슷하지만 극단 구간에서는 이상연루 비중이 커진다" —를
# 왜곡 없이 보여주는 초과비율(엔리치먼트) 곡선으로 바꾼다. immediate_withdrawal_ratio·
# night_txn_ratio는 정상/이상연루 모두 거의 0이라 이 방식으로도 그릴 신호 자체가 없어 제외하고,
# 실제로 신호가 있는 2개 지표(분산입금 상대방 수 / 일평균 거래빈도)만 쓴다.
_SIGNAL_COLS = ["distinct_senders", "txn_frequency_per_day"]
_EXCEEDANCE_P = [50, 40, 30, 25, 20, 15, 10, 7, 5, 3, 2, 1, 0.5]


def _percentile_of(value: float, population: np.ndarray) -> float:
    """population 안에서 value보다 작거나 같은 값의 비율(%) — value가 상위 몇 %에 해당하는지."""
    return float((population <= value).mean() * 100)


def _draw_exceedance_cell(ax, col: str, pf: dict) -> None:
    s = _state
    normal_vals = s["normal"][col].values
    anomaly_vals = s["anomaly"][col].values

    thresholds = [np.percentile(normal_vals, 100 - p) for p in _EXCEEDANCE_P]
    exceed_frac = [float((anomaly_vals > thr).mean() * 100) for thr in thresholds]

    ax.plot(_EXCEEDANCE_P, _EXCEEDANCE_P, linestyle="--", color="#999", linewidth=1.3, label="차이 없음 기준선")
    ax.plot(_EXCEEDANCE_P, exceed_frac, marker="o", markersize=4, color=_COLOR_ANOMALY, linewidth=2, label="이상연루 계좌 초과비율")
    ax.fill_between(_EXCEEDANCE_P, _EXCEEDANCE_P, exceed_frac, where=[e >= p for e, p in zip(exceed_frac, _EXCEEDANCE_P)], color=_COLOR_ANOMALY, alpha=0.12)

    # 이 계좌가 정상 분포에서 상위 몇 %에 해당하는지 계산해 곡선 위에 표시한다.
    case_value = pf["case_value"]
    case_top_p = 100 - _percentile_of(case_value, normal_vals)
    case_top_p_clamped = min(max(case_top_p, _EXCEEDANCE_P[-1]), _EXCEEDANCE_P[0])
    ax.axvline(case_top_p_clamped, color=_COLOR_CASE, linestyle="-", linewidth=2, label="이 계좌 위치")
    off_scale = case_top_p < _EXCEEDANCE_P[-1]
    case_label = f"이 계좌: 정상 상위 {case_top_p:.1f}%대\n(값 {case_value:.3f})"
    if off_scale:
        case_label = f"이 계좌: 정상 상위 {case_top_p:.2f}%\n(값 {case_value:.3f}, 그래프 범위보다 더 극단)"
    ax.annotate(
        case_label, xy=(case_top_p_clamped, ax.get_ylim()[1] if ax.get_ylim()[1] else 10),
        xytext=(0.97, 0.95), textcoords="axes fraction", ha="right", va="top",
        fontsize=8.5, fontweight="bold", color="#8a5a12",
        bbox=dict(boxstyle="round,pad=0.35", fc="#FFF3DC", ec=_COLOR_CASE),
    )

    p1_idx = _EXCEEDANCE_P.index(1)
    enrich_1pct = exceed_frac[p1_idx] / 1.0
    ax.text(
        0.5, -0.20,
        f"정상 상위 1% 기준선을 이상연루 계좌의 {exceed_frac[p1_idx]:.1f}%가 초과 (정상 대비 {enrich_1pct:.1f}배 쏠림)",
        transform=ax.transAxes, ha="center", va="top", fontsize=8.8, color="#7a1f1f", fontweight="bold",
    )

    ax.set_xscale("log")
    ax.invert_xaxis()
    ax.set_xticks(_EXCEEDANCE_P)
    ax.set_xticklabels([f"{p:g}%" for p in _EXCEEDANCE_P], fontsize=8, rotation=45, ha="right")
    ax.set_xlabel("정상계좌 기준 상위 P% (오른쪽일수록 극단적)", fontsize=9.5)
    ax.set_ylabel("그 기준선을 넘는 이상연루 계좌 비율(%)", fontsize=9.5)
    ax.set_title(pf["label"], fontsize=13, fontweight="bold")
    ax.tick_params(axis="y", labelsize=9)
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(True, alpha=0.25)


def _render_bar(position: dict) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 6))
    for ax, col in zip(axes, _SIGNAL_COLS):
        _draw_exceedance_cell(ax, col, position["per_feature"][col])
    fig.suptitle("정상 대비 이상연루 계좌의 극단치 쏠림 — 평소엔 비슷해도 극단 구간일수록 이상연루 비중이 커진다", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return _fig_to_base64(fig)


def _render_distance(position: dict) -> str:
    s = _state
    fig, ax = plt.subplots(figsize=(8, 5))
    pop_max = float(max(np.percentile(s["dist_normal"], 99), np.percentile(s["dist_anomaly"], 99)))
    bins = np.linspace(0, pop_max, 60)
    ax.hist(s["dist_normal"], bins=bins, color=_COLOR_NORMAL, alpha=0.55, density=True, label="정상 계좌")
    ax.hist(s["dist_anomaly"], bins=bins, color=_COLOR_ANOMALY, alpha=0.55, density=True, label="이상거래 연루 계좌")
    ax.axvline(position["dist_normal_mean"], color=_COLOR_NORMAL, linestyle="--", linewidth=1.5)
    ax.axvline(position["dist_anomaly_mean"], color=_COLOR_ANOMALY, linestyle="--", linewidth=1.5)

    case_dist = position["dist_from_normal"]
    ax.set_xlim(0, pop_max)
    if case_dist <= pop_max:
        ax.axvline(case_dist, color=_COLOR_CASE, linestyle="-", linewidth=2.5, label="이 계좌")
    else:
        # 데모 CSV는 관측 기간이 며칠뿐이라 이 케이스 값이 정상 분포 범위(상위 1%)를 훨씬 벗어나는
        # 경우가 흔하다. 축을 늘려서 정상·이상연루 분포를 다 눌러버리는 대신, 오른쪽 끝에 화살표로
        # "범위 밖" 값이라는 걸 명시해 분포 모양과 케이스 값을 동시에 읽을 수 있게 한다.
        ymax = ax.get_ylim()[1]
        ax.axvspan(pop_max * 0.965, pop_max, color=_COLOR_CASE, alpha=0.18)
        ax.annotate(
            f"이 계좌: {case_dist:.1f}\n(그래프 범위 밖 · 정상군보다 매우 이례적)",
            xy=(pop_max, ymax * 0.5), xytext=(pop_max * 0.55, ymax * 0.85),
            fontsize=10, fontweight="bold", color="#8a5a12",
            arrowprops=dict(arrowstyle="->", color=_COLOR_CASE, linewidth=2),
            bbox=dict(boxstyle="round,pad=0.4", fc="#FFF3DC", ec=_COLOR_CASE),
        )
    ax.set_xlabel("정상 계좌군 중심으로부터의 거리 (4개 지표 표준화 공간, 상위 1% 범위로 확대)")
    ax.set_ylabel("밀도")
    ax.set_title(
        f"정상군 중심 기준 이탈 정도 — 이 계좌: {position['dist_from_normal']:.2f} "
        f"(정상 평균 {position['dist_normal_mean']:.2f} / 이상연루 평균 {position['dist_anomaly_mean']:.2f})",
        fontsize=11.5, fontweight="bold",
    )
    ax.legend(fontsize=9.5, loc="upper right" if case_dist <= pop_max else "center right")
    fig.tight_layout()
    return _fig_to_base64(fig)


def render_figures(position: dict) -> list[dict]:
    return [
        {"title": "극단치 쏠림 비교(초과비율)", "image_base64": _render_bar(position)},
        {"title": "정상군 중심 이탈 거리", "image_base64": _render_distance(position)},
    ]
