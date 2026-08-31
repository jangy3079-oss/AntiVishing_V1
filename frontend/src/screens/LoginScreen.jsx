import { useState } from "react";
import { login } from "../lib/auth";

export default function LoginScreen({ onLoggedIn, onGoSignup }) {
  const [tellerId, setTellerId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);

  const submit = (e) => {
    e.preventDefault();
    try {
      const session = login({ teller_id: tellerId, password });
      onLoggedIn(session);
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
            <div className="headline">
              거래 접수 순간
              <br />
              보이스피싱을
              <br />
              놓치지 않도록
            </div>
            <div className="sub">
              창구 접수부터 최종 판정까지, 다음에 할 일 하나만 보여주는 실시간 이상거래 확인 보조 도구
            </div>
          </div>
          <div className="foot">금융보안원 2026 금융 AI CHALLENGE</div>
        </div>

        <div className="auth-form-side">
          <div className="auth-form-inner">
            <h1>로그인</h1>
            <p className="lede">영업점 직원 계정으로 접속하세요.</p>

            <form onSubmit={submit} className="auth-fields">
              <div>
                <div className="field-label">행번</div>
                <input
                  className="field-input mono"
                  inputMode="numeric"
                  placeholder="1043872"
                  value={tellerId}
                  onChange={(e) => setTellerId(e.target.value)}
                />
              </div>
              <div>
                <div className="field-label">비밀번호</div>
                <input
                  className="field-input password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              <button className="btn-primary-lg" type="submit" disabled={!tellerId || !password}>
                로그인
              </button>
            </form>

            {error && <div className="auth-error">{error}</div>}

            <div className="auth-links">
              <button className="auth-link-btn" type="button" onClick={onGoSignup}>
                계정 신청
              </button>
              <div className="auth-hint">비밀번호 재설정은 영업점 관리자에게 문의</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
