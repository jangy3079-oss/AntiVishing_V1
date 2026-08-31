const STATUS_META = {
  TIER1_LOW_RISK_COMPLETED: { text: "위험 낮음 · 완료", cls: "low" },
  TIER2_ESCALATED: { text: "확인 절차 진행 중", cls: "" },
  AWAITING_YESNO: { text: "확인 절차 진행 중", cls: "" },
  AWAITING_FREETEXT: { text: "확인 절차 진행 중", cls: "" },
  STT_HARD_BLOCKED: { text: "위험 높음", cls: "high" },
  FINAL_HIGH_RISK: { text: "위험 높음", cls: "high" },
  FINAL_LOW_RISK: { text: "위험 낮음 · 완료", cls: "low" },
  GOLDEN_TIME_FREEZE_REQUESTED: { text: "이미 송금됨", cls: "sent" },
};

export default function SummaryBar({ case: c, customerAge, customerGender, onReset }) {
  if (!c) return null;

  let meta = STATUS_META[c.status] || { text: c.status, cls: "" };
  if (c.status === "AWAITING_FREETEXT") {
    meta = { text: `질문 ${c.freetext_round || 1} / 3`, cls: "", mono: true };
  }
  const elderly = Boolean(c.tier1?.is_elderly_customer);
  const trusted = Boolean(c.tier1?.is_trusted_recipient);

  return (
    <div className="summary-bar">
      <div className="summary-item">
        <div className="k">고객</div>
        <div className="v">
          <span>
            {c.customer_name}
            {customerAge ? ` · ${customerAge}세` : ""}
            {customerGender && !customerAge ? ` · ${customerGender}` : ""}
          </span>
          {elderly && <span className="badge-elderly">고령 보호</span>}
        </div>
      </div>
      <div className="summary-divider" />
      <div className="summary-item">
        <div className="k">수취인</div>
        <div className="v">
          {trusted ? `${c.recipient_label} · ` : ""}
          {c.recipient_bank} {c.recipient_account_number}
        </div>
      </div>
      <div className="summary-divider" />
      <div className="summary-item">
        <div className="k">금액</div>
        <div className="v mono">{c.amount.toLocaleString()}원</div>
      </div>
      <div className="summary-right">
        <div className={`status-pill ${meta.cls}`} style={meta.mono ? { fontFamily: "var(--font-mono)" } : undefined}>
          {meta.text}
        </div>
        <button className="btn-reset" onClick={onReset}>
          새 거래 접수
        </button>
      </div>
    </div>
  );
}
