import { useEffect, useRef, useState } from "react";
import { getSession, logout } from "./lib/auth";
import { api } from "./api";
import LoginScreen from "./screens/LoginScreen";
import SignupScreen from "./screens/SignupScreen";
import Header from "./components/Header";
import StepIndicator from "./components/StepIndicator";
import SummaryBar from "./components/SummaryBar";
import TransactionForm from "./components/TransactionForm";
import VerificationPanel from "./components/VerificationPanel";
import ResultCard from "./components/ResultCard";
import GoldenTimeTracker from "./components/GoldenTimeTracker";
import PipelineView from "./components/PipelineView";
import DevToolsPanel from "./components/DevToolsPanel";
import "./App.css";

export default function App() {
  const [authScreen, setAuthScreen] = useState("login"); // login | signup
  const [teller, setTeller] = useState(() => getSession());

  const [currentCase, setCurrentCase] = useState(null);
  const [customerProfile, setCustomerProfile] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [goldenRequestedAt, setGoldenRequestedAt] = useState(null);

  const [testAccounts, setTestAccounts] = useState({ customers: [], recipients: [] });
  const formRef = useRef(null);

  const refreshTestAccounts = () => api.listTestAccounts().then(setTestAccounts).catch(() => {});

  useEffect(() => {
    if (teller) refreshTestAccounts();
  }, [teller]);

  useEffect(() => {
    if (currentCase?.status === "GOLDEN_TIME_FREEZE_REQUESTED" && !goldenRequestedAt) {
      setGoldenRequestedAt(Date.now());
    }
  }, [currentCase?.status, goldenRequestedAt]);

  if (!teller) {
    return authScreen === "login" ? (
      <div className="app-shell">
        <LoginScreen onLoggedIn={setTeller} onGoSignup={() => setAuthScreen("signup")} />
      </div>
    ) : (
      <div className="app-shell">
        <SignupScreen onSignedUp={() => setAuthScreen("login")} onGoLogin={() => setAuthScreen("login")} />
      </div>
    );
  }

  const resetCase = () => {
    setCurrentCase(null);
    setCustomerProfile(null);
    setDetailOpen(false);
    setGoldenRequestedAt(null);
  };

  const handleCaseCreated = (created, profile) => {
    setCurrentCase(created);
    setCustomerProfile(profile || null);
  };

  const isHigh =
    currentCase?.status === "STT_HARD_BLOCKED" ||
    currentCase?.status === "FINAL_HIGH_RISK" ||
    currentCase?.status === "GOLDEN_TIME_FREEZE_REQUESTED";
  const riskState =
    currentCase?.status === "GOLDEN_TIME_FREEZE_REQUESTED" ? "golden" : isHigh ? "high" : null;

  const showAutoBanner =
    currentCase?.status === "TIER2_ESCALATED" && Boolean(currentCase?.tier2?.high_auto_signal);

  const isGolden = currentCase?.status === "GOLDEN_TIME_FREEZE_REQUESTED";
  const isTerminal =
    currentCase &&
    !isGolden &&
    (currentCase.next_action === "none_completed" || currentCase.next_action === "high_risk_actions");

  return (
    <div className="app-shell">
      <div className="app-screen">
        <Header teller={teller} showTagline={!currentCase} riskState={riskState} />

        {currentCase && !isGolden && (
          <SummaryBar case={currentCase} customerAge={customerProfile?.age} customerGender={customerProfile?.gender} onReset={resetCase} />
        )}

        {showAutoBanner && (
          <div className="stt-auto-banner">
            <div className="dot" />
            <div className="msg">이상거래 정황이 감지되어 상담 내용이 자동으로 기록됩니다</div>
          </div>
        )}

        <StepIndicator case={currentCase} />

        {!currentCase && (
          <TransactionForm ref={formRef} tellerId={teller.teller_id} onCaseCreated={handleCaseCreated} />
        )}

        {currentCase && (
          <div className="screen-body">
            {isGolden ? (
              <GoldenTimeTracker case={currentCase} requestedAt={goldenRequestedAt} onPrint={() => window.print()} />
            ) : (
              <>
                <ResultCard case={currentCase} />
                <VerificationPanel case={currentCase} onUpdated={setCurrentCase} />
                {isTerminal && (
                  <PipelineView
                    case={currentCase}
                    open={detailOpen}
                    onToggle={() => setDetailOpen((v) => !v)}
                    primaryLabel={currentCase.next_action === "none_completed" ? "확인 완료" : null}
                    onPrimary={resetCase}
                  />
                )}
              </>
            )}
          </div>
        )}
      </div>

      <div style={{ textAlign: "center", marginTop: 12 }}>
        <button
          className="auth-link-btn"
          style={{ color: "#5c5f66", borderColor: "#5c5f66" }}
          onClick={() => {
            logout();
            setTeller(null);
            resetCase();
            api.reset().catch(() => {});
          }}
        >
          로그아웃
        </button>
      </div>

      <DevToolsPanel
        testAccounts={testAccounts}
        onRefreshTestAccounts={refreshTestAccounts}
        formRef={formRef}
        formAvailable={!currentCase}
      />
    </div>
  );
}
