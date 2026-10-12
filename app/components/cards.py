"""
[app/components/cards.py]
가운데 대화 영역의 메시지 블록. 모두 데이터 → HTML 문자열 순수 함수다.

- assistant_message(): AI 검토 답변 (검토한 문구 → 발견된 이슈 → 대체 문구 → 다른 표현).
- 이슈 문장의 [1][4] 같은 번호는 오른쪽 근거 패널의 번호와 같다(RAG 근거 연결).
- 응답에 ui 확장이 없어도(실제 API 초기 응답) 결과 계약 필드만으로 그려진다.
"""
from __future__ import annotations

from datetime import datetime

from app.components.brand import BRAND_NAME, mascot_img
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
      var done = function () {
        b.classList.add('is-done'); lbl.textContent = '복사됨';
        setTimeout(function () { b.classList.remove('is-done'); lbl.textContent = '복사'; }, 1600);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(t).then(done, function () { fallback(t); done(); });
      } else { fallback(t); done(); }
    });
  });
})();
</script>"""


def tag(text: str, tone: str, *, icon_name: str | None = None, small: bool = False) -> str:
    """상태·이슈 태그. tone: risk · caution · pass · hold · plain."""
    ic = icon(icon_name, 14) if icon_name else ""
    size = " is-sm" if small else ""
    return f'<span class="bw-tag is-{tone}{size}">{ic}{esc(text)}</span>'


def status_tag(verdict: str, *, small: bool = False) -> str:
    """판정 → '수정 필요' 같은 상태 태그."""
    label, tone = status_of(verdict)
    names = {"risk": "error", "caution": "warning_outline", "pass": "check_circle_outline", "hold": "help_outline"}
    return tag(label, tone, icon_name=names[tone], small=small)


def refs(numbers: list[int]) -> str:
    """근거 번호 위첨자 (오른쪽 근거 패널 번호와 같다). 여러 개면 1·4·5."""
    if not numbers:
        return ""
    return f'<sup class="bw-ref" title="오른쪽 근거 {", ".join(str(int(n)) for n in numbers)}번">{"·".join(str(int(n)) for n in numbers)}</sup>'


def _tone_of(h: dict) -> str:
    return "risk" if h.get("level") == 2 else "caution"


def highlighted(text: str, highlights: list[dict]) -> str:
    """원문에 위험 표현(로즈)·주의 표현(앰버 밑줄)·실증 일치 숫자(점선)를 표시한다. 겹치는 구간은 앞의 것만."""
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
            out.append(f'<span class="bw-mark is-{_tone_of(h)}" title="{esc(h.get("reason", ""))}">{piece}{refs(h.get("cites", []))}</span>')
        pos = h["end"]
    out.append(esc(text[pos:]))
    return "".join(out)


def user_message(text: str, at: datetime, context: str = "") -> str:
    """사용자 말풍선 (오른쪽)."""
    ctx = f'<span class="bw-bubble-ctx">{esc(context)}</span>' if context else ""
    return (f'<div class="bw-msg is-user"><div class="bw-bubble">{esc(text)}</div>'
            f'<div class="bw-msg-time">{ctx}{" · " if ctx else ""}{clock(at)}</div></div>')


def _ai_shell(inner: str, *, meta: str = "", foot: str = "") -> str:
    meta_html = f'<span class="bw-rag">{meta}</span>' if meta else ""
    foot_html = f'<div class="bw-ai-foot">{foot}</div>' if foot else ""
    return (f'<div class="bw-ai"><div class="bw-avatar">{mascot_img(30, tight=True)}</div>'
            f'<div class="bw-ai-body"><div class="bw-ai-name">{BRAND_NAME}{meta_html}</div>{inner}{foot_html}</div></div>')


def _issues(highlights: list[dict], result: dict) -> str:
    risks = sorted((h for h in highlights if h.get("kind") != "verified"),
                   key=lambda h: (not h.get("decisive"), -(h.get("level") or 0), h.get("start", 0)))
    rows = []
    for h in risks:
        reason = esc(h.get("reason", ""))
        rows.append(
            f'<div class="bw-issue">{tag(h.get("label") or VIOLATION_LABEL.get(h.get("violation_type") or "", "확인 필요"), _tone_of(h), icon_name="error" if h.get("level") == 2 else "warning_outline")}'
            f'<p><b>‘{esc(h.get("text", ""))}’</b> — {reason}{refs(h.get("cites", []))}</p></div>'
        )
    if not rows and result.get("violation_type") not in (None, "없음"):
        # ui 확장이 없을 때: 위반 유형과 검토 메모만으로 한 줄
        label = VIOLATION_LABEL.get(result["violation_type"], result["violation_type"])
        tone = "risk" if result.get("level") == 2 else "caution"
        rows.append(f'<div class="bw-issue">{tag(label, tone)}<p>{esc(result.get("review_notes") or "")}</p></div>')
    verified = [h for h in highlights if h.get("kind") == "verified"]
    note = ""
    if verified:
        words = " · ".join(esc(h["text"]) for h in verified)
        note = (f'<div class="bw-verified-note">{icon("check_circle_outline", 15)}'
                f'<span><b>{words}</b>은(는) 보유한 실증 자료와 일치합니다.</span></div>')
    if not rows and not note:
        return ""
    return (f'<section><div class="bw-sec-h"><h4>발견된 이슈</h4></div>'
            f'<div class="bw-issues">{"".join(rows)}{note}</div></section>')


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
            checks.append(f'<span>{icon("check", 13)}숫자 {rv["numbers_ok"]}/{rv["numbers_total"]} 실증 일치</span>')
        checks.append(f'<span>{icon("check", 13)}금지어 재검사 {rv.get("banned", 0)}건</span>')
    diff = ""
    if ui.get("diff"):
        items = "".join(
            f'<li class="{"is-del" if d["op"] == "-" else "is-add"}"><span class="op">{"−" if d["op"] == "-" else "+"}</span>'
            f'<span class="t">{esc(d["text"])}</span><span class="why">{esc(d.get("why", ""))}</span></li>'
            for d in ui["diff"]
        )
        diff = f'<div class="bw-diff"><span class="bw-diff-h">고친 곳</span><ul>{items}</ul></div>'
    return (
        '<section><div class="bw-sec-h"><h4>더 안전한 대체 문구</h4></div>'
        f'<div class="bw-suggest">{icon("check_circle", 20)}'
        f'<div class="bw-suggest-text">“{esc(text)}”</div>'
        f'<button type="button" class="bw-copy" data-copy="{esc(full)}" aria-label="대체 문구 복사">{icon("content_copy", 15)}<span class="lbl">복사</span></button>'
        f'<div class="bw-suggest-src">{esc(direction)}</div>'
        f'{"<div class=bw-suggest-check>" + "".join(checks) + "</div>" if checks else ""}'
        f'{diff}</div></section>'
    )


def _alternatives(resp: dict) -> str:
    alts = [a for a in resp.get("ui", {}).get("alternatives", []) if a and a != resp["result"].get("suggestion")]
    if not alts:
        return ""
    chips = "".join(f'<span class="bw-alt">{esc(a)}</span>' for a in alts[:4])
    return f'<section><div class="bw-sec-h"><h4>이런 표현도 쓸 수 있어요</h4></div><div class="bw-alts">{chips}</div></section>'


def _next_test(resp: dict) -> str:
    result, ui = resp["result"], resp.get("ui", {})
    nt = ui.get("next_test")
    if nt:
        body = f'<b>‘{esc(nt["phrase"])}’</b>까지 쓰려면 {esc(nt["need"])}{iga(nt["need"])} 필요합니다.'
    elif result.get("next_test") and result.get("level") == 1:
        body = esc(result["next_test"])
    else:
        return ""
    return f'<div class="bw-next">{icon("lock", 16)}<div>{body}</div></div>'


def assistant_message(resp: dict, at: datetime) -> str:
    """AI 검토 답변 한 덩어리 (복사 버튼 스크립트 포함 — layout.html(js=True) 로 그린다)."""
    result, ui = resp["result"], resp.get("ui", {})
    verdict = verdict_of(result)
    highlights = ui.get("highlights", [])
    summary = ui.get("summary") or result.get("review_notes") or ""
    intro = {
        "불가": "검토를 마쳤습니다. ",
        "조건부": "검토를 마쳤습니다. ",
        "가능": "검토를 마쳤습니다. ",
        "판단보류": "",
    }[verdict] + summary

    quote = (f'<section><div class="bw-sec-h"><h4>검토한 문구</h4>{status_tag(verdict, small=True)}</div>'
             f'<div class="bw-quote">“{highlighted(resp["input_text"], highlights)}”</div></section>')

    if verdict == "판단보류":
        body = (f'<section><div class="bw-sec-h"><h4>판단을 보류했습니다</h4></div>'
                f'<p class="bw-muted" style="font-size:13.5px">{esc(result.get("review_notes") or "")} '
                '근거가 부족한 상태에서 판정하지 않습니다.</p></section>')
    elif verdict == "가능":
        body = ('<section><div class="bw-sec-h"><h4>검토 결과</h4></div>'
                '<p style="font-size:13.5px;color:var(--bw-ink-2)">위반 소지가 있는 표현을 찾지 못했습니다. 그대로 사용할 수 있습니다.</p></section>'
                + _alternatives(resp))
    else:
        body = _issues(highlights, result) + _suggestion(resp) + _alternatives(resp) + _next_test(resp)

    n = len(result.get("citations", []))
    meta = f'{icon("travel_explore", 14)}근거 {n}건 검색' if n else ""
    t = resp.get("timing", {})
    foot = (f'<span>{clock(at)}</span>'
            f'<span>검색 <span class="bw-mono">{seconds(t.get("retrieval_ms"))}</span></span>'
            f'<span>판정 <span class="bw-mono">{seconds(t.get("llm_ms"))}</span></span>'
            f'<span>총 <span class="bw-mono">{seconds(t.get("total_ms"))}</span></span>')
    inner = f'<p class="bw-ai-text">{esc(intro)}</p><div class="bw-answer">{quote}{body}</div>'
    return _ai_shell(inner, meta=meta, foot=foot) + COPY_SCRIPT


def thinking(step: int, total: int, label: str) -> str:
    """검토 진행 중 표시 (현재 단계 이름 + 단계 막대)."""
    bars = "".join(f'<i class="{"on" if i < step else ""}"></i>' for i in range(total))
    inner = (f'<div class="bw-thinking"><span class="bw-dots"><i></i><i></i><i></i></span>'
             f'<span>{esc(label)}</span><span class="bw-progress">{bars}</span>'
             f'<span class="bw-step-n">{step}/{total}</span></div>')
    return _ai_shell(inner)


def error_message(message: str, at: datetime) -> str:
    """백엔드 오류를 대화 안에 표시한다 (Mock 으로 바꿔치기하지 않는다)."""
    inner = (f'<div class="bw-error">{icon("error", 18)}<div><b>검토하지 못했습니다.</b> {esc(message)}</div></div>')
    return _ai_shell(inner, foot=f'<span>{clock(at)}</span>')


def welcome(product_name: str) -> str:
    """대화가 없을 때 첫 화면."""
    return (f'<div class="bw-welcome">{mascot_img(64)}<h2>어떤 광고 문구를 검토할까요?</h2>'
            f'<p>문구를 입력하면 화장품법·식약처 고시·관리지침·적발 사례에서 근거를 찾아 판단하고, '
            f'<b>{esc(product_name)}</b>의 보유 실증 범위 안에서 더 안전한 문구를 제안합니다.</p></div>')
