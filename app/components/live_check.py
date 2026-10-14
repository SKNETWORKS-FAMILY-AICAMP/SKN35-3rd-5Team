"""
[app/components/live_check.py]
입력하는 동안 바로 밑줄 — 검토 대화 입력창 · 상세페이지 글 입력칸에 규칙 검사 결과를 글자 아래에 긋는다.

- 규칙은 mock.rule_table(product) 하나 — 답변의 규칙 밑줄(mock.detect)과 같은 규칙 · 같은 제품 조건 · 같은 겹침 정리.
  서버 왕복 없이 브라우저에서 돈다(글자를 칠 때마다 다시 그려도 서버는 쉰다).
- 같은 글꼴 · 여백의 밑줄 층(.bw-lc-bd)을 입력창 자리에 겹치고, 거기 글자는 투명하게 두어 밑줄만 보이게 한다.
  층은 Streamlit(React)이 관리하는 영역 밖(body)에 붙이고 위치만 따라간다 — 입력창 DOM 은 건드리지 않는다.
- 입력창 위(또는 아래) 한 줄(slot): 「입력 중 검사 · 위험 n · 주의 n · 실증 일치 n」. 최종 판정은 검토 결과가 정한다.
- 이 스크립트에는 꺾쇠 다음에 글자가 붙는 문자열을 쓰지 않는다(st.html 정화기가 블록을 지운다). 규칙 JSON 의 꺾쇠는 \\u003c 로 바꾼다.

쓰는 법: html(slot("bw_chat")) 을 입력창 가까이에, html(script(product, ["bw_chat"]), js=True) 를 화면 어디든 한 번.
"""
from __future__ import annotations

import json

from app.services import mock


def slot(target: str) -> str:
    """요약 한 줄 자리. target 은 입력 위젯의 key."""
    return f'<div class="bw-lc-sum is-empty" data-lc-for="{target}" aria-live="polite"></div>'


def script(product: dict, targets: list[str]) -> str:
    """입력 중 검사 스크립트 (제품이 바뀌면 문자열이 바뀌어 다시 실행되고, 규칙표만 갈아 끼운다)."""
    data = json.dumps({"targets": targets, **mock.rule_table(product)}, ensure_ascii=False).replace("<", "\\u003c")
    return "<script>" + _JS.replace("__DATA__", data) + "</script>"


_JS = r"""
(function () {
  var D = __DATA__;
  var W = window.__bwLC || (window.__bwLC = { boxes: [], targets: {} });
  function compile(src) { try { return new RegExp(src, 'g'); } catch (e) { return null; } }
  W.data = D;
  W.res = D.rules.map(function (r) { return compile(r.re); });
  W.dur = compile(D.duration);
  W.num = compile(D.number);
  D.targets.forEach(function (k) { W.targets[k] = true; });
  W.boxes.forEach(function (b) { b.last = null; });   // 규칙표가 바뀌었으면 다시 그린다

  function flat(t) { return (t || '').replace(/\s+/g, '').toLowerCase(); }
  function scan(re, text, fn) {
    if (!re) return;
    re.lastIndex = 0;
    var m;
    while ((m = re.exec(text)) !== null) {
      if (m[0] === '') { re.lastIndex += 1; continue; }
      fn(m);
    }
  }
  function add(hits, m, kind, label, level) {
    var g = m[0], span = g.trim();
    if (!span) return;
    var start = m.index + (g.length - g.replace(/^\s+/, '').length);
    hits.push({ start: start, end: start + span.length, kind: kind, label: label, level: level });
  }
  // mock.detect() 와 같은 순서 · 같은 조건 · 같은 겹침 정리
  W.detect = function (text) {
    var d = W.data, hits = [];
    d.rules.forEach(function (r, i) {
      scan(W.res[i], text, function (m) {
        if (r.acne && /여드름/.test(m[0]) && !/치료|완치/.test(m[0])) return;
        add(hits, m, 'risk', r.label, r.level);
      });
    });
    scan(W.dur, text, function (m) {
      var hrs = flat(m[0].match(/\d+\s*시간/)[0]);
      if (!d.evidence.some(function (ev) { return ev.flat.indexOf(hrs) !== -1; })) add(hits, m, 'risk', d.proof, 1);
    });
    scan(W.num, text, function (m) {
      var n = flat(m[0]);
      var matched = d.evidence.filter(function (ev) { return ev.flat.indexOf(n) !== -1; });
      if (matched.length && matched.every(function (ev) { return ev.survey; })) add(hits, m, 'risk', d.proof, 1);
      else if (matched.length) add(hits, m, 'verified', '실증 일치', null);
      else add(hits, m, 'risk', d.proof, 1);
    });
    hits.sort(function (a, b) {
      return ((a.kind === 'risk' ? 0 : 1) - (b.kind === 'risk' ? 0 : 1)) || ((b.level || 0) - (a.level || 0)) ||
             ((b.end - b.start) - (a.end - a.start)) || (a.start - b.start);
    });
    var kept = [];
    hits.forEach(function (h) {
      if (kept.some(function (k) { return h.start < k.end && k.start < h.end; })) return;
      kept.push(h);
    });
    return kept.sort(function (a, b) { return a.start - b.start; });
  };
  function tone(h) { return h.kind === 'verified' ? 'verified' : (h.level === 2 ? 'risk' : 'caution'); }

  var COPY = ['fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'letterSpacing', 'wordSpacing', 'lineHeight',
              'textIndent', 'textTransform', 'tabSize', 'boxSizing', 'paddingTop', 'paddingRight', 'paddingBottom',
              'paddingLeft', 'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth'];
  function sync(b) {
    var ta = b.ta, bd = b.bd, cs = getComputedStyle(ta), r = ta.getBoundingClientRect();
    if (!r.width || cs.visibility === 'hidden') { bd.style.display = 'none'; return; }
    bd.style.display = '';
    COPY.forEach(function (p) { bd.style[p] = cs[p]; });
    var bars = ta.offsetWidth - ta.clientWidth - parseFloat(cs.borderLeftWidth) - parseFloat(cs.borderRightWidth);
    bd.style.left = r.left + 'px';
    bd.style.top = r.top + 'px';
    bd.style.width = (r.width - Math.max(0, bars)) + 'px';
    bd.style.height = r.height + 'px';
    bd.scrollTop = ta.scrollTop;
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }
  function summary(key, hits, text) {
    var box = document.querySelector('.bw-lc-sum[data-lc-for="' + key + '"]');
    if (!box) return;
    box.textContent = '';
    if (!text.trim()) { box.classList.add('is-empty'); return; }
    box.classList.remove('is-empty');
    var n = { risk: 0, caution: 0, verified: 0 };
    hits.forEach(function (h) { n[tone(h)] += 1; });
    box.appendChild(el('span', 'k', '입력 중 검사'));
    if (!n.risk && !n.caution) box.appendChild(el('span', 'n is-clear', '규칙상 걸리는 표현 없음'));
    if (n.risk) box.appendChild(el('span', 'n is-risk', '위험 ' + n.risk));
    if (n.caution) box.appendChild(el('span', 'n is-caution', '주의 ' + n.caution));
    if (n.verified) box.appendChild(el('span', 'n is-verified', '실증 일치 ' + n.verified));
    hits.filter(function (h) { return h.kind === 'risk'; }).slice(0, 3).forEach(function (h) {
      var w = el('span', 'w'); w.appendChild(el('b', '', '‘' + text.slice(h.start, h.end) + '’'));
      w.appendChild(document.createTextNode(' ' + h.label)); box.appendChild(w);
    });
    box.appendChild(el('span', 'note', '금지 표현 사전 · 규칙 기준이며, 최종 판정은 검토 결과가 정합니다'));
  }
  function render(b) {
    var ta = b.ta, text = ta.value, bd = b.bd;
    b.last = text;
    var hits = text.trim() ? W.detect(text) : [];
    bd.textContent = '';
    var pos = 0;
    hits.forEach(function (h) {
      if (h.start > pos) bd.appendChild(document.createTextNode(text.slice(pos, h.start)));
      bd.appendChild(el('span', 'bw-lc-mark is-' + tone(h), text.slice(h.start, h.end)));
      pos = h.end;
    });
    bd.appendChild(document.createTextNode(text.slice(pos) + '​'));
    sync(b);
    summary(b.key, hits, text);
  }
  function attach() {
    Object.keys(W.targets).forEach(function (key) {
      document.querySelectorAll('.st-key-' + key + ' textarea').forEach(function (ta) {
        if (ta.__bwLC) return;
        var bd = el('div', 'bw-lc-bd');
        bd.setAttribute('aria-hidden', 'true');
        document.body.appendChild(bd);   // React 가 관리하는 입력창 쪽 DOM 에는 끼워 넣지 않는다
        ta.spellcheck = false;   // 브라우저 맞춤법 물결선이 규칙 밑줄과 겹치지 않게
        var b = { ta: ta, bd: bd, key: key, last: null };
        ta.__bwLC = b;
        W.boxes.push(b);
        ta.addEventListener('scroll', function () { bd.scrollTop = ta.scrollTop; });
        render(b);
      });
    });
    W.boxes = W.boxes.filter(function (b) {
      if (b.ta.isConnected) return true;
      if (b.bd.parentNode) b.bd.parentNode.removeChild(b.bd);
      return false;
    });
  }
  W.render = render;
  if (!W.bound) {
    W.bound = true;
    document.addEventListener('input', function (e) { var b = e.target && e.target.__bwLC; if (b) render(b); }, true);
    var queued = false;
    function follow() {   // 화면 · 패널이 스크롤되거나 크기가 바뀌면 다음 프레임에 자리를 맞춘다
      if (queued) return;
      queued = true;
      requestAnimationFrame(function () { queued = false; W.boxes.forEach(sync); });
    }
    document.addEventListener('scroll', follow, true);
    window.addEventListener('resize', follow);
    setInterval(function () {
      attach();
      W.boxes.forEach(function (b) { if (b.ta.value !== b.last) render(b); else sync(b); });
    }, 300);
  }
  attach();
})();
"""
