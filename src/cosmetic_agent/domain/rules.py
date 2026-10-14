"""
[domain/rules.py]
금지 표현 사전 및 표현 사다리를 기반으로 한 결정론적(Deterministic) 규칙 매칭 엔진.

판정 수준
    0 가능   : 걸리는 표현 없음, 또는 보유 근거로 입증됨
    1 조건부 : 실증 자료가 필요함 (수정하거나 시험을 추가하면 사용 가능)
    2 불가   : 근거가 있어도 쓸 수 없는 표현, 또는 보유 근거와 사실이 다른 표현

규칙 데이터 (data/assets, scripts/build_rule_assets.py 로 생성)
    banned_terms.json      불가(2) 표현      — 관리지침 [별표1], 시행규칙 [별표5] 제2호
    rule_patterns.json     조건부(1) 표현    — 관리지침 [별표2], 실증규정
    claim_ladder.json      효능별 표현 사다리
    functional_claims.json 기능성 유형별 심사 효능 천장 문구

공개 API
    check_banned_terms(text, category, functional_type=None) -> (0|2, hits)
        워크플로 하한 게이트와 CopyVerifier 가 쓰는 금지어 검사. 형식 변경 금지.
        hits[0] 은 가장 우선순위가 높은 위반이다.
    evaluate(text, product) -> dict
        금지어 + 실증·수치·비교 검사를 합친 규칙 판정 (R0 판정 모델이 사용)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..common.config import settings

VIOLATION_TYPES = ("의약품오인", "범위이탈", "기능성오인", "실증필요", "비교광고", "소비자오인", "없음")

# 같은 수준에서 위반이 겹칠 때 대표 유형을 고르는 순서 (앞일수록 우선)
VIOLATION_PRIORITY = ("의약품오인", "범위이탈", "기능성오인", "비교광고", "소비자오인", "실증필요")

# 숫자 + 단위. 단위 없는 숫자(제품명 숫자 등)는 효능 주장으로 보지 않는다. (verifier 와 같은 기준)
NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(%|퍼센트|배|주|일|개월|시간|분|회|명)")
UNIT_ALIASES = {"퍼센트": "%"}

# 실증규정 제3조 제3항: 조사결과(만족도 등)는 효능 주장의 직접 근거가 아니다.
SURVEY_KEYWORDS = ("만족", "설문", "선호", "응답", "소비자 조사", "사용감")
# 실증규정 제5조 제1호: 조사기관은 사업자와 독립적이어야 한다.
IN_HOUSE_KEYWORDS = ("자사", "사내", "자체")

# 수치가 효능 주장인지 가르는 서술어 (함량 표기와 구분)
_EFFICACY_RE = re.compile(r"개선|감소|증가|향상|효과|흡수|지속|완화|제거|입증|만족|높|빠르|깊|강해|케어")

_GENERIC_WORDS = {"피부", "모발", "손상된", "손상", "개선", "도움"}


def functional_types(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    """기능성 유형을 목록으로 정규화. '미백;주름 개선' 같은 복수 기능성(2중 기능성)도 받는다."""
    if not value:
        return []
    items = value if isinstance(value, (list, tuple)) else re.split(r"[;,/·+]|\s및\s", str(value))
    return [item.strip() for item in items if item and item.strip()]


def _matches_functional(functional_type: str | list[str] | tuple[str, ...] | None, exempt: list[str] | None) -> bool:
    """심사받은 기능성 유형이 규칙의 예외 목록에 해당하는지.
    '미백'·'피부 미백'처럼 표기가 달라도, '피부 미백, 주름 개선'처럼 두 가지여도 맞춘다."""
    if not exempt:
        return False
    parts = functional_types(functional_type)
    return any(part == e or part in e or e in part for part in parts for e in exempt if len(part) >= 2)


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def _number_tokens(text: str) -> set[str]:
    return {f"{n}{UNIT_ALIASES.get(u, u)}" for n, u in NUMBER_RE.findall(text or "")}


def _evidence_text(evidence: dict[str, Any]) -> str:
    return " ".join(str(evidence.get(k) or "") for k in ("test_type", "item", "value", "institute"))


def _is_survey(evidence: dict[str, Any]) -> bool:
    return any(k in _evidence_text(evidence) for k in SURVEY_KEYWORDS)


def _is_in_house(evidence: dict[str, Any]) -> bool:
    body = " ".join(str(evidence.get(k) or "") for k in ("test_type", "institute"))
    return any(k in body for k in IN_HOUSE_KEYWORDS)


class RuleEngine:
    def __init__(
        self,
        banned_terms_path: Path | None = None,
        claim_ladder_path: Path | None = None,
        functional_claims_path: Path | None = None,
        rule_patterns_path: Path | None = None,
    ):
        self.banned_terms_path = Path(banned_terms_path or settings.BANNED_TERMS_PATH)
        self.claim_ladder_path = Path(claim_ladder_path or settings.CLAIM_LADDER_PATH)
        self.functional_claims_path = Path(functional_claims_path or settings.FUNCTIONAL_CLAIMS_PATH)
        # config.py 를 건드리지 않도록 금지어 사전과 같은 폴더에서 찾는다
        self.rule_patterns_path = Path(rule_patterns_path or self.banned_terms_path.parent / "rule_patterns.json")

        self.banned_terms: list[dict[str, Any]] = self._load_json(self.banned_terms_path, [])
        self.claim_ladder: list[dict[str, Any]] = self._load_json(self.claim_ladder_path, [])
        self.functional_claims: list[dict[str, Any]] = self._load_json(self.functional_claims_path, [])
        patterns = self._load_json(self.rule_patterns_path, {})
        self.substantiation_rules: list[dict[str, Any]] = patterns.get("substantiation", [])
        self.comparison_rules: list[dict[str, Any]] = patterns.get("comparison", [])
        self.exaggeration_rules: list[dict[str, Any]] = patterns.get("exaggeration", [])
        self._compiled: dict[str, re.Pattern[str]] = {}

    # ------------------------------------------------------------------ 공통
    @staticmethod
    def _load_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _regex(self, pattern: str) -> re.Pattern[str]:
        if pattern not in self._compiled:
            self._compiled[pattern] = re.compile(pattern, re.IGNORECASE)
        return self._compiled[pattern]

    @staticmethod
    def _priority(hit: dict[str, Any]) -> tuple[int, int]:
        vtype = hit.get("type", "없음")
        rank = VIOLATION_PRIORITY.index(vtype) if vtype in VIOLATION_PRIORITY else len(VIOLATION_PRIORITY)
        return (-int(hit.get("level", 0)), rank)

    @staticmethod
    def _hit(rule: dict[str, Any], matched: str, level: int, **extra: Any) -> dict[str, Any]:
        return {
            "id": rule.get("id", ""),
            "term": rule.get("term", ""),
            "matched": matched,
            "level": level,
            "type": rule.get("type", "없음"),
            "basis_id": rule.get("basis_id", ""),
            "law_id": rule.get("law_id", ""),
            "fix_hint": rule.get("fix_hint"),
            "needs": rule.get("needs"),
            **extra,
        }

    @staticmethod
    def _is_exempt(rule: dict[str, Any], text: str, category: str, functional_type: str | list[str] | None) -> bool:
        """기능성 심사 범위 안의 표현이거나, 지침 단서 조항(예: '보습'+'일시적')을 만족하면 예외"""
        if category == "기능성" and functional_type and _matches_functional(functional_type, rule.get("exempt_functional")):
            return True
        required = rule.get("exempt_if_all") or []
        return bool(required) and all(word in text for word in required)

    # ------------------------------------------------------------------ 1) 금지 표현 (level 2)
    def check_banned_terms(
        self,
        text: str,
        product_category: str,
        functional_type: str | list[str] | None = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        """금지 표현 사전과 정규식 매칭하여 규칙 수준과 적발 항목을 반환합니다.

        Returns:
            (rule_level, hits)
            rule_level: 0 (적발 없음) 또는 2 (불가 표현 발견)
            hits: 우선순위 순 (hits[0] 이 대표 위반). 각 항목에 type, term, basis_id, law_id 포함.
        """
        hits: list[dict[str, Any]] = []
        if not text:
            return (0, hits)
        for rule in self.banned_terms:
            pattern = rule.get("pattern")
            if not pattern:
                continue
            if rule.get("scope", "공통") not in ("공통", product_category):
                continue
            if self._is_exempt(rule, text, product_category, functional_type):
                continue
            match = self._regex(pattern).search(text)
            if match:
                hits.append(self._hit(rule, match.group(0), int(rule.get("level", 2))))
        hits.sort(key=self._priority)
        return (max((h["level"] for h in hits), default=0), hits)

    # ------------------------------------------------------------------ 2) 수치 (보유 근거 대조)
    def _number_hits(self, text: str, evidences: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Separate sentences may legitimately cite different tests. Never pool their numbers.
        fragments = re.split(r"(?<=[.!?])\s+|\n+", text)
        return [hit for fragment in fragments for hit in self._number_claim_hits(fragment, evidences, context=text)]

    def _number_claim_hits(self, text: str, evidences: list[dict[str, Any]],
                           context: str | None = None) -> list[dict[str, Any]]:
        tokens = _number_tokens(text)
        if not tokens:
            return []
        # 줄바꿈으로 수치만 떨어진 경우('팔자 주름\n-18.49%')는 전체 문구에서 효능을 찾는다
        claim = self.detect_claim_type(text)
        if claim == "일반" and context:
            claim = self.detect_claim_type(context)
        scope = context or text
        if claim == "일반" and not _EFFICACY_RE.search(scope) and all(t.endswith("%") for t in tokens):
            # '레티놀 2%', '레티날 0.2퍼센트' 같은 함량 표기는 효능 수치가 아니다
            return []
        relevant = [e for e in evidences if claim != "일반" and self.detect_claim_type(str(e.get("item") or "")) == claim]
        valid = [e for e in relevant if not _is_survey(e) and not _is_in_house(e)]

        def supports(evidence: dict[str, Any]) -> bool:
            # Institution names / test labels are not measured results.
            return tokens <= _number_tokens(str(evidence.get("value") or ""))

        if any(supports(e) for e in valid):
            return []

        matched = ", ".join(sorted(tokens))
        # 수치가 조사(만족도·자사 조사) 자료에만 있음 → 실증자료로 인정되지 않음 (조건부)
        survey_sources = [e for e in evidences if (_is_survey(e) or _is_in_house(e)) and supports(e)]
        if survey_sources:
            in_house = any(_is_in_house(e) for e in survey_sources)
            rule = {
                "id": "N002", "term": "조사 결과 수치", "type": "실증필요",
                "basis_id": "NOTICE_실증규정_제5조" if in_house else "NOTICE_실증규정_제3조",
                "law_id": "LAW_시행규칙_별표5-2아",
                "needs": "사업자와 독립된 조사기관의 조사" if in_house else "효능 수치를 입증하는 인체적용시험 (만족도는 조사임을 밝혀야 함)",
            }
            return [self._hit(rule, matched, 1)]

        # 같은 효능의 시험을 갖고 있는데 수치가 다름 → 사실과 다른 표시 (불가)
        if valid:
            rule = {
                "id": "N001", "term": "보유 시험과 다른 수치", "type": "소비자오인",
                "basis_id": "GUIDE_관리지침_별표2_효능표현", "law_id": "LAW_시행규칙_별표5-2사",
                "fix_hint": "보유 시험 결과의 수치·기간을 그대로 사용",
            }
            return [self._hit(rule, matched, 2)]

        # 근거 시험 자체가 없음 → 실증 필요 (조건부)
        rule = {
            "id": "N003", "term": "근거 없는 수치", "type": "실증필요",
            "basis_id": "GUIDE_관리지침_별표2_효능표현", "law_id": "LAW_시행규칙_별표5-2아",
            "needs": "수치를 입증하는 인체적용시험 또는 인체 외 시험 자료 (시험 조건·기간 병기)",
        }
        return [self._hit(rule, matched, 1)]

    # ------------------------------------------------------------------ 3) 실증·비교·과장 (level 1)
    def _supported(self, rule: dict[str, Any], matched: str, text: str, product: dict[str, Any],
                   valid: list[dict[str, Any]]) -> bool:
        supports = rule.get("functional_supports") or []
        if product.get("category") == "기능성" and any(
            t in supports for t in functional_types(product.get("functional_type"))
        ):
            return True
        bodies = [_compact(_evidence_text(e)) for e in valid]
        rule_id = rule.get("id", "")

        if rule_id == "S002":  # 시험·검사 표현: 같은 효능의 시험이 있거나 수치가 시험과 일치
            claim = self.detect_claim_type(text)
            if claim != "일반" and any(self.detect_claim_type(_evidence_text(e)) == claim for e in valid):
                return True
            tokens = _number_tokens(text)
            return bool(tokens) and any(tokens <= _number_tokens(_evidence_text(e)) for e in valid)
        if rule_id == "S004":  # 무(無) 표현: 시험 분석 자료
            return any("분석" in body for body in bodies)
        if rule.get("type") == "비교광고":
            return any("비교" in body for body in bodies)

        # 별표2 실증대상: 같은 항목을 다룬 시험 자료가 있어야 함
        words = [re.sub(r"^(?:피부|모발)", "", w) for w in re.findall(r"[가-힣A-Za-z]{2,}", matched)]
        words = [w for w in words if len(w) >= 2 and w not in _GENERIC_WORDS]
        key = _compact(words[0])[:2] if words else _compact(matched)[:2]
        return bool(key) and any(key in body for body in bodies)

    def _soft_hits(self, text: str, product: dict[str, Any]) -> list[dict[str, Any]]:
        evidences = product.get("owned_evidence") or []
        valid = [e for e in evidences if not _is_survey(e) and not _is_in_house(e)]
        hits: list[dict[str, Any]] = []
        for rule in self.substantiation_rules + self.comparison_rules:
            match = self._regex(rule["pattern"]).search(text)
            if match and not self._supported(rule, match.group(0), text, product, valid):
                hits.append(self._hit(rule, match.group(0), int(rule.get("level", 1))))
        for rule in self.exaggeration_rules:
            match = self._regex(rule["pattern"]).search(text)
            if match:
                hits.append(self._hit(rule, match.group(0), int(rule.get("level", 1))))
        return hits

    # ------------------------------------------------------------------ 4) 표현 사다리
    def detect_claim_type(self, text: str) -> str:
        """표현 사다리 키워드로 문구의 효능 유형을 추정 (없으면 '일반')"""
        for entry in self.claim_ladder:
            for kw in entry.get("keywords", [entry.get("claim", "")]):
                if kw and kw in (text or ""):
                    return entry["claim"]
        return "일반"

    def get_ladder_ceiling(self, claim_keyword: str) -> dict[str, Any]:
        """표현 사다리에서 해당 키워드의 허용 단계별 요건을 조회합니다. 없으면 {}"""
        if not claim_keyword:
            return {}
        for entry in self.claim_ladder:
            if claim_keyword == entry.get("claim") or claim_keyword in entry.get("keywords", []):
                return entry
        return {}

    def get_functional_ceiling(self, functional_type: str | list[str] | None) -> dict[str, Any]:
        """기능성 유형별 심사받은 효능 천장 문구"""
        types = functional_types(functional_type)
        if not types:
            return {}
        return next((e for e in self.functional_claims if e.get("type") in types), {})

    # ------------------------------------------------------------------ 5) 종합 판정
    def evaluate(self, text: str, product: dict[str, Any]) -> dict[str, Any]:
        """금지어 + 수치 + 실증·비교·과장을 모두 검사한 규칙 판정

        Returns:
            {"level", "violation_type", "claim_type", "hits", "basis_ids", "next_test",
             "ladder", "functional_ceiling"}
        """
        category = product.get("category", "일반")
        functional_type = product.get("functional_type")
        evidences = product.get("owned_evidence") or []

        _, hard = self.check_banned_terms(text, category, functional_type)
        hits = hard + self._number_hits(text, evidences) + self._soft_hits(text, product)
        hits.sort(key=self._priority)

        level = max((h["level"] for h in hits), default=0)
        violation_type = hits[0]["type"] if hits else "없음"
        claim_type = self.detect_claim_type(text)
        # 법령(시행규칙 별표5) → 지침·고시 순으로 근거 ID 를 모은다
        basis_ids = list(dict.fromkeys(b for h in hits for b in (h.get("law_id"), h.get("basis_id")) if b))
        next_test = None
        if level == 1:
            needs = [h["needs"] for h in hits if h["level"] == 1 and h.get("needs")]
            next_test = " / ".join(dict.fromkeys(needs)) or "광고 주장과 직접 관련된 인체적용시험 또는 인체 외 시험 자료"

        return {
            "level": level,
            "violation_type": violation_type,
            "claim_type": claim_type,
            "hits": hits,
            "basis_ids": basis_ids,
            "next_test": next_test,
            "ladder": self.get_ladder_ceiling(claim_type),
            "functional_ceiling": self.get_functional_ceiling(functional_type),
        }
