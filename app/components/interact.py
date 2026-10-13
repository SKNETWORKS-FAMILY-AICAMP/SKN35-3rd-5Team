"""
[app/components/interact.py]
위험 표현 ↔ 오른쪽 근거(RAG) 연동 — 브라우저 쪽 스크립트 하나.

- 최신 답변(article[data-live="1"]) 안의 밑줄 표현 · 문제 표현 줄 · [n] · 출처 줄에는 data-cites="1,2",
  오른쪽 근거 조항에는 data-n="1" 이 붙어 있다 (cards.py · panels.py).
- 올리거나 키보드로 닿으면 양쪽을 함께 강조, 누르면 「근거」 탭으로 바꾸고 그 조항으로 부드럽게 스크롤.
- 오른쪽 조항에 올리면 가운데의 해당 표현이 강조된다.
- 문서 단위 이벤트 위임이라 다시 그려져도 한 번만 붙는다.
"""

LINK_SCRIPT = """<script>
(function () {
  if (window.__bwLink) return;
  window.__bwLink = true;
  var CENTER = 'article.bw-ai[data-live="1"] [data-cites]';
  var RIGHT = '.st-key-aside .bw-cite[data-n], .st-key-aside [data-cites]';
  function ids(el) { return (el.getAttribute('data-cites') || el.getAttribute('data-n') || '').split(',').filter(Boolean); }
  function clear() { document.querySelectorAll('.is-linked').forEach(function (e) { e.classList.remove('is-linked'); }); }
  function mark(ns) {
    clear();
    if (!ns.length) return;
    document.querySelectorAll('.st-key-aside .bw-cite[data-n]').forEach(function (e) {
      if (ns.indexOf(e.getAttribute('data-n')) >= 0) e.classList.add('is-linked');
    });
    document.querySelectorAll(CENTER + ', .st-key-aside [data-cites]').forEach(function (e) {
      if (ids(e).some(function (n) { return ns.indexOf(n) >= 0; })) e.classList.add('is-linked');
    });
  }
  function source(t) { return t && t.closest ? t.closest(CENTER + ', ' + RIGHT) : null; }
  function enter(e) { var s = source(e.target); if (s) mark(ids(s)); }
  function leave(e) { var s = source(e.target); if (s && !(e.relatedTarget && s.contains(e.relatedTarget))) clear(); }
  function jump(s) {
    var ns = ids(s);
    if (!ns.length) return;
    var tab = document.querySelector('.st-key-asidetabs [role="tab"]');
    if (tab && tab.getAttribute('aria-selected') !== 'true') tab.click();
    setTimeout(function () {
      mark(ns);
      var t = document.querySelector('.st-key-aside .bw-cite[data-n="' + ns[0] + '"]');
      if (!t) return;
      t.scrollIntoView({ behavior: 'smooth', block: 'center' });
      t.classList.remove('is-sweep'); void t.offsetWidth; t.classList.add('is-sweep');
    }, 80);
  }
  document.addEventListener('mouseover', enter);
  document.addEventListener('mouseout', leave);
  document.addEventListener('focusin', enter);
  document.addEventListener('focusout', leave);
  document.addEventListener('click', function (e) {
    var s = e.target.closest && e.target.closest(CENTER);
    if (s) jump(s);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var s = e.target.closest && e.target.closest(CENTER);
    if (s) { e.preventDefault(); jump(s); }
  });
})();
</script>"""
