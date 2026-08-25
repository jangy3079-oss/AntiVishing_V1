import { useState, useEffect, useRef } from "react";
import { api } from "../api";

export default function VerificationPanel({ case: c, onUpdated }) {
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const run = async (fn) => {
    setLoading(true);
    setError(null);
    try {
      const updated = await fn();
      onUpdated(updated);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (!c || !c.next_action || c.next_action === "none_completed") return null;

  if (c.next_action === "stt_optional_or_yesno" || c.next_action === "yesno") {
    return (
      <div className="panel">
        {c.next_action === "stt_optional_or_yesno" && (
          <SttBlock
            caseId={c.id}
            onRun={run}
            loading={loading}
            autoTrigger={Boolean(c.tier2?.high_auto_signal)}
          />
        )}
        <YesNoBlock caseId={c.id} onRun={run} loading={loading} />
        {error && <div className="error">{error}</div>}
      </div>
    );
  }

  if (c.next_action === "freetext") {
    return (
      <div className="panel">
        <FreeTextBlock caseId={c.id} onRun={run} loading={loading} followup={c.freetext_analysis} />
        {error && <div className="error">{error}</div>}
      </div>
    );
  }

  if (c.next_action === "high_risk_actions") {
    return (
      <div className="panel">
        <EscalationBlock caseId={c.id} onRun={run} loading={loading} alreadySent={c.already_sent} />
        {error && <div className="error">{error}</div>}
      </div>
    );
  }

  return null;
}

// 브라우저가 돌려주는 음성인식 오류 코드를 사람이 이해할 수 있는 한국어 안내로 변환한다.
function describeSttError(code) {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "마이크 권한이 거부되었습니다. 브라우저 주소창 옆 마이크 아이콘에서 권한을 허용해주세요.";
    case "no-speech":
      return "음성이 감지되지 않았습니다. 마이크와의 거리를 확인하고 다시 시도해주세요.";
    case "audio-capture":
      return "마이크를 찾을 수 없습니다. 마이크 연결 상태를 확인해주세요.";
    case "network":
      return "네트워크 오류로 음성인식에 실패했습니다.";
    case "aborted":
      return null; // 사용자가 직접 중지한 경우는 오류로 표시하지 않음
    default:
      return `음성인식 중 오류가 발생했습니다 (${code}). 아래에 직접 입력해주세요.`;
  }
}

function SttBlock({ caseId, onRun, loading, autoTrigger }) {
  const [transcript, setTranscript] = useState("");
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(true);
  const [errorMsg, setErrorMsg] = useState(null);
  const recognitionRef = useRef(null);
  const startedRef = useRef(false);

  // 이상거래 신호(첫 송금+고액+수취계좌 이상패턴)가 감지된 케이스(autoTrigger)는
  // 직원이 버튼을 누르지 않아도 음성인식이 자동으로 시작된다.
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSupported(false);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "ko-KR";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onresult = (e) => {
      let combined = "";
      for (let i = 0; i < e.results.length; i++) {
        combined += e.results[i][0].transcript;
      }
      setTranscript(combined);
    };
    recognition.onstart = () => setErrorMsg(null);
    recognition.onend = () => setListening(false);
    recognition.onerror = (e) => {
      setListening(false);
      setErrorMsg(describeSttError(e.error));
    };
    recognitionRef.current = recognition;

    if (autoTrigger && !startedRef.current) {
      startedRef.current = true;
      try {
        recognition.start();
        setListening(true);
      } catch {
        setListening(false);
      }
    }

    return () => recognition.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleListening = () => {
    const recognition = recognitionRef.current;
    if (!recognition) return;
    if (listening) {
      recognition.stop();
      setListening(false);
    } else {
      setErrorMsg(null);
      try {
        recognition.start();
        setListening(true);
      } catch {
        /* 이미 인식 중인 경우 등은 무시 */
      }
    }
  };

  return (
    <div className="stage">
      <h3>① 통화 중 코칭 정황 확인 {autoTrigger ? "(자동 시작됨)" : "(선택)"}</h3>

      {autoTrigger && (
        <div className="stt-notice">
          ⚠ 이상거래 정황(첫 송금·고액·수취계좌 이상패턴)이 감지되어 확인을 위해 상담 내용이
          자동으로 기록됩니다. 고객에게 안내해주세요.
        </div>
      )}

      {!supported ? (
        <p className="hint">
          이 브라우저는 음성인식을 지원하지 않습니다. 창구 대화 내용을 아래에 직접 입력해주세요. (Chrome
          사용을 권장합니다)
        </p>
      ) : (
        <div className="stt-status">
          {listening && (
            <span className="stt-wave">
              {[0, 1, 2, 3].map((i) => (
                <span key={i} className="wave-bar" style={{ animationDelay: `${i * 0.12}s` }} />
              ))}
            </span>
          )}
          <span>{listening ? "음성 인식 중..." : "음성 인식 대기 중"}</span>
          <button className="link-btn" type="button" onClick={toggleListening}>
            {listening ? "중지" : "다시 시작"}
          </button>
        </div>
      )}

      {errorMsg && <div className="stt-error">⚠ {errorMsg}</div>}

      {!autoTrigger && (
        <p className="hint">
          고객이 통화 중인 것으로 보이면, 창구 대화 STT 텍스트를 입력해 코칭 정황을 분석합니다. 해당 없으면
          아래 Y/N 질문으로 바로 진행하세요.
        </p>
      )}

      <textarea
        rows={3}
        value={transcript}
        onChange={(e) => setTranscript(e.target.value)}
        placeholder="예: 검찰청이라면서 안전계좌로 옮기라고 계속 통화중이에요"
      />
      <button
        disabled={!transcript || loading}
        onClick={() => onRun(() => api.submitStt(caseId, transcript))}
      >
        STT 분석 실행
      </button>
    </div>
  );
}

function YesNoBlock({ caseId, onRun, loading }) {
  const [known, setKnown] = useState(null);
  const [aware, setAware] = useState(null);
  const ready = known !== null && aware !== null;
  return (
    <div className="stage">
      <h3>② 확인 질문 (Y/N)</h3>
      <div className="question">
        <span>아는 사람/사업체인가요?</span>
        <YesNoButtons value={known} onChange={setKnown} />
      </div>
      <div className="question">
        <span>이 돈의 정확한 용도를 알고 계신가요?</span>
        <YesNoButtons value={aware} onChange={setAware} />
      </div>
      <button
        disabled={!ready || loading}
        onClick={() => onRun(() => api.submitYesNo(caseId, known, aware))}
      >
        답변 제출
      </button>
    </div>
  );
}

function YesNoButtons({ value, onChange }) {
  return (
    <span className="yesno-buttons">
      <button className={value === true ? "active" : ""} onClick={() => onChange(true)}>
        예
      </button>
      <button className={value === false ? "active" : ""} onClick={() => onChange(false)}>
        아니오
      </button>
    </span>
  );
}

function FreeTextBlock({ caseId, onRun, loading, followup }) {
  const [text, setText] = useState("");
  const followupQuestion = followup?.needs_followup ? followup.followup_question : null;
  return (
    <div className="stage">
      <h3>③ 자유텍스트 진술</h3>
      {followupQuestion ? (
        <p className="hint">후속 질문: {followupQuestion}</p>
      ) : (
        <p className="hint">"상황을 간단히 말씀해주세요" 라고 물은 뒤 고객 답변을 요약해서 입력하세요.</p>
      )}
      <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} />
      <button disabled={!text || loading} onClick={() => onRun(() => api.submitFreeText(caseId, text))}>
        제출 (LLM 패턴 대조)
      </button>
    </div>
  );
}

function EscalationBlock({ caseId, onRun, loading, alreadySent }) {
  return (
    <div className="stage stage-high">
      <h3>위험 높음 · 조치</h3>
      <div className="actions">
        <button onClick={() => onRun(() => api.submitEscalation(caseId, "confirm_with_sender"))} disabled={loading}>
          송금인 설명·진행여부 확인
        </button>
        <button onClick={() => onRun(() => api.submitEscalation(caseId, "escalate_fsi"))} disabled={loading}>
          내부/금감원 에스컬레이션
        </button>
        <button onClick={() => onRun(() => api.submitEscalation(caseId, "notify_guardian"))} disabled={loading}>
          보호자 참고 알림 (승인권한 없음)
        </button>
        {alreadySent && (
          <button onClick={() => onRun(() => api.submitEscalation(caseId, "freeze_request"))} disabled={loading}>
            골든타임 내 자동 지급정지 요청
          </button>
        )}
      </div>
    </div>
  );
}
