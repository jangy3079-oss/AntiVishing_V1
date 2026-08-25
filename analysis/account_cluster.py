"""
AI-Hub '이상 판별을 위한 금융거래 정보 및 사용자 패턴 합성데이터' (전자금융공동망, Validation)를
계좌 단위로 집계해 저희 account_analysis.py와 동일한 4개 지표(즉시인출비율/분산입금수/심야비중/
일평균거래빈도)를 실측으로 계산하고, 비지도 클러스터링으로 정상 vs 이상신호 누적 계좌군이
분리되는지 검증한다.

주의: 이 데이터셋은 "보이스피싱" 라벨이 아니라 "이상거래유형"(패턴 이상) 라벨만 갖고 있음.
      거래시간대는 시(hour) 단위 버킷만 있어 즉시인출비율은 '입금 당일~익일 인출' 근사치로 계산.
"""
import glob
import os

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, HDBSCAN
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = "/tmp/extract/val_efm"
OUT_DIR = os.path.dirname(__file__)
NIGHT_HOURS = set([23, 0, 1, 2, 3, 4, 5])
MIN_TXN = 3  # 패턴을 볼 수 있는 최소 거래 수


def load_raw():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")))
    dfs = [pd.read_csv(f, encoding="utf-8-sig") for f in files]
    df = pd.concat(dfs, ignore_index=True)
    df["거래일자"] = pd.to_datetime(df["거래일자"], format="%Y%m%d")
    return df


def build_account_features(df: pd.DataFrame) -> pd.DataFrame:
    inflow = df.rename(columns={"입금계좌일련번호": "account", "출금계좌일련번호": "counterparty"})
    outflow = df.rename(columns={"출금계좌일련번호": "account", "입금계좌일련번호": "counterparty"})

    # --- 즉시인출비율: 입금 당일~익일 그 계좌에서 나간 출금 총액 비율(금액가중평균) ---
    out_by_date = (
        outflow.groupby(["account", "거래일자"])["거래금액"].sum().rename("outflow_amt")
    )
    inflow2 = inflow.copy()
    inflow2["next_date"] = inflow2["거래일자"] + pd.Timedelta(days=1)
    inflow2 = inflow2.merge(
        out_by_date, left_on=["account", "거래일자"], right_index=True, how="left"
    ).rename(columns={"outflow_amt": "outflow_same"})
    inflow2 = inflow2.merge(
        out_by_date, left_on=["account", "next_date"], right_index=True, how="left"
    ).rename(columns={"outflow_amt": "outflow_next"})
    inflow2[["outflow_same", "outflow_next"]] = inflow2[["outflow_same", "outflow_next"]].fillna(0)
    inflow2["withdrawn"] = inflow2["outflow_same"] + inflow2["outflow_next"]
    inflow2["ratio"] = (inflow2["withdrawn"] / inflow2["거래금액"]).clip(upper=1.0)

    def weighted_ratio(g):
        w = g["거래금액"].sum()
        return (g["ratio"] * g["거래금액"]).sum() / w if w else 0.0

    immediate_withdrawal_ratio = inflow2.groupby("account").apply(weighted_ratio, include_groups=False)
    immediate_withdrawal_ratio.name = "immediate_withdrawal_ratio"

    # --- 분산입금 건수: 계좌가 관측된 전체 기간 동안 서로 다른 입금 상대방 수 ---
    distinct_senders = inflow.groupby("account")["counterparty"].nunique().rename("distinct_senders")

    # --- 심야거래비중 / 일평균거래빈도: 입출금 모두 포함 ---
    events = pd.concat(
        [inflow[["account", "거래시간대", "거래일자"]], outflow[["account", "거래시간대", "거래일자"]]],
        ignore_index=True,
    )
    txn_count = events.groupby("account").size().rename("txn_count")
    night_ratio = (
        events.assign(is_night=events["거래시간대"].isin(NIGHT_HOURS))
        .groupby("account")["is_night"]
        .mean()
        .rename("night_txn_ratio")
    )
    span = events.groupby("account")["거래일자"].agg(lambda s: max((s.max() - s.min()).days, 1))
    txn_freq = (txn_count / span).rename("txn_frequency_per_day")

    # --- 이상거래 연루 여부(평가용 참고 라벨, 클러스터링 입력에는 사용하지 않음) ---
    anomaly_rows = df[df["이상거래여부"] == 1]
    anomaly_accounts = set(anomaly_rows["입금계좌일련번호"]) | set(anomaly_rows["출금계좌일련번호"])

    feat = pd.concat([txn_count, distinct_senders, night_ratio, txn_freq, immediate_withdrawal_ratio], axis=1)
    feat["distinct_senders"] = feat["distinct_senders"].fillna(0)
    feat["immediate_withdrawal_ratio"] = feat["immediate_withdrawal_ratio"].fillna(0)
    feat["is_anomaly_account"] = feat.index.isin(anomaly_accounts)
    feat = feat[feat["txn_count"] >= MIN_TXN].copy()
    return feat


def cluster_and_report(feat: pd.DataFrame):
    cols = ["immediate_withdrawal_ratio", "distinct_senders", "night_txn_ratio", "txn_frequency_per_day"]
    X = feat[cols].values
    Xs = StandardScaler().fit_transform(X)

    print(f"\n분석 대상 계좌 수(거래 {MIN_TXN}건 이상): {len(feat)}")
    print(f"  - 이상거래 연루 계좌: {feat['is_anomaly_account'].sum()}건")
    print(f"  - 정상 계좌: {(~feat['is_anomaly_account']).sum()}건")

    print("\n=== 정상 계좌군 실측 평균/표준편차 (account_analysis.py _NORMAL_BASELINE 검증용) ===")
    normal = feat[~feat["is_anomaly_account"]]
    for c in cols:
        print(f"  {c}: mean={normal[c].mean():.3f}  std={normal[c].std():.3f}")

    print("\n=== 이상거래 연루 계좌군 평균/표준편차 ===")
    anomalous = feat[feat["is_anomaly_account"]]
    for c in cols:
        print(f"  {c}: mean={anomalous[c].mean():.3f}  std={anomalous[c].std():.3f}")

    def report_clusters(labels, name):
        f2 = feat.copy()
        f2["cluster"] = labels
        print(f"\n--- {name} ---")
        ct = f2.groupby("cluster")["is_anomaly_account"].agg(["mean", "count"])
        ct.columns = ["이상연루비율", "계좌수"]
        print(ct.to_string())
        return f2

    # (1) 기존 방식: 원값 그대로 StandardScaler + KMeans  → 불균형 데이터에서 큰 값(극단치)에
    #     쏠려 소수 이상군집을 못 찾는 전형적 실패 사례를 그대로 보여주기 위해 남겨둠.
    print("\n########## (1) 원값 StandardScaler + KMeans (베이스라인, 불균형에 취약) ##########")
    best_k, best_score = None, -1
    for k in [2, 3, 4, 5]:
        km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(Xs)
        score = silhouette_score(Xs, km.labels_)
        print(f"k={k} silhouette={score:.3f}")
        if score > best_score:
            best_k, best_score = k, score
    km = KMeans(n_clusters=best_k, random_state=42, n_init=10).fit(Xs)
    feat["cluster"] = km.labels_
    report_clusters(km.labels_, f"KMeans(k={best_k}) on raw-scaled features")

    # (2) log1p 변환으로 오른쪽 꼬리(극단치) 완화 후 KMeans
    print("\n########## (2) log1p 변환 + StandardScaler + KMeans (불균형 완화 시도) ##########")
    X_log = np.log1p(feat[cols].values)
    Xs_log = StandardScaler().fit_transform(X_log)
    best_k2, best_score2 = None, -1
    for k in [2, 3, 4, 5]:
        km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(Xs_log)
        score = silhouette_score(Xs_log, km.labels_)
        print(f"k={k} silhouette={score:.3f}")
        if score > best_score2:
            best_k2, best_score2 = k, score
    km_log = KMeans(n_clusters=best_k2, random_state=42, n_init=10).fit(Xs_log)
    feat_log = report_clusters(km_log.labels_, f"KMeans(k={best_k2}) on log1p-scaled features")

    # (3) HDBSCAN: 군집 크기를 가정하지 않는 밀도기반 클러스터링 (EKM과 같은 문제의식,
    #     scikit-learn에 바로 있는 실용적 대안). 참고: 동일 데이터에 DBSCAN(고정 eps)을
    #     시도했더니 밀집 영역에서 이웃탐색이 폭발해 메모리 초과로 죽었고, eps를 자동으로
    #     적응시키는 HDBSCAN으로 교체하니 문제없이 동작함.
    print("\n########## (3) HDBSCAN on log1p-scaled features (밀도기반, 크기 불균형 가정 없음) ##########")
    hdb = HDBSCAN(min_cluster_size=300, min_samples=20).fit(Xs_log)
    n_clusters = len(set(hdb.labels_)) - (1 if -1 in hdb.labels_ else 0)
    print(f"발견된 군집 수: {n_clusters} (군집 -1 = 노이즈/저밀도 이상치)")
    feat_db = report_clusters(hdb.labels_, "HDBSCAN")

    print("\n=== (1) 클러스터별 특징 평균 ===")
    print(feat.groupby("cluster")[cols].mean().to_string())
    print("\n=== (2) 클러스터별 특징 평균 (log1p) ===")
    print(feat_log.groupby("cluster")[cols].mean().to_string())
    print("\n=== (3) 클러스터별 특징 평균 (HDBSCAN) ===")
    print(feat_db.groupby("cluster")[cols].mean().to_string())

    # PCA 2D 시각화
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(Xs)
    feat["pc1"], feat["pc2"] = coords[:, 0], coords[:, 1]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    for c in sorted(feat["cluster"].unique()):
        sub = feat[feat["cluster"] == c]
        axes[0].scatter(sub["pc1"], sub["pc2"], s=8, alpha=0.5, label=f"cluster {c}")
    axes[0].set_title(f"KMeans 클러스터 (k={best_k})")
    axes[0].legend(markerscale=2)

    normal_pts = feat[~feat["is_anomaly_account"]]
    anomaly_pts = feat[feat["is_anomaly_account"]]
    axes[1].scatter(normal_pts["pc1"], normal_pts["pc2"], s=8, alpha=0.35, color="#4c72b0", label="정상 계좌")
    axes[1].scatter(anomaly_pts["pc1"], anomaly_pts["pc2"], s=14, alpha=0.8, color="#c0392b", label="이상거래 연루 계좌")
    axes[1].set_title("실제 라벨(이상거래 연루 여부)")
    axes[1].legend(markerscale=2)

    fig.suptitle("계좌 단위 집계 피처 기반 클러스터링 vs 실제 이상거래 라벨 (PCA 2D)")
    fig.tight_layout()
    out_png = os.path.join(OUT_DIR, "account_cluster_pca.png")
    fig.savefig(out_png, dpi=150)
    print(f"\n그림 저장: {out_png}")

    feat.to_csv(os.path.join(OUT_DIR, "account_features.csv"), encoding="utf-8-sig")
    print(f"피처 테이블 저장: {os.path.join(OUT_DIR, 'account_features.csv')}")

    return feat


if __name__ == "__main__":
    df = load_raw()
    feat = build_account_features(df)
    cluster_and_report(feat)
