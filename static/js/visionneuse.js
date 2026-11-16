/* 2.0.0 (lot 10) : visionneuse d'images IIIF intégrée (facultative). Aucune bibliothèque externe. */
(function () {
  "use strict";
  var root = document.querySelector("[data-viewer]");
  var data = document.getElementById("viewer-views");
  if (!root || !data) { return; }
  var views = JSON.parse(data.textContent);
  var image = root.querySelector("[data-viewer-image]");
  var page = root.querySelector("[data-viewer-page]");
  var label = root.querySelector("[data-viewer-label]");
  var zoom = root.querySelector("[data-viewer-zoom]");
  var index = 0;

  function show(i) {
    if (!views.length) { return; }
    index = Math.max(0, Math.min(views.length - 1, i));
    image.src = views[index].image;
    image.alt = "Vue " + (index + 1) + " du document";
    page.value = index + 1;
    label.textContent = views[index].label || "";
    if (index + 1 < views.length) { new Image().src = views[index + 1].image; }  // vue suivante préchargée
  }
  root.querySelector("[data-viewer-prev]").addEventListener("click", function () { show(index - 1); });
  root.querySelector("[data-viewer-next]").addEventListener("click", function () { show(index + 1); });
  page.addEventListener("change", function () { show(parseInt(page.value, 10) - 1); });
  zoom.addEventListener("click", function () { root.classList.toggle("viewer-zoomed"); });
  document.addEventListener("keydown", function (event) {
    if (event.target.tagName === "INPUT") { return; }
    if (event.key === "ArrowRight") { show(index + 1); }
    if (event.key === "ArrowLeft") { show(index - 1); }
  });
  show(0);
})();
