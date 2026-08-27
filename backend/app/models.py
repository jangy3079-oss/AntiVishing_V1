from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class CaseStatus(str, Enum):
    TIER1_LOW_RISK_COMPLETED = "TIER1_LOW_RISK_COMPLETED"
    TIER2_ESCALATED = "TIER2_ESCALATED"          # 애매함, STT/Y-N 대기
    STT_HARD_BLOCKED = "STT_HARD_BLOCKED"        # 통화중+강한 코칭 감지 -> 질문 없이 즉시 고위험
    AWAITING_YESNO = "AWAITING_YESNO"
    AWAITING_FREETEXT = "AWAITING_FREETEXT"
    FINAL_LOW_RISK = "FINAL_LOW_RISK"
    FINAL_HIGH_RISK = "FINAL_HIGH_RISK"
    GOLDEN_TIME_FREEZE_REQUESTED = "GOLDEN_TIME_FREEZE_REQUESTED"


class TransactionCreate(BaseModel):
    teller_id: str
    customer_name: str
    customer_account_number: str
    recipient_account_number: str
    recipient_bank: Optional[str] = None  # 창구직원이 입력한 은행명(표시용, 매칭에는 계좌번호만 사용)
    amount: int
    already_sent: bool = False


class SttSubmit(BaseModel):
    transcript: str


class YesNoAnswers(BaseModel):
    known_recipient: bool          # "아는 사람/사업체인가요?"
    aware_of_true_purpose: bool    # "이 돈의 정확한 용도를 알고 계신가요?"


class FreeTextSubmit(BaseModel):
    text: str


class EscalationAction(BaseModel):
    action: str  # confirm_with_sender | escalate_fsi | notify_guardian | freeze_request


class Case(BaseModel):
    id: str
    status: CaseStatus
    teller_id: str
    customer_name: str
    customer_account_number: str
    recipient_label: str
    recipient_bank: Optional[str] = None
    recipient_account_number: str
    amount: int
    already_sent: bool

    tier1: Optional[Dict[str, Any]] = None
    tier2: Optional[Dict[str, Any]] = None
    stt_result: Optional[Dict[str, Any]] = None
    yesno_answers: Optional[Dict[str, Any]] = None
    freetext_analysis: Optional[Dict[str, Any]] = None
    final_decision: Optional[Dict[str, Any]] = None
    escalation_log: List[Dict[str, Any]] = []
    conversation: List[Dict[str, Any]] = []  # 직원-고객 간 실제로 오간 질문/답변 기록

    next_action: Optional[str] = None  # 프론트에 "다음에 뭘 해야 하는지" 안내
