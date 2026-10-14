"""검토 기준과 규정 근거를 사용한 신규 광고 문구 생성 프롬프트."""

from typing import Any

GENERATION_SYSTEM_PROMPT = """\
너는 화장품 회사의 카피라이터이자 표시·광고 심의 담당자다.
제품 정보, 사용자가 선택한 보유 실증자료, 관련 규정 안에서 광고 문구 후보를 만든다.

[필수 원칙]
1. 제공되지 않은 성분, 시험, 인증, 수치, 기간, 순위는 만들지 않는다.
2. 일반 화장품에는 기능성 효능을 쓰지 않는다.
3. 기능성 화장품은 제공된 심사(보고) 기능성 범위 안에서만 표현한다.
4. 질병 치료·예방, 의약품 작용, 신체 구조 변화, 절대적·배타적 표현을 쓰지 않는다.
5. 수치와 시험 결과는 보유 실증자료에 적힌 내용과 정확히 일치할 때만 사용한다.
6. 원료의 일반적인 특성을 완제품의 입증된 효능처럼 바꾸지 않는다.
7. 관련 규정에 없는 사실을 추정하지 않는다.
8. strong, balanced, safe 후보를 하나씩 만들고, safe 후보는 별도 효능 근거 없이도 사용할 수 있는 관리·사용감 표현으로 만든다.

[출력]
- candidates: strong, balanced, safe 순서의 후보 3개
- 각 후보에는 text, tier, rationale, used_evidence, cited_ids를 포함한다.
- cited_ids는 [관련 규정]의 L1, L2 같은 번호만 사용한다.
"""


def build_generation_prompt(
    *,
    instruction: str,
    product: dict[str, Any],
    channel: str,
    tone: str,
    length: str,
    keywords: list[str],
    evidence_text: str,
    retry_note: str | None = None,
) -> str:
    evidences = product.get("owned_evidence") or []
    evidence_rows = []
    for evidence in evidences:
        values = [
            str(evidence.get(key))
            for key in ("test_type", "item", "value", "institute")
            if evidence.get(key)
        ]
        evidence_rows.append("- " + " / ".join(values))
    lines = [
        "[생성 요청]",
        instruction,
        "",
        "[제품]",
        f"- 제품명: {product.get('name', '')}",
        f"- 구분: {product.get('category', '일반')}",
        f"- 심사(보고) 기능성: {product.get('functional_type') or '없음'}",
        "",
        "[광고 조건]",
        f"- 채널: {channel}",
        f"- 분위기: {tone}",
        f"- 길이: {length}",
        f"- 포함 키워드: {', '.join(keywords) if keywords else '없음'}",
        "",
        "[사용 가능한 보유 실증자료]",
        *(evidence_rows or ["- 없음"]),
        "",
        "[관련 규정]",
        evidence_text or "- 검색된 규정 없음",
    ]
    if retry_note:
        lines += ["", "[이전 후보 검증 실패]", retry_note, "위 문제를 모두 제거해 새 후보를 작성한다."]
    return "\n".join(lines)
