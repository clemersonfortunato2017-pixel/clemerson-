import { useState, useEffect, useRef } from 'react'
import { Download, CheckCircle, AlertCircle, Loader, RefreshCw } from 'lucide-react'
import { importFromML, syncCompatibility, getSyncStatus, syncCompatFromTitles } from '../api'

export default function Import() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [syncLoading, setSyncLoading] = useState(false)
  const [syncResult, setSyncResult] = useState(null)
  const [titleSyncLoading, setTitleSyncLoading] = useState(false)
  const [titleSyncResult, setTitleSyncResult] = useState(null)
  const [titleSyncStatus, setTitleSyncStatus] = useState(null)
  const [syncStatus, setSyncStatus] = useState(null)
  const pollRef = useRef(null)

  function startPolling() {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        const s = await getSyncStatus()
        if (s.done || !s.running) {
          clearInterval(pollRef.current)
          pollRef.current = null
          setSyncLoading(false)
          setSyncResult({ processed: s.processed, compatibilities_added: s.added })
          setSyncStatus(s.error ? 'error' : 'success')
        }
      } catch {
        clearInterval(pollRef.current)
        pollRef.current = null
        setSyncLoading(false)
        setSyncStatus('error')
      }
    }, 3000)
  }

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  async function handleImportML() {
    setLoading(true)
    setStatus(null)
    setResult(null)
    try {
      const data = await importFromML()
      setResult(data)
      setStatus('success')
    } catch {
      setStatus('error')
    } finally {
      setLoading(false)
    }
  }

  async function handleSyncFromTitles() {
    setTitleSyncLoading(true)
    setTitleSyncStatus(null)
    setTitleSyncResult(null)
    try {
      const data = await syncCompatFromTitles()
      setTitleSyncResult(data)
      setTitleSyncStatus('success')
    } catch {
      setTitleSyncStatus('error')
    } finally {
      setTitleSyncLoading(false)
    }
  }

  async function handleSyncCompatibility() {
    setSyncLoading(true)
    setSyncStatus(null)
    setSyncResult(null)
    try {
      await syncCompatibility()
      startPolling()
    } catch {
      setSyncLoading(false)
      setSyncStatus('error')
    }
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900">Importar Estoque</h2>
        <p className="text-gray-500 text-sm mt-1">Sincronize seus anúncios dos marketplaces automaticamente</p>
      </div>

      <div className="grid gap-4 max-w-2xl">
        {/* Mercado Livre */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-yellow-400 rounded-lg flex items-center justify-center font-bold text-xs text-gray-900">ML</div>
              <div>
                <h3 className="font-semibold text-gray-900">Mercado Livre</h3>
                <p className="text-xs text-gray-500">Fortunato Auto Parts</p>
              </div>
            </div>
            <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium">Conectado</span>
          </div>
          <p className="text-sm text-gray-500 mb-4">
            Importa todos os anúncios ativos e sincroniza com o estoque do Pitbox. Peças novas são criadas automaticamente. <strong>Compatibilidade de veículos é importada junto.</strong>
          </p>

          {status === 'success' && result && (
            <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg flex items-start gap-2">
              <CheckCircle size={16} className="text-green-600 mt-0.5 shrink-0" />
              <div className="text-sm text-green-700">
                <strong>Importação concluída!</strong><br />
                {result.created} peças criadas · {result.updated} atualizadas · {result.total} total
                {result.compatibilities_added > 0 && (
                  <span> · <strong>{result.compatibilities_added} compatibilidades adicionadas</strong></span>
                )}
              </div>
            </div>
          )}

          {status === 'error' && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
              <AlertCircle size={16} className="text-red-600 mt-0.5 shrink-0" />
              <p className="text-sm text-red-700">Erro ao importar. Verifique as credenciais do ML.</p>
            </div>
          )}

          <button onClick={handleImportML} disabled={loading}
            className="flex items-center gap-2 bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            {loading ? <Loader size={16} className="animate-spin" /> : <Download size={16} />}
            {loading ? 'Importando...' : 'Importar agora'}
          </button>
        </div>

        {/* Sincronizar compatibilidade — todas as peças */}
        <div className="bg-white border border-blue-100 rounded-xl p-6">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center">
              <RefreshCw size={18} className="text-white" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Sincronizar compatibilidade de veículos</h3>
              <p className="text-xs text-gray-500">Atualiza veículos compatíveis de todas as peças via ML</p>
            </div>
          </div>
          <p className="text-sm text-gray-500 mb-4">
            Percorre todas as peças cadastradas que têm anúncio ativo no Mercado Livre e importa a lista de veículos compatíveis de cada uma. Use após a primeira importação ou quando quiser atualizar as compatibilidades em massa.
          </p>

          {syncStatus === 'success' && syncResult && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-start gap-2">
              <CheckCircle size={16} className="text-blue-600 mt-0.5 shrink-0" />
              <div className="text-sm text-blue-700">
                <strong>Sincronização concluída!</strong><br />
                {syncResult.processed} peças verificadas · <strong>{syncResult.compatibilities_added} veículos adicionados</strong>
              </div>
            </div>
          )}

          {syncStatus === 'error' && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
              <AlertCircle size={16} className="text-red-600 mt-0.5 shrink-0" />
              <p className="text-sm text-red-700">Erro ao sincronizar. Verifique o token do ML.</p>
            </div>
          )}

          <button onClick={handleSyncCompatibility} disabled={syncLoading}
            className="flex items-center gap-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            {syncLoading ? <Loader size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            {syncLoading ? 'Sincronizando... (pode demorar alguns minutos)' : 'Sincronizar compatibilidade'}
          </button>
        </div>

        {/* Compatibilidade por título */}
        <div className="bg-white border border-purple-100 rounded-xl p-6">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-purple-500 rounded-lg flex items-center justify-center text-white font-bold text-sm">IA</div>
            <div>
              <h3 className="font-semibold text-gray-900">Extrair compatibilidade dos títulos</h3>
              <p className="text-xs text-gray-500">Detecta marca, modelo e ano automaticamente pelo nome da peça</p>
            </div>
          </div>
          <p className="text-sm text-gray-500 mb-4">
            Analisa o título de cada peça (ex: <em>"Alternador Fiat Argo Cronos 2017-2020"</em>) e cadastra os veículos compatíveis automaticamente. Cobre Chevrolet, Fiat, Volkswagen, Ford, Honda, Toyota e mais.
          </p>

          {titleSyncStatus === 'success' && titleSyncResult && (
            <div className="mb-4 p-3 bg-purple-50 border border-purple-200 rounded-lg flex items-start gap-2">
              <CheckCircle size={16} className="text-purple-600 mt-0.5 shrink-0" />
              <div className="text-sm text-purple-700">
                <strong>Extração concluída!</strong><br />
                {titleSyncResult.parts_processed} peças analisadas · {titleSyncResult.skipped} sem padrão reconhecido · <strong>{titleSyncResult.compatibilities_added} compatibilidades adicionadas</strong>
              </div>
            </div>
          )}

          {titleSyncStatus === 'error' && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
              <AlertCircle size={16} className="text-red-600 mt-0.5 shrink-0" />
              <p className="text-sm text-red-700">Erro ao processar. Tente novamente.</p>
            </div>
          )}

          <button onClick={handleSyncFromTitles} disabled={titleSyncLoading}
            className="flex items-center gap-2 bg-purple-500 hover:bg-purple-600 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            {titleSyncLoading ? <Loader size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            {titleSyncLoading ? 'Analisando títulos...' : 'Extrair compatibilidade dos títulos'}
          </button>
        </div>

        {/* Shopee — em breve */}
        <div className="bg-white border border-gray-200 rounded-xl p-6 opacity-60">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-orange-500 rounded-lg flex items-center justify-center font-bold text-xs text-white">SP</div>
            <div>
              <h3 className="font-semibold text-gray-900">Shopee</h3>
              <p className="text-xs text-gray-500">Em breve</p>
            </div>
          </div>
        </div>

        {/* Amazon — em breve */}
        <div className="bg-white border border-gray-200 rounded-xl p-6 opacity-60">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-gray-900 rounded-lg flex items-center justify-center font-bold text-xs text-white">AMZ</div>
            <div>
              <h3 className="font-semibold text-gray-900">Amazon</h3>
              <p className="text-xs text-gray-500">Em breve</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
