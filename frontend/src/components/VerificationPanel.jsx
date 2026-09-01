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
    const autoTrigger = c.next_action === "stt_optional_or_yesno" && Boolean(c.tier2?.high_auto_signal);
    return (
      <div className="verify-wrap">
        {c.next_action === "stt_optional_or_yesno" && (
          <SttGate caseId={c.id} onRun={run} loading={loading} autoTrigger={autoTrigger} />
        )}
        {!autoTrigger && <YesNoBlock caseId={c.id} onRun={run} loading={loading} />}
        {error && <div className="field-error-msg">{error}</div>}
      </div>
    );
  }

  if (c.next_action === "freetext") {
    return (
      <div className="verify-wrap">
        <FreeTextBlock
          caseId={c.id}
          onRun={run}
          loading={loading}
          followup={c.freetext_analysis}
          conversation={c.conversation}
        />
        {error && <div className="field-error-msg">{error}</div>}
      </div>
    );
  }

  if (c.next_action === "high_risk_actions") {
    return (
      <div className="verify-wrap">
        <EscalationBlock caseId={c.id} onRun={run} loading={loading} case={c} />
        {error && <div className="field-error-msg">{error}</div>}
      </div>
    );
  }

  return null;
}

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
      return null;
    default:
      return `음성인식 중 오류가 발생했습니다 (${code}). 아래에 직접 입력해주세요.`;
  }
}

function describeSttStartError(err) {
  const name = err?.name || "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "마이크 권한이 거부되었거나, 보안 연결(HTTPS 또는 localhost)이 아니라서 음성 인식을 시작할 수 없습니다. 브라우저 주소창의 마이크 권한을 확인해주세요.";
  }
  return `음성 인식을 시작할 수 없습니다 (${name || err}). 아래에 직접 입력해주세요.`;
}

function useElapsedTimer(active) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!active) {
      setSeconds(0);
      return;
    }
    const start = Date.now();
    const id = setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, [active]);
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

function SttGate({ caseId, onRun, loading, autoTrigger }) {
  // 자동으로 강한 의심 신호가 잡힌 거래(autoTrigger)에서는 STT 화면으로 곧장 들어가기 전에,
  // "지금 상대와 통화 중인가요?"부터 먼저 확인한다. 답에 따라 SttBlock에 다른 안내 문구를
  // 보여준다(통화 중이면 "대화를 그대로 두세요", 아니면 "직원과의 대화를 녹음합니다").
  const [onCall, setOnCall] = useState(null);

  if (autoTrigger && onCall === null) {
    return (
      <div className="suspicion-gate">
        <div className="eyebrow">의심 정황이 발견되었습니다</div>
        <div className="verify-title md">지금 상대와 통화 중인가요?</div>
        <div className="yn-buttons">
          <button onClick={() => setOnCall(true)}>예</button>
          <button onClick={() => setOnCall(false)}>아니오</button>
        </div>
      </div>
    );
  }

  return <SttBlock caseId={caseId} onRun={onRun} loading={loading} autoTrigger={autoTrigger} onCall={onCall} />;
}

function SttBlock({ caseId, onRun, loading, autoTrigger, onCall }) {
  const [transcript, setTranscript] = useState("");
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(true);
  const [errorMsg, setErrorMsg] = useState(null);
  const [manualMode, setManualMode] = useState(false);
  const recognitionRef = useRef(null);
  const startedRef = useRef(false);

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
      for (let i = 0; i < e.results.length; i++) combined += e.results[i][0].transcript;
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
      } catch (err) {
        setListening(false);
        // InvalidStateError(이미 인식 중)는 무시해도 되지만, 그 외(보안 컨텍스트 아님 등)는
        // 예전엔 조용히 삼켜서 아무 반응도 없는 것처럼 보였다 - 원인을 화면에 보여준다.
        if (err?.name !== "InvalidStateError") {
          setErrorMsg(describeSttStartError(err));
        }
      }
    }
    return () => recognition.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startListening = () => {
    const recognition = recognitionRef.current;
    if (!recognition) return;
    setErrorMsg(null);
    setManualMode(false);
    try {
      recognition.start();
      setListening(true);
    } catch (err) {
      if (err?.name !== "InvalidStateError") {
        setErrorMsg(describeSttStartError(err));
      }
    }
  };
  const stopListening = () => {
    recognitionRef.current?.stop();
    setListening(false);
  };

  const showPanel = autoTrigger || listening || (transcript && !manualMode);
  const timer = useElapsedTimer(listening);

  if (!showPanel) {
    return (
      <div className="stt-optin-row">
        <div>
          <div className="t">고객과 나눈 대화를 기록해두면 판단에 참고됩니다</div>
          <div className="s">
            {supported
              ? "선택 사항 · 통화 중이 아니어도 괜찮습니다. 고객이 설명한 내용(예: 평소와 다른 계좌번호로 안내받음, 목소리는 맞는 것 같은데 뭔가 이상했음 등)을 그대로 기록해주세요"
              : "이 브라우저는 음성 인식을 지원하지 않습니다(Chrome/Edge 권장). 아래에 직접 입력해주세요."}
          </div>
        </div>
        <button className="btn-outline-navy" type="button" onClick={supported ? startListening : () => setManualMode(true)}>
          {supported ? "음성 인식 시작" : "직접 입력"}
        </button>
      </div>
    );
  }

  return (
    <div>
      {autoTrigger && (
        <div className="eyebrow" style={{ marginBottom: 8 }}>지금 할 일</div>
      )}
      {autoTrigger && (
        <div className="h-page" style={{ fontSize: 38, marginBottom: 22 }}>
          {onCall ? "고객이 통화 중인지 확인하고, 대화를 그대로 두세요" : "직원과의 대화를 녹음합니다"}
        </div>
      )}

      {(!supported || manualMode) ? (
        <div className="stt-manual-wrap">
          <textarea
            rows={3}
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            placeholder="예: 검찰청이라면서 안전계좌로 옮기라고 계속 통화중이에요 / 목소리는 친구 같았는데 평소와 다른 계좌번호를 알려줘서 이상해서 왔어요"
          />
        </div>
      ) : (
        <div className="stt-panel">
          <div className="stt-panel-head">
            <div className="dot" />
            <div className="label">{listening ? "음성 인식 중 · " + (autoTrigger ? "자동 시작됨" : "직접 시작함") : "음성 인식 대기"}</div>
            <div className="timer">{timer}</div>
          </div>
          <div className="wave-row">
            {Array.from({ length: 18 }).map((_, i) => (
              <div
                key={i}
                className="wave-bar"
                style={{ animationDelay: `${(i % 9) * 0.08}s`, opacity: listening ? 1 : 0.3 }}
              />
            ))}
          </div>
          <div className="stt-transcript-preview">
            {transcript ? `"${transcript}"` : "음성을 인식하면 여기에 실시간으로 표시됩니다..."}
          </div>
        </div>
      )}

      {errorMsg && <div className="stt-error-box">⚠ {errorMsg}</div>}

      <div className="verify-actions-row">
        <button
          className="btn-block"
          disabled={!transcript || loading}
          onClick={() => {
            stopListening();
            onRun(() => api.submitStt(caseId, transcript));
          }}
        >
          인식 중지하고 분석
        </button>
        <button className="btn-secondary" type="button" onClick={() => setManualMode((v) => !v)}>
          직접 입력
        </button>
      </div>
    </div>
  );
}

function YesNoBlock({ caseId, onRun, loading }) {
  const [known, setKnown] = useState(null);
  const [aware, setAware] = useState(null);
  const ready = known !== null && aware !== null;
  return (
    <div className="verify-wrap">
      <div className="eyebrow">고객에게 그대로 읽어주세요 · 2문항</div>
      <div className="verify-title md">답변을 눌러주세요</div>

      <div className="yn-question">
        <div className="q">1. 이 계좌의 주인을 아는 사람 또는 아는 사업체입니까?</div>
        <div className="yn-buttons">
          <button className={known === true ? "selected" : ""} onClick={() => setKnown(true)}>예</button>
          <button className={known === false ? "selected" : ""} onClick={() => setKnown(false)}>아니오</button>
        </div>
      </div>
      <div className="yn-question">
        <div className="q">2. 이 돈의 정확한 용도를 알고 계십니까?</div>
        <div className="yn-buttons">
          <button className={aware === true ? "selected" : ""} onClick={() => setAware(true)}>예</button>
          <button className={aware === false ? "selected" : ""} onClick={() => setAware(false)}>아니오</button>
        </div>
      </div>

      <button
        className="btn-block"
        disabled={!ready || loading}
        onClick={() => onRun(() => api.submitYesNo(caseId, known, aware))}
      >
        답변 제출 {!ready && "(2문항 모두 선택 후 활성화)"}
      </button>
    </div>
  );
}

function FreeTextBlock({ caseId, onRun, loading, followup, conversation }) {
  const [text, setText] = useState("");
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(true);
  const [errorMsg, setErrorMsg] = useState(null);
  const recognitionRef = useRef(null);

  const followupQuestion = followup?.needs_followup ? followup.followup_question : null;
  const question = followupQuestion || "상황을 간단히 말씀해주세요";
  const priorTurn = conversation && conversation.length > 0 ? conversation[conversation.length - 1] : null;

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
      for (let i = 0; i < e.results.length; i++) combined += e.results[i][0].transcript;
      setText(combined);
    };
    recognition.onstart = () => setErrorMsg(null);
    recognition.onend = () => setListening(false);
    recognition.onerror = (e) => {
      setListening(false);
      setErrorMsg(describeSttError(e.error));
    };
    recognitionRef.current = recognition;

    // 이전에는 "다시 받아쓰기" 버튼을 눌러야만 인식이 시작됐는데, 질문이 뜨는 순간부터
    // 자동으로 듣기 시작하는 게 자연스럽다(SttBlock의 autoTrigger와 동일한 패턴).
    try {
      recognition.start();
      setListening(true);
    } catch (err) {
      if (err?.name !== "InvalidStateError") {
        setErrorMsg(describeSttStartError(err));
      }
    }

    return () => recognition.stop();
  }, [question]);

  const restart = () => {
    setText("");
    setErrorMsg(null);
    try {
      recognitionRef.current?.start();
      setListening(true);
    } catch (err) {
      if (err?.name !== "InvalidStateError") {
        setErrorMsg(describeSttStartError(err));
      }
    }
  };

  return (
    <div className="verify-wrap">
      <div className="eyebrow">고객에게 물어보세요</div>
      <div className="verify-title">{question}</div>

      {priorTurn && (
        <div className="prior-answer">
          <div className="label">직전 답변</div>
          <div className="text">"{priorTurn.answer}"</div>
        </div>
      )}

      <div className="freetext-panel">
        {supported ? (
          <>
            <div className="freetext-panel-head">
              <div className="dot" />
              <div className="label">고객 답변 · {listening ? "음성으로 받아쓰는 중" : "받아쓰기 대기"}</div>
              {listening && (
                <div className="mini-wave">
                  {[0, 1, 2, 3, 4].map((i) => (
                    <div key={i} className="bar" style={{ animationDelay: `${i * 0.12}s` }} />
                  ))}
                </div>
              )}
            </div>
            <div className="freetext-answer-text">
              {text || "음성 인식 대기 중이거나, 아래에서 직접 타이핑할 수 있습니다."}
            </div>
          </>
        ) : (
          <div className="freetext-answer-text">
            <div className="hint2" style={{ marginBottom: 8 }}>
              이 브라우저는 음성 인식을 지원하지 않습니다(Chrome/Edge 권장). 아래에 직접 입력해주세요.
            </div>
            <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="고객 답변을 입력하세요" />
          </div>
        )}
      </div>

      {errorMsg && <div className="stt-error-box">⚠ {errorMsg}</div>}

      <div className="freetext-toolbar">
        {supported && (
          <>
            <button className="btn-secondary" type="button" onClick={restart}>다시 받아쓰기</button>
            <button className="btn-secondary" type="button" onClick={() => setSupported(false)}>직접 타이핑</button>
          </>
        )}
        <div className="note">이번 답변이 마지막이면 자동으로 최종 판정으로 넘어갑니다.</div>
      </div>

      <button className="btn-block" disabled={!text || loading} onClick={() => onRun(() => api.submitFreeText(caseId, text))}>
        답변 제출
      </button>
    </div>
  );
}

const ESCALATION_META = [
  { action: "confirm_with_sender", t: "송금인에게 설명하고 진행 여부 확인", s: "가장 먼저 하세요", primary: true },
  { action: "escalate_fsi", t: "내부·금감원 에스컬레이션", s: "로그에 기록됩니다" },
  { action: "notify_guardian", t: "보호자 참고 알림", s: "고객 동의 후 발송" },
  { action: "freeze_request", t: "골든타임 지급정지 요청", s: "이미 송금된 건에만 사용", needsSent: true },
];

function EscalationBlock({ caseId, onRun, loading, case: c }) {
  const done = new Set((c.escalation_log || []).map((e) => e.action));
  return (
    <div className="verify-wrap">
      <div className="eyebrow">지금 할 조치 · 복수 선택 가능</div>
      <div className="escalation-grid">
        {ESCALATION_META.map((m) => {
          const disabled = (m.needsSent && !c.already_sent) || loading;
          const isDone = done.has(m.action);
          const cls = disabled ? "" : isDone ? "done" : m.primary ? "primary" : "";
          return (
            <button
              key={m.action}
              className={`escalation-card ${cls}`}
              disabled={disabled}
              onClick={() => onRun(() => api.submitEscalation(caseId, m.action))}
            >
              <div className="t">{isDone ? `✓ ${m.t}` : m.t}</div>
              <div className="s">{m.s}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
