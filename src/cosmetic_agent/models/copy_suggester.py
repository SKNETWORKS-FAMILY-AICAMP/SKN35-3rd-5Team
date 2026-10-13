"""
[models/copy_suggester.py]
판정·검색 결과와 보유 근거를 받아 '근거가 허용하는 가장 센 문구'를 제안하는 LLM 호출부.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..common.config import settings
from .prompts import PROMPT_VERSION, SUGGEST_SYSTEM_PROMPT, build_suggest_user_prompt

# 실증규정 제3조·제4조: 광고 주장과 직접 관련된 시험결과(인체 적용시험 또는 인체 외 시험)가 실증자료다.
DEFAULT_NEXT_TEST = "광고 주장과 직접 관련된 인체 적용시험 또는 인체 외 시험 결과보고서 (화장품 표시·광고 실증에 관한 규정 제3조·제4조)"


class SuggestionOutput(BaseModel):
    suggestion: str = Field(description="고친 광고 문구")
    next_test: Optional[str] = Field(default=None, description="더 센 표현을 위해 필요한 실증자료")
    used_evidence: list[str] = Field(default_factory=list, description="문구에 사용한 보유 근거 항목")
    cited_ids: list[str] = Field(default_factory=list, description="참고한 관련 규정 번호 (L1 등)")
    rationale: str = Field(default="", description="무엇을 왜 바꿨는지")


def _load_functional_ceilings() -> dict[str, str]:
    path = settings.FUNCTIONAL_CLAIMS_PATH
    if not path.exists():
        return {}
    return {item["type"]: item["ceiling"] for item in json.loads(path.read_text(encoding="utf-8"))}


class CopySuggester:
    """문구 제안기. llm 을 주입하면(테스트 등) 그 객체의 invoke 를 사용한다."""

    def __init__(self, llm: Any = None, model_name: str | None = None, temperature: float = 0.2):
        self._llm = llm
        self.model_name = model_name or settings.OPENAI_MODEL_NAME
        self.temperature = temperature
        self.functional_ceilings = _load_functional_ceilings()

    @property
    def llm(self) -> Any:
        if self._llm is None:
            from langchain_openai import ChatOpenAI

            chat = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                api_key=settings.OPENAI_API_KEY or None,
                base_url=settings.OPENAI_BASE_URL,
            )
            self._llm = chat.with_structured_output(SuggestionOutput)
        return self._llm

    def suggest(
        self,
        *,
        copy_text: str,
        product: dict[str, Any],
        owned_evidence: list[dict[str, Any]] | None = None,
        level: int | None = None,
        violation_type: str | None = None,
        evidence_text: str = "",
        previous_suggestion: str | None = None,
        verify_note: str | None = None,
    ) -> dict[str, Any]:
        """제안 결과를 dict 로 반환한다. LLM 호출 실패 시 suggestion 은 None."""
        functional_type = product.get("functional_type") or ""
        ceiling = next(
            (text for kind, text in self.functional_ceilings.items() if kind and kind in functional_type),
            None,
        )
        user_prompt = build_suggest_user_prompt(
            copy_text=copy_text,
            product=product,
            owned_evidence=owned_evidence if owned_evidence is not None else product.get("owned_evidence", []),
            level=level,
            violation_type=violation_type,
            evidence_text=evidence_text,
            functional_ceiling=ceiling,
            previous_suggestion=previous_suggestion,
            verify_note=verify_note,
        )
        try:
            output = self.llm.invoke([("system", SUGGEST_SYSTEM_PROMPT), ("human", user_prompt)])
        except Exception as error:  # noqa: BLE001 - 네트워크·키 오류 시 검증 단계에서 재시도/종료 처리
            return {"suggestion": None, "next_test": None, "suggest_error": f"{type(error).__name__}: {error}",
                    "prompt_version": PROMPT_VERSION}

        if isinstance(output, dict):
            output = SuggestionOutput(**output)
        next_test = (output.next_test or "").strip()
        if next_test.lower() in {"", "null", "none", "없음", "-"}:
            next_test = None
        # 결과 계약(schemas.ReviewResult): 조건부(1) 판정에는 next_test 가 반드시 있어야 한다.
        if level == 1 and not next_test:
            next_test = DEFAULT_NEXT_TEST
        return {
            "suggestion": output.suggestion.strip(),
            "next_test": next_test,
            "used_evidence": output.used_evidence,
            "cited_ids": output.cited_ids,
            "suggest_rationale": output.rationale,
            "prompt_version": PROMPT_VERSION,
        }
