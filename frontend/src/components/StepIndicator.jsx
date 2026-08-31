const STEP_DEFS = [
  { key: "intake", label: "거래접수" },
  { key: "auto", label: "자동심사" },
  { key: "verify", label: "확인" },
  { key: "final", label: "최종판정" },
  { key: "action", label: "조치" },
];

export function computeSteps(c) {
  const steps = STEP_DEFS.map((s) => ({ ...s, state: "pending" }));

  if (!c) {
    steps[0].state = "active";
    return steps;
  }

  steps[0].state = "done";
  steps[1].state = "done";

  if (c.status === "TIER1_LOW_RISK_COMPLETED") {
    steps[2].state = "skipped";
    steps[2].label = "확인 · 건너뜀";
    steps[3].state = "done";
    steps[4].state = "skipped";
    steps[4].label = "조치 · 건너뜀";
    return steps;
  }

  if (["TIER2_ESCALATED", "AWAITING_YESNO", "AWAITING_FREETEXT"].includes(c.status)) {
    steps[2].state = "active";
    return steps;
  }

  if (c.status === "STT_HARD_BLOCKED") {
    steps[2].state = "done";
    steps[2].label = "확인 · 음성에서 종료";
    steps[3].state = "done";
    steps[4].state = c.next_action === "high_risk_actions" ? "active" : "done";
    return steps;
  }

  if (c.status === "FINAL_HIGH_RISK") {
    steps[2].state = "done";
    steps[3].state = "done";
    steps[4].state = "active";
    return steps;
  }

  if (c.status === "FINAL_LOW_RISK") {
    steps[2].state = "done";
    steps[3].state = "done";
    steps[4].state = "skipped";
    steps[4].label = "조치 · 건너뜀";
    return steps;
  }

  if (c.status === "GOLDEN_TIME_FREEZE_REQUESTED") {
    steps[2].state = "done";
    steps[3].state = "done";
    steps[4].state = "done";
    return steps;
  }

  return steps;
}

export default function StepIndicator({ case: c }) {
  const steps = computeSteps(c);
  return (
    <div className="steps">
      {steps.map((s) => (
        <div key={s.key} className={`step step-${s.state}`}>
          <div className="step-dot" />
          <div className="step-label">{s.label}</div>
        </div>
      ))}
    </div>
  );
}
