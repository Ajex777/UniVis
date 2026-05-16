(function () {
  let activeCount = 0;
  let overlay = null;

  function ensureOverlay() {
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.className = "global-loading hidden";
    overlay.innerHTML = '<div class="global-spinner"></div><div class="global-loading-text"></div>';
    document.body.appendChild(overlay);
    return overlay;
  }

  function show(text) {
    activeCount += 1;
    const node = ensureOverlay();
    node.querySelector(".global-loading-text").textContent = text || "Loading...";
    node.classList.remove("hidden");
  }

  function hide() {
    activeCount = Math.max(0, activeCount - 1);
    if (activeCount === 0 && overlay) overlay.classList.add("hidden");
  }

  async function withLoading(text, task) {
    show(text);
    try {
      return await task();
    } finally {
      hide();
    }
  }

  window.UniVisLoading = { hide, show, withLoading };
})();
