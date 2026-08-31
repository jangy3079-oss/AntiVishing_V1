import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { api } from "../api";

const BANKS = ["국민은행", "신한은행", "하나은행", "우리은행", "농협은행", "카카오뱅크", "새마을금고", "IBK기업은행"];

const TransactionForm = forwardRef(function TransactionForm({ tellerId, onCaseCreated }, ref) {
  const [customerName, setCustomerName] = useState("");
  const [customerAccount, setCustomerAccount] = useState("");
  const [recipientBank, setRecipientBank] = useState(BANKS[0]);
  const [recipientAccount, setRecipientAccount] = useState("");
  const [amount, setAmount] = useState(0);
  const [alreadySent, setAlreadySent] = useState(false);

  const [lookup, setLookup] = useState(null);
  const [lookupError, setLookupError] = useState(null);
  const [lookupTried, setLookupTried] = useState(false);

  const [submitError, setSubmitError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const debounceRef = useRef(null);

  // 개발자 도구 패널(하단)의 빠른 선택에서 값을 채워 넣을 수 있도록 부모에게 노출한다.
  useImperativeHandle(ref, () => ({
    fillCustomer(customer) {
      if (!customer) return;
      setCustomerName(customer.name);
      setCustomerAccount(customer.account_number);
    },
    fillRecipient(recipient) {
      if (!recipient) return;
      setRecipientAccount(recipient.account_number);
      setRecipientBank(recipient.bank);
    },
  }));

  useEffect(() => {
    clearTimeout(debounceRef.current);
    if (customerName.trim().length < 2 || customerAccount.trim().length < 5) {
      setLookup(null);
      setLookupError(null);
      setLookupTried(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const found = await api.lookupCustomer(customerName.trim(), customerAccount.trim());
        setLookup(found);
        setLookupError(null);
      } catch (e) {
        setLookup(null);
        setLookupError(e.message);
      } finally {
        setLookupTried(true);
      }
    }, 450);
    return () => clearTimeout(debounceRef.current);
  }, [customerName, customerAccount]);

  const addAmount = (delta) => setAmount((a) => Math.max(0, (Number(a) || 0) + delta));
  const clearAmount = () => setAmount(0);

  const canSubmit =
    Boolean(lookup) && recipientAccount.trim().length >= 5 && amount > 0 && !submitting;

  const submit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await api.createCase({
        teller_id: tellerId,
        customer_name: customerName.trim(),
        customer_account_number: customerAccount.trim(),
        recipient_bank: recipientBank,
        recipient_account_number: recipientAccount.trim(),
        amount: Number(amount),
        already_sent: alreadySent,
      });
      onCaseCreated(created, lookup);
    } catch (e) {
      setSubmitError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const nameError = lookupTried && lookupError ? true : false;

  return (
    <div className="intake-body">
      <div className="intake-form">
        <div className="h-page">거래 정보를 입력하세요</div>

        <div className="field-row">
          <div className="field-col">
            <div className="field-label">고객 이름</div>
            <input
              className={`field-input light${nameError ? " error" : ""}`}
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              placeholder="이순자"
            />
          </div>
          <div className="field-col">
            <div className="field-label">고객 본인 계좌번호</div>
            <input
              className={`field-input light mono${nameError ? " error" : ""}`}
              value={customerAccount}
              onChange={(e) => setCustomerAccount(e.target.value)}
              placeholder="330-4455-667788"
            />
          </div>
        </div>

        {lookupTried && lookupError && (
          <div className="error-banner">
            <div className="title">{lookupError}</div>
            <div className="sub">공백·하이픈 없이 입력된 계좌번호도 동일하게 처리됩니다.</div>
          </div>
        )}

        <div className="field-row">
          <div className="field-col">
            <div className="field-label">수취 은행</div>
            <div className="field-select light">
              <select value={recipientBank} onChange={(e) => setRecipientBank(e.target.value)}>
                {BANKS.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="field-col">
            <div className="field-label">수취 계좌번호</div>
            <input
              className="field-input light mono"
              value={recipientAccount}
              onChange={(e) => setRecipientAccount(e.target.value)}
              placeholder="110-452-889931"
              disabled={!lookup}
            />
          </div>
        </div>

        <div className="field-col">
          <div className="field-label">송금액</div>
          <div className="amount-box">
            <input
              inputMode="numeric"
              value={amount ? Number(amount).toLocaleString() : ""}
              onChange={(e) => {
                const digits = e.target.value.replace(/[^0-9]/g, "");
                setAmount(digits ? Number(digits) : 0);
              }}
              placeholder="0"
            />
            <span className="unit">원</span>
          </div>
          <div className="amount-quick">
            <button type="button" onClick={() => addAmount(100000)}>+10만</button>
            <button type="button" onClick={() => addAmount(1000000)}>+100만</button>
            <button type="button" onClick={() => addAmount(10000000)}>+1,000만</button>
            <button type="button" onClick={clearAmount}>지우기</button>
          </div>
        </div>

        <div
          className={`already-sent-row${alreadySent ? " checked" : ""}`}
          onClick={() => setAlreadySent((v) => !v)}
        >
          <div className="box" />
          <div className="label">이미 송금이 완료된 건입니다</div>
          <div className="hint2">체크 시 골든타임 플로우로 진행</div>
        </div>

        {submitError && (
          <div className="error-banner">
            <div className="title">{submitError}</div>
          </div>
        )}

        <div className="intake-submit">
          <button className="btn-block" disabled={!canSubmit} onClick={submit}>
            {submitting ? "접수 중..." : lookup ? "거래 접수" : "거래 접수 (고객 확인 후 활성화)"}
          </button>
        </div>
      </div>

      {lookup ? (
        <div className="lookup-panel">
          <div className="lookup-head">
            <div className="label">고객 조회 결과</div>
            <div className="lookup-badge">확인됨</div>
          </div>
          <div className="lookup-name">
            <div className="name">{lookup.name}</div>
            <div className="meta">
              {lookup.age}세 · {lookup.gender}
            </div>
          </div>
          {lookup.age >= 65 && (
            <div className="lookup-elderly">
              고령 금융소비자 보호 대상
              <br />
              <span className="sub">첫 거래 확대 기준 금액 50만 → 30만원</span>
            </div>
          )}
          <div className="lookup-rows">
            <div className="lookup-row">
              <div className="k">계좌 잔액</div>
              <div className="v">{Number(lookup.balance).toLocaleString()}원</div>
            </div>
            <div className="lookup-row">
              <div className="k">과거 최대 송금액</div>
              <div className="v">{Number(lookup.max_amount_ever).toLocaleString()}원</div>
            </div>
            <div className="lookup-row">
              <div className="k">최근 이용 채널</div>
              <div className="v wrap">{lookup.recent_channel}</div>
            </div>
          </div>
          {lookup.notable_activity && (
            <div className="lookup-notable">
              <div className="label">특이 동향</div>
              <div className="text">{lookup.notable_activity}</div>
            </div>
          )}
          <div className="lookup-foot">
            이름과 계좌번호가 모두 일치할 때만 표시됩니다. 신분증 확인 절차를 대체하지 않습니다.
          </div>
        </div>
      ) : (
        <div className="lookup-panel empty">
          <div className="label">고객 조회 결과</div>
          <div className="lookup-empty-title">표시할 정보가 없습니다</div>
          <div className="lookup-empty-text">
            등록된 고객으로 확인되면 나이·잔액·최근 이용 채널·특이 동향이 여기에 표시됩니다.
          </div>
        </div>
      )}
    </div>
  );
});

export default TransactionForm;
