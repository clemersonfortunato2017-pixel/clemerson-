// Captura o evento beforeinstallprompt assim que o app carrega, antes de qualquer
// navegação — no Chrome/Edge (Android e desktop) ele só dispara uma vez por sessão.
let deferredPrompt = null
const listeners = new Set()

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault()
  deferredPrompt = e
  listeners.forEach((cb) => cb(deferredPrompt))
})

window.addEventListener('appinstalled', () => {
  deferredPrompt = null
  listeners.forEach((cb) => cb(null))
})

export function getDeferredPrompt() {
  return deferredPrompt
}

export function onPromptChange(cb) {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

export async function triggerInstall() {
  if (!deferredPrompt) return null
  deferredPrompt.prompt()
  const choice = await deferredPrompt.userChoice
  deferredPrompt = null
  listeners.forEach((cb) => cb(null))
  return choice
}

export function isStandalone() {
  return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true
}
