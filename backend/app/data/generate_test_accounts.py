"""테스트 계좌 대량 생성 스크립트 (1회성 실행 도구, 서버 기동 시 자동 실행되지 않음).

목적: "이상계좌 판정이 하드코딩 라벨 아니냐"는 오해를 막기 위한 것.
현재도 위험 점수 자체는 계좌마다 박아둔 값이 아니라 account_analysis.py가
거래내역 CSV를 규칙기반+통계적 이상탐지로 실제 계산한 결과다. 다만 계좌 수가
9명/8개뿐이라 "몇 개 안 되는 걸 손으로 만든 것 아니냐"는 인상을 줄 수 있어,
여러 원형(정상/대포통장 등) 패턴을 무작위 파라미터로 다수 생성해 계좌 모집단을
키운다. 각 계좌의 최종 점수는 여기서 정하지 않고, 실행 후 account_analysis.py로
직접 계산해 검증한다(아래 __main__ 블록).

관측 기간(v2, 2026-08): 예전 버전은 계좌마다 며칠~2일짜리 거래내역만 담고 있었다.
"계좌 위치 분석"(account_figures.py)이 비교하는 AI-Hub 실측 모집단은 계좌를
수개월 단위로 관측한 데이터라서, 이 스케일 불일치 때문에 거래가 1~2건뿐인 계좌는
"일평균 거래빈도"가 하한값(관측기간 최소 1일 처리) 때문에 실제보다 수십~수백 배
부풀려져 보이는 문제가 있었다(거래 1건짜리 정상 계좌가 "정상군 중심에서 매우 멀다"로
나온 사례로 실제 확인됨). 지금은 모든 계좌가 최근 90일(3개월) 전체에 걸친 거래내역을
갖도록 만들어 이 문제를 근본적으로 줄인다 — 이상계좌도 "최근 며칠 새 갑자기 의심거래가
몰린 계좌"처럼, 평소엔 조용하다가 최근에 튀는 현실적인 서사로 구성한다.

원형(v2): 정상/이상 모두 "전형적인 것"과 "경계선/애매한 것"을 섞어 만든다(요청 반영).
- 정상: normal_light(전형), normal_business(전형), normal_freelance(다수 소액 거래처라
  약간 특이해 보일 수 있음), normal_saver(정기이체가 잦아 약간 특이해 보일 수 있음)
- 이상: mule_severe_combo/mule_severe_immediate(누가 봐도 전형적인 대포통장),
  mule_moderate_immediate/mule_moderate_structuring(규칙 문턱값에 걸치는 애매한 정도),
  mule_subtle_borderline(지표 하나만 문턱값 바로 아래/위로 걸치는 아주 애매한 경계선 사례)

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

N_PER_ARCHETYPE = 5  # 원형(아래 9종) 당 생성 개수 -> 총 45개 수취계좌 + 45명 고객

# 계좌 위치 분석(account_figures.py)이 비교하는 AI-Hub 실측 모집단과 관측 기간 스케일을
# 맞추기 위해, 모든 계좌가 이 기간(일) 전체에 걸친 거래내역을 갖도록 생성한다.
_OBSERVATION_DAYS = 90

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

_NOW = datetime(2026, 8, 30, 9, 0, 0)  # "오늘"에 해당하는 기준 시각(창구에서 조회하는 시점)
_WINDOW_START = _NOW - timedelta(days=_OBSERVATION_DAYS)


def _at(days_from_start: float, hour: float) -> datetime:
    """_WINDOW_START로부터 days_from_start일 지난 날짜의, hour시(0~24, 소수 가능)에 해당하는
    시각을 만든다. `_WINDOW_START + timedelta(hours=hour)`처럼 더하면 _WINDOW_START 자체가
    이미 09시라 시각이 밀려서(예: hour=21 의도해도 실제로는 09+21=30시=다음날 06시가 되는 등)
    "야간 거래 없음"으로 설계한 원형에서 의도치 않게 심야 시간대로 넘어가는 버그가 있었다."""
    base_day = _WINDOW_START + timedelta(days=days_from_start)
    midnight = base_day.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight + timedelta(minutes=round((hour % 24) * 60))


def _write_csv(filename: str, rows: list[tuple]) -> None:
    rows = sorted(rows, key=lambda r: r[0])
    path = os.path.join(_CSV_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write("거래일시,구분,금액,거래후잔액,상대방\n")
        bal = 0
        for dt, kind, amount, _stale_balance, counterparty in rows:
            bal = bal + amount if kind == "입금" else max(bal - amount, 0)
            f.write(f"{_fmt(dt)},{kind},{amount},{bal},{counterparty}\n")


def _gen_normal_light() -> list[tuple]:
    """정상(전형): 가족 등 소수 상대에게서 90일 내내 가끔 소액 입금. 즉시인출/야간거래 없음."""
    rows = []
    n = random.randint(3, 8)
    payer = _masked()
    second_payer = _masked() if random.random() < 0.3 else None
    for _ in range(n):
        t = _at(random.uniform(0, _OBSERVATION_DAYS - 1), random.uniform(8, 21))
        amt = random.randint(50_000, 500_000)
        who = second_payer if (second_payer and random.random() < 0.25) else payer
        rows.append((t, "입금", amt, None, who))
    return rows


def _gen_normal_business() -> list[tuple]:
    """정상(전형) 사업자: 90일 내내 단골 거래처들로부터 낮 시간 분산 입금 + 매달 임대료 등
    정기 출금. 거래처를 소수 고정 풀에서 반복 사용해(실제 단골 거래처처럼) 우연히 72시간 내에
    여러 건이 몰려도 같은 상대인 경우가 많게 한다 — 매번 다른 이름이면, 거래가 잦은 정상
    사업자도 "72시간 내 다수 상대 분산입금" 규칙에 우연히 걸릴 수 있어서다."""
    rows = []
    clients = [_rand_name() for _ in range(random.randint(5, 8))]
    n_in = random.randint(18, 35)
    for _ in range(n_in):
        t = _at(random.uniform(0, _OBSERVATION_DAYS - 1), random.uniform(9, 18))
        amt = random.randint(400_000, 1_400_000)
        rows.append((t, "입금", amt, None, random.choice(clients)))
    for month_offset in [10, 40, 70]:  # 매달 임대료/관리비
        for label in random.sample(["임대료", "매입대금", "관리비", "인건비"], k=random.randint(1, 2)):
            t = _at(month_offset + random.uniform(-2, 2), random.uniform(10, 16))
            amt = random.randint(200_000, 600_000)
            rows.append((t, "출금", amt, None, label))
    return rows


def _gen_normal_freelance() -> list[tuple]:
    """정상(약간 특이): 프리랜서/소규모 판매자 — 반복 거래처 풀에서 소액 입금이 잦다.
    상대방 수가 많아 "분산입금"처럼 보일 여지가 있지만, 단골 위주라 실제 서로 다른 상대 수는
    생각보다 적고 72시간 내로 몰리지도 않아 구조화 의심 패턴과는 다르다(정상 판정 유지가 맞음)."""
    rows = []
    clients = [_masked() for _ in range(random.randint(4, 7))]
    n_in = random.randint(12, 22)
    for _ in range(n_in):
        t = _at(random.uniform(0, _OBSERVATION_DAYS - 1), random.uniform(9, 22))
        amt = random.randint(30_000, 300_000)
        rows.append((t, "입금", amt, None, random.choice(clients)))
    for _ in range(random.randint(2, 4)):
        t = _at(random.uniform(0, _OBSERVATION_DAYS - 1), random.uniform(10, 20))
        amt = random.randint(100_000, 400_000)
        rows.append((t, "출금", amt, None, random.choice(["생활비", "재료비", "통신비"])))
    return rows


def _gen_normal_saver() -> list[tuple]:
    """정상(약간 특이): 정기적금처럼 규칙적으로 입금 후 일부를 옮기는 습관이 있는 계좌.
    이체 타이밍을 항상 6시간(즉시인출 판정 기준) 이후로 둬서, 습관적 이체일 뿐 인출 패턴이
    아니라는 걸 데이터로도 구분되게 한다."""
    rows = []
    n_cycles = random.randint(6, 10)
    payer = _masked()
    for i in range(n_cycles):
        day = i * (_OBSERVATION_DAYS / n_cycles) + random.uniform(0, 3)
        t = _at(day, random.uniform(9, 19))
        amt = random.randint(300_000, 900_000)
        rows.append((t, "입금", amt, None, "본인(급여)" if i % 2 == 0 else payer))
        if random.random() < 0.6:
            t2 = t + timedelta(hours=random.uniform(10, 30))  # 6시간 훨씬 이후
            out = int(amt * random.uniform(0.3, 0.5))
            rows.append((t2, "출금", out, None, "정기적금 이체"))
    return rows


def _gen_mule_severe_combo() -> list[tuple]:
    """이상(전형·고위험): 평소엔 조용하다가 최근 며칠 새 즉시인출+분산입금+심야가 한꺼번에 몰린다."""
    rows = []
    # 배경: 90일 전반부에 아주 가벼운 활동 1~2건(원래 있던 계좌처럼 보이게)
    for _ in range(random.randint(0, 2)):
        t = _at(random.uniform(5, 60), random.uniform(9, 18))
        rows.append((t, "입금", random.randint(50_000, 200_000), None, _masked()))
    # 최근 며칠: 의심 burst
    n = random.randint(6, 10)
    t = _NOW - timedelta(days=random.uniform(1.5, 3))
    for _ in range(n):
        amt = random.randint(800_000, 2_000_000)
        hour = random.choice([22, 23, 0, 1, 2, 9, 13, 17])
        t2 = t.replace(hour=hour % 24)
        rows.append((t2, "입금", amt, None, _masked()))
        t3 = t2 + timedelta(hours=random.uniform(0.5, 3))
        out = int(amt * random.uniform(0.8, 0.97))
        rows.append((t3, "출금", out, None, "타행이체"))
        t += timedelta(hours=random.uniform(6, 14))
    return rows


def _gen_mule_severe_immediate() -> list[tuple]:
    """이상(전형·고위험): 평소 조용하다가 최근 입금 즉시(수시간 내) 대부분 인출을 반복."""
    rows = []
    for _ in range(random.randint(0, 2)):
        t = _at(random.uniform(5, 60), random.uniform(9, 18))
        rows.append((t, "입금", random.randint(50_000, 200_000), None, _masked()))
    n = random.randint(5, 8)
    t = _NOW - timedelta(days=random.uniform(1, 2.5))
    for _ in range(n):
        amt = random.randint(1_000_000, 3_500_000)
        rows.append((t, "입금", amt, None, _masked()))
        t2 = t + timedelta(hours=random.uniform(1, 4))
        out = int(amt * random.uniform(0.88, 0.98))
        rows.append((t2, "출금", out, None, "ATM 출금"))
        t += timedelta(hours=random.uniform(4, 10))
    return rows


def _gen_mule_moderate_immediate() -> list[tuple]:
    """이상(중간 등급): 즉시인출비율이 규칙 문턱값(80%)에 못 미치는 50~70%대 — "의심스럽지만
    확정적이진 않은" 계좌. 규칙 점수만으론 안 걸릴 수 있고, 통계적 이상탐지가 보조로 잡을 수 있다."""
    rows = []
    for _ in range(random.randint(1, 3)):
        t = _at(random.uniform(5, 70), random.uniform(9, 20))
        rows.append((t, "입금", random.randint(80_000, 300_000), None, _masked()))
    n = random.randint(4, 7)
    t = _NOW - timedelta(days=random.uniform(3, 6))
    for _ in range(n):
        amt = random.randint(500_000, 1_500_000)
        rows.append((t, "입금", amt, None, _masked()))
        if random.random() < 0.6:  # 매번 인출하지는 않음(전형적 패턴과의 차이)
            t2 = t + timedelta(hours=random.uniform(1, 5))
            out = int(amt * random.uniform(0.45, 0.7))
            rows.append((t2, "출금", out, None, "이체"))
        t += timedelta(hours=random.uniform(10, 30))
    return rows


def _gen_mule_moderate_structuring() -> list[tuple]:
    """이상(중간 등급): 72시간 내 서로 다른 입금 상대가 규칙 문턱값(5명)에 딱 걸치는 수준(5~6명)."""
    rows = []
    for _ in range(random.randint(1, 3)):
        t = _at(random.uniform(5, 70), random.uniform(9, 20))
        rows.append((t, "입금", random.randint(80_000, 250_000), None, _masked()))
    n = random.randint(5, 6)
    t = _NOW - timedelta(hours=random.uniform(40, 65))
    for _ in range(n):
        amt = random.randint(200_000, 400_000)
        rows.append((t, "입금", amt, None, _masked()))
        t += timedelta(hours=random.uniform(3, 10))
    t_out = t + timedelta(hours=random.uniform(20, 40))
    rows.append((t_out, "출금", random.randint(300_000, 700_000), None, "생활비"))
    return rows


def _gen_mule_subtle_borderline() -> list[tuple]:
    """이상(경계선·매우 애매): 지표 하나만 문턱값 바로 아래에서 걸친다(즉시인출비율 78%
    안팎, 딱 하나만 애매하고 나머지는 정상 범위) — 실무에서도 판단이 갈릴 법한 사례."""
    rows = []
    for _ in range(random.randint(2, 4)):
        t = _at(random.uniform(0, _OBSERVATION_DAYS - 5), random.uniform(9, 20))
        rows.append((t, "입금", random.randint(100_000, 400_000), None, _masked()))
    # 최근 1~2건만 애매하게 빠른 인출(78% 안팎, 80% 문턱값 바로 아래)
    for _ in range(random.randint(2, 3)):
        t = _NOW - timedelta(days=random.uniform(0.5, 4), hours=random.uniform(0, 10))
        amt = random.randint(500_000, 1_200_000)
        rows.append((t, "입금", amt, None, _masked()))
        t2 = t + timedelta(hours=random.uniform(2, 5))
        out = int(amt * random.uniform(0.72, 0.79))
        rows.append((t2, "출금", out, None, "이체"))
    return rows


_ARCHETYPES = {
    "normal_light": (_gen_normal_light, "개인 명의 계좌(가족 송금 추정)", False, None),
    "normal_business": (_gen_normal_business, "개인사업자 계좌(거래처 입금)", False, True),
    "normal_freelance": (_gen_normal_freelance, "개인 명의 계좌(프리랜서·다수 소액 거래처)", False, None),
    "normal_saver": (_gen_normal_saver, "개인 명의 계좌(정기이체 습관)", False, None),
    "mule_severe_combo": (_gen_mule_severe_combo, "개인 명의 계좌(최근 급증·복합 이상거래)", True, None),
    "mule_severe_immediate": (_gen_mule_severe_immediate, "개인 명의 계좌(최근 급증·즉시인출)", True, None),
    "mule_moderate_immediate": (_gen_mule_moderate_immediate, "개인 명의 계좌(즉시인출 의심·중간등급)", False, None),
    "mule_moderate_structuring": (_gen_mule_moderate_structuring, "개인 명의 계좌(분산입금 의심·중간등급)", False, None),
    "mule_subtle_borderline": (_gen_mule_subtle_borderline, "개인 명의 계좌(경계선 사례)", False, None),
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
        print(f"{r['transactions_csv']:<32} txn={analysis['txn_count']:>3} rule={analysis['rule_score']:>3} anomaly={analysis['anomaly_flag']!s:<5} -> score={score}")

    print(f"\n점수 분포: min={min(scores)} max={max(scores)} mean={sum(scores)/len(scores):.1f}")
    print("모든 점수는 CSV 거래내역에서 매번 새로 계산된 값이며, 계좌별로 미리 박아둔 라벨이 아니다.")
