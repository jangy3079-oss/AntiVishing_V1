const HEADLINE = {
  stt_hard_block: "통화 내용에서 실시간 지시 정황이 확인되었습니다",
  freetext_high_risk: "진술 내용에서 보이스피싱 정황이 확인되었습니다",
  yesno_cleared: "추가 확인 없이 진행하세요",
  freetext_low_risk: "확인 결과 위험이 낮은 것으로 판정되었습니다",
  fallback_auto_signal: "종합 판단 결과입니다",
};

export default function ResultCard({ case: c }) {
  if (!c) return null;

  // Tier1에서 바로 저위험 종료된 케이스는 비용 절감을 위해 Claude를 호출하지 않아
  // final_decision이 없다 (backend 설계). tier1 데이터만으로 설명을 만든다.
  //
  // 주의: 이 상태로 끝나는 경로는 두 가지다 (tier1.py 참고).
  //   ① 등록된 신뢰 수취인(is_trusted_recipient)
  //   ② 신뢰 수취인은 아니지만(첫 거래), 금액이 확대 기준 미만이고 평소 최대 거래액 대비도 크게
  //      벗어나지 않아 애초에 확대 대상이 아니었던 경우
  // 예전에는 항상 ①번 문구("신뢰 수취인으로 확인되어...")를 고정으로 보여줘서, ②번 케이스(첫
  // 거래인데 소액이라 통과)에서도 마치 등록된 신뢰 수취인인 것처럼 잘못 설명하는 버그가 있었다.
  // tier1 데이터를 보고 실제로 어느 경로였는지에 따라 설명을 다르게 만든다.
  if (c.status === "TIER1_LOW_RISK_COMPLETED" && !c.final_decision) {
    const t1 = c.tier1 || {};
    const explanation = t1.is_trusted_recipient
      ? "이 수취계좌는 고객이 과거에 반복 송금한 등록 신뢰 수취인입니다. 상대 계좌 심층 조사 단계로 확대하지 않고 접수 즉시 종료했습니다. 고객에게 추가로 질문할 내용이 없습니다."
      : `이 수취계좌는 등록된 신뢰 수취인은 아니지만, 첫 거래 확대 기준 금액(${
          t1.is_elderly_customer ? "고령 금융소비자 기준 30만원" : "50만원"
        }) 미만이고 평소 최대 거래액 대비 ${t1.amount_ratio_vs_max ?? "?"}배로 크게 벗어나지 않아 상대 계좌 심층 조사 단계로 확대하지 않고 접수 즉시 종료했습니다. 고객에게 추가로 질문할 내용이 없습니다.`;

    return (
      <div className="result-card">
        <div className="result-badge">위험 낮음</div>
        <div className="result-headline">추가 확인 없이 진행하세요</div>
        <div className="result-explanation">{explanation}</div>
      </div>
    );
  }

  if (!c.final_decision) return null;
  const isHigh = c.final_decision.risk_level === "high";
  const headline =
    HEADLINE[c.final_decision.trigger] || (isHigh ? "위험이 높은 것으로 판정되었습니다" : "추가 확인 없이 진행하세요");

  return (
    <div className={`result-card${isHigh ? " high" : ""}`}>
      {!isHigh && <div className="result-badge">위험 낮음</div>}
      <div className="result-headline">{headline}</div>
      <div className="result-explanation">{c.final_decision.explanation}</div>
    </div>
  );
}
