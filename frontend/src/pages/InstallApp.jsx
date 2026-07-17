import { useEffect, useState } from 'react'
import { Smartphone, Monitor, Share, Menu, PlusSquare, CheckCircle2 } from 'lucide-react'
import { getDeferredPrompt, onPromptChange, triggerInstall, isStandalone } from '../pwaInstall'

const ua = navigator.userAgent
const isIOS = /iphone|ipad|ipod/i.test(ua) && !window.MSStream
const isAndroid = /android/i.test(ua)
const isMobileUA = isIOS || isAndroid

function InstallButton({ onInstalled }) {
  const [prompt, setPrompt] = useState(getDeferredPrompt())

  useEffect(() => onPromptChange(setPrompt), [])

  if (!prompt) return null

  const install = async () => {
    const choice = await triggerInstall()
    if (choice?.outcome === 'accepted') onInstalled?.()
  }

  return (
    <button
      onClick={install}
      className="w-full flex items-center justify-center gap-2 bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium py-2.5 rounded-lg"
    >
      <PlusSquare size={16} /> Instalar agora
    </button>
  )
}

function Step({ n, children }) {
  return (
    <li className="flex gap-3 items-start">
      <span className="shrink-0 w-5 h-5 rounded-full bg-gray-900 text-white text-xs font-bold flex items-center justify-center mt-0.5">
        {n}
      </span>
      <span className="text-sm text-gray-700">{children}</span>
    </li>
  )
}

export default function InstallApp() {
  const [installed, setInstalled] = useState(isStandalone())

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-lg font-bold text-gray-900 mb-1">Instalar o Pitbox</h1>
      <p className="text-gray-500 text-sm mb-6">
        Fixe o Pitbox como um atalho na tela do celular e na área de trabalho do computador — abre direto, sem passar pelo navegador.
      </p>

      {installed && (
        <div className="flex items-center gap-2 bg-green-50 border border-green-100 rounded-lg px-4 py-3 mb-6 text-green-800 text-sm">
          <CheckCircle2 size={16} /> O Pitbox já está instalado neste dispositivo.
        </div>
      )}

      {/* Celular */}
      <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Smartphone size={18} className="text-orange-500" />
          <h2 className="font-bold text-gray-900">No celular</h2>
          {isMobileUA && <span className="text-[10px] font-bold text-orange-600 bg-orange-50 rounded-full px-2 py-0.5">você está aqui</span>}
        </div>

        {isAndroid ? (
          <>
            <InstallButton onInstalled={() => setInstalled(true)} />
            <p className="text-gray-400 text-xs mt-3">
              Se o botão não aparecer, toque no menu <Menu size={11} className="inline -mt-0.5" /> do Chrome (⋮) e escolha <b>"Instalar app"</b> ou <b>"Adicionar à tela inicial"</b>.
            </p>
          </>
        ) : isIOS ? (
          <ol className="space-y-2.5">
            <Step n={1}>Toque no ícone de <b>Compartilhar</b> <Share size={13} className="inline -mt-0.5" /> na barra do Safari.</Step>
            <Step n={2}>Role a lista e toque em <b>"Adicionar à Tela de Início"</b>.</Step>
            <Step n={3}>Toque em <b>"Adicionar"</b> no canto superior direito.</Step>
          </ol>
        ) : (
          <p className="text-gray-500 text-sm">
            Abra este link no celular (Chrome no Android ou Safari no iPhone) pra ver o passo a passo específico do seu aparelho.
          </p>
        )}
      </div>

      {/* Computador */}
      <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Monitor size={18} className="text-orange-500" />
          <h2 className="font-bold text-gray-900">No computador</h2>
          {!isMobileUA && <span className="text-[10px] font-bold text-orange-600 bg-orange-50 rounded-full px-2 py-0.5">você está aqui</span>}
        </div>

        {!isMobileUA && <InstallButton onInstalled={() => setInstalled(true)} />}

        <p className="text-gray-500 text-sm mt-3">
          Se o botão não aparecer: no Chrome ou Edge, clique no ícone de instalação <PlusSquare size={13} className="inline -mt-0.5" /> que fica dentro da barra de endereço, à direita do link do Pitbox, e depois em <b>"Instalar"</b>.
        </p>
      </div>
    </div>
  )
}
