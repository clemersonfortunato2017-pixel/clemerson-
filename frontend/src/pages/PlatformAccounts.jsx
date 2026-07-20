import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link2, Plus, X, Power, Trash2, AlertTriangle, RefreshCw, CheckCircle2 } from 'lucide-react'
import {
  getPlatformsStatus, getPlatformAccounts, connectPlatformAccount,
  togglePlatformAccount, deletePlatformAccount, getSyncFailures, retrySyncFailure,
} from '../api'

const PLATFORM_LABELS = { mercadolivre: 'Mercado Livre', shopee: 'Shopee', amazon: 'Amazon', magalu: 'Magazine Luiza', facebook: 'Facebook Marketplace' }
const CONNECTABLE = ['mercadolivre', 'shopee']

export default function PlatformAccounts() {
  const [connectFor, setConnectFor] = useState(null)
  const [label, setLabel] = useState('')
  const [authUrl, setAuthUrl] = useState(null)
  const [error, setError] = useState('')
  const qc = useQueryClient()

  const { data: status } = useQuery({ queryKey: ['platforms-status'], queryFn: getPlatformsStatus })
  const { data: accounts } = useQuery({ queryKey: ['platform-accounts'], queryFn: getPlatformAccounts })
  const { data: failures } = useQuery({ queryKey: ['sync-failures'], queryFn: getSyncFailures, refetchInterval: 30000 })

  const toggleMut = useMutation({
    mutationFn: togglePlatformAccount,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['platform-accounts'] }),
  })
  const deleteMut = useMutation({
    mutationFn: deletePlatformAccount,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['platform-accounts'] }),
  })
  const retryMut = useMutation({
    mutationFn: retrySyncFailure,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sync-failures'] }),
  })

  const startConnect = async () => {
    setError('')
    setAuthUrl(null)
    try {
      const r = await connectPlatformAccount(connectFor, label)
      setAuthUrl(r.auth_url)
    } catch (e) {
      setError(e.response?.data?.detail || 'Erro ao gerar link de conexão')
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Contas conectadas</h2>
          <p className="text-gray-500 text-sm mt-1">Multi-conta — cada conta extra entra automaticamente na publicação e na baixa de estoque cruzada</p>
        </div>
        <button onClick={() => { setConnectFor('mercadolivre'); setLabel(''); setAuthUrl(null); setError('') }}
          className="flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
          <Plus size={16} /> Conectar conta
        </button>
      </div>

      {/* Alertas de sincronização falhada */}
      {failures?.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle size={16} className="text-red-500" />
            <h3 className="text-sm font-semibold text-red-700">{failures.length} anúncio(s) sem sincronizar estoque com as outras contas</h3>
          </div>
          <div className="space-y-2">
            {failures.map(f => (
              <div key={f.listing_id} className="flex items-center justify-between bg-white rounded-lg px-3 py-2 text-sm">
                <div>
                  <span className="font-medium text-gray-800">{f.part_title || `Peça #${f.part_id}`}</span>
                  <span className="text-gray-400 ml-2">{PLATFORM_LABELS[f.marketplace] || f.marketplace} · {f.marketplace_listing_id}</span>
                </div>
                <button onClick={() => retryMut.mutate(f.listing_id)} disabled={retryMut.isPending}
                  className="flex items-center gap-1 text-orange-600 hover:text-orange-700 text-xs font-medium disabled:opacity-50">
                  <RefreshCw size={13} /> Tentar de novo
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Status por plataforma */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {status?.map(p => (
          <div key={p.name} className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-gray-900 text-sm">{p.display_name}</span>
              {p.connected
                ? <CheckCircle2 size={16} className="text-green-500" />
                : <Link2 size={16} className="text-gray-300" />}
            </div>
            <p className="text-xs text-gray-400">{p.accounts.length} conta(s) ativa(s)</p>
            {p.accounts.map(a => (
              <p key={a.account_id ?? 'legacy'} className="text-xs text-gray-500 mt-1">• {a.label}</p>
            ))}
          </div>
        ))}
      </div>

      {/* Lista de contas extras cadastradas */}
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Contas extras cadastradas</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-400 text-xs border-b border-gray-100">
              <th className="py-2 font-medium">Plataforma</th>
              <th className="py-2 font-medium">Rótulo</th>
              <th className="py-2 font-medium">ID externo</th>
              <th className="py-2 font-medium">Status</th>
              <th className="py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {accounts?.length === 0 && (
              <tr><td colSpan={5} className="py-4 text-gray-400 text-center">Nenhuma conta extra ainda — a conta ML principal roda fora desta lista.</td></tr>
            )}
            {accounts?.map(a => (
              <tr key={a.id} className="border-b border-gray-50">
                <td className="py-2">{PLATFORM_LABELS[a.platform] || a.platform}</td>
                <td className="py-2 font-medium text-gray-700">{a.label}</td>
                <td className="py-2 text-gray-500">{a.external_id}</td>
                <td className="py-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${a.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {a.active ? 'ativa' : 'pausada'}
                  </span>
                </td>
                <td className="py-2 flex gap-2 justify-end">
                  <button onClick={() => toggleMut.mutate(a.id)} title="Ativar/pausar" className="text-gray-400 hover:text-orange-500">
                    <Power size={15} />
                  </button>
                  <button onClick={() => confirm(`Remover a conta "${a.label}"?`) && deleteMut.mutate(a.id)} title="Remover" className="text-gray-400 hover:text-red-500">
                    <Trash2 size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal conectar */}
      {connectFor && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-bold text-gray-900">Conectar conta</h3>
              <button onClick={() => setConnectFor(null)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Plataforma</label>
                <select value={connectFor} onChange={e => { setConnectFor(e.target.value); setAuthUrl(null) }}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                  {CONNECTABLE.map(p => <option key={p} value={p}>{PLATFORM_LABELS[p]}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Rótulo (pra identificar depois)</label>
                <input value={label} onChange={e => setLabel(e.target.value)} placeholder="Ex: ML - Pessoa física"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
              </div>

              {error && <p className="text-xs text-red-500">{error}</p>}

              {!authUrl ? (
                <button onClick={startConnect} disabled={!label}
                  className="w-full bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white py-2.5 rounded-lg text-sm font-medium transition-colors">
                  Gerar link de autorização
                </button>
              ) : (
                <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 text-xs text-orange-800 space-y-2">
                  <p className="font-medium">Abra este link NUM NAVEGADOR LOGADO na conta que você quer conectar (não na principal) e autorize:</p>
                  <a href={authUrl} target="_blank" rel="noreferrer" className="block bg-white border border-orange-200 rounded px-2 py-1.5 text-orange-600 break-all hover:underline">
                    {authUrl}
                  </a>
                  <p>Depois de autorizar, a conta aparece automaticamente nesta lista.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
