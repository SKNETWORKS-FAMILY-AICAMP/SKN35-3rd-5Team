"""
[domain/verifier.py]
LLM이 생성한 제안 문구의 숫자, 효능, 표현이 실제 보유 근거와 일치하는지 코드로 역검증하는 엔진.

검사 규칙(data/assets/copy_guard.json)은 법령·고시·지침 원문에서만 가져왔다.
1. 금지 표현 재등장      - 관리지침 [별표 1], 시행규칙 [별표 5] 제2호
2. 기능성 오인/범위 이탈 - 시행규칙 [별표 5] 2.나, 시행규칙 제2조, 관리지침 [별표 1] 기능성 관련
3. 실증 필요 표현        - 관리지침 [별표 2] (보유 근거와 직접 관련된 자료가 있어야 함)
4. 숫자 날조             - 관리지침 [별표 2] 2., 시행규칙 [별표 5] 2.아
5. 만족도 수치의 효능화  - 실증규정 제3조 제3항 (조사결과는 효능 주장의 직접 근거가 아님)
6. 자사 조사 수치 사용   - 실증규정 제5조 제1호 (조사기관은 사업자와 독립적이어야 함)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..common.config import settings

# 숫자 + 단위. 단위 없는 숫자(제품명의 숫자 등)는 효능 주장으로 보지 않는다.
NUMBER_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(%|퍼센트|주|일(?!반)|시간|개월|배(?!합|송)|명(?!품)|세(?!럼|트|정|안|대|틸|포|라|척)|살(?!균)|년|분(?![말석비])|회(?!사))"
)
UNIT_ALIASES = {"퍼센트": "%", "살": "세"}


@dataclass(frozen=True)
class VerifyIssue:
    code: str       # 금지표현 / 기능성오인 / 범위이탈 / 실증필요 / 숫자날조 / 조사결과오용 / 금지어 / 미수정 / 빈문구
    basis_id: str   # RAG 청크 ID 규칙과 같은 근거 ID
    message: str
    matched: str = ""

    def __str__(self) -> str:
        found = f" ('{self.matched}')" if self.matched else ""
        return f"[{self.code}|{self.basis_id}] {self.message}{found}"


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def _number_tokens(text: str) -> set[str]:
    """'4주', '42%' 처럼 숫자+단위를 정규화해 모은다. ('24주' 안의 '4주'는 별개로 본다)"""
    return {f"{number}{UNIT_ALIASES.get(unit, unit)}" for number, unit in NUMBER_RE.findall(text or "")}


def _evidence_text(evidence: dict[str, Any]) -> str:
    return " ".join(str(evidence.get(key) or "") for key in ("test_type", "item", "value", "institute"))


class CopyVerifier:
    """제안 문구 검증기"""

    def __init__(self, guard_path: Path | None = None):
        path = Path(guard_path or settings.COPY_GUARD_PATH)
        guard = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.forbidden: list[dict[str, Any]] = guard.get("forbidden", [])
        self.functional_claims: list[dict[str, Any]] = guard.get("functional_claims", [])
        self.substantiation: list[dict[str, Any]] = guard.get("substantiation_required", [])
        self.survey_keywords: list[str] = guard.get("survey_keywords", [])
        self.in_house_keywords: list[str] = guard.get("in_house_keywords", [])

    # ------------------------------------------------------------------ 공개 API
    def verify_suggestion(
        self,
        suggestion: str,
        owned_evidences: list[dict[str, Any]],
        banned_engine: Any,
        *,
        product_category: str = "일반",
        functional_type: str | None = None,
        original: str | None = None,
    ) -> tuple[bool, str]:
        """제안 문구를 다각도로 검증합니다.

        Returns:
            (is_valid, note) - note 는 실패 시 재제안 프롬프트에 그대로 전달된다.
        """
        issues = self.inspect(
            suggestion,
            owned_evidences,
            banned_engine,
            product_category=product_category,
            functional_type=functional_type,
            original=original,
        )
        if not issues:
            return (True, "검증 통과")
        return (False, "검증 실패: " + " / ".join(str(issue) for issue in issues))

    def inspect(
        self,
        suggestion: str,
        owned_evidences: list[dict[str, Any]],
        banned_engine: Any = None,
        *,
        product_category: str = "일반",
        functional_type: str | None = None,
        original: str | None = None,
    ) -> list[VerifyIssue]:
        """위반 항목 목록을 반환합니다. 비어 있으면 통과."""
        text = (suggestion or "").strip()
        if not text:
            return [VerifyIssue("빈문구", "-", "제안 문구가 비어 있습니다")]

        evidences = [e if isinstance(e, dict) else dict(e) for e in owned_evidences or []]
        own_types = self._functional_types(product_category, functional_type)

        issues: list[VerifyIssue] = []
        if original is not None and _compact(original) == _compact(text):
            issues.append(VerifyIssue("미수정", "-", "원문과 같은 문구를 다시 제안했습니다"))
        issues += self._check_forbidden(text, own_types)
        issues += self._check_functional(text, product_category, own_types)
        issues += self._check_substantiation(text, evidences, own_types)
        issues += self._check_numbers(text, evidences)
        issues += self._check_banned_engine(text, product_category, functional_type, banned_engine)
        return issues

    # ------------------------------------------------------------------ 개별 검사
    def _functional_types(self, category: str, functional_type: str | None) -> set[str]:
        """제품이 심사(보고)받은 기능성 유형. 일반 제품은 빈 집합."""
        if category != "기능성" or not functional_type:
            return set()
        return {
            claim["type"]
            for claim in self.functional_claims
            if any(keyword in functional_type for keyword in claim.get("type_keywords", []))
        }

    def _check_forbidden(self, text: str, own_types: set[str]) -> list[VerifyIssue]:
        issues = []
        for rule in self.forbidden:
            match = re.search(rule["pattern"], text, re.IGNORECASE)
            if not match:
                continue
            if rule.get("unless") and re.search(rule["unless"], text, re.IGNORECASE):
                continue
            if own_types & set(rule.get("unless_functional", [])):
                continue
            issues.append(VerifyIssue("금지표현", rule["basis_id"], rule["reason"], match.group(0)))
        return issues

    def _check_functional(self, text: str, category: str, own_types: set[str]) -> list[VerifyIssue]:
        issues = []
        for claim in self.functional_claims:
            match = re.search(claim["pattern"], text, re.IGNORECASE)
            if not match or claim["type"] in own_types:
                continue
            if category != "기능성":
                issues.append(VerifyIssue(
                    "기능성오인", "LAW_시행규칙_별표5-2나",
                    f"일반 화장품에 '{claim['type']}' 기능성 표현({claim['law']})을 썼습니다",
                    match.group(0),
                ))
            else:
                issues.append(VerifyIssue(
                    "범위이탈", "GUIDE_관리지침_별표1_기능성",
                    f"심사(보고)받은 기능성 범위 밖의 '{claim['type']}' 표현입니다",
                    match.group(0),
                ))
        return issues

    def _is_survey(self, evidence: dict[str, Any]) -> bool:
        body = _evidence_text(evidence)
        return any(keyword in body for keyword in self.survey_keywords)

    def _check_substantiation(
        self, text: str, evidences: list[dict[str, Any]], own_types: set[str]
    ) -> list[VerifyIssue]:
        # 실증규정 제3조 제3항: 효능 주장은 조사결과(만족도 등)가 아닌 시험결과로 입증해야 한다.
        tests = [_compact(_evidence_text(e)) for e in evidences if not self._is_survey(e)]
        issues = []
        for rule in self.substantiation:
            match = re.search(rule["pattern"], text, re.IGNORECASE)
            if not match:
                continue
            if own_types & set(rule.get("functional_supports", [])):
                continue
            keywords = [_compact(k) for k in rule.get("evidence_keywords", [])]
            supported = any(
                (not keywords) or any(keyword in body for keyword in keywords)
                for body in tests
            )
            if not supported:
                issues.append(VerifyIssue(
                    "실증필요", rule["basis_id"],
                    "실증 대상 표현인데 이를 직접 입증하는 보유 시험자료가 없습니다",
                    match.group(0),
                ))
        return issues

    def _check_numbers(self, text: str, evidences: list[dict[str, Any]]) -> list[VerifyIssue]:
        owned = [(_number_tokens(_evidence_text(e)), self._is_survey(e), e) for e in evidences]
        mentions_survey = any(keyword in text for keyword in self.survey_keywords)
        compact_text = _compact(text)
        issues = []
        for token in sorted(_number_tokens(text)):
            matched = [(is_survey, e) for tokens, is_survey, e in owned if token in tokens]
            owners = [is_survey for is_survey, _ in matched]
            if not owners:
                issues.append(VerifyIssue(
                    "숫자날조", "GUIDE_관리지침_별표2_효능표현",
                    "보유 근거에 없는 수치입니다", token,
                ))
            elif all(owners) and all(self._is_in_house(e) for _, e in matched):
                # 실증규정 제5조 1호: 조사기관은 사업자와 독립적이어야 한다.
                issues.append(VerifyIssue(
                    "조사결과오용", "NOTICE_실증규정_제5조",
                    "회사가 직접 한 조사 수치는 실증자료로 인정되지 않습니다 (독립된 조사기관 필요)",
                    token,
                ))
            elif all(owners) and not mentions_survey:
                issues.append(VerifyIssue(
                    "조사결과오용", "NOTICE_실증규정_제3조",
                    "만족도·설문 조사 수치를 효능 수치처럼 표현했습니다 ('만족도' 등 조사임을 밝혀야 함)",
                    token,
                ))
            elif all(owners) and not any(self._mentions_item(compact_text, e) for _, e in matched):
                issues.append(VerifyIssue(
                    "조사결과오용", "NOTICE_실증규정_제3조",
                    "조사 수치를 조사 항목과 다른 효능에 붙였습니다 (조사한 항목을 함께 밝혀야 함)",
                    token,
                ))
        return issues

    def _is_in_house(self, evidence: dict[str, Any]) -> bool:
        body = " ".join(str(evidence.get(key) or "") for key in ("test_type", "institute"))
        return any(keyword in body for keyword in self.in_house_keywords)

    def _mentions_item(self, compact_text: str, evidence: dict[str, Any]) -> bool:
        """조사 항목(예: '피부 탄력감 만족도'의 '탄력감')이 문구에 함께 나오는지."""
        words = re.findall(r"[가-힣A-Za-z]{2,}", str(evidence.get("item") or ""))
        generic = {"피부", "모발", "제품", "사용", *self.survey_keywords}
        words = [w for w in words if w not in generic and not any(k in w for k in self.survey_keywords)]
        return not words or any(_compact(w) in compact_text for w in words)

    @staticmethod
    def _check_banned_engine(
        text: str, category: str, functional_type: str | None, banned_engine: Any
    ) -> list[VerifyIssue]:
        """규칙 엔진(rules.py)이 있으면 같은 사전으로 한 번 더 검사한다.

        기능성 유형을 함께 넘겨야 심사받은 효능 문구(예: 탈모 증상 완화)를 금지어로 오탐하지 않는다.
        """
        if banned_engine is None or not hasattr(banned_engine, "check_banned_terms"):
            return []
        try:
            level, hits = banned_engine.check_banned_terms(text, category, functional_type)
        except TypeError:  # 기능성 유형을 받지 않는 예전 엔진
            level, hits = banned_engine.check_banned_terms(text, category)
        if level < 2:
            return []
        return [
            VerifyIssue("금지어", str(hit.get("basis_id", "-")), f"금지어 사전 적발: {hit.get('term', '')}")
            for hit in hits
        ] or [VerifyIssue("금지어", "-", "금지어 사전 적발")]
