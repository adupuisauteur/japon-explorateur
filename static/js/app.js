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
  // 2.0.0 (lot 5) : fenêtres de notification (toasts Bootstrap), sans script en ligne.
  function showToasts(root) {
    (root || document).querySelectorAll("[data-jed-toast]:not([data-shown])").forEach(function (el) {
      el.setAttribute("data-shown", "1");
      var toast = bootstrap.Toast.getOrCreateInstance(el, {
        autohide: el.getAttribute("data-autohide") === "true", delay: 12000
      });
      el.addEventListener("hidden.bs.toast", function () { el.remove(); });
      toast.show();
    });
  }
  document.addEventListener("htmx:afterSettle", function (e) { showToasts(e.detail.target); });

  // 2.0.0 (lot 5) : les actualisations périodiques sont suspendues quand l'onglet est masqué, puis reprennent
  // dès qu'il redevient visible (aucun filtre HTMX en ligne : politique de sécurité du contenu).
  document.addEventListener("htmx:beforeRequest", function (e) {
    var elt = e.detail && e.detail.elt;
    if (document.hidden && elt && elt.closest && elt.closest("[data-pause-hidden]")) { e.preventDefault(); }
  });
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { document.body.dispatchEvent(new CustomEvent("jed:visible")); }
  });
  // 2.0.0 (lot 8) : choix du modèle dans une liste. Le champ texte reste la valeur envoyée ; il ne s'affiche
  // que pour « Autre modèle (saisie libre) » ou quand aucune liste n'est disponible.
  function syncModelPicker(select) {
    var input = document.querySelector(select.getAttribute("data-model-select"));
    if (!input) { return; }
    if (select.value === "__libre__") {
      input.classList.remove("d-none");
    } else {
      if (select.value) { input.value = select.value; }
      input.classList.add("d-none");
    }
  }
  document.addEventListener("change", function (e) {
    var select = e.target.closest && e.target.closest("[data-model-select]");
    if (select) {
      syncModelPicker(select);
      if (select.value === "__libre__") {
        var input = document.querySelector(select.getAttribute("data-model-select"));
        if (input) { input.focus(); }
      }
    }
  });
  document.addEventListener("htmx:afterSettle", function (e) {
    var root = e.detail && e.detail.target;
    if (!root || !root.classList || !root.classList.contains("model-picker")) { return; }
    var select = root.querySelector("[data-model-select]");
    var input = document.getElementById(root.id.replace(/^mp-/, ""));
    if (select) { syncModelPicker(select); } else if (input) { input.classList.remove("d-none"); }
  });
})();
