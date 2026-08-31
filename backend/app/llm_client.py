"""
Claude API 연동 래퍼.
- STT 트랜스크립트 코칭 의도 분류
- 자유텍스트 RAG 패턴 대조 (KNOWN_SCAM_PATTERNS를 컨텍스트로 제공)
- 최종 위험판정 XAI 근거 설명 생성

ANTHROPIC_API_KEY 환경변수가 없으면 명확한 에러를 던진다 (조용히 목업으로 대체하지 않음 -
"실제 LLM 추론 연동"을 선택했으므로 키가 없으면 실패를 드러내는 게 맞다).
"""
import os
import json
import re
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY가 설정되어 있지 않습니다. backend/.env 파일에 키를 넣어주세요 "
                "(.env.example 참고)."
            )
        _client = Anthropic(api_key=api_key)
    return _client


def _get_text(resp) -> str:
    """응답 content 블록 중 텍스트 블록만 골라서 합친다.
    (일부 모델은 thinking 블록을 함께 반환하는데, ThinkingBlock에는 .text가 없어
    content[0]을 그냥 쓰면 깨진다.)"""
    parts = [block.text for block in resp.content if getattr(block, "type", None) == "text"]
    if not parts:
        raise ValueError("LLM 응답에서 텍스트 블록을 찾을 수 없습니다.")
    return "".join(parts)


def _check_not_truncated(resp) -> None:
    """max_tokens에 걸려 응답이 중간에 잘렸으면 즉시 명확한 에러를 던진다.
    (안 이러면 잘린 JSON이 _extract_json에서 "JSON을 찾을 수 없다"는 애매한 에러로만
    보여서, 진짜 원인이 max_tokens 부족이라는 걸 알기 어렵다 — 실제로 tier2_context가
    큰 케이스에서 analyze_freetext가 이렇게 잘린 적이 있었다.)"""
    if getattr(resp, "stop_reason", None) == "max_tokens":
        raise ValueError(
            "LLM 응답이 max_tokens 제한에 걸려 중간에 잘렸습니다. 호출부의 max_tokens 값을 늘려야 합니다."
        )


def _extract_json(text: str) -> dict:
    """모델 응답에서 JSON 블록만 추출해 파싱한다."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"LLM 응답에서 JSON을 찾을 수 없습니다: {text[:200]}")
    return json.loads(match.group(0))


def analyze_stt_transcript(transcript: str) -> dict:
    """창구 대화 STT 텍스트에서 '강한 코칭 정황'(제3자가 실시간으로 지시하는 정황)을 판별."""
    prompt = f"""당신은 은행 창구 보이스피싱 탐지 에이전트입니다.
아래는 창구 직원이 고객과 대화 중 채록한 음성인식(STT) 텍스트입니다.
고객이 전화 통화 중이며, 통화 상대가 실시간으로 지시(코칭)하고 있다는 강한 정황이 있는지 판단하세요.

STT 텍스트:
\"\"\"{transcript}\"\"\"

다음 JSON 형식으로만 답하세요 (다른 텍스트 없이):
{{
  "coaching_detected": true 또는 false,
  "confidence": 0.0~1.0 사이 숫자,
  "matched_scam_type": "감지된 사기 유형 (예: 검찰_금감원_사칭, 자녀_사칭, 없음 등)",
  "reasoning": "판단 근거를 한국어 1~2문장으로"
}}"""
    resp = _get_client().messages.create(
        model=_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    _check_not_truncated(resp)
    return _extract_json(_get_text(resp))


def analyze_freetext(
    customer_statement: str,
    known_patterns: list[dict],
    tier2_context: dict,
    conversation_history: list[dict] | None = None,
) -> dict:
    """고객 진술 자유텍스트를 알려진 사기 스크립트 패턴(RAG 컨텍스트)과 대조."""
    patterns_text = "\n".join(
        f"- [{p['id']}] {p['summary']} (전형 신호: {', '.join(p['signals'])})" for p in known_patterns
    )
    history = conversation_history or []
    history_text = (
        "\n".join(f"- Q: {t['question']}\n  A: {t['answer']}" for t in history)
        if history
        else "(아직 없음)"
    )
    prompt = f"""당신은 은행 창구 보이스피싱 탐지 에이전트입니다.
창구 직원이 고객에게 "이 돈을 어디에, 왜 보내시는지" 물었고, 고객이 다음과 같이 답했습니다.

지금까지 이 고객과 실제로 나눈 질문/답변 (반드시 확인하고, 여기 나온 내용은 절대 다시 묻지 마세요):
{history_text}

이번 답변: "{customer_statement}"

참고할 수 있는 알려진 사기 스크립트 패턴 목록:
{patterns_text}

거래 관련 자동 신호(참고용): {json.dumps(tier2_context, ensure_ascii=False)}

이 진술이 위 알려진 사기 패턴 중 하나와 유사한지, 혹은 정상적인 선의의 거래로 보이는지 판단하세요.
단순 키워드 매칭이 아니라 맥락과 의미를 함께 고려하세요.

애매하다면 후속 질문을 제안할 수 있지만, 아래 제약을 반드시 지키세요.
- 후속 질문은 최대 2번까지만 추가로 물을 수 있습니다. 꼭 필요한 경우에만 요청하세요.
- 후속 질문은 반드시 고객 본인이 스스로 알고 답할 수 있는 것만 물어야 합니다.
  (예: 이 거래를 어떻게 알게 됐는지, 직접 방문/통화했는지, 누가 이렇게 하라고 안내했는지 등)
- 수취계좌 명의, 사업자등록 여부, 계좌 소유자 정보처럼 고객이 알 수 없고 은행 시스템이
  자체적으로 조회해야 할 내용을 고객에게 확인하라고 요구하지 마세요.
- 위 "지금까지 나눈 질문/답변"에 이미 나온 내용은 표현을 바꿔서도 다시 묻지 마세요.
- 아직 결제(송금)가 완료되지 않은 거래입니다. "이번 결제의 영수증을 보여달라"처럼 아직
  존재할 수 없는 서류를 요구하지 마세요. 사전에 이미 존재할 수 있는 것(견적서, 계약서 등)만 물을 수 있습니다.
- 사소하거나 이미 답변된 사기 무관 정황까지 의심해서 고객을 다그치듯 캐묻지 마세요. 고객은
  일반적인 선의의 고객일 수 있다는 전제를 유지하세요.

다음 JSON 형식으로만 답하세요 (다른 텍스트 없이):
{{
  "risk_level": "low" 또는 "medium" 또는 "high",
  "matched_pattern_id": "패턴 ID 또는 null",
  "needs_followup": true 또는 false,
  "followup_question": "필요하면 후속 질문, 아니면 null",
  "reasoning": "판단 근거를 한국어 1~2문장으로"
}}"""
    resp = _get_client().messages.create(
        model=_MODEL,
        # tier2_context(계좌 특징/사유 목록)가 큰 케이스에서 reasoning이 길어지며 실제로
        # 1200으로는 JSON이 중간에 잘리는 문제가 있었다 (닫는 "}" 전에 max_tokens 도달).
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    _check_not_truncated(resp)
    return _extract_json(_get_text(resp))


def explain_account_position(position: dict) -> str:
    """수취계좌 위치 분석(account_figures.compute_case_position 결과)을 근거로,
    이 계좌가 정상/이상연루 모집단 중 어디에 더 가까운지, 어떤 지표가 특히 벗어났는지를
    자연어로 설명한다. 숫자를 지어내지 않도록 계산된 값만 프롬프트에 넣고 그대로 인용하게 한다."""
    prompt = f"""당신은 은행 창구 직원에게 "이 수취계좌가 왜 이런 위험 신호를 보였는지"를
데이터에 기반해 설명하는 에이전트입니다.

아래는 AI-Hub 실제 금융거래 데이터로 만든 정상/이상거래연루 계좌 모집단을 기준선으로,
이번 케이스의 수취계좌 위치를 계산한 결과입니다(전부 실제로 계산된 값이며, 새로운 숫자를
지어내지 마세요. 아래 값만 인용하세요):

{json.dumps(position, ensure_ascii=False, indent=2)}

이 데이터를 보고 3~4문장의 자연스러운 한국어로 설명하세요:
- 이 계좌가 정상군과 이상연루군 중 어느 쪽에 더 가까운지 (정상군 중심 이탈 거리 기준)
- per_feature 중 정상 대비 배율(ratio_vs_normal)이 크게 벗어난 지표가 있다면 구체적으로 언급
- tier2_rule_reasons/tier2_anomaly_flag와 앞뒤가 맞게 설명 (이미 잡힌 규칙과 모순되지 않게)
- caveat 필드에 적힌 한계(관측 기간이 짧아 배율이 과장될 수 있음)를 반드시 감안해서, 배율 절대값을
  그대로 강조하기보다 방향성 위주로 신중하게 서술하세요 (예: "802배"처럼 과장된 숫자를 그대로
  강조하지 말고 "정상 범위보다 뚜렷하게 높다" 정도로 표현)
- 배율이나 거리가 애매하면 "단정할 수 없다"는 취지로 신중하게 서술 (과장 금지)

불릿포인트 없이 문장으로 서술하세요. JSON이 아닌 순수 텍스트로만 답하세요."""
    resp = _get_client().messages.create(
        model=_MODEL,
        max_tokens=700,
        messages=[{"role": "user", "content": prompt}],
    )
    _check_not_truncated(resp)
    return _get_text(resp).strip()


def generate_xai_explanation(case_summary: dict) -> str:
    """최종 위험판정에 대한 근거 설명(XAI)을 자연어로 생성."""
    prompt = f"""당신은 은행 창구 직원에게 보이스피싱 위험판정 근거를 설명하는 에이전트입니다.
아래는 한 거래에 대해 수집된 모든 신호입니다.

{json.dumps(case_summary, ensure_ascii=False, indent=2)}

이 신호들을 종합해서, 창구 직원이 고객을 응대할 때 참고할 수 있도록
왜 이런 위험판정이 나왔는지 3~4문장의 자연스러운 한국어로 설명하세요.
불릿포인트 없이 문장으로 서술하세요. JSON이 아닌 순수 텍스트로만 답하세요."""
    resp = _get_client().messages.create(
        model=_MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    _check_not_truncated(resp)
    return _get_text(resp).strip()
