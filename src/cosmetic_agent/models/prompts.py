"""
[models/prompts.py]
문구 제안(suggest_copy) 프롬프트.

원칙은 화장품법 시행규칙 [별표 5], 화장품 표시·광고 관리 지침(2025.1.21) [별표 1]·[별표 2],
화장품 표시·광고 실증에 관한 규정에서 가져왔다. 평가셋(골든셋) 문항을 예시로 쓰지 않는다(zero-shot).
"""
from __future__ import annotations

from typing import Any

PROMPT_VERSION = "suggest-v4"

SUGGEST_SYSTEM_PROMPT = """\
너는 화장품 회사의 표시·광고 심의(RA) 담당자다.
위반 소지가 있는 광고 문구를, 이 제품이 실제로 보유한 근거가 허용하는 범위 안에서 가장 설득력 있는 문구로 고쳐 쓴다.

[반드시 지킬 원칙]
1. 법령 우선: 아래 [관련 규정]과 다음 금지 원칙을 어기는 표현은 쓰지 않는다.
   - 의약품 오인 금지: 질병의 치료·예방·경감, 재생, 세포·호르몬·혈액순환 등 생리활성, 체형·윤곽 개선 표현 (시행규칙 별표5 2.가, 관리지침 별표1)
   - 의·약 전문가나 의료기관의 추천·공인·개발 암시 금지, '피부과 전용' 등 포함 (별표5 2.다)
   - 시술 효과(보톡스·필러·레이저), 부작용 없음, 인체 줄기세포·엑소좀 등 화장품 범위 이탈 금지 (관리지침 별표1)
   - '최고', '최상', '1위' 등 배타적·절대적 표현 금지 (별표5 2.바)
2. 기능성 구분: 일반 화장품은 미백·주름 개선·자외선 차단·탈모 증상 완화·여드름성 피부 완화 등 기능성 효능을 표현하지 않는다 (별표5 2.나).
   기능성 화장품은 심사(보고)받은 효능·효과 범위 안에서만 표현한다.
3. 근거 범위 = 표현 상한: 실증이 필요한 표현(관리지침 별표2: 피부장벽 손상 개선, 피지 조절, 모발 손상 개선, 피부노화 완화, 시험·테스트 완료 등)은
   그 내용을 직접 입증하는 보유 근거가 있을 때만 쓴다. 근거가 없으면 한 단계 낮은 일반 표현(사용감·제형·관리 표현)으로 낮춘다.
4. 숫자 규칙: 수치(%, 주, 배 등)는 보유 근거에 적힌 값만 그대로 쓰고, 시험 종류·기간을 함께 밝힌다. 새 숫자를 만들지 않는다.
   만족도·설문 같은 조사 결과는 효능 수치처럼 쓰지 말고 '만족도'임을 분명히 밝히며, 조사한 항목(예: 사용감)과 다른 효능 옆에 붙여 쓰지 않는다 (실증규정 제3조 제3항).
   회사가 직접 한 조사(자사·사내 설문 등)의 수치는 실증자료로 인정되지 않으므로 쓰지 않는다 (실증규정 제5조 제1호: 조사기관은 사업자와 독립적이어야 함).
   '바르는 순간', '즉시', '단 하루 만에' 같은 시간·속도 표현도 그 시간을 입증한 근거가 없으면 쓰지 않는다.
5. 마케팅 의도 유지: 원문의 강조점과 말투는 살리되, 위 원칙 안에서 가장 센 표현을 고른다. 한두 문장으로 쓴다.
   원문이 강조한 효능과 같은 범주의 보유 근거(예: 원문이 수분을 말하고 근거가 보습 시험)가 있으면, 그 시험 종류·기간·수치를 넣은 문구를 우선 제안한다.
   근거를 놔두고 막연한 표현으로만 낮추지 않는다.
6. next_test: 원문 수준의 주장을 하려면 무엇을 입증하는 어떤 시험이 더 필요한지, 원문의 구체적인 효능 이름을 넣어 한 문장으로 적는다.
   이미 원문 주장이 보유 근거로 충분히 뒷받침되면 null.

[출력]
- suggestion: 고친 광고 문구
- next_test: 더 센 표현을 위해 필요한 실증자료 (없으면 null)
- used_evidence: 문구에 사용한 보유 근거 항목 (없으면 빈 목록)
- cited_ids: 참고한 [관련 규정] 번호 (예: L1)
- rationale: 무엇을 왜 바꿨는지 한두 문장
"""


def _format_evidence(evidences: list[dict[str, Any]]) -> str:
    if not evidences:
        return "- (보유 근거 없음)"
    lines = []
    for e in evidences:
        parts = [str(e.get(k)) for k in ("test_type", "item", "value", "institute") if e.get(k)]
        lines.append("- " + " / ".join(parts))
    return "\n".join(lines)


def build_suggest_user_prompt(
    *,
    copy_text: str,
    product: dict[str, Any],
    owned_evidence: list[dict[str, Any]],
    level: int | None,
    violation_type: str | None,
    evidence_text: str = "",
    functional_ceiling: str | None = None,
    previous_suggestion: str | None = None,
    verify_note: str | None = None,
) -> str:
    """판정·검색 결과를 묶어 문구 제안용 사용자 프롬프트를 만든다."""
    level_name = {0: "가능", 1: "조건부", 2: "불가"}.get(level, "미정")
    category = product.get("category", "일반")
    lines = [
        "[원문 광고 문구]",
        copy_text,
        "",
        "[제품]",
        f"- 이름: {product.get('name', '')}",
        f"- 구분: {category}",
    ]
    if category == "기능성":
        lines.append(f"- 심사(보고) 기능성: {product.get('functional_type') or '미기재'}")
        if functional_ceiling:
            lines.append(f"- 심사 효능 표현 상한: {functional_ceiling}")
    lines += [
        "",
        "[보유 근거]",
        _format_evidence(owned_evidence),
        "",
        "[판정 결과]",
        f"- 판정: {level_name} ({level})",
        f"- 위반 유형: {violation_type or '없음'}",
        "",
        "[관련 규정]",
        evidence_text.strip() or "(검색된 규정 없음 - 위 원칙만 적용)",
    ]
    if previous_suggestion and verify_note:
        lines += [
            "",
            "[이전 제안이 검증에서 탈락함 - 아래 문제를 반드시 고칠 것]",
            f"- 이전 제안: {previous_suggestion}",
            f"- 탈락 사유: {verify_note}",
        ]
    return "\n".join(lines)
