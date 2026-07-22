import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getDailyReport, getParts, publishReady, preparePendingNow } from '../api'
import { CheckCircle2, XCircle, Calendar, Camera, Sparkles, AlertTriangle, Loader2 } from 'lucide-react'
import PhotoUploadModal from '../components/PhotoUploadModal'

const todayStr = () => new Date().toISOString().slice(0, 10)

function ReadyToPublish() {
  const qc = useQueryClient()
  const { data: ready } = useQuery({
    queryKey: ['parts', 'ready_to_publish'],
    queryFn: () => getParts({ status: 'ready_to_publish', limit: 50 }),
    refetchInterval: 30000,
  })
  const { data: review } = useQuery({
    queryKey: ['parts', 'needs_review'],
    queryFn: () => getParts({ status: 'needs_review', limit: 50 }),
    refetchInterval: 30000,
  })

  const publishMutation = useMutation({
    mutationFn: publishReady,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['parts'] })
      qc.invalidateQueries({ queryKey: ['daily-report'] })
    },
  })

  const checkNowMutation = useMutation({
    mutationFn: preparePendingNow,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['parts'] }),
  })

  const readyItems = ready?.items || []
  const reviewItems = review?.items || []

  if (readyItems.length === 0 && reviewItems.length === 0) return null

  return (
    <div className="mb-6 space-y-3">
      {readyItems.length > 0 && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles size={16} className="text-green-600" />
            <h2 className="text-sm font-semibold text-green-800">
              {readyItems.length} peça(s) identificada(s) sozinha — pronta(s) pra publicar
            </h2>
          </div>
          <div className="space-y-2">
            {readyItems.map((p) => (
              <div key={p.id} className="flex items-center justify-between bg-white rounded-lg px-3 py-2 border border-green-100">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800 truncate">{p.title}</p>
                  <p className="text-xs text-gray-500">{(p.sale_price || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</p>
                </div>
                <button
                  onClick={() => publishMutation.mutate(p.id)}
                  disabled={publishMutation.isPending}
                  className="flex items-center gap-1 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-xs font-medium px-3 py-1.5 rounded-lg ml-2 shrink-0"
                >
                  {publishMutation.isPending && publishMutation.variables === p.id ? <Loader2 size={12} className="animate-spin" /> : null}
                  Publicar
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {reviewItems.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle size={16} className="text-amber-600" />
            <h2 className="text-sm font-semibold text-amber-800">
              {reviewItems.length} peça(s) precisam de revisão manual
            </h2>
          </div>
          <div className="space-y-1">
            {reviewItems.map((p) => (
              <p key={p.id} className="text-sm text-amber-900">{p.title || `Peça #${p.id}`}</p>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={() => checkNowMutation.mutate()}
        disabled={checkNowMutation.isPending}
        className="text-xs text-gray-500 hover:text-gray-700 underline"
      >
        {checkNowMutation.isPending ? 'Verificando...' : 'Verificar peças pendentes agora'}
      </button>
    </div>
  )
}

export default function DailyReport() {
  const [date, setDate] = useState(todayStr())
  const [showUpload, setShowUpload] = useState(false)
  const { data, isLoading, isError } = useQuery({
    queryKey: ['daily-report', date],
    queryFn: () => getDailyReport(date),
    retry: 3,
  })

  return (
    <div className="p-6 max-w-3xl">
      {showUpload && <PhotoUploadModal onClose={() => setShowUpload(false)} />}

      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-lg font-bold text-gray-900">Esteira automática</h1>
          <p className="text-gray-500 text-sm">Tire foto de uma peça pra publicar sozinha, e acompanhe o que já saiu hoje.</p>
        </div>
      </div>

      <button onClick={() => setShowUpload(true)}
        className="w-full md:w-auto flex items-center justify-center gap-2 bg-orange-500 hover:bg-orange-600 text-white px-5 py-3 rounded-lg text-sm font-medium transition-colors mb-6">
        <Camera size={18} /> Tirar foto — anunciar sozinho
      </button>

      <ReadyToPublish />

      <div className="flex items-center justify-between mb-6">
        <h2 className="text-sm font-semibold text-gray-700">Relatório do dia</h2>
        <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-lg px-3 py-1.5">
          <Calendar size={14} className="text-gray-400" />
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="text-sm outline-none" />
        </div>
      </div>

      {isLoading && <p className="text-gray-400 text-sm">Carregando...</p>}
      {isError && (
        <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          Não consegui carregar o relatório agora (o servidor pode estar reiniciando). Recarregue a página em alguns segundos.
        </p>
      )}

      {data && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-white border border-gray-100 rounded-xl p-4">
              <p className="text-xs text-gray-500">Publicados</p>
              <p className="text-2xl font-bold text-gray-900">{data.published_count}</p>
            </div>
            <div className="bg-white border border-gray-100 rounded-xl p-4">
              <p className="text-xs text-gray-500">Valor total</p>
              <p className="text-2xl font-bold text-green-600">
                {(data.total_value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
              </p>
            </div>
            <div className="bg-white border border-gray-100 rounded-xl p-4">
              <p className="text-xs text-gray-500">Erros (não publicados)</p>
              <p className="text-2xl font-bold text-red-500">{data.error_count}</p>
            </div>
          </div>

          <h2 className="text-sm font-semibold text-gray-700 mb-2">Publicados</h2>
          <div className="space-y-2 mb-6">
            {(data.published || []).map((p, i) => (
              <a key={i} href={p.url} target="_blank" rel="noreferrer"
                className="flex items-center justify-between bg-white border border-gray-100 rounded-lg px-4 py-2.5 hover:border-orange-300 transition-colors">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-green-500" />
                  <span className="text-sm text-gray-800">{p.title}</span>
                </div>
                <span className="text-sm font-medium text-gray-900">
                  {(p.price || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                </span>
              </a>
            ))}
            {(data.published || []).length === 0 && <p className="text-gray-400 text-sm">Nenhum anúncio publicado neste dia.</p>}
          </div>

          <h2 className="text-sm font-semibold text-gray-700 mb-2">Erros — precisam de atenção</h2>
          <div className="space-y-2">
            {(data.errors || []).map((e, i) => (
              <div key={i} className="bg-red-50 border border-red-100 rounded-lg px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <XCircle size={16} className="text-red-500" />
                  <span className="text-sm text-gray-800">{e.title}</span>
                </div>
                <pre className="text-xs text-red-700 mt-1 whitespace-pre-wrap">{JSON.stringify(e.log, null, 2)}</pre>
              </div>
            ))}
            {(data.errors || []).length === 0 && <p className="text-gray-400 text-sm">Nenhum erro neste dia.</p>}
          </div>
        </>
      )}
    </div>
  )
}
