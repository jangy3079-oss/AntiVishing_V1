import { useState } from "react";
import { api } from "../api";

// 테스트/시연용 편의 도구. 실제 창구 화면(이름+계좌번호 직접 입력, blind lookup)과는
// 별개로 접어둔 패널이며, 로그아웃 버튼 옆 토글로만 열린다.
export default function DevToolsPanel({ testAccounts, onRefreshTestAccounts, formRef, formAvailable }) {
  const [open, setOpen] = useState(false);
  const [n, setN] = useState(5);
  const [regenerating, setRegenerating] = useState(false);
  const [regenResult, setRegenResult] = useState(null);
  const [regenError, setRegenError] = useState(null);

  const selectCustomer = (accountNumber) => {
    if (!accountNumber) return;
    const c = testAccounts.customers.find((x) => x.account_number === accountNumber);
    if (c) formRef.current?.fillCustomer(c);
  };

  const selectRecipient = (accountNumber) => {
    if (!accountNumber) return;
    const r = testAccounts.recipients.find((x) => x.account_number === accountNumber);
    if (r) formRef.current?.fillRecipient(r);
  };

  const regenerate = async () => {
    setRegenerating(true);
    setRegenError(null);
    setRegenResult(null);
    try {
      const result = await api.regenerateTestAccounts(n);
      setRegenResult(result);
      await onRefreshTestAccounts();
    } catch (e) {
      setRegenError(e.message);
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ textAlign: "center" }}>
        <button
          type="button"
          className="auth-link-btn"
          style={{ color: "#5c5f66", borderColor: "#5c5f66" }}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "개발자 도구 닫기" : "개발자 도구"}
        </button>
      </div>

      {open && (
        <div
          style={{
            maxWidth: 640,
            margin: "12px auto 0",
            border: "1px solid #d8dae0",
            background: "#fafafa",
            padding: 16,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 4 }}>테스트 계정 빠른 선택</div>
          <div className="hint2" style={{ marginBottom: 10 }}>
            거래 접수 화면의 고객 이름·계좌번호, 수취 은행·계좌번호를 자동으로 채워 넣습니다.
          </div>

          {!formAvailable && (
            <div className="hint2" style={{ marginBottom: 10 }}>
              지금은 거래 접수 화면이 아니라서 채워 넣을 폼이 없습니다. 케이스를 초기화한 뒤 사용하세요.
            </div>
          )}

          <div className="field-row">
            <div className="field-col">
              <div className="field-label">테스트 고객 빠른 선택</div>
              <div className="field-select light">
                <select
                  defaultValue=""
                  disabled={!formAvailable}
                  onChange={(e) => selectCustomer(e.target.value)}
                >
                  <option value="">직접 입력</option>
                  {testAccounts.customers.map((c) => (
                    <option key={c.account_number} value={c.account_number}>
                      {c.name} ({c.age}세·{c.gender}) · {c.account_number}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="field-col">
              <div className="field-label">테스트 수취계좌 빠른 선택</div>
              <div className="field-select light">
                <select
                  defaultValue=""
                  disabled={!formAvailable}
                  onChange={(e) => selectRecipient(e.target.value)}
                >
                  <option value="">직접 입력</option>
                  {testAccounts.recipients.map((r) => (
                    <option key={r.account_number} value={r.account_number}>
                      {r.label} · {r.account_number}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div style={{ height: 1, background: "#d8dae0", margin: "16px 0" }} />

          <div style={{ fontWeight: 700, marginBottom: 4 }}>랜덤 테스트 계좌 재생성</div>
          <div className="hint2" style={{ marginBottom: 10 }}>
            정상/대포통장(즉시인출·분산입금·심야거래·복합) 원형을 무작위로 다시 뽑아 위 목록을 교체합니다.
            손으로 만든 데모 시나리오 계좌는 그대로 유지됩니다. 서버 재시작이 필요 없습니다.
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className="hint2">원형당 개수</span>
            <input
              className="field-input light mono"
              style={{ width: 64 }}
              inputMode="numeric"
              value={n}
              onChange={(e) => setN(Math.max(1, Number(e.target.value.replace(/[^0-9]/g, "")) || 1))}
            />
            <button type="button" className="btn-block" style={{ width: "auto", padding: "0 16px" }} onClick={regenerate} disabled={regenerating}>
              {regenerating ? "생성 중..." : "랜덤 계좌 재생성"}
            </button>
          </div>
          {regenResult && (
            <div className="hint2" style={{ marginTop: 8 }}>
              생성 완료: 고객 {regenResult.customers}명 · 수취계좌 {regenResult.recipients}개
            </div>
          )}
          {regenError && (
            <div className="error-banner" style={{ marginTop: 8 }}>
              <div className="title">{regenError}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
