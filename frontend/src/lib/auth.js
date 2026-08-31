// 백엔드에 계정/인증 API가 없는 프로토타입이라, 계정 신청·로그인은 localStorage 기반
// 간이 디렉터리로 흉내낸다. 실제 서비스에서는 서버측 인증으로 교체되어야 한다.
const DIRECTORY_KEY = "antivishing_tellers";
const SESSION_KEY = "antivishing_session";

const SEED_TELLER = {
  name: "김도현",
  teller_id: "1043872",
  branch: "서울 중앙지점",
  password: "0000",
};

function readDirectory() {
  try {
    const raw = localStorage.getItem(DIRECTORY_KEY);
    const list = raw ? JSON.parse(raw) : [];
    if (!list.some((t) => t.teller_id === SEED_TELLER.teller_id)) {
      list.push(SEED_TELLER);
    }
    return list;
  } catch {
    return [SEED_TELLER];
  }
}

function writeDirectory(list) {
  localStorage.setItem(DIRECTORY_KEY, JSON.stringify(list));
}

export function signup({ name, teller_id, branch, password }) {
  if (!name || !teller_id || !branch || !password) {
    throw new Error("모든 항목을 입력해주세요.");
  }
  const list = readDirectory();
  if (list.some((t) => t.teller_id === teller_id)) {
    throw new Error("이미 등록된 행번입니다.");
  }
  list.push({ name, teller_id, branch, password });
  writeDirectory(list);
  return { name, teller_id, branch };
}

export function login({ teller_id, password }) {
  const list = readDirectory();
  const found = list.find((t) => t.teller_id === teller_id);
  if (!found || found.password !== password) {
    throw new Error("행번 또는 비밀번호가 올바르지 않습니다.");
  }
  const session = { name: found.name, teller_id: found.teller_id, branch: found.branch };
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

export function getSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function logout() {
  localStorage.removeItem(SESSION_KEY);
}
