"""klue/roberta-small을 파인튜닝한 로컬 텍스트 분류기 (v5.1). STT 자유텍스트에서
"정상 대화"를 빠르게/무료로 걸러내는 1차 필터 역할만 한다 — 최종 코칭탐지 판단과
근거 설명(XAI)은 여전히 llm_client의 Claude 호출(analyze_stt_transcript)이 담당한다.

학습 데이터(총 1,621건: 정상 885 / 보이스피싱 736, 이 중 65건은 Claude 합성
하드example)와 v1→v5.1 개선 과정, 측정된 실제 성능은 ml/README.md에 정직하게
기록되어 있다. 요약하면:
- v1(KorCCViD 121건만)은 은행 창구의 정상 송금 발화까지 보이스피싱으로 오분류했다.
- v2(정상 데이터만 대폭 추가)는 반대로 실시간 코칭 정황까지 정상으로 오분류하는
  더 위험한 실패였다 (클래스 비율 11.6:1로 다수 클래스 붕괴).
- v4는 보이스피싱 표본을 731건으로 늘려 두 문제를 해결했지만, "급함/큰금액/제3자가
  불러준 계좌"처럼 표면적으로 사기 각본과 겹치는 정상 거래(부동산 계약금, 등록금 등)를
  전부 보이스피싱으로 오탐하는 문제가 실사용 테스트에서 새로 드러났다.
- v5는 이 오탐을 겨냥한 하드-네거티브를 추가해 크게 개선했지만, 부작용으로 짧은
  "코칭 진행중" 단문("불러주는 대로 계좌번호 입력하고 있어요" 등)이 전부 붕괴하는
  회귀가 생겨 배포하지 않고 폐기했다.
- v5.1은 같은 어휘("급하게/계좌번호/불러주신")를 쓰되 실제 코칭 문맥인 하드-포지티브를
  대칭으로 추가해 어휘가 아니라 문맥으로 구분하도록 재균형했다. 가족/지인 사칭
  (자녀납치빙자, 메신저해킹 지인사칭)도 이때 함께 보강했다.

**여전히 남은 한계**: 아주 짧고 구체성이 낮은 문자 가족 사칭("엄마 나 폰 고장나서
돈 좀 보내줘" 수준의 한 문장)은 여전히 정상으로 오분류한다. 또한 이 모델은 결정
경계가 매우 가파른 편이라(중간 확률값이 거의 없이 0.1%/99.9%로 쏠림), 학습 데이터를
조금만 바꿔도 특정 표현의 판정이 크게 흔들릴 수 있다. 그래서 이 모듈은 여전히 "정상"
으로 아주 강하게 판단될 때만 Claude 호출을 건너뛰는 보수적인 1차 필터로만 쓴다
(아래 SKIP_LLM_THRESHOLD 참고). 조금이라도 애매하거나 의심스러우면 항상 Claude로
넘긴다 — 아직 발견 못한 실패 사례가 더 있을 수 있다는 전제를 유지한다.
"""
import os

_MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "coaching_classifier")

# 이 값보다 "보이스피싱일 확률"이 낮아야만 Claude 호출을 생략한다. 보수적으로 낮게 잡는다.
SKIP_LLM_THRESHOLD = 0.05

_tokenizer = None
_model = None
_unavailable_reason: str | None = None


def _ensure_loaded():
    global _tokenizer, _model, _unavailable_reason
    if _model is not None or _unavailable_reason is not None:
        return
    try:
        import torch  # noqa: F401
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        if not os.path.isdir(_MODEL_DIR) or not os.listdir(_MODEL_DIR):
            _unavailable_reason = (
                f"로컬 분류기 모델이 없습니다 ({_MODEL_DIR}). "
                "ml/train_coaching_classifier.py로 학습 후 배치하세요."
            )
            return
        _tokenizer = AutoTokenizer.from_pretrained(_MODEL_DIR)
        _model = AutoModelForSequenceClassification.from_pretrained(_MODEL_DIR)
        _model.eval()
    except Exception as e:  # torch/transformers 미설치 등
        _unavailable_reason = f"로컬 분류기 로드 실패: {e}"


def predict(text: str) -> dict:
    """반환: {"available": bool, "label": "정상"|"보이스피싱"|None, "prob_phishing": float|None,
    "skip_llm": bool, "reason": str|None}
    available=False면 prob_phishing 등은 None이고, 호출측은 항상 Claude로 넘어가야 한다."""
    _ensure_loaded()
    if _model is None:
        return {
            "available": False,
            "label": None,
            "prob_phishing": None,
            "skip_llm": False,
            "reason": _unavailable_reason,
        }

    import torch

    with torch.no_grad():
        enc = _tokenizer(text, truncation=True, max_length=256, padding="max_length", return_tensors="pt")
        logits = _model(**enc).logits
        prob_phishing = torch.softmax(logits, dim=-1)[0, 1].item()

    label = "보이스피싱" if prob_phishing >= 0.5 else "정상"
    skip_llm = prob_phishing < SKIP_LLM_THRESHOLD
    return {
        "available": True,
        "label": label,
        "prob_phishing": round(prob_phishing, 4),
        "skip_llm": skip_llm,
        "reason": None,
    }
