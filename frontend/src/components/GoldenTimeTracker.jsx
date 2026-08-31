import { useEffect, useState } from "react";

function findTime(log, event) {
  const entry = [...(log || [])].reverse().find((e) => e.event === event);
  if (!entry?.timestamp) return null;
  try {
    return new Date(entry.timestamp).toLocaleTimeString("ko-KR", { hour12: false });
  } catch {
    return null;
  }
}

export default function GoldenTimeTracker({ case: c, requestedAt, onPrint }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = requestedAt || Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, [requestedAt]);

  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");
  const nowLabel = new Date().toLocaleTimeString("ko-KR", { hour12: false });

  return (
    <div className="verify-wrap">
      <div className="golden-timer-box">
        <div>
          <div className="label">지급정지 요청 후 경과</div>
          <div className="status">수취 은행 접수 확인 대기</div>
        </div>
        <div className="clock">{mm}:{ss}</div>
      </div>

      <div className="golden-status-panel">
        <h2>처리 현황</h2>
        <div className="golden-step-list">
          <div className="golden-step">
            <div className="dot" />
            <div className="t">지급정지 요청 전송 완료</div>
            <div className="time">{nowLabel}</div>
          </div>
          <div className="golden-step">
            <div className="dot" />
            <div className="t">내부 이상거래 대응팀 통보</div>
            <div className="time">{nowLabel}</div>
          </div>
          <div className="golden-step pending">
            <div className="dot" />
            <div className="t">수취 은행 접수 확인</div>
            <div className="time">대기 중</div>
          </div>
          <div className="golden-step upcoming">
            <div className="dot" />
            <div className="t">고객 피해구제 신청 안내</div>
            <div className="time">—</div>
          </div>
        </div>
      </div>

      <div className="verify-actions-row">
        <button className="btn-block" onClick={onPrint}>고객에게 안내문 출력</button>
      </div>
    </div>
  );
}
