// Applies the saved theme before the first paint to prevent flash.
// Loaded via <script src="..."> in <head> so CSP 'self' allows it.
(function () {
  var saved = localStorage.getItem("theme");
  if (saved === "dark" || saved === "light") {
    document.documentElement.setAttribute("data-theme", saved);
  }
  // Default: light mode (:root variables). OS media-query is the fallback when
  // no explicit preference is stored (handled in CSS).
}());
