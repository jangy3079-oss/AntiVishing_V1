"""
account_features.csv(계좌 단위 피처)에 EKM을 실제로 적용해본다.
저희 실제 불균형 비율(필터링 후 약 30:1, 원본 기준 약 256:1)이 DCN_EKM_Project_Report.pdf가
찾은 붕괴 임계값(9:1)을 넘는지 직접 확인.
"""
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import normalized_mutual_info_score, adjusted_rand_score

from ekm import equilibrium_kmeans

feat = pd.read_pickle("/tmp/feat.pkl")
cols = ["immediate_withdrawal_ratio", "distinct_senders", "night_txn_ratio", "txn_frequency_per_day"]
y = feat["is_anomaly_account"].astype(int).values

n_anom = y.sum()
n_normal = len(y) - n_anom
print(f"계좌 수: {len(y)}  (이상연루 {n_anom} / 정상 {n_normal}, 비율 약 {n_normal/n_anom:.1f}:1)\n")

X_log = np.log1p(feat[cols].values)
Xs_log = StandardScaler().fit_transform(X_log)

X_raw = feat[cols].values
Xs_raw = StandardScaler().fit_transform(X_raw)


def evaluate(labels, y, collapsed, name):
    nmi = normalized_mutual_info_score(y, labels)
    ari = adjusted_rand_score(y, labels)
    sizes = pd.Series(labels).value_counts().to_dict()
    anomaly_rate_by_cluster = pd.Series(y).groupby(labels).mean().to_dict()
    print(f"{name}")
    print(f"  collapsed={collapsed}  cluster_sizes={sizes}")
    print(f"  NMI={nmi:.4f}  ARI={ari:.4f}")
    print(f"  cluster별 이상연루비율={ {c: round(v,4) for c,v in anomaly_rate_by_cluster.items()} }")
    print()


print("=" * 20, "log1p-scaled features", "=" * 20)
for scale in [2, 5, 10, 20, 50]:
    labels, centroids, alpha, collapsed = equilibrium_kmeans(Xs_log, k=2, scale=scale, seed=42)
    evaluate(labels, y, collapsed, f"EKM scale={scale} (alpha={alpha:.4f})")

print("=" * 20, "raw-scaled features (log1p 없이)", "=" * 20)
for scale in [2, 5, 10, 20, 50]:
    labels, centroids, alpha, collapsed = equilibrium_kmeans(Xs_raw, k=2, scale=scale, seed=42)
    evaluate(labels, y, collapsed, f"EKM scale={scale} (alpha={alpha:.4f})")

# 참고용: 같은 지표로 KMeans와 비교
from sklearn.cluster import KMeans
km = KMeans(n_clusters=2, random_state=42, n_init=10).fit(Xs_log)
evaluate(km.labels_, y, False, "참고: KMeans(k=2) on log1p-scaled (동일 지표)")
