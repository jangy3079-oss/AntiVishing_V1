"""
정상 계좌군 vs 이상거래 연루 계좌군 비교 시각화 (발표/보고서용).
account_features.csv(AI-Hub 전자금융공동망 실측 데이터 기반, 계좌 단위 집계)를 사용.

생성 파일:
- fig1_feature_ratio_bar.png   : 지표별 평균 비교 + 배율(×N.N)
- fig2_feature_boxplot.png     : 지표별 분포 비교(박스플롯, 로그축)
- fig3_pca_distance.png        : PCA 2D 평면에 투영 후 두 군집 중심 간 거리 표시
- fig4_distance_from_normal.png: 정상군 중심으로부터의 거리 분포 (표준화 4차원 공간, z-score 근거)
"""
import os
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.lines import Line2D
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

# "Noto Sans CJK JP" 이름만 지정하면 이 폰트가 없는 환경에서 한글이 네모(tofu)로 깨진다
# (backend/app/pipeline/account_figures.py에서 실제로 발생 확인). 같은 번들 폰트를 사용해
# 어떤 환경에서 실행하든 항상 한글이 정상 렌더링되게 한다.
_KOREAN_FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "app", "assets", "fonts", "NanumGothic-Regular.ttf")
if os.path.exists(_KOREAN_FONT_PATH):
    fm.fontManager.addfont(_KOREAN_FONT_PATH)
    plt.rcParams["font.family"] = fm.FontProperties(fname=_KOREAN_FONT_PATH).get_name()
else:
    plt.rcParams["font.family"] = "Noto Sans CJK JP"
plt.rcParams["axes.unicode_minus"] = False

OUT_DIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT_DIR, exist_ok=True)

COLOR_NORMAL = "#4C72B0"
COLOR_ANOMALY = "#C0392B"

cols = ["immediate_withdrawal_ratio", "distinct_senders", "night_txn_ratio", "txn_frequency_per_day"]
LABELS = {
    "immediate_withdrawal_ratio": "즉시인출비율",
    "distinct_senders": "분산입금 상대방 수",
    "night_txn_ratio": "심야거래 비중",
    "txn_frequency_per_day": "일평균 거래빈도",
}

feat = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "account_features.csv"), index_col=0
)
feat["is_anomaly_account"] = feat["is_anomaly_account"].astype(bool)

normal = feat[~feat["is_anomaly_account"]]
anomaly = feat[feat["is_anomaly_account"]]
print(f"정상 계좌 {len(normal)}건 / 이상거래 연루 계좌 {len(anomaly)}건")

# ---------------------------------------------------------------
# Fig 1. 지표별 평균 비교 + 배율
# ---------------------------------------------------------------
fig, axes = plt.subplots(1, 4, figsize=(16, 4.2))
for ax, c in zip(axes, cols):
    m_normal, m_anomaly = normal[c].mean(), anomaly[c].mean()
    se_normal = normal[c].std() / np.sqrt(len(normal))
    se_anomaly = anomaly[c].std() / np.sqrt(len(anomaly))
    bars = ax.bar(
        ["정상", "이상연루"],
        [m_normal, m_anomaly],
        yerr=[se_normal, se_anomaly],
        color=[COLOR_NORMAL, COLOR_ANOMALY],
        capsize=5,
        width=0.55,
    )
    ratio = m_anomaly / m_normal if m_normal > 0 else float("nan")
    ax.set_title(LABELS[c], fontsize=12, fontweight="bold")
    # 두 평균이 모두 0에 가까운 지표(즉시인출비율)는 배율이 노이즈에 크게 좌우되므로
    # 강조 표시 대신 데이터 한계를 명시한다 (거짓으로 강한 신호처럼 보이는 것 방지).
    unreliable = m_normal < 0.01 and m_anomaly < 0.01
    if unreliable:
        ax.text(
            0.5, 0.95, "값이 0에 가까워\n배율 해석 주의\n(데이터 한계)", transform=ax.transAxes,
            ha="center", va="top", fontsize=9.5, color="#888", fontstyle="italic",
        )
    else:
        ax.text(
            0.5, 0.95, f"×{ratio:.1f}", transform=ax.transAxes,
            ha="center", va="top", fontsize=13, color="#8a2b2b", fontweight="bold",
        )
    for b, v in zip(bars, [m_normal, m_anomaly]):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.3f}", ha="center", va="bottom", fontsize=9)
fig.suptitle("정상 계좌 vs 이상거래 연루 계좌 — 지표별 평균 비교 (오차막대: 표준오차)", fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig(os.path.join(OUT_DIR, "fig1_feature_ratio_bar.png"), dpi=180)
plt.close(fig)

# ---------------------------------------------------------------
# Fig 2. 지표별 분포 비교 (박스플롯)
# ---------------------------------------------------------------
fig, axes = plt.subplots(1, 4, figsize=(16, 4.5))
for ax, c in zip(axes, cols):
    data = [normal[c].values, anomaly[c].values]
    bp = ax.boxplot(
        data, labels=["정상", "이상연루"], patch_artist=True, showfliers=True,
        flierprops=dict(marker="o", markersize=2, alpha=0.3),
    )
    for patch, color in zip(bp["boxes"], [COLOR_NORMAL, COLOR_ANOMALY]):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_title(LABELS[c], fontsize=12, fontweight="bold")
    if c in ("distinct_senders", "txn_frequency_per_day"):
        ax.set_yscale("symlog")
fig.suptitle("정상 계좌 vs 이상거래 연루 계좌 — 지표별 분포 비교 (박스플롯)", fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig(os.path.join(OUT_DIR, "fig2_feature_boxplot.png"), dpi=180)
plt.close(fig)

# ---------------------------------------------------------------
# Fig 3. PCA 2D 평면 + 두 집단 중심 간 거리
# ---------------------------------------------------------------
X = feat[cols].values
Xs = StandardScaler().fit_transform(np.log1p(X))
pca = PCA(n_components=2, random_state=42)
coords = pca.fit_transform(Xs)
feat["pc1"], feat["pc2"] = coords[:, 0], coords[:, 1]

normal2 = feat[~feat["is_anomaly_account"]]
anomaly2 = feat[feat["is_anomaly_account"]]

# 평균 중심은 소수의 극단치(예: PC1=40 근방 이상치)에 크게 흔들리므로,
# 중앙값 기반 중심을 주 지표로 쓰고 평균 기반은 참고용으로만 표기.
c_normal_med = normal2[["pc1", "pc2"]].median().values
c_anomaly_med = anomaly2[["pc1", "pc2"]].median().values
dist_med = np.linalg.norm(c_normal_med - c_anomaly_med)
c_normal_mean = normal2[["pc1", "pc2"]].mean().values
c_anomaly_mean = anomaly2[["pc1", "pc2"]].mean().values
dist_mean = np.linalg.norm(c_normal_mean - c_anomaly_mean)

# 밀집 구간 확대 범위 (전체 포인트의 1~97 백분위 기준)
all_pc1 = feat["pc1"].values
all_pc2 = feat["pc2"].values
xlim_zoom = (np.percentile(all_pc1, 0.5), np.percentile(all_pc1, 96))
ylim_zoom = (np.percentile(all_pc2, 0.5), np.percentile(all_pc2, 96))

fig, axes = plt.subplots(1, 2, figsize=(15, 7))

for ax, zoomed in zip(axes, [False, True]):
    ax.scatter(normal2["pc1"], normal2["pc2"], s=6, alpha=0.25, color=COLOR_NORMAL, label=f"정상 계좌 (n={len(normal2)})")
    ax.scatter(anomaly2["pc1"], anomaly2["pc2"], s=14, alpha=0.7, color=COLOR_ANOMALY, label=f"이상거래 연루 계좌 (n={len(anomaly2)})")
    ax.scatter(*c_normal_med, s=280, marker="X", color="#1f2d50", edgecolor="white", linewidth=1.5, zorder=5, label="정상군 중심(중앙값)")
    ax.scatter(*c_anomaly_med, s=280, marker="X", color="#5c0a0a", edgecolor="white", linewidth=1.5, zorder=5, label="이상연루군 중심(중앙값)")
    ax.plot([c_normal_med[0], c_anomaly_med[0]], [c_normal_med[1], c_anomaly_med[1]], "k--", linewidth=1.5, zorder=4)
    if zoomed:
        ax.set_xlim(*xlim_zoom)
        ax.set_ylim(*ylim_zoom)
        ax.set_title("밀집 구간 확대", fontsize=12, fontweight="bold")
        mid = (c_normal_med + c_anomaly_med) / 2
        ax.annotate(
            f"두 중심 간 거리(중앙값 기준) = {dist_med:.2f}", xy=mid, xytext=(10, 20), textcoords="offset points",
            ha="left", fontsize=11.5, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#888", alpha=0.95),
            arrowprops=dict(arrowstyle="->", color="#444"),
        )
        ax.legend(loc="upper left", fontsize=8.5, framealpha=0.9)
    else:
        ax.set_title(f"전체 범위 (극단치 포함, 참고용 평균 중심 거리 = {dist_mean:.2f})", fontsize=12, fontweight="bold")
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}% 분산 설명)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.1f}% 분산 설명)")

fig.suptitle("계좌 특징 4개 지표를 PCA 2D 평면에 투영 — 정상군 vs 이상연루군 중심 거리", fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(os.path.join(OUT_DIR, "fig3_pca_distance.png"), dpi=180)
plt.close(fig)

# ---------------------------------------------------------------
# Fig 4. 정상군 중심으로부터의 거리 분포 (표준화 4차원 공간, z-score 근거 시각화)
# ---------------------------------------------------------------
normal_mask = ~feat["is_anomaly_account"].values
centroid_4d = Xs[normal_mask].mean(axis=0)
dist_4d = np.linalg.norm(Xs - centroid_4d, axis=1)
feat["dist_from_normal_centroid"] = dist_4d

fig, ax = plt.subplots(figsize=(8.5, 5))
bins = np.linspace(0, np.percentile(dist_4d, 99), 60)
ax.hist(dist_4d[normal_mask], bins=bins, color=COLOR_NORMAL, alpha=0.55, density=True, label="정상 계좌")
ax.hist(dist_4d[~normal_mask], bins=bins, color=COLOR_ANOMALY, alpha=0.55, density=True, label="이상거래 연루 계좌")
ax.axvline(dist_4d[normal_mask].mean(), color=COLOR_NORMAL, linestyle="--", linewidth=1.5)
ax.axvline(dist_4d[~normal_mask].mean(), color=COLOR_ANOMALY, linestyle="--", linewidth=1.5)
ax.set_xlabel("정상 계좌군 중심으로부터의 거리 (4개 지표 표준화 공간, 유클리드 거리)")
ax.set_ylabel("밀도")
ax.set_title(
    f"정상군 중심 기준 이탈 정도 비교\n"
    f"평균 거리 — 정상: {dist_4d[normal_mask].mean():.2f} / 이상연루: {dist_4d[~normal_mask].mean():.2f} "
    f"(×{dist_4d[~normal_mask].mean()/dist_4d[normal_mask].mean():.1f})",
    fontsize=12, fontweight="bold",
)
ax.legend(fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "fig4_distance_from_normal.png"), dpi=180)
plt.close(fig)

print("\n모든 figure 저장 완료:", OUT_DIR)
for f in sorted(os.listdir(OUT_DIR)):
    print(" -", f)
