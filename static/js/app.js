// Progressive enhancement only: every form still works server-side without this file.
(function () {
  "use strict";

  // ── Theme toggle ──────────────────────────────────────────────────────────
  var html   = document.documentElement;
  var btn    = document.getElementById("theme-toggle");
  var icon   = document.getElementById("theme-icon");
  var lbl    = document.getElementById("theme-label");

  function currentTheme() {
    var attr = html.getAttribute("data-theme");
    if (attr === "dark" || attr === "light") { return attr; }
    // Fall back to OS preference
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function applyTheme(theme) {
    html.setAttribute("data-theme", theme);
    try { localStorage.setItem("theme", theme); } catch (e) { /* storage blocked: theme just won't persist */ }
    if (!icon || !lbl || !btn) { return; }
    if (theme === "dark") {
      icon.textContent = "☀️";
      lbl.textContent  = "Light";
      btn.setAttribute("aria-label", "Switch to light mode");
    } else {
      icon.textContent = "🌙";
      lbl.textContent  = "Dark";
      btn.setAttribute("aria-label", "Switch to dark mode");
    }
  }

  // Sync button to whatever theme-init.js already set (or defaulted to)
  applyTheme(currentTheme());

  if (btn) {
    btn.addEventListener("click", function () {
      applyTheme(currentTheme() === "dark" ? "light" : "dark");
    });
  }

  // ── Mobile sidebar toggle ────────────────────────────────────────────────
  var sidebarToggle = document.getElementById("sidebar-toggle");
  var sidebar       = document.getElementById("sidebar");

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener("click", function () {
      var open = sidebar.classList.toggle("open");
      sidebarToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });

    // Close sidebar when clicking outside it on mobile
    document.addEventListener("click", function (e) {
      if (window.innerWidth > 768) { return; }
      if (!sidebar.contains(e.target) && !sidebarToggle.contains(e.target)) {
        sidebar.classList.remove("open");
        sidebarToggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  // ── Confirm destructive actions ──────────────────────────────────────────
  document.addEventListener("submit", function (event) {
    var message = event.target.getAttribute("data-confirm");
    if (message && !window.confirm(message)) { event.preventDefault(); }
  });

  // ── Sales entry: add/remove product lines + running estimate ─────────────
  var lines = document.getElementById("lines");
  if (!lines) { return; }
  var estimate = document.getElementById("estimate");

  function refresh() {
    var total = 0;
    lines.querySelectorAll(".line").forEach(function (line) {
      var sel    = line.querySelector("select");
      var inp    = line.querySelector("input[name='quantity']");
      var option = sel ? sel.selectedOptions[0] : null;
      var qty    = inp ? parseInt(inp.value, 10) : NaN;
      var price  = option ? parseFloat(option.dataset.price) : NaN;
      if (!isNaN(price) && qty > 0) { total += price * qty; }
    });
    if (estimate) {
      estimate.textContent = "₹" + total.toLocaleString("en-IN", {
        minimumFractionDigits: 2, maximumFractionDigits: 2
      });
    }
    lines.querySelectorAll(".remove-line").forEach(function (b) {
      b.disabled = lines.querySelectorAll(".line").length === 1;
    });
  }

  var addLineBtn = document.getElementById("add-line");
  if (addLineBtn) {
    addLineBtn.addEventListener("click", function () {
      var copy = lines.querySelector(".line").cloneNode(true);
      copy.querySelector("select").selectedIndex = 0;
      var qtyInput = copy.querySelector("input[name='quantity']");
      if (qtyInput) { qtyInput.value = "1"; }
      lines.appendChild(copy);
      refresh();
    });
  }

  lines.addEventListener("click", function (event) {
    if (event.target.classList.contains("remove-line")) {
      event.target.closest(".line").remove();
      refresh();
    }
  });

  lines.addEventListener("input", refresh);

  lines.addEventListener("change", function (event) {
    var line   = event.target.closest(".line");
    var option = line && line.querySelector("select").selectedOptions[0];
    if (option && option.dataset.stock) {
      var qtyInput = line.querySelector("input[name='quantity']");
      if (qtyInput) { qtyInput.max = option.dataset.stock; }
    }
    refresh();
  });

  refresh();
}());
