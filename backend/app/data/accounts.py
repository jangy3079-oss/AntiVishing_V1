"""
테스트용 고객·수취계좌 데이터셋.

기존에는 "6개 고정 시나리오 카드"를 화면에서 선택하는 방식이었지만, 실제 창구
업무를 재현하기 위해 아래처럼 흐름을 바꾼다.
    ① 고객 신분증 스캔 시뮬레이션: 고객 이름 + 본인 계좌번호로 CUSTOMERS를 조회
    ② 수취 계좌 입력: 수취 계좌번호로 RECIPIENTS를 조회 (은행명은 표시용 참고 정보)
두 조회 모두 화면에 힌트/목록을 노출하지 않는다(실제 창구처럼, 일치하지 않으면
그냥 "조회 실패"). 어떤 이름/계좌번호 조합이 어떤 성격의 케이스인지는 아래
CUSTOMERS/RECIPIENTS 정의와 docs/03_API명세서.md 부록에서만 확인 가능하다.

수취계좌 CSV(정상/이상거래)는 하드코딩된 위험 플래그가 아니라 analysis/ 폴더에서
실제 AI-Hub 금융거래 데이터를 분석해 확인한 특징을 반영해 만들었다:
- 분산입금 상대방 수: 계좌가 관측된 전체 기간 누적 기준으로는 이상연루 계좌가 정상 대비
  약 5배 많음(comparison_figures.py fig1). 다만 account_analysis.py가 실제 쓰는 "최근 72시간
  이내" 버전으로 좁혀서 다시 계산하면 정상(0.53)과 이상연루(0.61) 계좌의 차이가 크지 않아,
  이 72시간 윈도우 지표 자체의 판별력은 약하다(account_analysis.py의 _NORMAL_BASELINE 주석 참고).
- 일평균 거래빈도: 이상연루 계좌가 정상 대비 약 4배 높음(같은 정의로 실측 재현됨, 가장 신뢰할 만한 지표).
- 즉시인출비율/심야거래비중은 실측 데이터에서는 신호가 약했던(노이즈에 가까운)
  지표라, 데모 스토리텔링용으로만 일부 계좌(대포통장 전형 패턴)에 남겨두었고
  판단의 주 근거로 과장하지 않는다.
"""

# --- 고객 (창구에 온 사람). 이름 + 본인 계좌번호 조합으로만 조회된다. ---
CUSTOMERS = [
    {
        "name": "김영희",
        "account_number": "110-2233-445566",
        "age": 75,
        "gender": "여",
        "balance": 3_240_000,
        "recent_channel": "영업점 창구 방문 (본인)",
        "notable_activity": None,
        "avg_monthly_tx_count": 1.5,
        "avg_amount": 300_000,
        "max_amount_ever": 1_500_000,
        "trusted_recipient_account_numbers": {"352-1044-782211"},
    },
    {
        "name": "박철수",
        "account_number": "220-3344-556677",
        "age": 68,
        "gender": "남",
        "balance": 5_120_000,
        "recent_channel": "모바일 앱 인증 후 창구 방문",
        "notable_activity": None,
        "avg_monthly_tx_count": 3.5,
        "avg_amount": 500_000,
        "max_amount_ever": 2_000_000,
        "trusted_recipient_account_numbers": set(),
    },
    {
        "name": "이순자",
        "account_number": "330-4455-667788",
        "age": 80,
        "gender": "여",
        "balance": 26_140_500,
        "recent_channel": "영업점 창구 방문 (본인)",
        "notable_activity": (
            "2일 전 비대면(스마트폰 앱)으로 2,500만원 신용대출 실행 이력 있음. "
            "고령 고객의 비대면 대출 직후 창구 전액 송금은 대표적 주의 패턴."
        ),
        "avg_monthly_tx_count": 0.1,
        "avg_amount": 0,
        "max_amount_ever": 200_000,
        "trusted_recipient_account_numbers": set(),
    },
    {
        "name": "정민호",
        "account_number": "440-5566-778899",
        "age": 72,
        "gender": "남",
        "balance": 12_400_000,
        "recent_channel": "영업점 창구 방문 (본인)",
        "notable_activity": None,
        "avg_monthly_tx_count": 2.0,
        "avg_amount": 400_000,
        "max_amount_ever": 3_000_000,
        "trusted_recipient_account_numbers": set(),
    },
    {
        "name": "최영자",
        "account_number": "550-6677-889900",
        "age": 77,
        "gender": "여",
        "balance": 3_850_000,
        "recent_channel": "영업점 창구 방문 (본인)",
        "notable_activity": None,
        "avg_monthly_tx_count": 0.2,
        "avg_amount": 0,
        "max_amount_ever": 100_000,
        "trusted_recipient_account_numbers": set(),
    },
]

# --- 수취계좌. 계좌번호로만 조회된다(은행명은 표시용 참고 정보, 매칭에는 쓰지 않음). ---
# transactions_csv(상대 계좌 실제 입출금 내역)는 Tier2가 account_analysis로 직접 분석한다.
# early_warning_db_hit/biz_reg_verified는 거래내역만으로는 알 수 없는 별도 DB 조회 결과이므로
# 여기서 값으로 유지한다.
RECIPIENTS = [
    {
        "label": "김영희 아들 계좌",
        "bank": "국민은행",
        "account_number": "352-1044-782211",
        "transactions_csv": "REC_TRUSTED_01.csv",
        "early_warning_db_hit": False,
        "biz_reg_verified": None,
    },
    {
        "label": "'안전계좌' 명의 계좌",
        "bank": "하나은행",
        "account_number": "110-452-889931",
        "transactions_csv": "REC_SAFE_ACC.csv",
        "early_warning_db_hit": True,
        "biz_reg_verified": None,
    },
    {
        "label": "가구점 사업자 계좌",
        "bank": "신한은행",
        "account_number": "301-882-744102",
        "transactions_csv": "REC_FURNITURE.csv",
        "early_warning_db_hit": False,
        "biz_reg_verified": True,
    },
    {
        "label": "개인 명의 계좌(신규 급증 패턴)",
        "bank": "우리은행",
        "account_number": "643-210-099871",
        "transactions_csv": "REC_MULE_02.csv",
        "early_warning_db_hit": False,
        "biz_reg_verified": None,
    },
    {
        "label": "개인 명의 계좌(첫 거래)",
        "bank": "카카오뱅크",
        "account_number": "902-114-556602",
        "transactions_csv": "REC_NORMAL_01.csv",
        "early_warning_db_hit": False,
        "biz_reg_verified": None,
    },
]

# --- 알려진 보이스피싱/사기 스크립트 패턴 (RAG 대조용 참고 문서) ---
KNOWN_SCAM_PATTERNS = [
    {
        "id": "PROSECUTOR_IMPERSONATION",
        "summary": "검찰/금감원 등 기관 사칭, 계좌가 범죄에 연루되었다며 '안전계좌'로 이체 유도",
        "signals": ["검찰", "금감원", "안전계좌", "계좌 동결", "수사", "명의도용"],
    },
    {
        "id": "FAMILY_EMERGENCY",
        "summary": "자녀/가족을 사칭해 사고·합의금 등 긴급 상황을 조성, 신속한 송금 유도",
        "signals": ["사고", "합의금", "다급", "전화 바꿔서", "폰 고장", "급하게"],
    },
    {
        "id": "FAKE_INVESTMENT",
        "summary": "지인·텔레마케터 소개로 고수익 투자처를 안내하며 개인 계좌로 입금 유도",
        "signals": ["투자", "고수익", "소개", "리딩방", "텔레마케터"],
    },
    {
        "id": "LEGITIMATE_MERCHANT_DISCOUNT",
        "summary": "정상 사업자가 카드 수수료 절감을 위해 계좌이체 시 할인 제공 (선의의 거래)",
        "signals": ["가구", "계좌이체 할인", "현금영수증", "사업자"],
    },
]


def find_customer(name: str, account_number: str) -> dict | None:
    """이름+본인 계좌번호가 모두 일치해야 조회된다 (신분증 스캔 시뮬레이션)."""
    for c in CUSTOMERS:
        if c["name"] == name and c["account_number"] == account_number:
            return c
    return None


def find_recipient(account_number: str) -> dict | None:
    """수취 계좌번호로 조회한다."""
    for r in RECIPIENTS:
        if r["account_number"] == account_number:
            return r
    return None
