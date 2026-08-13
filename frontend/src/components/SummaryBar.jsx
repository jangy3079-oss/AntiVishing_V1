const STATUS_LABEL = {
  TIER1_LOW_RISK_COMPLETED: "저위험 · 즉시 완료",
  TIER2_ESCALATED: "심층 조사 완료 · 확인 필요",
  AWAITING_YESNO: "확인 질문 대기",
  AWAITING_FREETEXT: "자유텍스트 대기",
  STT_HARD_BLOCKED: "통화 중 코칭 정황 감지 · 하드블록",
  FINAL_HIGH_RISK: "위험 높음",
  FINAL_LOW_RISK: "위험 낮음 · 완료",
  GOLDEN_TIME_FREEZE_REQUESTED: "골든타임 지급정지 요청됨",
};

export default function SummaryBar({ case: c, onReset }) {
  if (!c) return null;
  return (
    <div className="summary-bar">
      <div className="summary-info">
        <span className="summary-name">{c.customer_name}</span>
        <span className="summary-sep">·</span>
        <span>{c.recipient_label}</span>
        <span className="summary-sep">·</span>
        <span>{c.amount.toLocaleString()}원</span>
        {c.already_sent && <span className="badge-sent">이미 송금됨</span>}
      </div>
      <div className="summary-status">
        <span className="status-pill">{STATUS_LABEL[c.status] || c.status}</span>
        <button className="link-btn" onClick={onReset}>
          다른 시나리오 테스트
        </button>
      </div>
    </div>
  );
}
