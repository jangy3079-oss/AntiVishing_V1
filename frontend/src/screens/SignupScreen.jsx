import { useState } from "react";
import { signup } from "../lib/auth";

const BRANCHES = ["서울 중앙지점", "강남지점", "부산 서면지점", "대전 둔산지점", "광주 상무지점"];

export default function SignupScreen({ onSignedUp, onGoLogin }) {
  const [name, setName] = useState("");
  const [tellerId, setTellerId] = useState("");
  const [branch, setBranch] = useState(BRANCHES[0]);
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  const submit = (e) => {
    e.preventDefault();
    try {
      signup({ name, teller_id: tellerId, branch, password });
      setError(null);
      setDone(true);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="app-screen">
      <div className="auth-screen">
        <div className="auth-hero">
          <div className="wordmark">ANTIVISHING_V1</div>
          <div>
            <div className="headline" style={{ fontSize: 46 }}>
              영업점 단위로
              <br />
              계정을 발급합니다
            </div>
            <div className="sub">
              신청 후 영업점 관리자 승인이 완료되면 행번으로 로그인할 수 있습니다.
            </div>
          </div>
          <div className="foot">승인 소요 1영업일</div>
        </div>

        <div className="auth-form-side">
          <div className="auth-form-inner">
          <h1>계정 신청</h1>

          {done ? (
            <>
              <p className="lede">
                신청이 접수되었습니다. (프로토타입에서는 즉시 로그인 가능하도록 처리됩니다.)
              </p>
              <button className="btn-primary-lg" onClick={onGoLogin}>
                로그인하러 가기
              </button>
            </>
          ) : (
            <form onSubmit={submit}>
              <div className="auth-fields grid-2">
                <div>
                  <div className="field-label">이름</div>
                  <input className="field-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="김도현" />
                </div>
                <div>
                  <div className="field-label">행번</div>
                  <input
                    className="field-input mono"
                    inputMode="numeric"
                    value={tellerId}
                    onChange={(e) => setTellerId(e.target.value)}
                    placeholder="1043872"
                  />
                </div>
              </div>

              <div style={{ marginTop: 20 }}>
                <div className="field-label">영업점</div>
                <div className="field-select">
                  <select value={branch} onChange={(e) => setBranch(e.target.value)}>
                    {BRANCHES.map((b) => (
                      <option key={b} value={b}>
                        {b}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div style={{ marginTop: 20 }}>
                <div className="field-label">비밀번호</div>
                <input
                  className="field-input password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                />
              </div>

              <button
                className="btn-primary-lg"
                type="submit"
                disabled={!name || !tellerId || !password}
              >
                신청하기
              </button>

              {error && <div className="auth-error">{error}</div>}

              <div className="auth-hint" style={{ marginTop: 22 }}>
                이미 계정이 있으신가요?{" "}
                <button className="auth-link-btn" type="button" onClick={onGoLogin} style={{ fontSize: 15 }}>
                  로그인
                </button>
              </div>
            </form>
          )}
          </div>
        </div>
      </div>
    </div>
  );
}
