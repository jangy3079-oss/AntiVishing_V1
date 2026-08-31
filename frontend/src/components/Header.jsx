export default function Header({ teller, showTagline = false, riskState = null }) {
  const isHigh = riskState === "high" || riskState === "golden";

  let right;
  if (riskState === "high") {
    right = <span style={{ color: "#fff", fontWeight: 700 }}>위험 높음 — 거래를 진행하지 마세요</span>;
  } else if (riskState === "golden") {
    right = <span style={{ color: "#fff", fontWeight: 700 }}>이미 송금됨 — 골든타임 진행 중</span>;
  } else {
    right = (
      <span className="who">
        {teller.branch} · {teller.name} ({teller.teller_id})
      </span>
    );
  }

  return (
    <div className={`app-header${isHigh ? " risk-high" : ""}`}>
      <div className="wordmark">
        ANTIVISHING_V1
        {showTagline && <span className="tagline">창구 이상거래 확인 보조</span>}
      </div>
      {right}
    </div>
  );
}
