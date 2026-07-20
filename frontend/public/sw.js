// Autodestruição: qualquer service worker antigo (de qualquer versão anterior,
// inclusive uma que cacheava agressivamente) precisa sumir. Limpa todo cache
// do navegador, cancela o próprio registro e força reload de todas as abas
// abertas — sem isso, um cliente com SW travado nunca vê os fixes do servidor.
self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys()
      await Promise.all(keys.map((key) => caches.delete(key)))
      await self.registration.unregister()
      const clientsList = await self.clients.matchAll({ type: 'window' })
      clientsList.forEach((client) => client.navigate(client.url))
    })()
  )
})
