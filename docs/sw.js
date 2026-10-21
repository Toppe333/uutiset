// Sovelluksen kuori välimuistista, news.json aina verkosta (välimuisti varalla offline-tilaan).
const CACHE = "uutiset-v5";
const SHELL = ["./", "index.html", "style.css", "app.js", "manifest.webmanifest", "icon.svg", "icon-192.png",
  "logos/yle.svg", "logos/hs.svg", "logos/kl.svg", "logos/al.svg", "logos/hasa.svg"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;

  if (url.pathname.endsWith("/news.json")) {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(new Request(url.pathname), copy));
          return res;
        })
        .catch(() => caches.match(new Request(url.pathname)))
    );
    return;
  }

  // Kuori: välimuisti ensin, päivitys taustalla.
  e.respondWith(
    caches.match(e.request).then((cached) => {
      const network = fetch(e.request).then((res) => {
        if (res.ok) caches.open(CACHE).then((c) => c.put(e.request, res.clone()));
        return res;
      }).catch(() => cached);
      return cached || network;
    })
  );
});
