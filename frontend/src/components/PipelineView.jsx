export default function PipelineView({ case: c }) {
  if (!c) return null;
  const hasDetail = c.tier1 || c.tier2 || c.stt_result || c.yesno_answers || c.freetext_analysis;
  if (!hasDetail) return null;

  return (
    <details className="detail-panel">
      <summary>자세히 보기 (단계별 원시 데이터)</summary>

      <Stage title="Tier 1 · 경량 실시간 필터" data={c.tier1}>
        {c.tier1 && (
          <>
            <div>Tier2 확대 여부: {c.tier1.escalate_to_tier2 ? "예" : "아니오"}</div>
            {c.tier1.reasons.map((r, i) => (
              <div key={i} className="reason">
                - {r}
              </div>
            ))}
          </>
        )}
      </Stage>

      {c.tier2 && (
        <Stage title="Tier 2 · 심층 조사 (상대 계좌 입출금 내역 분석, 자동)" data={c.tier2}>
          <div>상대 계좌: {c.tier2.recipient_label} ({c.tier2.account_number})</div>
          <div>자동 의심 스코어: {c.tier2.auto_suspicion_score}/100</div>
          {c.tier2.account_features && (
            <div className="reason">
              즉시인출비율 {Math.round(c.tier2.account_features.immediate_withdrawal_ratio * 100)}% ·
              최근 72h 입금상대 {c.tier2.account_features.distinct_senders_72h}명 ·
              심야거래비중 {Math.round(c.tier2.account_features.night_txn_ratio * 100)}% ·
              일평균거래 {c.tier2.account_features.txn_frequency_per_day}건
            </div>
          )}
          {c.tier2.reasons.map((r, i) => (
            <div key={i} className="reason">
              - {r}
            </div>
          ))}
        </Stage>
      )}

      {c.conversation && c.conversation.length > 0 && (
        <Stage title="직원-고객 간 나눈 대화" data={c.conversation}>
          {c.conversation.map((turn, i) => (
            <div key={i} className="conv-turn">
              <div className="conv-q">Q. {turn.question}</div>
              <div className="conv-a">A. {turn.answer}</div>
            </div>
          ))}
        </Stage>
      )}

      {c.stt_result && (
        <Stage title="STT 코칭 정황 분석 결론" data={c.stt_result}>
          <div>코칭 감지: {c.stt_result.coaching_detected ? "예 (강한 정황)" : "아니오"}</div>
          <div>신뢰도: {c.stt_result.confidence}</div>
          <div>매칭 유형: {c.stt_result.matched_scam_type}</div>
          <div className="reason">{c.stt_result.reasoning}</div>
        </Stage>
      )}

      {c.yesno_answers && (
        <Stage title="Y/N 확인 결론" data={c.yesno_answers}>
          <div>명확히 정상 판정: {c.yesno_answers.clearly_normal ? "예" : "아니오"}</div>
        </Stage>
      )}

      {c.freetext_analysis && (
        <Stage title="자유텍스트 LLM 패턴 대조 결론" data={c.freetext_analysis}>
          <div>위험도: {c.freetext_analysis.risk_level}</div>
          <div>매칭 패턴: {c.freetext_analysis.matched_pattern_id || "없음"}</div>
          <div className="reason">{c.freetext_analysis.reasoning}</div>
        </Stage>
      )}
    </details>
  );
}

function Stage({ title, data, children }) {
  if (!data) return null;
  return (
    <div className="stage">
      <h3>{title}</h3>
      {children}
    </div>
  );
}
