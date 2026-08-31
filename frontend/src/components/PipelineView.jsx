import PipelineDiagram from "./PipelineDiagram";
import AccountFigures from "./AccountFigures";
import TransactionHistory from "./TransactionHistory";

export default function PipelineView({ case: c, open, onToggle, primaryLabel, onPrimary }) {
  if (!c) return null;
  const hasDetail = c.tier1 || c.tier2 || c.stt_result || c.yesno_answers || c.freetext_analysis;
  if (!hasDetail) return null;

  return (
    <>
      <div className="verify-actions-row" style={{ marginTop: open ? 0 : "auto" }}>
        {primaryLabel && (
          <button className="btn-block" onClick={onPrimary}>
            {primaryLabel}
          </button>
        )}
        <button className="btn-secondary" onClick={onToggle}>
          자세히 보기 {open ? "▴ 닫기" : "▾"}
        </button>
        {!open && !primaryLabel && (
          <div className="auth-hint" style={{ alignSelf: "center" }}>
            점수·특징치·대화 전문은 접혀 있습니다.
          </div>
        )}
      </div>

      {open && <PipelineDiagram case={c} />}
      {open && <AccountFigures caseId={c.id} enabled={Boolean(c.tier2)} />}
      {open && (
        <TransactionHistory caseId={c.id} enabled={Boolean(c.tier2)} reasons={c.tier2?.reasons} />
      )}

      {open && (
        <div className="detail-grid" style={{ padding: 0 }}>
          <div className="detail-col">
            {c.tier1 && (
              <div className="detail-card">
                <div className="detail-card-head">
                  <div className="label">TIER 1 · 경량 실시간 필터</div>
                </div>
                <div className="detail-kv-list">
                  <div className="detail-kv"><span className="k">신뢰 수취인</span><span className="v">{c.tier1.is_trusted_recipient ? "예" : "아니오"}</span></div>
                  <div className="detail-kv"><span className="k">첫 거래</span><span className="v">{c.tier1.is_first_time ? "예" : "아니오"}</span></div>
                  <div className="detail-kv"><span className="k">고령 금융소비자</span><span className="v">{c.tier1.is_elderly_customer ? "예" : "아니오"}</span></div>
                  <div className="detail-kv"><span className="k">평소 최대 대비</span><span className="v">{c.tier1.amount_ratio_vs_max?.toFixed?.(1) ?? c.tier1.amount_ratio_vs_max}배</span></div>
                </div>
                {c.tier1.reasons?.length > 0 && <div className="detail-note">{c.tier1.reasons.join(" / ")}</div>}
              </div>
            )}

            {c.tier2 && (
              <div className="detail-card grow">
                <div className="detail-card-head">
                  <div className="label">TIER 2 · 상대계좌 심층 조사</div>
                  <div className={`detail-score ${c.tier2.auto_suspicion_score >= 70 ? "high" : "low"}`}>
                    {c.tier2.auto_suspicion_score} / 100
                  </div>
                </div>
                {c.tier2.account_features && (
                  <div className="detail-feature-grid">
                    <div className="detail-feature"><span className="k">즉시인출비율</span><span className="v">{c.tier2.account_features.immediate_withdrawal_ratio}</span></div>
                    <div className="detail-feature"><span className="k">72h 입금 상대 수</span><span className="v">{c.tier2.account_features.distinct_senders_72h}</span></div>
                    <div className="detail-feature"><span className="k">심야거래 비중</span><span className="v">{c.tier2.account_features.night_txn_ratio}</span></div>
                    <div className="detail-feature"><span className="k">일평균 거래건수</span><span className="v">{c.tier2.account_features.txn_frequency_per_day}</span></div>
                  </div>
                )}
                <div className="detail-reason-grid">
                  {c.tier2.reasons?.map((r, i) => (
                    <div key={i} className="detail-reason">· {r}</div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="detail-col">
            {c.stt_result && (
              <div className="detail-card">
                <div className="detail-card-head"><div className="label">음성 코칭 판정 · 2단계</div></div>
                <div className="detail-split-2">
                  <div>
                    <span className="k">로컬 분류기</span>
                    <span className="v">
                      {c.stt_result.raw?.local_classifier?.available
                        ? `${c.stt_result.raw.local_classifier.prob_phishing} · ${c.stt_result.raw.local_classifier.label}`
                        : "—"}
                    </span>
                  </div>
                  <div>
                    <span className="k">최종 판단</span>
                    <span className={`v ${c.stt_result.coaching_detected ? "alert" : ""}`}>
                      {c.stt_result.raw?.source === "local_classifier"
                        ? "Claude 호출 생략"
                        : c.stt_result.coaching_detected
                        ? "강한 코칭 감지"
                        : "정상 판단"}
                    </span>
                  </div>
                </div>
                <div className="detail-note">{c.stt_result.reasoning}</div>
              </div>
            )}

            {c.freetext_analysis && (
              <div className="detail-card">
                <div className="detail-card-head"><div className="label">자유텍스트 LLM 패턴 대조</div></div>
                <div className="detail-kv-list">
                  <div className="detail-kv"><span className="k">위험도</span><span className="v">{c.freetext_analysis.risk_level}</span></div>
                  <div className="detail-kv"><span className="k">매칭 패턴</span><span className="v">{c.freetext_analysis.matched_pattern_id || "없음"}</span></div>
                </div>
                <div className="detail-note">{c.freetext_analysis.reasoning}</div>
              </div>
            )}

            {c.conversation?.length > 0 && (
              <div className="detail-card grow">
                <div className="detail-card-head"><div className="label">직원–고객 대화 전문</div></div>
                <div className="conv-log">
                  {c.conversation.map((turn, i) => (
                    <div key={i}>
                      <div className="conv-log-item">
                        <div className="q">{turn.question}</div>
                        <div className="a">{turn.answer}</div>
                      </div>
                      {i < c.conversation.length - 1 && <div className="conv-log-divider" />}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
