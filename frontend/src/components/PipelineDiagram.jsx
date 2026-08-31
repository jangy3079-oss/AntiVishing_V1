// 기획서 4장의 "단계형 탐지·확인 파이프라인" 순서를 그대로 시각화한다:
// 거래 접수 → Tier1(경량 실시간 필터) → Tier2(자동 심층 조사) →
// 저마찰 확인 절차(STT 코칭감지 → Y/N → 자유텍스트 LLM 대조) → 최종 판정(XAI) → 에스컬레이션
// 상단 StepIndicator(거래접수/자동심사/확인/최종판정/조치)의 5단계보다 한 단계 더 세분화해서,
// 지금 이 케이스가 실제로 어느 단계를 거쳤는지/건너뛰었는지를 케이스 데이터로부터 그대로 계산한다.
export function computePipelineNodes(c) {
  const nodes = [
    { key: "intake", label: "거래접수", sub: "", state: "pending" },
    { key: "tier1", label: "Tier1", sub: "경량 실시간 필터", state: "pending" },
    { key: "tier2", label: "Tier2", sub: "상대계좌 심층조사", state: "pending" },
    { key: "stt", label: "STT", sub: "통화 코칭감지", state: "pending" },
    { key: "yn", label: "Y/N", sub: "저마찰 확인", state: "pending" },
    { key: "freetext", label: "자유텍스트", sub: "LLM 패턴대조", state: "pending" },
    { key: "final", label: "최종판정", sub: "XAI 설명", state: "pending" },
    { key: "escalation", label: "에스컬레이션", sub: "골든타임 등", state: "pending" },
  ];
  if (!c) return nodes;
  const byKey = Object.fromEntries(nodes.map((n) => [n.key, n]));

  byKey.intake.state = "done";
  byKey.tier1.state = "done";

  const escalated = c.status !== "TIER1_LOW_RISK_COMPLETED";
  if (!escalated) {
    byKey.tier2.state = "skipped";
    byKey.stt.state = "skipped";
    byKey.yn.state = "skipped";
    byKey.freetext.state = "skipped";
    byKey.final.state = "done";
    byKey.final.sub = "Tier1 즉시 종료";
    byKey.escalation.state = "skipped";
    return nodes;
  }
  byKey.tier2.state = "done";

  // STT는 선택 단계(next_action: stt_optional_or_yesno) — 값이 있으면 실제로 거친 것이고,
  // 아직 TIER2_ESCALATED 단계면 진행 중, 그 이후 상태인데도 없으면 생략하고 바로 Y/N으로 간 것.
  if (c.stt_result) {
    byKey.stt.state = "done";
    byKey.stt.sub = c.stt_result.coaching_detected ? "코칭 감지됨" : "정상 판단";
  } else if (c.status === "TIER2_ESCALATED") {
    byKey.stt.state = "active";
  } else {
    byKey.stt.state = "skipped";
  }

  const sttBlocked = Boolean(c.stt_result?.coaching_detected);

  if (sttBlocked) {
    byKey.yn.state = "skipped";
    byKey.freetext.state = "skipped";
  } else if (c.yesno_answers) {
    byKey.yn.state = "done";
    byKey.yn.sub = c.yesno_answers.clearly_normal ? "정상으로 확인" : "추가 확인 필요";
  } else if (c.status === "AWAITING_YESNO") {
    byKey.yn.state = "active";
  }

  const ynClearedNormal = Boolean(c.yesno_answers?.clearly_normal);
  if (sttBlocked || ynClearedNormal) {
    byKey.freetext.state = "skipped";
  } else if (c.freetext_analysis) {
    byKey.freetext.state = "done";
    byKey.freetext.sub = `위험도 ${c.freetext_analysis.risk_level}`;
  } else if (c.status === "AWAITING_FREETEXT") {
    byKey.freetext.state = "active";
  }

  if (c.final_decision) {
    byKey.final.state = "done";
    byKey.final.sub = c.final_decision.risk_level === "high" ? "고위험" : "저위험";
  }

  const isHighRisk = c.final_decision?.risk_level === "high";
  if (c.status === "GOLDEN_TIME_FREEZE_REQUESTED") {
    byKey.escalation.state = "done";
    byKey.escalation.sub = "골든타임 지급정지 요청";
  } else if (c.final_decision && !isHighRisk) {
    byKey.escalation.state = "skipped";
    byKey.escalation.sub = "저위험 · 해당없음";
  } else if (c.escalation_log?.length > 0) {
    byKey.escalation.state = "done";
  } else if (isHighRisk) {
    byKey.escalation.state = "active";
  }

  return nodes;
}

export default function PipelineDiagram({ case: c }) {
  const nodes = computePipelineNodes(c);
  return (
    <div className="pipeline-diagram">
      {nodes.map((n, i) => (
        <div className="pipeline-diagram-item" key={n.key}>
          <div className={`pipeline-node pipeline-node-${n.state}`}>
            <div className="pipeline-node-label">{n.label}</div>
            {n.sub && <div className="pipeline-node-sub">{n.sub}</div>}
          </div>
          {i < nodes.length - 1 && <div className="pipeline-arrow">›</div>}
        </div>
      ))}
    </div>
  );
}
