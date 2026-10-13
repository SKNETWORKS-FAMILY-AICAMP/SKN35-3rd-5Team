"""
[app/components/cards.py]
가운데 대화 영역의 메시지 블록. 모두 데이터 → HTML 문자열 순수 함수다 (화면 위젯 없음).

- assistant_message(): AI 답변 — 머리(아바타 · 이름 · "규정 문서 n건을 근거로") → 판정 한 줄 →
  답변 문서(검토한 문구 · 문제 표현 · 수정 제안 · 다른 표현 · 출처 줄).
- 문제 표현 끝의 [1] [4] 번호는 오른쪽 「근거」 패널의 번호와 같다 (RAG 근거 연결).
- 응답에 ui 확장이 없어도(실제 API 초기 응답) 결과 계약 필드만으로 그려진다.
"""
from __future__ import annotations

from datetime import datetime

from app.components.brand import ASSISTANT_NAME, avatar_img, character_img
from app.components.icons import icon
from app.components.layout import clock, esc, iga, seconds
from app.components.theme import VIOLATION_LABEL, status_of
from app.services.contract import verdict_of

# 복사 버튼 동작 (메인 문서에서 실행). 같은 버튼에 두 번 붙지 않게 data-bound 로 표시한다.
COPY_SCRIPT = """<script>
(function () {
  function fallback(t) {
    var ta = document.createElement('textarea');
    ta.value = t; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(ta);
  }
  document.querySelectorAll('button.bw-copy[data-copy]:not([data-bound])').forEach(function (b) {
    b.setAttribute('data-bound', '1');
    b.addEventListener('click', function () {
      var t = b.getAttribute('data-copy');
      var lbl = b.querySelector('.lbl');
      var orig = b.getAttribute('data-label') || lbl.textContent;
      b.setAttribute('data-label', orig);
      var done = function () {
        b.classList.add('is-done'); lbl.textContent = '복사됨';
        setTimeout(function () { b.classList.remove('is-done'); lbl.textContent = orig; }, 1600);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(t).then(done, function () { fallback(t); done(); });
      } else { fallback(t); done(); }
    });
  });
})();
</script>"""


# ── 작은 부품 ──────────────────────────────────────────────────────────
def tag(text: str, tone: str, *, small: bool = False) -> str:
    """상태·이슈 태그 (점 + 글자). tone: risk · caution · pass · hold · plain."""
    return f'<span class="bw-tag is-{tone}{" is-sm" if small else ""}">{esc(text)}</span>'


def status_tag(verdict: str, *, small: bool = False) -> str:
    """판정 → '수정 필요' 같은 상태 태그."""
    label, tone = status_of(verdict)
    return tag(label, tone, small=small)


def refs(numbers: list[int]) -> str:
    """근거 번호 [n] (오른쪽 근거 패널의 번호와 같다)."""
    if not numbers:
        return ""
    chips = "".join(f'<span class="bw-cn" title="오른쪽 근거 {int(n)}번">{int(n)}</span>' for n in numbers)
    return f'<span class="bw-refs">{chips}</span>'   # 번호 묶음은 한 덩어리로 줄바꿈


def _tone_of(h: dict) -> str:
    return "risk" if h.get("level") == 2 else "caution"


def highlighted(text: str, highlights: list[dict]) -> str:
    """원문에 위험 표현·주의 표현(밑줄)·실증 일치 숫자(점선)를 표시한다. 겹치는 구간은 앞의 것만."""
    spans = sorted(
        (h for h in highlights or [] if 0 <= h.get("start", -1) < h.get("end", -1) <= len(text)),
        key=lambda h: (h["start"], -h["end"]),
    )
    out, pos = [], 0
    for h in spans:
        if h["start"] < pos:
            continue
        out.append(esc(text[pos:h["start"]]))
        piece = esc(text[h["start"]:h["end"]])
        kind = "verified" if h.get("kind") == "verified" else _tone_of(h)
        out.append(f'<span class="bw-mark is-{kind}" title="{esc(h.get("reason", ""))}">{piece}</span>')
        pos = h["end"]
    out.append(esc(text[pos:]))
    return "".join(out)


def _ai_head(meta: str = "", at: datetime | None = None) -> str:
    when = f'<span class="bw-ai-time">{clock(at)}</span>' if at else ""
    return (f'<div class="bw-ai-head"><span class="bw-avatar">{avatar_img(32, alt="")}</span>'
            f'<b>{ASSISTANT_NAME}</b>{meta}{when}</div>')


# ── 메시지 ─────────────────────────────────────────────────────────────
def user_message(text: str, at: datetime, context: str = "") -> str:
    """사용자 말풍선 (오른쪽). context 는 그때의 검토 기준 한 마디(예: '실증 1건 기준')."""
    meta = f'{esc(context)} · {clock(at)}' if context else clock(at)
    return (f'<div class="bw-user"><div class="bw-bubble">{esc(text)}</div>'
            f'<div class="bw-msg-time">{meta}</div></div>')


def _issues(highlights: list[dict], result: dict) -> str:
    risks = sorted((h for h in highlights if h.get("kind") != "verified"),
                   key=lambda h: (not h.get("decisive"), -(h.get("level") or 0), h.get("start", 0)))
    rows = []
    for h in risks:
        label = h.get("label") or VIOLATION_LABEL.get(h.get("violation_type") or "", "확인 필요")
        level = "위험 높음" if h.get("level") == 2 else "주의"
        rows.append(
            f'<li class="bw-issue is-{_tone_of(h)}"><div class="bw-issue-h">{tag(label, _tone_of(h), small=True)}'
            f'<b>‘{esc(h.get("text", ""))}’</b><span class="lvl">{level}</span></div>'
            f'<p>{esc(h.get("reason", ""))}{refs(h.get("cites", []))}</p></li>'
        )
    if not rows and result.get("violation_type") not in (None, "없음"):
        # ui 확장이 없을 때: 위반 유형과 검토 메모만으로 한 줄
        label = VIOLATION_LABEL.get(result["violation_type"], result["violation_type"])
        tone = "risk" if result.get("level") == 2 else "caution"
        rows.append(f'<li class="bw-issue is-{tone}"><div class="bw-issue-h">{tag(label, tone, small=True)}</div>'
                    f'<p>{esc(result.get("review_notes") or "")}</p></li>')
    verified = [h for h in highlights if h.get("kind") == "verified"]
    note = ""
    if verified:
        words = " · ".join(esc(h["text"]) for h in verified)
        note = (f'<div class="bw-verified">{icon("check", 16)}'
                f'<span>‘{words}’ 수치는 보유한 실증 자료와 일치합니다.</span></div>')
    if not rows and not note:
        return ""
    head = f'문제 표현 <span class="n">{len(rows)}</span>' if rows else "확인한 표현"
    return f'<section><h4 class="bw-sec">{head}</h4><ul class="bw-issues">{"".join(rows)}</ul>{note}</section>'


def _suggestion(resp: dict) -> str:
    result, ui = resp["result"], resp.get("ui", {})
    text = result.get("suggestion")
    if not text or verdict_of(result) == "가능":
        return ""
    source = ui.get("suggestion_source", "")
    direction = ui.get("direction") or (f"보유 실증 {source} 범위 안에서 쓸 수 있는 가장 강한 표현입니다." if source
                                        else "보유한 근거 범위 안에서 쓸 수 있는 표현입니다.")
    full = f"{text} {source}".strip()
    checks = []
    rv = ui.get("reverify")
    if rv:
        if rv.get("numbers_total"):
            checks.append(f'<span>{icon("check", 14)}숫자 {rv["numbers_ok"]}/{rv["numbers_total"]} 실증 일치</span>')
        checks.append(f'<span>{icon("check", 14)}금지어 재검사 {rv.get("banned", 0)}건</span>')
    diff = ""
    if ui.get("diff"):
        items = "".join(
            f'<li class="{"is-del" if d["op"] == "-" else "is-add"}"><span class="op">{"−" if d["op"] == "-" else "+"}</span>'
            f'<span class="t">{esc(d["text"])}</span><span class="why">{esc(d.get("why", ""))}</span></li>'
            for d in ui["diff"]
        )
        diff = (f'<details class="bw-diff"><summary>{icon("chevron_right", 16)}고친 곳 {len(ui["diff"])}군데</summary>'
                f'<ul>{items}</ul></details>')
    return (
        '<section><h4 class="bw-sec">수정 제안</h4>'
        f'<div class="bw-suggest"><div class="bw-suggest-top"><p class="bw-suggest-text">{esc(text)}</p>'
        f'<button type="button" class="bw-copy" data-copy="{esc(full)}" aria-label="제안 문구 복사">'
        f'{icon("content_copy", 15)}<span class="lbl">복사</span></button></div>'
        f'<p class="bw-suggest-src">{esc(direction)}</p>'
        f'{"<div class=bw-suggest-check>" + "".join(checks) + "</div>" if checks else ""}'
        f'{diff}</div></section>'
    )


def _alternatives(resp: dict) -> str:
    alts = [a for a in resp.get("ui", {}).get("alternatives", []) if a and a != resp["result"].get("suggestion")]
    if not alts:
        return ""
    rows = "".join(f'<li><span>{esc(a)}</span><button type="button" class="bw-copy is-quiet" data-copy="{esc(a)}" '
                   f'aria-label="복사">{icon("content_copy", 14)}<span class="lbl">복사</span></button></li>'
                   for a in alts[:3])
    return f'<section><h4 class="bw-sec">다른 표현</h4><ul class="bw-alts">{rows}</ul></section>'


def _next_test(resp: dict) -> str:
    result, ui = resp["result"], resp.get("ui", {})
    nt = ui.get("next_test")
    if nt:
        body = f'‘{esc(nt["phrase"])}’까지 쓰려면 {esc(nt["need"])}{iga(nt["need"])} 필요합니다.'
    elif result.get("next_test") and result.get("level") == 1:
        body = esc(result["next_test"])
    else:
        return ""
    return f'<div class="bw-next">{icon("lock", 16)}<span>{body}</span></div>'


def _sources(result: dict) -> str:
    """답변 아래 출처 줄 — 근거 상위 3건 (전체는 오른쪽 패널)."""
    cites = result.get("citations", [])
    if not cites:
        return ""
    items = "".join(
        f'<span class="bw-src"><span class="bw-cn">{i}</span>{esc(c.get("source", ""))} {esc(c.get("article", ""))}</span>'
        for i, c in enumerate(cites[:3], start=1))
    more = f'<span class="bw-src-more">외 {len(cites) - 3}건</span>' if len(cites) > 3 else ""
    return f'<div class="bw-sources"><span class="k">출처</span>{items}{more}</div>'


def assistant_message(resp: dict, at: datetime) -> str:
    """AI 검토 답변 한 덩어리 (복사 버튼 스크립트 포함 — layout.html(js=True) 로 그린다)."""
    result, ui = resp["result"], resp.get("ui", {})
    verdict = verdict_of(result)
    highlights = ui.get("highlights", [])
    summary = ui.get("summary") or result.get("review_notes") or ""
    _, tone = status_of(verdict)
    n = len(result.get("citations", []))
    t = resp.get("timing", {})

    meta = (f'<span class="bw-rag">{icon("menu_book", 15)}규정 문서 {n}건을 근거로</span>' if n
            else '<span class="bw-rag is-none">근거 문서 없음</span>')
    verdict_line = f'<div class="bw-verdict">{status_tag(verdict)}<p>{esc(summary)}</p></div>'
    quote = (f'<section><h4 class="bw-sec">검토한 문구</h4>'
             f'<blockquote class="bw-quote is-{tone}">{highlighted(resp["input_text"], highlights)}</blockquote></section>')

    if verdict == "판단보류":
        body = ('<section><h4 class="bw-sec">판단을 보류한 이유</h4>'
                f'<p class="bw-plain">{esc(result.get("review_notes") or "")} 근거가 부족한 상태에서 판정하지 않습니다. '
                'RA 담당자의 검토를 권합니다.</p></section>')
    elif verdict == "가능":
        body = ('<section><h4 class="bw-sec">검토 결과</h4><p class="bw-plain">위반 소지가 있는 표현을 찾지 못했습니다. '
                '그대로 사용할 수 있습니다.</p></section>' + _alternatives(resp))
    else:
        body = _issues(highlights, result) + _suggestion(resp) + _alternatives(resp) + _next_test(resp)

    foot = (f'<div class="bw-ai-foot"><span>응답 <span class="bw-mono">{seconds(t.get("total_ms"))}</span></span>'
            '<span class="sep"></span><span>AI 판단은 참고용입니다. 게재 전 RA 담당자 검토를 권합니다.</span></div>')
    return (f'<article class="bw-ai">{_ai_head(meta, at)}{verdict_line}'
            f'<div class="bw-doc">{quote}{body}{_sources(result)}</div>{foot}</article>' + COPY_SCRIPT)


def thinking(step: int, total: int, label: str) -> str:
    """검토 진행 중 표시 (현재 단계 이름 + 단계 막대)."""
    bars = "".join(f'<i class="{"on" if i < step else ""}"></i>' for i in range(total))
    meta = '<span class="bw-rag">규정 문서를 찾고 있습니다</span>'
    return (f'<article class="bw-ai">{_ai_head(meta)}<div class="bw-thinking"><span class="bw-dots"><i></i><i></i><i></i></span>'
            f'<span>{esc(label)}</span><span class="bw-progress">{bars}</span>'
            f'<span class="bw-step-n">{step}/{total}</span></div></article>')


def error_message(message: str, at: datetime) -> str:
    """백엔드 오류를 대화 안에 표시한다 (Mock 으로 바꿔치기하지 않는다)."""
    return (f'<article class="bw-ai">{_ai_head("", at)}<div class="bw-error">{icon("error", 18)}'
            f'<div><b>검토하지 못했습니다.</b> {esc(message)}</div></div></article>')


def welcome(product_name: str) -> str:
    """대화가 없을 때 첫 화면 — 캐릭터는 여기서만 크게 쓴다."""
    return (f'<div class="bw-welcome">{character_img(176)}'
            '<h2>광고 문구를 붙여 넣어 주세요</h2>'
            '<p>화장품법·식약처 고시·관리지침·적발 사례에서 근거를 찾아 판단하고, '
            f'<b>{esc(product_name)}</b>의 보유 실증 범위 안에서 더 안전한 문구를 제안합니다.</p></div>')

