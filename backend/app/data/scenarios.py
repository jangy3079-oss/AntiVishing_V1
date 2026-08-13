"""
고정 목업 데이터: 고객, 수취계좌, 조기경보DB, 신뢰 수취인 목록, 6개 고정 시나리오.
실제 코어뱅킹/조기경보DB/통신사 API 연동 없이 로컬 테스트용으로 하드코딩.
"""

# --- 고객 (창구에 온 사람) ---
CUSTOMERS = {
    "CUST001": {"name": "김영희", "age": 75, "avg_monthly_tx_count": 1.5, "avg_amount": 300_000, "max_amount_ever": 1_500_000},
    "CUST002": {"name": "박철수", "age": 68, "avg_monthly_tx_count": 3.5, "avg_amount": 500_000, "max_amount_ever": 2_000_000},
    "CUST003": {"name": "이순자", "age": 80, "avg_monthly_tx_count": 0.1, "avg_amount": 0, "max_amount_ever": 200_000},
    "CUST004": {"name": "정민호", "age": 72, "avg_monthly_tx_count": 2.0, "avg_amount": 400_000, "max_amount_ever": 3_000_000},
    "CUST005": {"name": "최영자", "age": 77, "avg_monthly_tx_count": 0.2, "avg_amount": 0, "max_amount_ever": 100_000},
}

# --- 신뢰 수취인 등록 목록 (customer_id -> set of recipient_id) ---
TRUSTED_RECIPIENTS = {
    "CUST001": {"REC_TRUSTED_01"},
}

# --- 수취계좌 ---
# recent_inbound_senders_72h/rapid_full_withdrawal_pattern은 더 이상 하드코딩하지 않고,
# transactions_csv(상대 계좌 실제 입출금 내역)를 Tier2에서 직접 분석해 계산한다.
# early_warning_db_hit/biz_reg_verified는 거래내역만으로는 알 수 없는 별도 DB 조회 결과이므로 유지.
RECIPIENTS = {
    "REC_TRUSTED_01": {
        "label": "김영희 아들 계좌",
        "account_number": "352-1044-782211",
        "transactions_csv": "REC_TRUSTED_01.csv",
        "early_warning_db_hit": False,
        "biz_reg_verified": None,
    },
    "REC_SAFE_ACC": {
        "label": "'안전계좌' 명의 계좌",
        "account_number": "110-452-889931",
        "transactions_csv": "REC_SAFE_ACC.csv",
        "early_warning_db_hit": True,
        "biz_reg_verified": None,
    },
    "REC_FURNITURE": {
        "label": "가구점 사업자 계좌",
        "account_number": "301-882-744102",
        "transactions_csv": "REC_FURNITURE.csv",
        "early_warning_db_hit": False,
        "biz_reg_verified": True,
    },
    "REC_MULE_02": {
        "label": "개인 명의 계좌(신규 급증 패턴)",
        "account_number": "643-210-099871",
        "transactions_csv": "REC_MULE_02.csv",
        "early_warning_db_hit": False,
        "biz_reg_verified": None,
    },
    "REC_NORMAL_01": {
        "label": "개인 명의 계좌(첫 거래)",
        "account_number": "902-114-556602",
        "transactions_csv": "REC_NORMAL_01.csv",
        "early_warning_db_hit": False,
        "biz_reg_verified": None,
    },
}

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

# --- 6개 고정 시나리오 ---
SCENARIOS = [
    {
        "id": "S1_NORMAL",
        "title": "정상 송금 (신뢰 수취인)",
        "customer_id": "CUST001",
        "recipient_id": "REC_TRUSTED_01",
        "amount": 400_000,
        "already_sent": False,
        "expected": "TIER1 저위험 → 즉시 완료",
    },
    {
        "id": "S2_PROSECUTOR_SCAM",
        "title": "명백한 보이스피싱 (검찰 사칭 · 안전계좌)",
        "customer_id": "CUST003",
        "recipient_id": "REC_SAFE_ACC",
        "amount": 25_000_000,
        "already_sent": False,
        "expected": "TIER2 고위험 → STT 강한 코칭 감지 시 하드블록",
        "sample_stt_transcript": "검찰청이라고 하면서 제 명의가 범죄에 연루됐으니 지금 바로 안전계좌로 옮기라고 계속 통화하고 계세요.",
    },
    {
        "id": "S3_FURNITURE_BENIGN",
        "title": "애매하지만 선의의 거래 (가구점 할인)",
        "customer_id": "CUST002",
        "recipient_id": "REC_FURNITURE",
        "amount": 800_000,
        "already_sent": False,
        "expected": "TIER2 애매 → Y/N·자유텍스트에서 정상 확인",
        "sample_freetext": "이사할 때 쓸 가구를 사면서 계좌이체하면 카드 수수료만큼 싸게 해준다고 해서 이체하는 거예요.",
    },
    {
        "id": "S4_MULE_SUSPECT",
        "title": "대포통장 의심 애매 케이스 (투자 사기)",
        "customer_id": "CUST004",
        "recipient_id": "REC_MULE_02",
        "amount": 9_000_000,
        "already_sent": False,
        "expected": "TIER2 애매 → 자유텍스트 LLM 패턴대조 → 위험높음",
        "sample_freetext": "아는 사람이 소개해준 투자처인데 리딩방에서 알려준 계좌로 입금하면 고수익을 준다고 해서요.",
    },
    {
        "id": "S5_FAMILY_IMPERSONATION",
        "title": "고령층 첫 거래 이상 송금 (자녀 사칭)",
        "customer_id": "CUST005",
        "recipient_id": "REC_NORMAL_01",
        "amount": 3_000_000,
        "already_sent": False,
        "expected": "TIER2 애매 → 자유텍스트 패턴대조 → 위험높음",
        "sample_freetext": "딸이 전화로 사고가 났다고 다급하게 말하면서 합의금이 필요하다고 이 계좌로 보내달라고 했어요.",
    },
    {
        "id": "S6_ALREADY_SENT",
        "title": "이미 송금 완료 후 뒤늦게 의심 (골든타임)",
        "customer_id": "CUST001",
        "recipient_id": "REC_SAFE_ACC",
        "amount": 18_000_000,
        "already_sent": True,
        "expected": "골든타임 내 자동 지급정지 요청",
        "sample_stt_transcript": "아드님이 사고쳤다고 전화받고 급하게 보냈는데 지금 생각하니 이상해요.",
    },
]


def get_scenario(scenario_id: str):
    for s in SCENARIOS:
        if s["id"] == scenario_id:
            return s
    return None
