// Progressive enhancement only: every form still works server-side without this file.
(function () {
  "use strict";

  // Confirm destructive actions (forms carrying data-confirm).
  document.addEventListener("submit", function (event) {
    var message = event.target.getAttribute("data-confirm");
    if (message && !window.confirm(message)) { event.preventDefault(); }
  });

  // Sales entry: add/remove product lines and show a non-authoritative estimate.
  var lines = document.getElementById("lines");
  if (!lines) { return; }
  var estimate = document.getElementById("estimate");

  function refresh() {
    var total = 0;
    lines.querySelectorAll(".line").forEach(function (line) {
      var option = line.querySelector("select").selectedOptions[0];
      var qty = parseInt(line.querySelector("input").value, 10);
      var price = option ? parseFloat(option.dataset.price) : NaN;
      if (!isNaN(price) && qty > 0) { total += price * qty; }
    });
    estimate.textContent = "₹" + total.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    lines.querySelectorAll(".remove-line").forEach(function (b) {
      b.disabled = lines.querySelectorAll(".line").length === 1;
    });
  }

  document.getElementById("add-line").addEventListener("click", function () {
    var copy = lines.querySelector(".line").cloneNode(true);
    copy.querySelector("select").selectedIndex = 0;
    copy.querySelector("input").value = "1";
    lines.appendChild(copy);
    refresh();
  });
  lines.addEventListener("click", function (event) {
    if (event.target.classList.contains("remove-line")) {
      event.target.closest(".line").remove();
      refresh();
    }
  });
  lines.addEventListener("input", refresh);
  lines.addEventListener("change", function (event) {
    var line = event.target.closest(".line");
    var option = line && line.querySelector("select").selectedOptions[0];
    if (option && option.dataset.stock) { line.querySelector("input").max = option.dataset.stock; }
    refresh();
  });
  refresh();
})();
