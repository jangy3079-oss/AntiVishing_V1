"""STT 트리거 기반 '통화 중 + 강한 코칭 정황' 감지.
Tier2로 확대된 거래에 한해, 창구 직원이 대화 중 채록된 텍스트를 제출하면 활성화된다.
(통신사 통화신호 연동 대신 텍스트 기반 의도 분류로 대체)
"""
from app import llm_client

COACHING_CONFIDENCE_THRESHOLD = 0.7


def analyze_stt(transcript: str) -> dict:
    result = llm_client.analyze_stt_transcript(transcript)
    coaching_detected = bool(result.get("coaching_detected")) and float(result.get("confidence", 0)) >= COACHING_CONFIDENCE_THRESHOLD
    return {
        "coaching_detected": coaching_detected,
        "confidence": result.get("confidence"),
        "matched_scam_type": result.get("matched_scam_type"),
        "reasoning": result.get("reasoning"),
        "raw": result,
    }
