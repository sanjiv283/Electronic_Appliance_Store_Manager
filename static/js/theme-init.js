// Applies the saved theme before the first paint to prevent a flash.
// Loaded via <script src="..."> in <head> so CSP 'self' allows it.
(function () {
  try {
    var saved = localStorage.getItem("theme");
    if (saved === "dark" || saved === "light") {
      document.documentElement.setAttribute("data-theme", saved);
    }
  } catch (e) { /* storage blocked (private window): fall through to the default */ }
  // No saved choice: dark palette by default; the CSS follows an OS light preference.
}());
