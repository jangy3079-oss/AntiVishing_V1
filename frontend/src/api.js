const BASE = "/api";

async function handle(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `요청 실패 (${res.status})`);
  }
  return data;
}

export const api = {
  lookupCustomer: (name, accountNumber) =>
    fetch(`${BASE}/customer-lookup?${new URLSearchParams({ name, account_number: accountNumber })}`).then(
      handle
    ),
  listTestAccounts: () => fetch(`${BASE}/test-accounts`).then(handle),
  regenerateTestAccounts: (nPerArchetype) =>
    fetch(`${BASE}/dev/regenerate-test-accounts?${new URLSearchParams({ n_per_archetype: nPerArchetype })}`, {
      method: "POST",
    }).then(handle),
  createCase: (payload) =>
    fetch(`${BASE}/cases`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(handle),
  getCase: (caseId) => fetch(`${BASE}/cases/${caseId}`).then(handle),
  submitStt: (caseId, transcript) =>
    fetch(`${BASE}/cases/${caseId}/stt`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript }),
    }).then(handle),
  submitYesNo: (caseId, known_recipient, aware_of_true_purpose) =>
    fetch(`${BASE}/cases/${caseId}/yesno`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ known_recipient, aware_of_true_purpose }),
    }).then(handle),
  submitFreeText: (caseId, text) =>
    fetch(`${BASE}/cases/${caseId}/freetext`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }).then(handle),
  submitEscalation: (caseId, action) =>
    fetch(`${BASE}/cases/${caseId}/escalate-action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    }).then(handle),
  getLog: (caseId) => fetch(`${BASE}/cases/${caseId}/log`).then(handle),
};
