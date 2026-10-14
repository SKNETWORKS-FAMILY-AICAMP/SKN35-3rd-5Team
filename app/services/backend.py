"""
[app/services/backend.py]
화면이 부르는 유일한 데이터 함수 모음. Mock 과 실제 API 를 같은 모양(app/services/contract.py)으로 돌려준다.

백엔드 담당자가 바꿀 곳
- 모드 전환: 환경변수 UI_DATA_MODE = "mock"(기본) | "api" | "local".
  local = 별도 서버 없이 FastAPI 앱(api.main)을 이 프로세스 안에서 그대로 실행한다 (무료 배포용, 응답은 api 와 같음).
- API 주소: cosmetic_agent.common.config.settings.API_BASE_URL (.env 의 API_BASE_URL). 기본 http://localhost:8000.
- 엔드포인트: POST /review · POST /review/bulk · GET /search · GET /health — 아래 _post/_get 을 부르는 함수만 보면 된다.
- 진행 이벤트: review_events() — POST /review/stream(NDJSON)이 있으면 단계·토큰을 그대로 흘리고, 없으면(404)
  POST /review 결과 하나만 낸다. 화면은 받은 이벤트만 그린다(지어낸 진행률 없음).
- API 가 실패하면 Mock 으로 바꿔치기하지 않고 BackendError 를 올린다(화면이 오류로 보여 준다).
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import httpx

from app.services import data_sources as ds
from app.services import mock

_REPO = Path(__file__).resolve().parents[2]
MAX_SENTENCES = 100


class BackendError(Exception):
    """화면에 그대로 보여 줄 한국어 메시지를 담은 오류."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message)
        self.message = message
        self.cause = cause


# ── 모드 · 연결 ─────────────────────────────────────────────────────
def data_mode() -> str:
    """"mock"(기본) · "api" · "local"."""
    mode = os.getenv("UI_DATA_MODE", "mock").strip().lower()
    return mode if mode in ("api", "local") else "mock"


def api_base_url() -> str:
    if data_mode() == "local":
        return "내장 에이전트"
    try:
        from cosmetic_agent.common.config import settings

        return settings.API_BASE_URL.rstrip("/")
    except Exception:
        return os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


_LOCAL_CLIENT = None


def _local_client():
    """local 모드: FastAPI 앱을 한 번만 띄워(lifespan 실행) 같은 프로세스에서 호출한다."""
    global _LOCAL_CLIENT
    if _LOCAL_CLIENT is None:
        if str(_REPO) not in sys.path:
            sys.path.insert(0, str(_REPO))
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()  # 시작 이벤트: 검토 서비스·그래프를 한 번 준비
        _LOCAL_CLIENT = client
    return _LOCAL_CLIENT


def _send(method: str, path: str, *, timeout: float, **kwargs):
    if data_mode() == "local":
        return _local_client().request(method, path, **kwargs)
    return httpx.request(method, f"{api_base_url()}{path}", timeout=timeout, **kwargs)


def _get(path: str, *, params: dict | None = None, timeout: float = 30.0):
    try:
        res = _send("GET", path, params=params, timeout=timeout)
        res.raise_for_status()
        return res.json()
    except httpx.HTTPStatusError as err:
        raise BackendError(f"서버가 오류를 돌려줬습니다 (HTTP {err.response.status_code}).", err) from err
    except httpx.HTTPError as err:
        raise BackendError(f"검토 서버({api_base_url()})에 연결하지 못했습니다. 서버가 켜져 있는지 확인하세요.", err) from err


def _post(path: str, payload: dict, *, timeout: float = 60.0):
    try:
        res = _send("POST", path, json=payload, timeout=timeout)
        res.raise_for_status()
        return res.json()
    except httpx.HTTPStatusError as err:
        detail = ""
        try:
            detail = err.response.json().get("detail", "")
        except Exception:
            pass
        msg = detail if isinstance(detail, str) and detail else f"서버가 요청을 처리하지 못했습니다 (HTTP {err.response.status_code})."
        raise BackendError(msg, err) from err
    except httpx.HTTPError as err:
        raise BackendError(f"검토 서버({api_base_url()})에 연결하지 못했습니다. 서버가 켜져 있는지 확인하세요.", err) from err


def health() -> dict:
    """{mode, ok, label, detail} — 화면 오른쪽 위·사이드바 아래 상태 표시."""
    if data_mode() == "mock":
        return {"mode": "mock", "ok": True, "label": "데모 데이터", "detail": "백엔드 연결 전, Mock 응답으로 동작합니다"}
    if data_mode() == "local":
        try:
            info = _get("/health", timeout=60.0)
            return {"mode": "local", "ok": True, "label": "에이전트 실행 중",
                    "detail": f"내장 실행 · {info.get('service', '')} {info.get('version', '')}".strip()}
        except Exception as err:  # noqa: BLE001 - 초기화 실패도 화면에 그대로 보여 준다
            return {"mode": "local", "ok": False, "label": "에이전트 시작 실패", "detail": str(err)[:200]}
    try:
        info = _get("/health", timeout=2.0)
        return {"mode": "api", "ok": True, "label": "API 연결됨", "detail": f"{api_base_url()} · {info.get('service', '')} {info.get('version', '')}".strip()}
    except BackendError as err:
        return {"mode": "api", "ok": False, "label": "API 연결 실패", "detail": err.message}


# ── 제품 ────────────────────────────────────────────────────────────
def list_products() -> list[dict]:
    """심사할 제품 목록(data/assets/mock_products.json). 백엔드에 제품 API 가 없어 두 모드가 같다."""
    return [dict(p, owned_evidence=[dict(ev) for ev in p.get("owned_evidence", [])]) for p in ds.mock_products()]


def unlock_hint(product: dict, evidence: dict) -> str | None:
    """그 실증 하나가 여는 표현 칸 한 줄. 여는 칸이 없으면 None."""
    claim = ds.evidence_claim(evidence, product)
    if ds.evidence_kind(evidence) == "survey":
        return "만족도 조사라 효능 표현 칸은 열지 못합니다"
    if claim is None:
        return None
    alone = dict(product, owned_evidence=[evidence])
    bare = dict(product, owned_evidence=[])
    with_ev, without_ev = ds.ladder_for(claim, alone), ds.ladder_for(claim, bare)
    if with_ev is None:
        return None
    if with_ev["reachable"] > without_ev["reachable"]:
        return f"{claim} 표현 Lv{with_ev['reachable']}까지 열림"
    if ds.evidence_kind(evidence) == "human" and with_ev["reachable"] == 2:
        return f"{claim} 표현 Lv2 수치 표기 근거"
    return None


# ── 검토 ────────────────────────────────────────────────────────────
# 위험 표현 라벨 → 근거 스니펫에서 찾을 낱말 (API 모드에서 하이라이트를 실제 근거 번호에 잇는다)
_LABEL_WORDS = {
    "의약품 오인": ("의약품",), "기능성 오인": ("기능성",), "범위 이탈": ("범위",), "과장 표현": ("과장", "사실과 다르게"),
    "실증 필요": ("실증",), "최상급 표현": ("최고", "배타"), "비교 표현": ("비교",), "전문가 표방": ("의사", "추천"),
    "소비자 오인": ("소비자",),
}


def _link_citations(highlights: list[dict], citations: list[dict]) -> None:
    """하이라이트마다 근거 번호(cites)를 붙인다 — 스니펫·조항에 그 표현이나 유형 낱말이 나오는 번호.
    하나도 없으면 법령(권위 1) 첫 근거 하나. 근거가 없으면 비워 둔다."""
    texts = [f'{c.get("source", "")} {c.get("article", "")} {c.get("content_snippet", "")}' for c in citations]
    for h in highlights:
        if h.get("kind") == "verified" or h.get("cites"):
            continue
        words = {h.get("text", "")} | {w for w in re.split(r"\s+", h.get("text", "")) if len(w) >= 2}
        words |= set(_LABEL_WORDS.get(h.get("label", ""), ()))
        cites = [i for i, t in enumerate(texts, start=1) if any(w and w in t for w in words)]
        if not cites:
            cites = [i for i, c in enumerate(citations, start=1) if int(c.get("authority", 4)) == 1][:1]
        h["cites"] = cites


def _variants_from(resp: dict) -> list[dict] | None:
    """백엔드 제안 후보 → 화면 variants. ui.variants 가 오면 그대로, copy_suggester 결과
    (candidates · rejected_notes · used_evidence)가 응답에 실려 오면 같은 뜻으로 옮긴다."""
    ui = resp.get("ui") or {}
    if ui.get("variants"):
        return ui["variants"]
    cands = resp.get("candidates") or ui.get("candidates")
    if not cands:
        return None
    chosen = resp["result"].get("suggestion")
    notes = list(resp.get("rejected_notes") or ui.get("rejected_notes") or [])
    used = resp.get("used_evidence") or ui.get("used_evidence") or []
    tiers = ["strong", "balanced", "safe"] if len(cands) >= 3 else ["strong", "safe"]
    chosen_at = cands.index(chosen) if chosen in cands else 0
    out = []
    for i, text in enumerate(cands[:3]):
        verified = True if i == chosen_at else (False if i < chosen_at else None)
        note = notes[i] if verified is False and i < len(notes) else None
        basis = ("사용한 보유 근거: " + ", ".join(used)) if i == 0 and used else ""
        out.append({"text": text, "tier": tiers[min(i, len(tiers) - 1)], "basis": basis,
                    "verified": verified, "note": note, "chosen": i == chosen_at})
    return out


def _with_rule_highlights(resp: dict, product: dict) -> dict:
    """API 응답에 화면 확장(ui)이 없으면 규칙 자산 기반 하이라이트를 붙이고 실제 근거 번호에 잇는다
    (판정·근거는 서버 것 그대로). 제안 후보가 실려 오면 variants 로 옮긴다."""
    ui = resp.setdefault("ui", {})
    if not ui.get("highlights"):
        hits = mock.detect(resp.get("input_text", ""), product)
        ui["derived"] = True
        ui["highlights"] = [{"start": h.start, "end": h.end, "text": h.text, "kind": h.kind, "label": h.label,
                             "reason": h.reason, "violation_type": h.violation, "level": h.level,
                             "decisive": h.decisive, "cites": []} for h in hits]
    _link_citations(ui["highlights"], resp["result"].get("citations", []))
    variants = _variants_from(resp)
    if variants:
        ui["variants"] = variants
    return resp


def review_events(copy_text: str, product: dict) -> Iterator[dict]:
    """검토 진행 이벤트 (contract 의 StageEvent · TokenEvent · WaitEvent · ResultEvent).
    - Mock: 엔진이 계산하는 순서대로 단계 이벤트(시간은 실측) → result
    - API: POST /review/stream(NDJSON)이 있으면 그 줄들을 그대로 → result. 없으면 wait → POST /review → result
    실패는 BackendError. 화면은 이 함수가 낸 것만 그린다."""
    if data_mode() == "mock":
        yield from mock.review_iter(copy_text, product)
        return
    if data_mode() == "local":  # 내장 실행에는 스트림 엔드포인트가 없다
        yield {"type": "wait"}
        yield {"type": "result", "resp": review_copy(copy_text, product)}
        return
    payload = {"copy_text": copy_text, "product": product}
    try:
        with httpx.stream("POST", f"{api_base_url()}/review/stream", json=payload,
                          timeout=httpx.Timeout(300.0, connect=5.0)) as res:
            if res.status_code not in (404, 405):
                res.raise_for_status()
                for line in res.iter_lines():
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if event.get("type") == "result":
                        yield {"type": "result", "resp": _with_rule_highlights(event["resp"], product)}
                        return
                    yield event
                raise BackendError("검토 서버가 결과 없이 스트림을 끝냈습니다.")
    except httpx.HTTPStatusError as err:
        raise BackendError(f"서버가 요청을 처리하지 못했습니다 (HTTP {err.response.status_code}).", err) from err
    except httpx.HTTPError as err:
        raise BackendError(f"검토 서버({api_base_url()})에 연결하지 못했습니다. 서버가 켜져 있는지 확인하세요.", err) from err
    yield {"type": "wait"}
    yield {"type": "result", "resp": review_copy(copy_text, product)}


def review_copy(copy_text: str, product: dict) -> dict:
    """광고 문구 한 개 검토 → ReviewResponse."""
    if data_mode() == "mock":
        return mock.review(copy_text, product)
    resp = _post("/review", {"copy_text": copy_text, "product": product})
    return _with_rule_highlights(resp, product)


def split_sentences(full_text: str) -> list[str]:
    """서버(api/text.py)와 같은 규칙으로 문장을 나눈다."""
    try:
        if str(_REPO) not in sys.path:
            sys.path.insert(0, str(_REPO))
        from api.text import split_sentences as _split

        return _split(full_text)
    except Exception:
        boundary = re.compile(r'''[!?]+[”’"']*|\.+[”’"']*(?=\s|$)|\n+''')
        out, start = [], 0
        for m in boundary.finditer(full_text):
            piece = full_text[start:m.end()].strip()
            if piece:
                out.append(piece)
            start = m.end()
        if full_text[start:].strip():
            out.append(full_text[start:].strip())
        return out


def review_page_events(full_text: str, product: dict) -> Iterator[dict]:
    """상세페이지 일괄 검토 진행. Mock 은 문장 하나를 실제로 끝낼 때마다 {"type": "sentence", "done", "total"},
    API(/review/bulk 는 한 번에 돌려준다)는 {"type": "wait", "total"} 하나. 마지막은 {"type": "result", "items"}."""
    sentences = split_sentences(full_text)
    if not sentences:
        raise BackendError("검토할 문장이 없습니다.")
    if len(sentences) > MAX_SENTENCES:
        raise BackendError(f"한 번에 최대 {MAX_SENTENCES}문장까지 검토할 수 있습니다. 지금은 {len(sentences)}문장입니다.")
    if data_mode() == "mock":
        items = []
        for i, sentence in enumerate(sentences, start=1):
            items.append(mock.review(sentence, product))
            yield {"type": "sentence", "done": i, "total": len(sentences)}
        yield {"type": "result", "items": items}
        return
    yield {"type": "wait", "total": len(sentences)}
    items = _post("/review/bulk", {"full_text": full_text, "product": product}, timeout=300.0)
    yield {"type": "result", "items": [_with_rule_highlights(r, product) for r in items]}


def review_page(full_text: str, product: dict) -> list[dict]:
    """상세페이지 글 전체를 문장 단위로 검토 → [ReviewResponse, ...] (입력 순서)."""
    return next(e for e in review_page_events(full_text, product) if e["type"] == "result")["items"]


def search_rules(query: str, scope: str = "공통", limit: int = 8) -> list[dict]:
    """규정 검색 → [{content, metadata}] (GET /search 와 같은 모양)."""
    if data_mode() == "mock":
        return mock.search(query, scope, limit)
    return _get("/search", params={"q": query, "scope": scope})[:limit]


# ── 원문 자료 (두 모드 같음: data/ 를 직접 읽는다) ─────────────────────
kb_stats = ds.kb_stats
enforcement_trends = ds.enforcement_trends
law_documents = ds.law_documents
guide_document = ds.guide_document
case_documents = ds.case_documents
guide_rows = ds.guide_rows
banned_terms = ds.banned_terms
claim_ladders = ds.claim_ladders
functional_claims = ds.functional_claims

_DOC_SUMMARY = {
    "화장품법": "부당한 표시·광고 금지(제13조) · 표시·광고 실증(제14조)",
    "화장품법_시행규칙": "[별표 5] 화장품 표시·광고의 범위 및 준수사항",
    "표시광고_실증규정": "실증자료의 종류와 시험 결과의 요건",
    "기능성화장품_심사규정": "기능성화장품 심사 대상과 제출 자료",
    "화장품_안전기준규정": "사용할 수 없는 원료 · 사용상 제한이 필요한 원료",
}


def _law_ref(doc: dict) -> dict:
    return {"key": doc["key"], "title": doc["title"], "kind": doc["kind"],
            "org": "국가법령정보센터" if doc["kind"] == "법령" else "식품의약품안전처 고시",
            "version": doc.get("readme_version") or doc.get("version") or "",
            "summary": _DOC_SUMMARY.get(doc["key"], ""), "file": doc["file"]}


def _guide_ref() -> dict:
    g = ds.guide_document()
    return {"key": g["key"], "title": g["title"], "kind": "지침", "org": "식품의약품안전처",
            "version": g.get("version") or "", "summary": "[별표 1] 금지 표현 표 — 의약품 오인 · 범위 이탈 등", "file": g["file"]}


def _case_ref(case: dict) -> dict:
    count = case.get("cosmetics_count") or case.get("count")
    return {"key": case["key"], "title": ds.case_title(case), "kind": "사례", "org": "식품의약품안전처 보도자료",
            "date": case["date"], "summary": f"화장품 부당광고 {count}건" if count else "", "file": case["file"]}


def all_reference_documents() -> list[dict]:
    """수집 문서 전체: 법령·고시 → 지침 → 적발 사례(최신 순)."""
    return [_law_ref(d) for d in ds.law_documents()] + [_guide_ref()] + [_case_ref(c) for c in ds.case_documents()]


def reference_documents(citations: list[dict]) -> list[dict]:
    """근거 조항이 나온 원문 문서 (중복 없이, 권위 순)."""
    refs: dict[str, dict] = {}
    for c in citations or []:
        cid = c.get("chunk_id", "")
        doc = None
        if cid.startswith("CASE_"):
            case = ds.case_document(cid)
            doc = _case_ref(case) if case else None
        elif cid.startswith("GUIDE_"):
            doc = _guide_ref()
        else:
            parts = cid.split("_")
            short = parts[1] if len(parts) > 1 else ""
            found = ds.law_document(short) or ds.law_document(c.get("source", ""))
            doc = _law_ref(found) if found else None
        if doc and doc["key"] not in refs:
            refs[doc["key"]] = doc
    order = {"법령": 1, "고시": 2, "지침": 3, "사례": 4}
    return sorted(refs.values(), key=lambda d: order.get(d["kind"], 9))
