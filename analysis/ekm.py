"""
Equilibrium K-Means (EKM) — DCN_EKM_Project_Report.pdf 3장 수식을 그대로 구현.

W = U · (1 − α(D² − Σ D²·U))
- U: 점 i가 각 centroid k에 대해 갖는 Boltzmann-style membership (softmax(-α D²))
- D̄²_i = Σ_k U_ik D²_ik  (점 i의 membership 가중 평균 거리)
- W_ik = U_ik (1 − α(D²_ik − D̄²_i))  → centroid보다 먼 점은 음수 가중치로 그 centroid를 밀어냄

α = scale / (전체 점들의 global mean까지의 평균제곱거리)  (리포트 3장, "scale"만 사용자가 고름)
"""
import numpy as np


def _pairwise_sq_dists(X, centroids):
    # (n, k)
    return ((X[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)


def equilibrium_kmeans(X, k, scale=10.0, max_iter=100, tol=1e-5, seed=42, verbose=False):
    rng = np.random.default_rng(seed)
    n, d = X.shape

    # alpha: 리포트 설명대로 scale을 데이터 자체의 분산으로 나눠 무차원화
    global_mean = X.mean(axis=0)
    mean_sq_dist_to_mean = ((X - global_mean) ** 2).sum(axis=1).mean()
    alpha = scale / mean_sq_dist_to_mean

    # 초기화: K-means++ 스타일로 흩어진 초기 centroid 선택
    idx0 = rng.integers(n)
    centroids = [X[idx0]]
    for _ in range(k - 1):
        d2 = np.min(_pairwise_sq_dists(X, np.array(centroids)), axis=1)
        probs = d2 / d2.sum() if d2.sum() > 0 else np.ones(n) / n
        centroids.append(X[rng.choice(n, p=probs)])
    centroids = np.array(centroids)

    collapsed = False
    for it in range(max_iter):
        D2 = _pairwise_sq_dists(X, centroids)  # (n, k)
        # Boltzmann membership (softmax(-alpha*D2)), 오버플로 방지를 위해 안정화
        logits = -alpha * D2
        logits -= logits.max(axis=1, keepdims=True)
        U = np.exp(logits)
        U /= U.sum(axis=1, keepdims=True)

        D_bar = (U * D2).sum(axis=1, keepdims=True)  # (n,1)
        W = U * (1 - alpha * (D2 - D_bar))  # (n,k), 음수 가능

        denom = W.sum(axis=0)  # (k,)
        new_centroids = centroids.copy()
        for j in range(k):
            if abs(denom[j]) < 1e-8:
                continue  # 이 centroid는 이번 반복에서 갱신 skip (0분모 방지)
            new_centroids[j] = (W[:, j:j + 1] * X).sum(axis=0) / denom[j]

        shift = np.linalg.norm(new_centroids - centroids)
        centroids = new_centroids
        if verbose:
            print(f"  iter {it}: shift={shift:.6f}")
        if shift < tol:
            break

    D2 = _pairwise_sq_dists(X, centroids)
    labels = np.argmin(D2, axis=1)
    n_used_clusters = len(set(labels.tolist()))
    if n_used_clusters < k:
        collapsed = True

    return labels, centroids, alpha, collapsed
