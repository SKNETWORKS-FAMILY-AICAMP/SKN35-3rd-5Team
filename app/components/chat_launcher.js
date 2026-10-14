/* Keep Streamlit's native popover/form; only control dragging and placement. */
(() => {
  const singleton = "__beauretteChatLauncher";
  if (window[singleton]) {
    window[singleton].refresh();
    return;
  }

  const storageKey = "beaurette.chat.launcher.position.v1";
  const margin = 12;
  const gap = 12;
  const buttonSelector = '.st-key-chat_launcher [data-testid="stPopoverButton"]';
  let position = null;
  let drag = null;
  let suppressClick = false;
  let frame = null;
  let popup = null;
  let launcher = null;
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey));
    if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)) position = saved;
  } catch (_) { /* Storage is optional, including in private browsing. */ }

  const clamp = (value, low, high) => Math.min(Math.max(value, low), Math.max(low, high));
  const viewport = () => {
    const view = window.visualViewport;
    const left = view?.offsetLeft || 0;
    const top = view?.offsetTop || 0;
    const width = view?.width || window.innerWidth;
    const height = view?.height || window.innerHeight;
    return { left, top, width, height, right: left + width, bottom: top + height };
  };
  const style = (element, key, value) => {
    if (element.style.getPropertyValue(key) !== value) element.style.setProperty(key, value);
  };
  const bounds = (view, box) => ({
    left: view.left + margin,
    top: view.top + margin,
    right: Math.max(view.left + margin, view.right - box.width - margin),
    bottom: Math.max(view.top + margin, view.bottom - box.height - margin),
  });

  function move(x, y, remember = false) {
    if (!launcher) return;
    const view = viewport();
    const box = launcher.getBoundingClientRect();
    const limits = bounds(view, box);
    x = clamp(x, limits.left, limits.right);
    y = clamp(y, limits.top, limits.bottom);
    style(launcher, "left", `${x}px`);
    style(launcher, "top", `${y}px`);
    style(launcher, "bottom", "auto");
    if (remember) {
      position = {
        x: (x - limits.left) / Math.max(1, limits.right - limits.left),
        y: (y - limits.top) / Math.max(1, limits.bottom - limits.top),
      };
      try { sessionStorage.setItem(storageKey, JSON.stringify(position)); } catch (_) { /* Optional. */ }
    }
  }

  function placePopup() {
    const button = document.querySelector(buttonSelector);
    if (!popup || !button) return;
    const view = viewport();
    style(popup, "--bw-chat-popup-max-height", `${Math.max(1, view.height - margin * 2)}px`);
    style(popup, "--bw-chat-popup-max-width", `${Math.max(1, view.width - margin * 2)}px`);
    popup.dataset.bwChatPositioned = "true";
    const mini = popup.querySelector(".st-key-chat_mini");
    const history = mini?.querySelector(".st-key-chat_messages_mini")?.parentElement;
    if (history) {
      const css = getComputedStyle(popup);
      const chrome = mini.getBoundingClientRect().height - history.getBoundingClientRect().height
        + parseFloat(css.borderTopWidth) + parseFloat(css.borderBottomWidth);
      const historyHeight = Math.floor(clamp(view.height - margin * 2 - chrome, 80, 260) * 10) / 10;
      style(popup, "--bw-chat-popup-messages-height", `${historyHeight}px`);
    }
    const anchor = button.getBoundingClientRect();
    const box = popup.getBoundingClientRect();
    const right = view.right - anchor.right >= anchor.left - view.left;
    const down = view.bottom - anchor.bottom >= anchor.top - view.top;
    const x = right ? anchor.right + gap : anchor.left - box.width - gap;
    const y = down ? anchor.bottom + gap : anchor.top - box.height - gap;
    const limits = bounds(view, box);
    style(popup, "--bw-chat-popup-x", `${clamp(x, limits.left, limits.right)}px`);
    style(popup, "--bw-chat-popup-y", `${clamp(y, limits.top, limits.bottom)}px`);
    popup.dataset.bwChatDirection = `${down ? "down" : "up"}-${right ? "right" : "left"}`;
  }

  const resizeObserver = new ResizeObserver(() => refresh());
  function refresh() {
    if (frame !== null) return;
    frame = requestAnimationFrame(() => {
      frame = null;
      const nextLauncher = document.querySelector(".st-key-chat_launcher");
      const nextPopup = document.querySelector('[data-testid="stPopoverBody"]:has(.st-key-chat_mini)');
      if (launcher !== nextLauncher || popup !== nextPopup) {
        resizeObserver.disconnect();
        launcher = nextLauncher;
        popup = nextPopup;
        if (launcher) resizeObserver.observe(launcher);
        if (popup) resizeObserver.observe(popup);
      }
      if (launcher && !drag) {
        const view = viewport();
        const limits = bounds(view, launcher.getBoundingClientRect());
        move(position ? limits.left + clamp(position.x, 0, 1) * (limits.right - limits.left) : view.left + 22,
             position ? limits.top + clamp(position.y, 0, 1) * (limits.bottom - limits.top) : view.bottom - 82);
      }
      placePopup();
    });
  }

  document.addEventListener("pointerdown", (event) => {
    const button = event.target.closest?.(buttonSelector);
    if (!button || event.button !== 0 || !event.isPrimary) return;
    launcher = button.closest(".st-key-chat_launcher");
    const box = launcher.getBoundingClientRect();
    suppressClick = false;
    drag = { id: event.pointerId, button, startX: event.clientX, startY: event.clientY,
             left: box.left, top: box.top, moved: false };
    button.setPointerCapture(event.pointerId);
  }, true);

  document.addEventListener("pointermove", (event) => {
    if (!drag || drag.id !== event.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) < 6) return;
    drag.moved = true;
    launcher.dataset.bwDragging = "true";
    event.preventDefault();
    move(drag.left + dx, drag.top + dy);
    placePopup();
  }, { capture: true, passive: false });

  function finish(event) {
    if (!drag || drag.id !== event.pointerId) return;
    const current = drag;
    drag = null;
    delete launcher.dataset.bwDragging;
    if (current.moved) {
      const box = launcher.getBoundingClientRect();
      move(box.left, box.top, true);
      suppressClick = event.type !== "pointercancel";
    }
    if (current.button.hasPointerCapture(event.pointerId)) current.button.releasePointerCapture(event.pointerId);
    refresh();
  }
  document.addEventListener("pointerup", finish, true);
  document.addEventListener("pointercancel", finish, true);
  document.addEventListener("lostpointercapture", finish, true);
  document.addEventListener("click", (event) => {
    if (suppressClick && event.detail > 0 && event.target.closest?.(buttonSelector)) {
      suppressClick = false;
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);

  document.addEventListener("keydown", (event) => {
    if (!event.altKey || !event.target.closest?.(buttonSelector)) return;
    const offsets = { ArrowLeft: [-20, 0], ArrowRight: [20, 0], ArrowUp: [0, -20], ArrowDown: [0, 20] };
    if (!offsets[event.key]) return;
    event.preventDefault();
    const box = launcher.getBoundingClientRect();
    move(box.left + offsets[event.key][0], box.top + offsets[event.key][1], true);
    placePopup();
  }, true);

  new MutationObserver(refresh).observe(document.body, { childList: true, subtree: true });
  window.addEventListener("resize", refresh);
  window.visualViewport?.addEventListener("resize", refresh);
  window.visualViewport?.addEventListener("scroll", refresh);
  window[singleton] = { refresh };
  refresh();
})();
