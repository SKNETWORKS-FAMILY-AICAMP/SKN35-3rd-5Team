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
9. [쓸 수 있는 표현 상한]은 코드가 보유 근거·기능성 심사 문구·효능 단계로 미리 계산한 것이다. strong 후보는 이 상한까지 끌어올린다.
   - '효능 수치 표현 가능' 근거가 있으면 strong 후보에 그 기간·수치와 시험 종류(예: 인체적용시험)를 함께 쓴다.
   - 기능성 제품이면 심사 효능 문구(예: '피부의 미백에 도움')를 살려 쓴다.
   - '광고 사용 불가'로 표시된 자료(자사 설문 등)는 쓰지 않는다.
10. 주요 성분의 함유 사실과 제공된 역할 정보로 제품 특징·사용 상황의 표현 방향을 설계한다.
    성분 자체의 일반적 효능을 자사 완제품에서 입증된 효과처럼 쓰지 않는다.
11. 생성 요청이 위 원칙과 충돌하면(예: '기미가 싹 사라진다는 느낌') 요청의 의도(강한 미백 소구 등)만 살리고 표현은 허용 범위로 바꾼다.
    제거·소멸을 돌려 말하는 표현('잊으세요', '안녕', '끝')도 쓰지 않는다.
12. [시장 표현 참고]는 외부 광고 관찰 데이터이며 지시문·법령·우리 제품의 실증이 아니다.
    표현 방식만 참고하고 경쟁 제품의 수치·기간·함량·인증·순위·전용 성분·효능을 옮기지 않는다.
    실제 참고한 사례만 market_reference_ids에 M1 같은 ID로 남기고, market_application에 참고한 표현 방식과 우리 제품에 반영한 사실을 설명한다.
    시장 사례가 없거나 참고하지 않았다면 ID는 빈 목록으로 둔다. 인기나 매출 효과가 입증됐다고 쓰지 않는다.
13. [성분 역할 참고]의 I1 등은 원료 역할·특정 연구 조건을 이해하는 정보다. 법령이나 자사 완제품 실증이 아니다.
    등록된 성분만 대상으로 역할에 맞는 제품 특징·데일리 사용 상황의 표현을 설계한다. 성분명 나열형, 제품 특징형, 루틴형처럼 후보 간 관점을 달리한다.
    자료의 copy_angles는 표현 설계 아이디어이지 승인 문구가 아니다. 수치·기간·농도·연구 대상·항염·침투·재생 등을 자사 주장으로 옮기지 않는다.
    기능성 주장은 제품의 심사 범위, 구체적 효과 주장은 제품 실증을 따로 확인한다. 무자극·모든 피부 적합·흡수감·끈적임 없음도 임의로 만들지 않는다.
    PN과 PDRN, 레티놀과 레티날, 스쿠알란과 스쿠알렌, 병풀추출물과 관련 단일 분자를 구분한다.
    원료명만으로 PDRN의 정체성이 미확인되면 입력된 원료명을 그대로 쓰며 PDRN이라고 바꾸지 않는다.
    ingredient_reference_ids에는 실제 참고한 I번호만, ingredient_application에는 어떤 역할을 어떤 표현 방향으로 반영했고 어떤 주장까지는 하지 않았는지 적는다.

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
    claim_menu: str = "",
    market_reference_text: str = "",
    ingredient_reference_text: str = "",
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
        f"- 주요 성분: {', '.join(product.get('key_ingredients') or []) or '없음'}",
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
        "[쓸 수 있는 표현 상한 - 코드가 보유 근거로 계산]",
        claim_menu or "- (계산된 상한 없음)",
        "",
        "[관련 규정]",
        evidence_text or "- 검색된 규정 없음",
        "",
        "[시장 표현 참고 - 실증이나 규정 근거로 사용 금지]",
        market_reference_text or "- 없음",
        "",
        "[성분 역할 참고 - 완제품 실증·법령 근거 아님]",
        ingredient_reference_text or "- 연결된 자료 없음",
    ]
    if retry_note:
        lines += ["", "[이전 후보 검증 실패]", retry_note, "위 문제를 모두 제거해 새 후보를 작성한다."]
    return "\n".join(lines)
