/**
 * IKFlow Mecânica — Service Worker PWA
 * Cache estratégico: Shell estático + Network-first para dados
 */
const CACHE_NAME = 'ikflow-mecanica-v6';
const CACHE_STATIC = 'ikflow-static-v6';
const CACHE_PAGES = 'ikflow-pages-v6';

// Assets locais — cacheados individualmente (erros ignorados)
const SHELL_LOCAL = [
  '/static/js/script.js',
  '/static/img/icon-192.png',
];

// Assets externos CDN — mode no-cors, erros ignorados
const SHELL_CDN = [
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
];

// Cachear um asset sem lançar erro se falhar
async function tryCache(cache, url, opts) {
  try {
    await cache.add(new Request(url, opts || {}));
  } catch (e) {
    console.log('[SW] Cache ignorado (erro esperado):', url);
  }
}

// Instalar: pré-cachear shell de forma tolerante a falhas
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_STATIC).then(async cache => {
      for (const url of SHELL_LOCAL)  await tryCache(cache, url);
      for (const url of SHELL_CDN)    await tryCache(cache, url, { mode: 'no-cors' });
    })
  );
});

// Ativar: limpar TODOS os caches antigos
self.addEventListener('activate', event => {
  self.clients.claim();
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_STATIC && k !== CACHE_PAGES && k !== CACHE_NAME).map(k => {
        console.log('[SW] Deletando cache antigo:', k);
        return caches.delete(k);
      }))
    )
  );
});

// Fetch: Cache-first para estáticos, Network-first para páginas
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  const request = event.request;

  // Ignorar requisições não-GET e API
  if (request.method !== 'GET') return;
  if (url.pathname.startsWith('/api/')) return;

  // Estáticos (/static/*): stale-while-revalidate
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.open(CACHE_STATIC).then(cache =>
        cache.match(request).then(cached => {
          const fetchPromise = fetch(request).then(response => {
            if (response.ok) cache.put(request, response.clone());
            return response;
          }).catch(() => cached);
          return cached || fetchPromise;
        })
      )
    );
    return;
  }

  // Páginas HTML: network-first, NÃO salvar em cache (sempre atualizado)
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match(request).then(cached => {
          if (cached) return cached;
          // Fallback offline
          return new Response(
            `<!DOCTYPE html><html lang="pt-br"><head><meta charset="UTF-8">
            <title>IKFlow — Offline</title>
            <style>body{font-family:sans-serif;text-align:center;padding:60px;background:#0b2447;color:#fff}
            h2{color:#08a5b2}p{color:#ccc}.btn{display:inline-block;margin-top:20px;padding:12px 28px;
            background:#08a5b2;color:#fff;border-radius:8px;text-decoration:none}</style></head>
            <body><h2>IKFlow Mecânica</h2>
            <p>Você está offline. Algumas funções não estão disponíveis.</p>
            <a class="btn" href="/">Tentar novamente</a></body></html>`,
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        })
      )
    );
    return;
  }

  // Outros recursos: network-first
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});

// Listener de mensagens do cliente (para skipWaiting)
self.addEventListener('message', event => {
  if (event.data && event.data.action === 'skipWaiting') {
    self.skipWaiting();
  }
});

// Sincronização em background (quando voltar online)
self.addEventListener('sync', event => {
  if (event.tag === 'sync-pendentes') {
    console.log('[SW] Sincronizando dados pendentes...');
  }
});

// ── Web Push Notifications ──────────────────────────────────
self.addEventListener('push', event => {
  let data = { titulo: 'IKFlow Mecânica', corpo: 'Nova notificação', url: '/' };
  try {
    if (event.data) data = { ...data, ...event.data.json() };
  } catch (e) {
    if (event.data) data.corpo = event.data.text();
  }
  const options = {
    body: data.corpo,
    icon: '/static/img/icon-192.png',
    badge: '/static/img/icon-192.png',
    data: { url: data.url || '/' },
    vibrate: [200, 100, 200],
    tag: 'ikflow-notif',
    renotify: true,
  };
  event.waitUntil(
    self.registration.showNotification(data.titulo, options)
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = (event.notification.data || {}).url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const client of list) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
