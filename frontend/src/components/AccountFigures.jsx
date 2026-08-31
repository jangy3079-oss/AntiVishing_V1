import { useEffect, useState } from "react";
import { api } from "../api";

// Tier2가 실행된 케이스에서만 의미가 있다 (수취계좌 CSV를 분석한 결과가 있어야 함).
// AI-Hub 실측 데이터로 만든 정상/이상거래연루 계좌 모집단 대비, 이번 케이스 수취계좌가
// 어디에 위치하는지 그래프 2장 + LLM 설명을 보여준다. "자세히 보기"가 열릴 때 1회만 불러오고,
// 백엔드가 케이스에 결과를 캐시하므로 다시 열어도 재계산하지 않는다.
export default function AccountFigures({ caseId, enabled }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!enabled || !caseId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getAccountFigures(caseId)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, enabled]);

  if (!enabled) return null;

  return (
    <div className="account-figures">
      <div className="account-figures-head">수취계좌 위치 분석 (AI-Hub 실측 데이터 기준)</div>

      {loading && <div className="hint2">계좌 위치를 계산하고 있습니다 (그래프 생성 + AI 설명, 몇 초 걸릴 수 있어요)...</div>}

      {error && (
        <div className="error-banner">
          <div className="title">{error}</div>
        </div>
      )}

      {data && (
        <>
          <div className="account-figures-grid">
            {data.figures.map((f) => (
              <div className="account-figure-card" key={f.title}>
                <div className="account-figure-title">{f.title}</div>
                <img src={`data:image/png;base64,${f.image_base64}`} alt={f.title} />
              </div>
            ))}
          </div>
          <div className="account-figures-explanation">{data.explanation}</div>
        </>
      )}
    </div>
  );
}
