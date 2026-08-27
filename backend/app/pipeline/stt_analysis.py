"""STT 트리거 기반 '통화 중 + 강한 코칭 정황' 감지.
Tier2로 확대된 거래에 한해, 창구 직원이 대화 중 채록된 텍스트를 제출하면 활성화된다.
(통신사 통화신호 연동 대신 텍스트 기반 의도 분류로 대체)

1차 필터: KorCCViD 파인튜닝 로컬 분류기(coaching_classifier)로 "매우 명백한 정상 대화"만
빠르게/무료로 걸러낸다. 그 외(로컬 모델이 의심스럽다고 보거나, 모델을 못 불러온 경우)는
전부 기존처럼 Claude(analyze_stt_transcript)로 넘겨 최종 판단과 근거 설명을 받는다.
즉 로컬 모델은 비용/속도 최적화용 게이트일 뿐, 최종 판정 권한은 여전히 Claude에 있다.
"""
from app import llm_client
from app.pipeline import coaching_classifier

COACHING_CONFIDENCE_THRESHOLD = 0.7


def analyze_stt(transcript: str) -> dict:
    local = coaching_classifier.predict(transcript)
    if local["skip_llm"]:
        return {
            "coaching_detected": False,
            "confidence": 1.0 - local["prob_phishing"],
            "matched_scam_type": "없음",
            "reasoning": (
                f"1차 로컬 분류기(local classifier)가 정상 대화로 강하게 판단해 "
                f"(보이스피싱 확률 {local['prob_phishing']:.1%}) Claude 정밀분석을 생략했습니다."
            ),
            "raw": {"source": "local_classifier", **local},
        }

    result = llm_client.analyze_stt_transcript(transcript)
    coaching_detected = bool(result.get("coaching_detected")) and float(result.get("confidence", 0)) >= COACHING_CONFIDENCE_THRESHOLD
    return {
        "coaching_detected": coaching_detected,
        "confidence": result.get("confidence"),
        "matched_scam_type": result.get("matched_scam_type"),
        "reasoning": result.get("reasoning"),
        "raw": {"source": "claude", "local_classifier": local, **result},
    }
