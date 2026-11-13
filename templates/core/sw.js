/* Service worker — cache contrôlé de l'interface et des fiches explicitement mises en cache (§3.3).
   Les recherches externes, synchronisations et actions nécessitent Internet. */
const SHELL = "shell-v{{ version }}";
const FICHES = "fiches-v1";
const SHELL_URLS = [
  "/hors-ligne/",
  "{{ static_prefix }}css/app.css",
  "{{ static_prefix }}js/app.js",
  "{{ static_prefix }}vendor/bootstrap/bootstrap.min.css",
  "{{ static_prefix }}vendor/bootstrap/bootstrap.bundle.min.js",
  "{{ static_prefix }}vendor/htmx/htmx.min.js",
  "{{ static_prefix }}vendor/bootstrap-icons/bootstrap-icons.min.css",
  "{{ static_prefix }}vendor/bootstrap-icons/fonts/bootstrap-icons.woff2",
  "{{ static_prefix }}icons/icon-192.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_URLS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k.startsWith("shell-") && k !== SHELL).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Ressources statiques : cache d'abord
  if (url.pathname.startsWith("{{ static_prefix }}")) {
    event.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(SHELL).then((c) => c.put(req, copy));
      return res;
    })));
    return;
  }

  // Pages : réseau d'abord ; si hors ligne, fiche mise en cache explicitement ou page hors ligne
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).then((res) => {
        // Rafraîchit une fiche déjà mise en cache par l'utilisateur
        const copy = res.clone();
        caches.open(FICHES).then((c) => c.match(req).then((hit) => { if (hit && copy.ok) c.put(req, copy); }));
        return res;
      }).catch(() => caches.match(req, { cacheName: FICHES }).then((hit) => hit || caches.match("/hors-ligne/")))
    );
  }
});
