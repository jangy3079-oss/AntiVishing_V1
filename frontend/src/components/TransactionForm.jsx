import { useEffect, useState } from "react";
import { api } from "../api";

export default function TransactionForm({ onCaseCreated }) {
  const [scenarios, setScenarios] = useState([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.listScenarios().then(setScenarios).catch((e) => setError(e.message));
  }, []);

  const start = async () => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      const created = await api.createCaseFromScenario(selected);
      onCaseCreated(created);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const current = scenarios.find((s) => s.id === selected);

  return (
    <div className="panel">
      <h2>거래 접수</h2>
      <p className="hint">고정 시나리오 중 하나를 골라 창구 거래를 접수합니다.</p>
      <select value={selected} onChange={(e) => setSelected(e.target.value)}>
        <option value="">-- 시나리오 선택 --</option>
        {scenarios.map((s) => (
          <option key={s.id} value={s.id}>
            {s.title}
          </option>
        ))}
      </select>

      {current && (
        <div className="scenario-detail">
          <div>금액: {current.amount.toLocaleString()}원</div>
          <div>기 송금 여부: {current.already_sent ? "이미 송금됨" : "송금 전"}</div>
          <div>예상 흐름: {current.expected}</div>
          {current.sample_stt_transcript && (
            <div className="sample">STT 예시: “{current.sample_stt_transcript}”</div>
          )}
          {current.sample_freetext && (
            <div className="sample">자유텍스트 예시: “{current.sample_freetext}”</div>
          )}
        </div>
      )}

      <button disabled={!selected || loading} onClick={start}>
        {loading ? "접수 중..." : "거래 접수"}
      </button>
      {error && <div className="error">{error}</div>}
    </div>
  );
}
