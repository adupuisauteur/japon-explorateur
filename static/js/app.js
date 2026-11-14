/* Interactions légères : HTMX + quelques aides. Aucun appel externe. */
(function () {
  "use strict";

  // Service worker (PWA)
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(function () {});
  }

  // Bandeau hors ligne
  function updateOnline() {
    var b = document.getElementById("offline-banner");
    if (b) { b.classList.toggle("d-none", navigator.onLine); }
  }
  window.addEventListener("online", updateOnline);
  window.addEventListener("offline", updateOnline);
  updateOnline();

  // Tout sélectionner / désélectionner
  document.addEventListener("change", function (e) {
    var t = e.target;
    if (t.matches("[data-select-all]")) {
      document.querySelectorAll(t.getAttribute("data-select-all")).forEach(function (c) { c.checked = t.checked; });
      updateSelectionCount();
    } else if (t.matches(".js-select")) {
      updateSelectionCount();
    }
  });

  function updateSelectionCount() {
    var n = document.querySelectorAll(".js-select:checked").length;
    document.querySelectorAll("[data-selection-count]").forEach(function (el) { el.textContent = n; });
    document.querySelectorAll("[data-needs-selection]").forEach(function (el) { el.disabled = n === 0; });
  }
  document.addEventListener("htmx:afterSwap", updateSelectionCount);
  document.addEventListener("DOMContentLoaded", updateSelectionCount);

  // Panneau latéral : ouverture d'une notice sans quitter la session
  document.addEventListener("htmx:afterSwap", function (e) {
    if (e.detail.target && e.detail.target.id === "panel-body") {
      var panel = bootstrap.Offcanvas.getOrCreateInstance(document.getElementById("panel"));
      panel.show();
      var t = e.detail.target.querySelector("[data-panel-title]");
      if (t) { document.getElementById("panel-title").textContent = t.getAttribute("data-panel-title"); }
    }
  });

  // 2.0.0 : copie d'un texte dans le presse-papiers (« Copier le diagnostic »), sans script en ligne
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy-target]");
    if (!btn) { return; }
    var source = document.querySelector(btn.getAttribute("data-copy-target"));
    if (!source) { return; }
    var text = source.textContent;
    var status = document.querySelector("[data-copy-status]");
    function done(ok) {
      if (status) { status.textContent = ok ? (btn.getAttribute("data-copy-done") || "Copié") : "Copie impossible : sélectionnez le texte puis Ctrl+C"; }
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
    } else {
      var range = document.createRange();
      range.selectNodeContents(source);
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      try { done(document.execCommand("copy")); } catch (err) { done(false); }
    }
  });

  // Comportements déclaratifs (remplacent les gestionnaires en ligne, interdits par la politique CSP)
  document.addEventListener("change", function (e) {
    var t = e.target;
    if (t.matches("[data-autosubmit]") && t.form) { t.form.requestSubmit ? t.form.requestSubmit() : t.form.submit(); }
    if (t.matches("[data-toggle-show]") && t.checked) {
      document.querySelectorAll(t.getAttribute("data-toggle-show")).forEach(function (el) { el.classList.remove("d-none"); });
    }
    if (t.matches("[data-toggle-hide]") && t.checked) {
      document.querySelectorAll(t.getAttribute("data-toggle-hide")).forEach(function (el) { el.classList.add("d-none"); });
    }
  });
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-set-field]");
    if (btn && btn.form) {
      var field = btn.form.elements[btn.getAttribute("data-set-field")];
      if (field) { field.value = btn.getAttribute("data-set-value") || ""; }
    }
  });

  // Confirmation explicite
  document.addEventListener("submit", function (e) {
    var f = e.target;
    var msg = f.getAttribute("data-confirm") || (e.submitter && e.submitter.getAttribute("data-confirm"));
    if (msg && !window.confirm(msg)) { e.preventDefault(); }
  });

  // Mise en cache explicite d'une fiche pour consultation hors ligne
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-cache-offline]");
    if (!btn || !("caches" in window)) { return; }
    e.preventDefault();
    var url = btn.getAttribute("data-cache-offline");
    caches.open("fiches-v1").then(function (cache) {
      return cache.add(new Request(url, { credentials: "same-origin" }));
    }).then(function () {
      btn.innerHTML = '<i class="bi bi-check2"></i> Disponible hors ligne';
      btn.classList.replace("btn-outline-secondary", "btn-outline-success");
    }).catch(function () { btn.textContent = "Mise en cache impossible"; });
  });
})();
