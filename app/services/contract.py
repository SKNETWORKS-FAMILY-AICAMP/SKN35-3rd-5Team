"""
[app/services/contract.py]
화면(app/)이 데이터 공급 함수(app/services/backend.py)에서 받는 데이터 모양.

- 화면 코드는 이 파일의 모양만 안다. Mock 이든 실제 API 든 같은 모양으로 넘어온다.
- ReviewResponse 의 필수 부분은 팀 계약 src/cosmetic_agent/domain/schemas.py 와 같다.
- `ui` 키는 화면이 쓰는 **선택 확장**이다. 백엔드가 아직 주지 않아도 화면은 동작하고,
  해당 블록(위험 표현 하이라이트, 표현 사다리 위치 등)만 생략된다.
- 아래 EXAMPLE_* 는 화면 개발·시각 점검용 예시다. 실제 판정 결과가 아니다.
"""
from typing import Literal, NotRequired, TypedDict

Level = Literal[0, 1, 2]
Status = Literal["판정", "판단보류"]
Verdict = Literal["가능", "조건부", "불가", "판단보류"]
ViolationType = Literal["의약품오인", "범위이탈", "기능성오인", "실증필요", "비교광고", "소비자오인", "없음"]
Authority = Literal[1, 2, 3, 4]

AUTHORITY_LABEL: dict[int, str] = {1: "법령", 2: "고시", 3: "지침", 4: "사례"}
VERDICT_BY_LEVEL: dict[int, Verdict] = {0: "가능", 1: "조건부", 2: "불가"}

# LangGraph 9단계 노드 (src/cosmetic_agent/workflow/graph.py 순서) → 화면 표시 이름
PIPELINE_STEPS: list[tuple[str, str]] = [
    ("parse_input", "입력 확인"),
    ("rule_check", "금지어 규칙 검사"),
    ("judge_claim", "AI 판정"),
    ("build_query", "검색 질의 재작성"),
    ("retrieve_rules", "법령 하이브리드 검색"),
    ("organize_evidence", "근거 정리"),
    ("suggest_copy", "대체 문구 제안"),
    ("verify_copy", "제안 문구 역검증"),
    ("finalize", "최종 확정"),
]


# ── 제품·실증 (= schemas.OwnedEvidence / ProductCard) ─────────────────────
class Evidence(TypedDict):
    test_type: str              # 시험 종류 (인체적용시험 · 자사비교시험 …)
    item: str                   # 시험 항목
    value: str | None           # 결과 수치 ("4주 사용 후 보습력 42% 개선")
    institute: str | None       # 시험 기관


class Product(TypedDict):
    product_id: str
    name: str
    category: Literal["일반", "기능성"]
    functional_type: str | None
    owned_evidence: list[Evidence]   # 심사 요청에는 사이드바에서 체크한 실증만 담는다


# ── 심사 결과 (= schemas.Citation / ReviewResult / ExecutionTiming) ──────
class Citation(TypedDict):
    chunk_id: str               # "LAW_화장품법_제13조"
    source: str                 # "화장품법"
    article: str                # "제13조 제1항 제1호"
    authority: Authority        # 1 법령 · 2 고시 · 3 지침 · 4 사례
    content_snippet: str | None


class Result(TypedDict):
    status: Status
    level: Level | None         # 판단보류면 None
    violation_type: ViolationType
    claim_type: str | None      # 효능 분류 (보습 · 진정 · 탈모 …)
    citations: list[Citation]
    suggestion: str | None      # 보유 실증 기준 최선의 문구
    next_test: str | None       # 한 칸 더 오르려면 필요한 시험
    review_notes: str | None


class Timing(TypedDict):
    retrieval_ms: float
    llm_ms: float
    total_ms: float


# ── 화면 선택 확장 (ui) ────────────────────────────────────────────────
class Highlight(TypedDict):
    start: int                  # input_text 안 문자 위치 [start, end)
    end: int
    text: str
    kind: Literal["risk", "verified"]   # risk = 위험 표현 · verified = 보유 실증과 일치하는 숫자
    label: str                  # "의약품 오인" · "과장 표현" · "실증 일치"
    reason: str
    violation_type: ViolationType | None
    level: Level | None
    decisive: bool              # 판정을 결정한 표현이면 True (채움 표시), 나머지 risk 는 밑줄
    cites: list[int]            # result.citations 의 1-기반 번호


class Rung(TypedDict):
    lv: int | Literal["X"]      # 0 · 1 · 2, "X" = 불가 칸 (어떤 실증으로도 못 씀)
    text: str                   # 예시 표현
    needs: str                  # 필요한 근거
    owned: bool                 # 지금 체크한 실증으로 충족되는지


class Ladder(TypedDict):
    claim: str                  # 효능 분류
    rungs: list[Rung]           # 낮은 칸 → 높은 칸 → 불가 칸 순
    reachable: int              # 보유 실증으로 갈 수 있는 최고 칸
    original: int | Literal["X"] | None   # 원문이 놓인 칸
    proposal: int | None        # 제안 문구가 놓인 칸


class DiffItem(TypedDict):
    op: Literal["-", "+"]
    text: str
    why: str


class Reverify(TypedDict):
    numbers_ok: int             # 제안 문구 속 숫자 중 실증과 일치한 개수
    numbers_total: int
    banned: int                 # 제안 문구 금지어 재검사 적발 건수


class Step(TypedDict):
    key: str                    # PIPELINE_STEPS 의 노드 이름
    name: str
    status: Literal["done", "fail", "skip", "pending"]
    ms: float | None


class NextTest(TypedDict):
    phrase: str                 # 시험을 갖추면 열리는 표현 ("24시간 보습")
    need: str                   # 필요한 시험
    rung: int                   # 열리는 칸


class Variant(TypedDict, total=False):
    """대체 문구 후보 한 개. 백엔드 copy_suggester 의 candidates(강한→안전 순) 한 칸에 대응한다."""
    text: str
    tier: Literal["strong", "balanced", "safe"]   # 근거 최대 · 균형 · 가장 안전 (candidates 순서)
    basis: str                  # 이 표현을 쓸 수 있는 근거 한 줄 (used_evidence · 사다리 칸 · 필요 자료)
    verified: bool | None       # 역검증 통과 True · 탈락 False · 검증 안 함 None
    note: str | None            # 탈락 사유 (rejected_notes)
    chosen: bool                # 엔진이 고른 제안 (= result.suggestion)


class ChartBlock(TypedDict, total=False):
    """답변에 붙는 차트 — 데이터가 있을 때만 백엔드가 보낸다."""
    type: Literal["chart"]
    title: str
    unit: str
    data: list[dict]            # [{label, value}]


class QuestionBlock(TypedDict, total=False):
    """추가 질문 — 판정에 사용자 입력이 필요할 때만 백엔드가 보낸다."""
    type: Literal["question"]
    id: str
    prompt: str
    options: list[str]          # 고르면 그 답을 붙여 다시 묻는다
    follow_up: str              # 다시 물을 문장 틀. "{answer}" 자리에 고른 답이 들어간다


class UiExtras(TypedDict, total=False):
    highlights: list[Highlight]
    ladder: Ladder
    diff: list[DiffItem]
    reverify: Reverify
    steps: list[Step]
    next_test: NextTest
    suggestion_source: str      # 제안 문구 뒤 출처 괄호 "(인체적용시험, 한국피부과학연구원)"
    summary: str                # 판정 한 줄 요약
    direction: str              # 제안 방향 한 줄
    alternatives: list[str]     # (구) 다른 표현 — variants 가 있으면 쓰지 않는다
    variants: list[Variant]     # 대체 문구 후보 (강한 → 안전)
    blocks: list[ChartBlock | QuestionBlock]   # 필요할 때만 붙는 확장 블록


# ── 검토 진행 이벤트 (backend.review_events 가 내는 것) ─────────────────
# API 에 POST /review/stream (NDJSON, 한 줄 = 이벤트 하나)이 생기면 그대로 흘려보내고, 없으면 result 하나만 낸다.
class StageEvent(TypedDict):
    type: Literal["stage"]
    key: str                    # PIPELINE_STEPS 의 노드 이름
    status: Literal["start", "done", "skip"]
    ms: NotRequired[float | None]   # done 일 때 실제 걸린 시간


class TokenEvent(TypedDict):
    type: Literal["token"]
    text: str                   # 답변 요약(review_notes) 조각 — LLM 이 실제로 흘려보낼 때만


class WaitEvent(TypedDict):
    type: Literal["wait"]       # 단계 정보 없이 서버 응답을 기다리는 중 (스트림이 없는 API)


class ResultEvent(TypedDict):
    type: Literal["result"]
    resp: "ReviewResponse"


class ReviewResponse(TypedDict):
    request_id: str
    input_text: str
    result: Result
    timing: Timing
    ui: NotRequired[UiExtras]
    mock: NotRequired[bool]     # Mock 응답이면 True → 화면이 "데모 데이터" 를 표시


class GeneratedCandidate(TypedDict):
    text: str
    tier: Literal["strong", "balanced", "safe"]
    rationale: str
    used_evidence: list[str]
    cited_ids: list[str]
    verified: bool
    verify_note: str


class GenerateResponse(TypedDict):
    request_id: str
    status: Literal["생성완료", "생성보류"]
    product_id: str
    candidates: list[GeneratedCandidate]
    citations: list[Citation]
    warnings: list[str]
    timing: Timing
    mock: NotRequired[bool]


# ── 규정 검색 (= api/routes/search.py 응답 한 건) ──────────────────────
class SearchHit(TypedDict):
    content: str
    metadata: dict              # id · source · doc_type(법령|고시|지침|사례) · authority · article · product_scope · effective_date


def verdict_of(result: Result) -> Verdict:
    """결과 계약에서 화면 판정 이름을 구한다."""
    if result.get("status") == "판단보류" or result.get("level") is None:
        return "판단보류"
    return VERDICT_BY_LEVEL[int(result["level"])]


# ── 예시 데이터 (화면 개발·시각 점검용) ─────────────────────────────────
def _span(text: str, phrase: str) -> tuple[int, int]:
    start = text.index(phrase)
    return start, start + len(phrase)


EXAMPLE_PRODUCT: Product = {
    "product_id": "PROD_001",
    "name": "하이드라 워터 크림",
    "category": "일반",
    "functional_type": None,
    "owned_evidence": [
        {
            "test_type": "인체적용시험",
            "item": "피부 겉보습 및 속보습 개선",
            "value": "4주 사용 후 보습력 42% 개선",
            "institute": "한국피부과학연구원",
        }
    ],
}

_CITE_LAW_13: Citation = {
    "chunk_id": "LAW_화장품법_제13조",
    "source": "화장품법",
    "article": "제13조 제1항 제1호",
    "authority": 1,
    "content_snippet": "영업자 또는 판매자는 다음 각 호의 어느 하나에 해당하는 표시 또는 광고를 하여서는 아니 된다. "
    "1. 의약품으로 잘못 인식할 우려가 있는 표시 또는 광고",
}
_CITE_RULE_ANNEX5: Citation = {
    "chunk_id": "LAW_시행규칙_별표5-2가",
    "source": "화장품법 시행규칙",
    "article": "[별표 5] 제2호 가목",
    "authority": 1,
    "content_snippet": "의약품으로 잘못 인식할 우려가 있는 내용, 제품의 명칭 및 효능ㆍ효과 등에 대한 표시ㆍ광고를 하지 말 것",
}
_CITE_RULE_ANNEX5_SA: Citation = {
    "chunk_id": "LAW_시행규칙_별표5-2사",
    "source": "화장품법 시행규칙",
    "article": "[별표 5] 제2호 사목",
    "authority": 1,
    "content_snippet": "사실과 다르거나 부분적으로 사실이라고 하더라도 전체적으로 보아 소비자가 잘못 인식할 우려가 있는 "
    "표시ㆍ광고 또는 소비자를 속이거나 소비자가 속을 우려가 있는 표시ㆍ광고를 하지 말 것",
}
_CITE_NOTICE_3: Citation = {
    "chunk_id": "NOTICE_실증규정_제3조",
    "source": "화장품 표시·광고 실증에 관한 규정",
    "article": "제3조(실증자료)",
    "authority": 2,
    "content_snippet": "실증자료의 내용은 광고에서 주장하는 내용과 직접적인 관계가 있어야 한다.",
}
_CITE_GUIDE_ANNEX1: Citation = {
    "chunk_id": "GUIDE_관리지침_별표1",
    "source": "화장품 표시·광고 관리 지침",
    "article": "[별표 1] 생리활성 관련 금지 표현",
    "authority": 3,
    "content_snippet": "금지 표현: 혈액순환 · 피부재생, 세포 재생 · 호르몬 분비촉진 등 내분비 작용 · 세포 성장을 촉진한다.",
}
_CITE_CASE_20250806: Citation = {
    "chunk_id": "CASE_2025-08-06",
    "source": "식약처 보도자료",
    "article": "2025-08-06 \"피부재생\", \"염증완화\" 등 화장품 부당광고 적발",
    "authority": 4,
    "content_snippet": "\"피부재생\", \"염증완화\" 등 의약품으로 오인할 우려가 있는 화장품 부당광고 83건 적발",
}

_FAIL_TEXT = "단 4주 만에 보습력 42% 폭발적 개선 입증! 손상 피부 완벽 재생!"
_s_regen = _span(_FAIL_TEXT, "완벽 재생")
_s_boom = _span(_FAIL_TEXT, "폭발적 개선")
_s_4w = _span(_FAIL_TEXT, "4주")
_s_42 = _span(_FAIL_TEXT, "42%")

_MOISTURE_RUNGS: list[Rung] = [
    {"lv": 0, "text": "촉촉하게 가꿔줌 / 건조함 예방", "needs": "근거 불필요", "owned": True},
    {"lv": 1, "text": "피부 보습 유지에 도움", "needs": "성분·제형 근거", "owned": True},
    {"lv": 2, "text": "24시간 보습 지속 / 보습력 N% 개선", "needs": "인체적용시험 보고서 + 시험 대상·조건 표기", "owned": True},
    {"lv": "X", "text": "진피층까지 수분 침투 / 수분 세포 영구 재생", "needs": "불가 (의약품 오인 또는 범위 이탈)", "owned": False},
]


def _steps(llm_ms: float, retrieval_ms: float) -> list[Step]:
    timed = {"judge_claim": llm_ms, "retrieve_rules": retrieval_ms}
    return [{"key": k, "name": n, "status": "done", "ms": timed.get(k)} for k, n in PIPELINE_STEPS]


EXAMPLE_REVIEW_FAIL: ReviewResponse = {
    "request_id": "REQ_DEMO_001",
    "input_text": _FAIL_TEXT,
    "result": {
        "status": "판정",
        "level": 2,
        "violation_type": "의약품오인",
        "claim_type": "보습",
        "citations": [_CITE_LAW_13, _CITE_RULE_ANNEX5, _CITE_NOTICE_3, _CITE_GUIDE_ANNEX1, _CITE_CASE_20250806],
        "suggestion": "4주 사용 후 피부 보습력 42% 개선",
        "next_test": "보습 지속 시간(24시간) 표현을 쓰려면 지속 시간을 측정한 인체적용시험 보고서와 시험 대상·조건 표기가 필요합니다.",
        "review_notes": "'완벽 재생'은 관리지침이 금지한 '피부재생, 세포 재생' 표현에 해당해 의약품으로 오인될 수 있습니다.",
    },
    "timing": {"retrieval_ms": 412.0, "llm_ms": 1870.0, "total_ms": 2410.0},
    "ui": {
        "summary": "의약품으로 오인될 표현이 있어 이대로는 게재할 수 없습니다.",
        "highlights": [
            {"start": _s_regen[0], "end": _s_regen[1], "text": "완벽 재생", "kind": "risk", "label": "의약품 오인",
             "reason": "관리지침이 금지한 표현 '피부재생, 세포 재생'에 해당합니다.", "violation_type": "의약품오인",
             "level": 2, "decisive": True, "cites": [1, 4, 5]},
            {"start": _s_boom[0], "end": _s_boom[1], "text": "폭발적 개선", "kind": "risk", "label": "과장 표현",
             "reason": "효과를 부풀려 소비자를 오인하게 하는 과장 표현입니다.", "violation_type": "소비자오인",
             "level": 1, "decisive": False, "cites": [2]},
            {"start": _s_4w[0], "end": _s_4w[1], "text": "4주", "kind": "verified", "label": "실증 일치",
             "reason": "보유한 인체적용시험 결과(4주 사용)와 일치합니다.", "violation_type": None,
             "level": None, "decisive": False, "cites": [3]},
            {"start": _s_42[0], "end": _s_42[1], "text": "42%", "kind": "verified", "label": "실증 일치",
             "reason": "보유한 인체적용시험 결과(보습력 42% 개선)와 일치합니다.", "violation_type": None,
             "level": None, "decisive": False, "cites": [3]},
        ],
        "ladder": {"claim": "보습", "rungs": _MOISTURE_RUNGS, "reachable": 2, "original": "X", "proposal": 2},
        "diff": [
            {"op": "-", "text": "손상 피부 완벽 재생", "why": "의약품 오인 표현 삭제"},
            {"op": "-", "text": "폭발적, 입증!", "why": "과장 표현 삭제"},
            {"op": "+", "text": "인체적용시험, 한국피부과학연구원", "why": "실증 출처 표기"},
        ],
        "reverify": {"numbers_ok": 2, "numbers_total": 2, "banned": 0},
        "steps": _steps(1870.0, 412.0),
        "next_test": {"phrase": "24시간 보습", "need": "지속 시간을 측정한 인체적용시험 보고서 + 시험 대상·조건 표기", "rung": 2},
        "suggestion_source": "(인체적용시험, 한국피부과학연구원)",
    },
    "mock": True,
}

_COND_TEXT = "바르는 순간부터 24시간 촉촉함이 지속되는 수분 크림"
_s_24 = _span(_COND_TEXT, "24시간 촉촉함이 지속")

EXAMPLE_REVIEW_CONDITIONAL: ReviewResponse = {
    "request_id": "REQ_DEMO_002",
    "input_text": _COND_TEXT,
    "result": {
        "status": "판정",
        "level": 1,
        "violation_type": "실증필요",
        "claim_type": "보습",
        "citations": [
            {"chunk_id": "LAW_화장품법_제14조", "source": "화장품법", "article": "제14조 제1항", "authority": 1,
             "content_snippet": "영업자 및 판매자는 자기가 행한 표시ㆍ광고 중 사실과 관련한 사항에 대하여는 이를 실증할 수 있어야 한다."},
            _CITE_NOTICE_3,
        ],
        "suggestion": "4주 사용 후 피부 보습력 42% 개선",
        "next_test": "24시간 보습 지속을 표현하려면 지속 시간을 측정한 인체적용시험 보고서가 필요합니다.",
        "review_notes": "보유 실증은 보습력 개선이고, 지속 시간은 실증하지 않았습니다.",
    },
    "timing": {"retrieval_ms": 388.0, "llm_ms": 1520.0, "total_ms": 2030.0},
    "ui": {
        "summary": "지속 시간을 실증하는 시험이 있어야 쓸 수 있습니다.",
        "highlights": [
            {"start": _s_24[0], "end": _s_24[1], "text": "24시간 촉촉함이 지속", "kind": "risk", "label": "실증 필요",
             "reason": "보습 지속 시간은 보유 실증(4주 보습력 개선)으로 뒷받침되지 않습니다.", "violation_type": "실증필요",
             "level": 1, "decisive": True, "cites": [1, 2]},
        ],
        "ladder": {"claim": "보습", "rungs": _MOISTURE_RUNGS, "reachable": 2, "original": 2, "proposal": 2},
        "diff": [
            {"op": "-", "text": "24시간 촉촉함이 지속", "why": "실증 없는 지속 시간 삭제"},
            {"op": "+", "text": "4주 사용 후 피부 보습력 42% 개선", "why": "보유 실증 수치로 교체"},
        ],
        "reverify": {"numbers_ok": 2, "numbers_total": 2, "banned": 0},
        "steps": _steps(1520.0, 388.0),
        "next_test": {"phrase": "24시간 보습", "need": "지속 시간을 측정한 인체적용시험 보고서 + 시험 대상·조건 표기", "rung": 2},
        "suggestion_source": "(인체적용시험, 한국피부과학연구원)",
    },
    "mock": True,
}

EXAMPLE_REVIEW_PASS: ReviewResponse = {
    "request_id": "REQ_DEMO_003",
    "input_text": "피부 보습 유지에 도움을 주는 데일리 수분 크림",
    "result": {
        "status": "판정",
        "level": 0,
        "violation_type": "없음",
        "claim_type": "보습",
        "citations": [],
        "suggestion": None,
        "next_test": None,
        "review_notes": "일반 화장품의 보습 표현 범위 안입니다.",
    },
    "timing": {"retrieval_ms": 301.0, "llm_ms": 1104.0, "total_ms": 1520.0},
    "ui": {
        "summary": "그대로 써도 됩니다.",
        "highlights": [],
        "ladder": {"claim": "보습", "rungs": _MOISTURE_RUNGS, "reachable": 2, "original": 1, "proposal": None},
        "steps": [
            {"key": k, "name": n, "status": "skip" if k in ("suggest_copy", "verify_copy") else "done", "ms": None}
            for k, n in PIPELINE_STEPS
        ],
    },
    "mock": True,
}

EXAMPLE_REVIEW_HOLD: ReviewResponse = {
    "request_id": "REQ_DEMO_004",
    # 2026-10-13: '엑소좀'은 팀 금지 표현 사전 B091(인체유래 표방)로 판정이 생겨 보류 예시를 PDRN 으로 바꿨다
    "input_text": "PDRN 성분이 피부 속 깊이 전달되는 신개념 앰플",
    "result": {
        "status": "판단보류",
        "level": None,
        "violation_type": "없음",
        "claim_type": None,
        "citations": [],
        "suggestion": None,
        "next_test": None,
        "review_notes": "신뢰할 수 있는 법령 근거를 찾지 못하여 RA 전문가 검토가 필요합니다.",
    },
    "timing": {"retrieval_ms": 1210.0, "llm_ms": 980.0, "total_ms": 2390.0},
    "ui": {
        "summary": "근거 조항을 충분히 찾지 못했습니다. 전문가 검토가 필요합니다.",
        "highlights": [],
        "steps": [
            {"key": k, "name": n, "status": "skip" if k in ("organize_evidence", "suggest_copy", "verify_copy") else "done", "ms": None}
            for k, n in PIPELINE_STEPS
        ],
    },
    "mock": True,
}

EXAMPLE_REVIEWS: dict[Verdict, ReviewResponse] = {
    "불가": EXAMPLE_REVIEW_FAIL,
    "조건부": EXAMPLE_REVIEW_CONDITIONAL,
    "가능": EXAMPLE_REVIEW_PASS,
    "판단보류": EXAMPLE_REVIEW_HOLD,
}
