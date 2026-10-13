"""
[models/copy_suggester.py]
판정·검색 결과와 보유 근거를 받아 '근거가 허용하는 가장 센 문구'를 제안하는 LLM 호출부.

1. 코드가 보유 근거·기능성 심사·표현 사다리로 '쓸 수 있는 표현 상한'을 계산해 프롬프트에 넣는다.
2. LLM 은 강한 순서로 후보 3개를 낸다.
3. 검증기(verifier)를 통과하는 후보 중 가장 강한 것을 고른다.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..common.config import settings
from .prompts import PROMPT_VERSION, SUGGEST_SYSTEM_PROMPT, build_claim_menu, build_suggest_user_prompt

# 실증규정 제3조·제4조: 광고 주장과 직접 관련된 시험결과(인체 적용시험 또는 인체 외 시험)가 실증자료다.
DEFAULT_NEXT_TEST = "광고 주장과 직접 관련된 인체 적용시험 또는 인체 외 시험 결과보고서 (화장품 표시·광고 실증에 관한 규정 제3조·제4조)"


class SuggestionOutput(BaseModel):
    candidates: list[str] = Field(default_factory=list, description="강한 순서의 후보 문구 3개")
    suggestion: str = Field(default="", description="(하위 호환) 단일 제안 문구")
    next_test: Optional[str] = Field(default=None, description="더 센 표현을 위해 필요한 것")
    used_evidence: list[str] = Field(default_factory=list, description="후보에 사용한 보유 근거 항목")
    cited_ids: list[str] = Field(default_factory=list, description="참고한 관련 규정 번호 (L1 등)")
    rationale: str = Field(default="", description="무엇을 왜 바꿨는지")


def _load_json(path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


class CopySuggester:
    """문구 제안기. llm 을 주입하면(테스트 등) 그 객체의 invoke 를 사용한다."""

    def __init__(
        self,
        llm: Any = None,
        model_name: str | None = None,
        temperature: float = 0.2,
        verifier: Any = None,
        rule_engine: Any = None,
    ):
        self._llm = llm
        self.model_name = model_name or settings.OPENAI_MODEL_NAME
        self.temperature = temperature
        self.functional_ceilings = {
            item["type"]: item["ceiling"] for item in _load_json(settings.FUNCTIONAL_CLAIMS_PATH)
        }
        self.claim_ladder = _load_json(settings.CLAIM_LADDER_PATH)
        self._verifier = verifier
        self._rule_engine = rule_engine

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

    @property
    def verifier(self) -> Any:
        if self._verifier is None:
            from ..domain.verifier import CopyVerifier

            self._verifier = CopyVerifier()
        return self._verifier

    @property
    def rule_engine(self) -> Any:
        if self._rule_engine is None:
            from ..domain.rules import RuleEngine

            self._rule_engine = RuleEngine()
        return self._rule_engine

    def _ceiling(self, functional_type: str) -> str | None:
        """'피부 미백' 같은 유형 이름과 제품의 '미백' 표기가 달라도 찾는다."""
        if not functional_type:
            return None
        for kind, text in self.functional_ceilings.items():
            if kind in functional_type or functional_type in kind:
                return text
        generic = {"피부", "증상", "완화", "개선", "도움", "차단"}
        for kind, text in self.functional_ceilings.items():
            keys = [w for w in kind.split() if w not in generic]
            if keys and all(k in functional_type for k in keys):
                return text
        return None

    def _pick(self, options: list[str], product: dict[str, Any], copy_text: str, level: int | None):
        """검증을 통과하는 후보 중 가장 앞(가장 강한) 것을 고른다. 없으면 첫 후보."""
        notes = []
        for text in options:
            passed, note = self.verifier.verify_suggestion(
                text,
                product.get("owned_evidence", []),
                self.rule_engine,
                product_category=product.get("category", "일반"),
                functional_type=product.get("functional_type"),
                original=copy_text if (level or 0) >= 1 else None,
            )
            if passed:
                return text, notes
            notes.append(note)
        return options[0], notes

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
        evidences = owned_evidence if owned_evidence is not None else product.get("owned_evidence", [])
        ceiling = self._ceiling(product.get("functional_type") or "")
        user_prompt = build_suggest_user_prompt(
            copy_text=copy_text,
            product=product,
            owned_evidence=evidences,
            level=level,
            violation_type=violation_type,
            evidence_text=evidence_text,
            functional_ceiling=ceiling,
            claim_menu=build_claim_menu(
                copy_text=copy_text,
                product=product,
                owned_evidence=evidences,
                claim_ladder=self.claim_ladder,
                functional_ceiling=ceiling,
            ),
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
        options = [c.strip() for c in output.candidates if c and c.strip()] or [output.suggestion.strip()]
        chosen, rejected = self._pick(options, product, copy_text, level)

        next_test = (output.next_test or "").strip()
        if next_test.lower() in {"", "null", "none", "없음", "-"}:
            next_test = None
        # 결과 계약(schemas.ReviewResult): 조건부(1) 판정에는 next_test 가 반드시 있어야 한다.
        if level == 1 and not next_test:
            next_test = DEFAULT_NEXT_TEST
        return {
            "suggestion": chosen,
            "next_test": next_test,
            "candidates": options,
            "rejected_notes": rejected,
            "used_evidence": output.used_evidence,
            "cited_ids": output.cited_ids,
            "suggest_rationale": output.rationale,
            "prompt_version": PROMPT_VERSION,
        }
