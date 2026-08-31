import { useEffect, useState } from "react";
import { api } from "../api";

// Tier2가 실행된 케이스에서만 의미가 있다. 수취계좌의 원본 입출금 내역을 그대로 표로 보여주고,
// "왜 의심스러운지"는 이미 tier2에서 계산해둔 reasons를 그대로 재사용한다(중복 계산/중복 설명
// 생성 없이, 위 TIER2 카드에 나오는 것과 동일한 근거를 표 옆에 다시 보여주는 것).
export default function TransactionHistory({ caseId, enabled, reasons }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!enabled || !caseId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getAccountTransactions(caseId)
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
    <div className="txn-history">
      <div className="account-figures-head">수취계좌 거래내역</div>

      {loading && <div className="hint2">거래내역을 불러오고 있습니다...</div>}

      {error && (
        <div className="error-banner">
          <div className="title">{error}</div>
        </div>
      )}

      {data && (
        <>
          {reasons?.length > 0 && (
            <div className="txn-history-reasons">
              {reasons.map((r, i) => (
                <div key={i}>· {r}</div>
              ))}
            </div>
          )}
          <table className="txn-history-table">
            <thead>
              <tr>
                <th>거래일시</th>
                <th>구분</th>
                <th>금액</th>
                <th>거래후잔액</th>
                <th>상대방</th>
              </tr>
            </thead>
            <tbody>
              {data.transactions.map((t, i) => (
                <tr key={i}>
                  <td>{t.datetime}</td>
                  <td className={t.type === "출금" ? "withdraw" : "deposit"}>{t.type}</td>
                  <td>{t.amount.toLocaleString()}원</td>
                  <td>{t.balance_after.toLocaleString()}원</td>
                  <td>{t.counterparty}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
