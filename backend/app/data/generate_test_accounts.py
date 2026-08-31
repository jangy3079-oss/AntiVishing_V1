"""테스트 계좌 대량 생성 스크립트 (1회성 실행 도구, 서버 기동 시 자동 실행되지 않음).

목적: "이상계좌 판정이 하드코딩 라벨 아니냐"는 오해를 막기 위한 것.
현재도 위험 점수 자체는 계좌마다 박아둔 값이 아니라 account_analysis.py가
거래내역 CSV를 규칙기반+통계적 이상탐지로 실제 계산한 결과다. 다만 계좌 수가
9명/8개뿐이라 "몇 개 안 되는 걸 손으로 만든 것 아니냐"는 인상을 줄 수 있어,
여러 원형(정상/대포통장 등) 패턴을 무작위 파라미터로 다수 생성해 계좌 모집단을
키운다. 각 계좌의 최종 점수는 여기서 정하지 않고, 실행 후 account_analysis.py로
직접 계산해 검증한다(아래 __main__ 블록).

실행 방법:
    cd backend && python -m app.data.generate_test_accounts

실행하면:
1. account_transactions/GEN_*.csv 를 새로 만든다.
2. accounts_generated.json 에 생성된 고객/수취계좌 목록을 덮어쓴다.
   (accounts.py 는 모듈 로드 시 이 JSON을 읽어 기존 CUSTOMERS/RECIPIENTS 뒤에 이어붙인다.
   프론트 개발자 도구의 "랜덤 계좌 재생성" 버튼은 accounts.regenerate_generated_pool()을 통해
   서버를 재시작하지 않고 같은 일을 한다.)
   .py가 아니라 .json으로 저장하는 이유: uvicorn --reload는 *.py 파일이 바뀌면 서버를
   통째로 재시작한다. 예전에 결과를 .py로 저장했더니 "재생성" API 요청이 자기 자신을
   처리하는 도중 서버가 재시작되며 응답이 끊겨 프론트에 500 에러로 뜨는 문제가 있었다.
3. 생성된 계좌 전체를 account_analysis.py로 재계산해 점수 분포를 출력한다
   (하드코딩이 아니라 계산된 값이라는 것을 바로 확인할 수 있도록).

재현성을 위해 random.seed 고정. 개수를 늘리고 싶으면 N_PER_ARCHETYPE만 올려서
다시 실행하면 된다(기존 GEN_* 파일은 덮어쓴다).
"""
import os
import random

random.seed(42)

_HERE = os.path.dirname(__file__)
_CSV_DIR = os.path.join(_HERE, "account_transactions")

N_PER_ARCHETYPE = 5  # 원형(아래 6종) 당 생성 개수 -> 총 30개 수취계좌 + 30명 고객

SURNAMES_MASKED = ["김", "이", "박", "최", "정", "조", "강", "윤", "장", "임", "한", "오", "서", "신", "권"]
GIVEN_NAMES = [
    "민준", "서연", "도윤", "지우", "예준", "하윤", "시우", "채원", "주원", "수아",
    "지호", "은서", "건우", "다은", "우진", "지민", "현우", "소율", "준서", "예은",
]
BANKS = ["국민은행", "신한은행", "하나은행", "우리은행", "농협은행", "기업은행", "카카오뱅크", "토스뱅크", "신협", "케이뱅크"]
CHANNELS = ["영업점 창구 방문 (본인)", "모바일 앱 인증 후 창구 방문"]

_used_customer_accounts = {
    "110-2233-445566", "220-3344-556677", "330-4455-667788", "440-5566-778899",
    "550-6677-889900", "660-7788-990011", "770-8899-001122", "880-9900-112233",
    "990-0011-223344",
}
_used_recipient_accounts = {
    "352-1044-782211", "110-452-889931", "301-882-744102", "643-210-099871",
    "902-114-556602", "204-778-330091", "823-119-004432", "701-334-882210",
}


def _rand_account_number(used: set) -> str:
    while True:
        acc = f"{random.randint(100, 999)}-{random.randint(1000, 9999)}-{random.randint(100000, 999999)}"
        if acc not in used:
            used.add(acc)
            return acc


def _rand_name() -> str:
    return random.choice(SURNAMES_MASKED) + random.choice(GIVEN_NAMES)


def _masked(surname_pool=SURNAMES_MASKED) -> str:
    return random.choice(surname_pool) + "OO"


def _fmt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


from datetime import datetime, timedelta  # noqa: E402

_BASE = datetime(2026, 8, 5, 8, 0, 0)


def _write_csv(filename: str, rows: list[tuple]) -> None:
    path = os.path.join(_CSV_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write("거래일시,구분,금액,거래후잔액,상대방\n")
        for dt, kind, amount, balance, counterparty in rows:
            f.write(f"{_fmt(dt)},{kind},{amount},{balance},{counterparty}\n")


def _gen_normal_light() -> list[tuple]:
    """정상: 가족 등 소수 상대에게서 가끔 소액 입금. 즉시인출/야간거래 없음."""
    rows = []
    bal = 0
    n = random.randint(1, 3)
    t = _BASE - timedelta(days=random.randint(5, 40))
    payer = _masked()
    for _ in range(n):
        amt = random.randint(50_000, 500_000)
        bal += amt
        rows.append((t, "입금", amt, bal, payer))
        t += timedelta(days=random.randint(3, 20), hours=random.randint(0, 8))
    return rows


def _gen_normal_business() -> list[tuple]:
    """정상 사업자: 여러 거래처에서 낮 시간 분산 입금 + 임대료/매입대금 등 정기 출금."""
    rows = []
    bal = 0
    t = _BASE - timedelta(days=random.randint(2, 6))
    n_in = random.randint(3, 6)
    for _ in range(n_in):
        amt = random.randint(600_000, 1_400_000)
        bal += amt
        hour = random.randint(9, 18)
        rows.append((t.replace(hour=hour), "입금", amt, bal, _rand_name()))
        t += timedelta(days=1)
    for label in random.sample(["임대료", "매입대금", "관리비", "인건비"], k=2):
        amt = random.randint(200_000, 600_000)
        bal -= amt
        t += timedelta(hours=random.randint(2, 10))
        rows.append((t, "출금", amt, max(bal, 0), label))
    return rows


def _gen_mule_immediate() -> list[tuple]:
    """대포통장 전형: 입금 직후(수시간 내) 대부분 인출."""
    rows = []
    bal = 0
    t = _BASE - timedelta(days=random.randint(1, 3))
    n = random.randint(4, 7)
    for _ in range(n):
        amt = random.randint(1_000_000, 3_500_000)
        bal += amt
        rows.append((t, "입금", amt, bal, _masked()))
        t += timedelta(hours=random.uniform(1, 4))
        out = int(amt * random.uniform(0.85, 0.98))
        bal -= out
        rows.append((t, "출금", out, max(bal, 0), "ATM 출금"))
        t += timedelta(hours=random.uniform(4, 10))
    return rows


def _gen_mule_structuring() -> list[tuple]:
    """구조화 의심: 72시간 내 다수(5명 이상)의 서로 다른 상대로부터 분산 입금."""
    rows = []
    bal = 0
    n = random.randint(5, 9)
    t = _BASE - timedelta(hours=random.randint(40, 60))
    for _ in range(n):
        amt = random.randint(200_000, 400_000)
        bal += amt
        rows.append((t, "입금", amt, bal, _masked()))
        t += timedelta(hours=random.uniform(2, 8))
    out = int(bal * random.uniform(0.2, 0.4))
    bal -= out
    t += timedelta(hours=random.uniform(20, 40))  # 입금들과 6시간 이상 떨어뜨려 즉시인출로 안 잡히게
    rows.append((t, "출금", out, max(bal, 0), "생활비"))
    return rows


def _gen_mule_night() -> list[tuple]:
    """심야거래 비중이 높은 패턴 (23시~06시 집중)."""
    rows = []
    bal = 0
    t = _BASE.replace(hour=23, minute=0) - timedelta(days=random.randint(1, 2))
    n = random.randint(6, 10)
    for _ in range(n):
        amt = random.randint(300_000, 900_000)
        bal += amt
        night_hour = random.choice([23, 0, 1, 2, 3, 4, 5])
        t2 = t.replace(hour=night_hour % 24)
        rows.append((t2, "입금", amt, bal, _masked()))
        t2 += timedelta(hours=random.uniform(0.5, 2))
        out = int(amt * random.uniform(0.5, 0.9))
        bal -= out
        rows.append((t2, "출금", out, max(bal, 0), "ATM 출금"))
        t += timedelta(hours=random.uniform(20, 30))
    return rows


def _gen_mule_combo() -> list[tuple]:
    """복합 고위험: 즉시인출 + 분산입금 + 심야거래가 함께 나타남(가장 위험도 높은 원형)."""
    rows = []
    bal = 0
    t = _BASE - timedelta(hours=random.randint(48, 60))
    n = random.randint(6, 10)
    for _ in range(n):
        amt = random.randint(800_000, 2_000_000)
        bal += amt
        hour = random.choice([22, 23, 0, 1, 2, 9, 13, 17])
        t2 = t.replace(hour=hour % 24)
        rows.append((t2, "입금", amt, bal, _masked()))
        t2 += timedelta(hours=random.uniform(0.5, 3))
        out = int(amt * random.uniform(0.8, 0.97))
        bal -= out
        rows.append((t2, "출금", out, max(bal, 0), "타행이체"))
        t += timedelta(hours=random.uniform(6, 14))
    return rows


_ARCHETYPES = {
    "normal_light": (_gen_normal_light, "개인 명의 계좌(가족 송금 추정)", False, None),
    "normal_business": (_gen_normal_business, "개인사업자 계좌(거래처 입금)", False, True),
    "mule_immediate": (_gen_mule_immediate, "개인 명의 계좌(즉시인출 패턴)", True, None),
    "mule_structuring": (_gen_mule_structuring, "개인 명의 계좌(분산입금 패턴)", False, None),
    "mule_night": (_gen_mule_night, "개인 명의 계좌(심야거래 패턴)", False, None),
    "mule_combo": (_gen_mule_combo, "개인 명의 계좌(복합 이상거래 패턴)", True, None),
}


def generate():
    generated_customers = []
    generated_recipients = []

    gen_idx = 0
    for archetype, (gen_fn, label_prefix, ew_hit, biz_verified) in _ARCHETYPES.items():
        for _ in range(N_PER_ARCHETYPE):
            gen_idx += 1
            csv_name = f"GEN_{archetype.upper()}_{gen_idx:02d}.csv"
            rows = gen_fn()
            _write_csv(csv_name, rows)

            recipient_acc = _rand_account_number(_used_recipient_accounts)
            biz_ok = biz_verified if biz_verified is None else (random.random() < 0.7)
            generated_recipients.append({
                "label": f"{label_prefix} #{gen_idx}",
                "bank": random.choice(BANKS),
                "account_number": recipient_acc,
                "transactions_csv": csv_name,
                "early_warning_db_hit": bool(ew_hit and random.random() < 0.5),
                "biz_reg_verified": biz_ok,
            })

            customer_acc = _rand_account_number(_used_customer_accounts)
            age = random.choice([random.randint(28, 64), random.randint(65, 88)])
            balance = random.randint(1_000_000, 40_000_000)
            trusted = {recipient_acc} if archetype == "normal_light" and random.random() < 0.4 else set()
            generated_customers.append({
                "name": _rand_name(),
                "account_number": customer_acc,
                "age": age,
                "gender": random.choice(["남", "여"]),
                "balance": balance,
                "recent_channel": random.choice(CHANNELS),
                "notable_activity": None,
                "avg_monthly_tx_count": round(random.uniform(0.1, 5.0), 1),
                "avg_amount": random.choice([0, random.randint(100_000, 800_000)]),
                "max_amount_ever": random.randint(200_000, 5_000_000),
                "trusted_recipient_account_numbers": trusted,
            })

    return generated_customers, generated_recipients


GENERATED_JSON_PATH = os.path.join(_HERE, "accounts_generated.json")


def save_json(customers: list[dict], recipients: list[dict], path: str = GENERATED_JSON_PATH) -> None:
    """생성 결과를 JSON으로 저장한다.

    주의: 반드시 .py가 아닌 .json으로 저장해야 한다. uvicorn --reload(README에 안내된 로컬 실행
    방식)는 기본적으로 *.py 파일 변경을 감시하다가 바뀌면 서버 프로세스를 재시작하는데, 예전에
    이 결과를 accounts_generated.py로 저장했을 때 "랜덤 계좌 재생성" API 요청이 자기 자신을
    처리하는 도중에 서버가 재시작되면서 응답이 끊겨 프론트에 500 에러로 보이는 문제가 있었다.
    """
    def _jsonable(rows):
        out = []
        for row in rows:
            row = dict(row)
            if isinstance(row.get("trusted_recipient_account_numbers"), set):
                row["trusted_recipient_account_numbers"] = sorted(row["trusted_recipient_account_numbers"])
            out.append(row)
        return out

    import json

    with open(path, "w", encoding="utf-8") as f:
        json.dump({"customers": _jsonable(customers), "recipients": _jsonable(recipients)}, f, ensure_ascii=False, indent=2)


def load_json(path: str = GENERATED_JSON_PATH) -> tuple[list[dict], list[dict]]:
    """저장된 생성 계좌를 불러온다. 파일이 없으면(최초 실행 전) 빈 목록을 반환한다."""
    import json

    if not os.path.exists(path):
        return [], []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    customers = data.get("customers", [])
    for c in customers:
        c["trusted_recipient_account_numbers"] = set(c.get("trusted_recipient_account_numbers", []))
    return customers, data.get("recipients", [])


if __name__ == "__main__":
    import sys

    sys.path.insert(0, os.path.join(_HERE, "..", "..", ".."))
    customers, recipients = generate()

    save_json(customers, recipients)
    print(f"생성 완료: 고객 {len(customers)}명, 수취계좌 {len(recipients)}개 -> {GENERATED_JSON_PATH}")

    # 방금 만든 CSV들을 실제로 재계산해서 점수 분포를 검증한다(하드코딩이 아님을 확인).
    from app.pipeline import account_analysis  # noqa: E402

    print("\n--- 생성 계좌 위험점수 재계산 검증 (account_analysis.py, 규칙기반+통계) ---")
    scores = []
    for r in recipients:
        csv_path = os.path.join(_CSV_DIR, r["transactions_csv"])
        analysis = account_analysis.analyze_account(csv_path)
        score = analysis["rule_score"]
        if r["early_warning_db_hit"]:
            score += 50
        if r["biz_reg_verified"] is True:
            score -= 40
        if analysis["anomaly_flag"]:
            score += 20
        score = max(0, min(100, score))
        scores.append(score)
        print(f"{r['transactions_csv']:<28} rule={analysis['rule_score']:>3} anomaly={analysis['anomaly_flag']!s:<5} -> score={score}")

    print(f"\n점수 분포: min={min(scores)} max={max(scores)} mean={sum(scores)/len(scores):.1f}")
    print("모든 점수는 CSV 거래내역에서 매번 새로 계산된 값이며, 계좌별로 미리 박아둔 라벨이 아니다.")
