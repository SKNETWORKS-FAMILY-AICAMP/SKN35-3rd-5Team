"""
[workflow/prompts.py]
LangChain LCEL 체인 및 노드에서 사용하는 프롬프트 템플릿 모음.
"""
from langchain_core.prompts import ChatPromptTemplate

# 1. GPT 판정 프롬프트 (구분자 <<< >>> 로 프롬프트 인젝션 방어)
JUDGE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "당신은 대한민국 화장품법 및 식약처 광고 실증 가이드라인 전문 RA(규제과학) 심사관입니다.\n"
        "제공된 화장품 정보와 광고 문구를 엄격히 분석하여 위반 여부를 판정하십시오.\n"
        "판정 기준: 0 (위반 없음 / 가능), 1 (실증자료/조건 필요 / 조건부), 2 (화장품법 위반 / 불가)",
    ),
    (
        "human",
        "제품 분류: {product_category} (기능성 여부: {functional_type})\n"
        "심사 대상 광고 문구:\n<<<\n{copy_text}\n>>>",
    ),
])

# 2. 문구 교정 및 상위 표현 제안 프롬프트
SUGGEST_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "당신은 화장품 규정 준수 카피라이터입니다.\n"
        "지적된 위반 사유와 현재 보유하고 있는 실증 근거를 바탕으로,\n"
        "1) 법적 리스크가 없는 가장 매력적인 대체 문구를 제안하고,\n"
        "2) 더 강력한 광고를 위해 추가로 필요한 시험을 안내하십시오.",
    ),
    (
        "human",
        "원본 문구: {copy_text}\n"
        "판정 결과: Level {level} (위반 유형: {violation_type})\n"
        "현재 보유 근거: {owned_evidence}\n"
        "근거 법령 조항:\n{evidence_text}",
    ),
])
