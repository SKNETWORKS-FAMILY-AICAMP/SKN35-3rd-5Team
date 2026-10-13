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
      var ic = b.querySelector('.bw-i');
      var done = function () {
        b.classList.add('is-done'); lbl.textContent = '복사됨';
        if (ic) ic.classList.replace('bw-i--content_copy', 'bw-i--check');
        setTimeout(function () {
          b.classList.remove('is-done'); lbl.textContent = orig;
          if (ic) ic.classList.replace('bw-i--check', 'bw-i--content_copy');
        }, 1600);
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


def _cites_attr(numbers: list[int] | None) -> str:
    """연동 스크립트용 data-cites (오른쪽 근거 번호). 번호가 없으면 빈 문자열."""
    nums = [str(int(n)) for n in numbers or []]
    return f' data-cites="{",".join(nums)}" tabindex="0"' if nums else ""


def refs(numbers: list[int]) -> str:
    """근거 번호 [n] (오른쪽 근거 패널의 번호와 같다). 누르면 그 조항으로 간다."""
    if not numbers:
        return ""
    chips = "".join(f'<span class="bw-cn" data-cites="{int(n)}" title="오른쪽 근거 {int(n)}번 보기">{int(n)}</span>'
                    for n in numbers)
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
        if h.get("kind") == "verified":
            out.append(f'<span class="bw-mark is-verified" title="{esc(h.get("reason", ""))}">{piece}</span>')
        else:
            out.append(f'<span class="bw-mark is-{_tone_of(h)}" title="{esc(h.get("reason", ""))}"'
                       f'{_cites_attr(h.get("cites"))}>{piece}</span>')
        pos = h["end"]
    out.append(esc(text[pos:]))
    return "".join(out)


def _avatar_state(verdict: str | None, fresh: bool) -> str:
    """토끼 아바타 상태 — 처음 도착한 답변에만 판정별 짧은 동작 한 번."""
    if not fresh or verdict is None:
        return ""
    return {"가능": " is-fresh is-pass", "판단보류": " is-fresh is-hold"}.get(verdict, " is-fresh is-risk")


def _arrive(fresh: bool) -> str:
    """처음 도착한 답변에만 붙는 도착 연출 클래스 (다시 그릴 때는 빠져서 반복하지 않는다)."""
    return " is-arrive" if fresh else ""


def _ai_head(meta: str = "", at: datetime | None = None, state: str = "") -> str:
    when = f'<span class="bw-ai-time">{clock(at)}</span>' if at else ""
    return (f'<div class="bw-ai-head"><span class="bw-avatar{state}">{avatar_img(32, alt="")}</span>'
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
            f'<li class="bw-issue is-{_tone_of(h)}"{_cites_attr(h.get("cites"))}>'
            f'<div class="bw-issue-h">{tag(label, _tone_of(h), small=True)}'
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


_TIER = {"strong": "근거 최대", "balanced": "균형", "safe": "가장 안전"}


def _suggestion(resp: dict) -> str:
    """지난 답변의 수정 제안 (정적). 최신 답변은 suggest.render 가 위젯으로 그린다."""
    result, ui = resp["result"], resp.get("ui", {})
    text = result.get("suggestion")
    if not text or verdict_of(result) == "가능":
        return ""
    source = ui.get("suggestion_source", "")
    direction = ui.get("direction") or (f"보유 실증 {source} 범위 안에서 쓸 수 있는 가장 강한 표현입니다." if source
                                        else "보유한 근거 범위 안에서 쓸 수 있는 표현입니다.")
    full = f"{text} {source}".strip()
    others = ""
    variants = [v for v in ui.get("variants") or [] if not v.get("chosen")]
    if variants:
        rows = "".join(f'<li><span><em>{_TIER.get(v.get("tier"), "후보")}</em>{esc(v["text"])}</span>'
                       f'<button type="button" class="bw-copy is-quiet" data-copy="{esc(v["text"])}" aria-label="복사">'
                       f'{icon("content_copy", 14)}<span class="lbl">복사</span></button></li>' for v in variants)
        others = (f'<details class="bw-diff"><summary>{icon("chevron_right", 16)}다른 후보 {len(variants)}개</summary>'
                  f'<ul class="bw-alts is-in">{rows}</ul></details>')
    return (
        '<section><h4 class="bw-sec">수정 제안</h4>'
        f'<div class="bw-suggest"><div class="bw-suggest-top"><p class="bw-suggest-text">{esc(full)}</p>'
        f'<button type="button" class="bw-copy" data-copy="{esc(full)}" aria-label="제안 문구 복사">'
        f'{icon("content_copy", 15)}<span class="lbl">복사</span></button></div>'
        f'<p class="bw-suggest-src">{esc(direction)}</p>{others}</div></section>'
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
    """답변 아래 출처 줄 — 근거 상위 3건 (전체는 오른쪽 패널). 누르면 그 조항으로 간다."""
    cites = result.get("citations", [])
    if not cites:
        return ""
    items = "".join(
        f'<span class="bw-src" data-cites="{i}" tabindex="0"><span class="bw-cn">{i}</span>'
        f'{esc(c.get("source", ""))} {esc(c.get("article", ""))}</span>'
        for i, c in enumerate(cites[:3], start=1))
    more = f'<span class="bw-src-more">외 {len(cites) - 3}건</span>' if len(cites) > 3 else ""
    return f'<div class="bw-sources"><span class="k">출처</span>{items}{more}</div>'


def _parts(resp: dict, at: datetime, *, live: bool, fresh: bool) -> dict:
    """답변을 조각으로 나눈다: head(머리·판정) · top(문구·이슈 …) · tail(다음 시험·출처) · foot.
    live 면 수정 제안·다른 표현은 빼고(위젯이 그린다) split=True 를 돌려준다."""
    result, ui = resp["result"], resp.get("ui", {})
    verdict = verdict_of(result)
    highlights = ui.get("highlights", [])
    summary = ui.get("summary") or result.get("review_notes") or ""
    _, tone = status_of(verdict)
    n = len(result.get("citations", []))
    t = resp.get("timing", {})

    meta = (f'<span class="bw-rag">{icon("menu_book", 15)}규정 문서 {n}건을 근거로</span>' if n
            else '<span class="bw-rag is-none">근거 문서 없음</span>')
    head = _ai_head(meta, at, _avatar_state(verdict, fresh)) + \
        f'<div class="bw-verdict">{status_tag(verdict)}<p>{esc(summary)}</p></div>'
    quote = (f'<section><h4 class="bw-sec">검토한 문구</h4>'
             f'<blockquote class="bw-quote is-{tone}">{highlighted(resp["input_text"], highlights)}</blockquote></section>')
    split = False
    if verdict == "판단보류":
        top = quote + ('<section><h4 class="bw-sec">판단을 보류한 이유</h4>'
                       f'<p class="bw-plain">{esc(result.get("review_notes") or "")} 근거가 부족한 상태에서 판정하지 않습니다. '
                       'RA 담당자의 검토를 권합니다.</p></section>')
        tail = ""
    elif verdict == "가능":
        top = quote + ('<section><h4 class="bw-sec">검토 결과</h4><p class="bw-plain">위반 소지가 있는 표현을 찾지 못했습니다. '
                       '그대로 사용할 수 있습니다.</p></section>' + _alternatives(resp))
        tail = ""
    else:
        split = live and bool(result.get("suggestion"))
        top = quote + _issues(highlights, result)
        if not split:
            top += _suggestion(resp) + ("" if ui.get("variants") else _alternatives(resp))
        tail = _next_test(resp)
    tail += _sources(result)
    foot = (f'<div class="bw-ai-foot"><span>응답 <span class="bw-mono">{seconds(t.get("total_ms"))}</span></span>'
            '<span class="sep"></span><span>AI 판단은 참고용입니다. 게재 전 RA 담당자 검토를 권합니다.</span></div>')
    return {"head": head, "top": top, "tail": tail, "foot": foot, "split": split}


def assistant_message(resp: dict, at: datetime, *, live: bool = False, fresh: bool = False) -> str:
    """AI 검토 답변 한 덩어리 (복사 버튼 스크립트 포함 — layout.html(js=True) 로 그린다).
    live=True 는 최신 답변 — 위험 표현 ↔ 근거 연동이 켜진다(수정 제안 위젯을 따로 그리지 않을 때)."""
    p = _parts(resp, at, live=False, fresh=fresh)
    live_attr = ' data-live="1"' if live else ""
    return (f'<article class="bw-ai{_arrive(fresh)}"{live_attr}>{p["head"]}'
            f'<div class="bw-doc">{p["top"]}{p["tail"]}</div>{p["foot"]}</article>' + COPY_SCRIPT)


def assistant_live(resp: dict, at: datetime, *, fresh: bool = False) -> tuple[str, str, bool] | None:
    """최신 답변을 위젯 앞·뒤 조각으로 (위·아래 HTML, 아래 조각이 있는가). 나눌 필요가 없으면 None."""
    p = _parts(resp, at, live=True, fresh=fresh)
    if not p["split"]:
        return None
    top = (f'<article class="bw-ai{_arrive(fresh)}" data-live="1">{p["head"]}'
           f'<div class="bw-doc is-top">{p["top"]}</div></article>' + COPY_SCRIPT)
    tail = f'<div class="bw-doc is-bottom">{p["tail"]}</div>' if p["tail"] else ""
    bottom = f'<article class="bw-ai is-cont{_arrive(fresh)}" data-live="1">{tail}{p["foot"]}</article>'
    return top, bottom, bool(p["tail"])


def thinking(step: int, total: int, label: str) -> str:
    """상세페이지 일괄 검토 진행 (실제로 끝낸 문장 수 / 전체)."""
    meta = '<span class="bw-rag">문장을 검토하고 있습니다</span>'
    return (f'<article class="bw-ai">{_ai_head(meta, None, " is-thinking")}<div class="bw-thinking">'
            f'<span class="bw-dots"><i></i><i></i><i></i></span>'
            f'<span>{esc(label)}</span><span class="bw-step-n">{step}/{total}</span></div></article>')


def error_message(message: str, at: datetime, *, fresh: bool = False) -> str:
    """백엔드 오류를 대화 안에 표시한다 (Mock 으로 바꿔치기하지 않는다)."""
    return (f'<article class="bw-ai">{_ai_head("", at, " is-error" if fresh else "")}<div class="bw-error">{icon("error", 18)}'
            f'<div><b>검토하지 못했습니다.</b> {esc(message)}</div></div></article>')


def welcome(product_name: str) -> str:
    """대화가 없을 때 첫 화면 — 캐릭터는 여기서만 크게 쓴다."""
    return (f'<div class="bw-welcome"><span class="bw-hero">{character_img(176)}</span>'
            '<h2>광고 문구를 붙여 넣어 주세요</h2>'
            '<p>화장품법·식약처 고시·관리지침·적발 사례에서 근거를 찾아 판단하고, '
            f'<b>{esc(product_name)}</b>의 보유 실증 범위 안에서 더 안전한 문구를 제안합니다.</p></div>')
