(function () {
  const KEY = "ss-sidebar-collapsed";

  function applyState(collapsed) {
    const sidebar = document.getElementById("rest-sidebar");
    const layout = document.getElementById("layout-root");
    if (!sidebar || !layout) return;
    if (collapsed) {
      sidebar.classList.add("collapsed");
      layout.classList.add("sidebar-collapsed");
    } else {
      sidebar.classList.remove("collapsed");
      layout.classList.remove("sidebar-collapsed");
    }
  }

  function init() {
    const initial = localStorage.getItem(KEY) === "1";
    applyState(initial);
    const btn = document.getElementById("sidebar-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      const next = !(localStorage.getItem(KEY) === "1");
      localStorage.setItem(KEY, next ? "1" : "0");
      applyState(next);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
