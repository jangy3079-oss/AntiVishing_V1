import { useState } from "react";
import TransactionForm from "./components/TransactionForm";
import StepIndicator from "./components/StepIndicator";
import SummaryBar from "./components/SummaryBar";
import VerificationPanel from "./components/VerificationPanel";
import ResultCard from "./components/ResultCard";
import PipelineView from "./components/PipelineView";
import "./App.css";

export default function App() {
  const [currentCase, setCurrentCase] = useState(null);

  return (
    <div className="app">
      <header>
        <h1>AntiVishing</h1>
        <p>은행 창구직원용 보이스피싱 탐지 보조 도구 (로컬 프로토타입)</p>
      </header>

      <StepIndicator case={currentCase} />

      <main className="single-col">
        {!currentCase && <TransactionForm onCaseCreated={setCurrentCase} />}

        {currentCase && (
          <>
            <SummaryBar case={currentCase} onReset={() => setCurrentCase(null)} />
            <VerificationPanel case={currentCase} onUpdated={setCurrentCase} />
            <ResultCard case={currentCase} />
            <PipelineView case={currentCase} />
          </>
        )}
      </main>
    </div>
  );
}
