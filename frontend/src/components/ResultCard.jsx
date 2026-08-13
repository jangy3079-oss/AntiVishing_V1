export default function ResultCard({ case: c }) {
  if (!c || !c.final_decision) return null;
  const isHigh = c.final_decision.risk_level === "high";

  return (
    <div className={`panel result-card ${isHigh ? "result-high" : "result-low"}`}>
      <div className="risk-badge">{isHigh ? "위험 높음" : "위험 낮음 · 완료"}</div>
      <p className="explanation">{c.final_decision.explanation}</p>
    </div>
  );
}
