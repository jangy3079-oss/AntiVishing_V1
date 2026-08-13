"""케이스 저장소 (in-memory) + 로깅. 로컬 테스트용이라 프로세스 재시작 시 초기화된다."""
import uuid
from typing import Dict

_CASES: Dict[str, dict] = {}
_LOG: list[dict] = []


def create_case(data: dict) -> dict:
    case_id = str(uuid.uuid4())[:8]
    case = {"id": case_id, **data}
    _CASES[case_id] = case
    log_event(case_id, "case_created", data)
    return case


def get_case(case_id: str) -> dict | None:
    return _CASES.get(case_id)


def update_case(case_id: str, **fields) -> dict:
    case = _CASES[case_id]
    case.update(fields)
    return case


def add_conversation(case_id: str, question: str, answer: str):
    """직원-고객 간 실제 질문/답변 한 턴을 케이스 대화 기록에 추가한다."""
    case = _CASES[case_id]
    case.setdefault("conversation", []).append({"question": question, "answer": answer})


def log_event(case_id: str, event: str, payload: dict):
    _LOG.append({"case_id": case_id, "event": event, "payload": payload})


def get_log(case_id: str | None = None) -> list[dict]:
    if case_id:
        return [e for e in _LOG if e["case_id"] == case_id]
    return list(_LOG)


def reset():
    _CASES.clear()
    _LOG.clear()
