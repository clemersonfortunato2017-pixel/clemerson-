import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Search, Plus, Package, WifiOff, X, Camera, Loader2 } from 'lucide-react'
import { getParts, createPart, uploadPhotos } from '../api'

const MIN_PHOTOS = 6 // mais que 5, por pedido do Clemerson — evita anúncio com peça mal fotografada

function PhotoUploadModal({ onClose }) {
  const [files, setFiles] = useState([])
  const [err, setErr] = useState('')
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: uploadPhotos,
    onSuccess: () => { qc.invalidateQueries(['parts']); setFiles([]); onClose() },
    onError: e => setErr(e?.response?.data?.detail || 'Erro ao enviar fotos'),
  })

  const submit = (e) => {
    e.preventDefault()
    if (files.length < MIN_PHOTOS) {
      return setErr(`Envie no mínimo ${MIN_PHOTOS} fotos desta peça (${files.length} selecionada${files.length === 1 ? '' : 's'} até agora).`)
    }
    setErr('')
    if (!window.confirm('Tem certeza que deseja anunciar esta peça?')) return
    mutation.mutate(files)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white w-full md:max-w-lg md:rounded-2xl rounded-t-2xl p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-bold text-gray-900">Tirar/enviar foto da peça</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>

        <p className="text-sm text-gray-500 mb-4">
          A esteira automática identifica a peça, pesquisa compatibilidade/preço e publica
          no Mercado Livre sozinha — sem revisão antes de publicar. Acompanhe no Relatório Diário.
        </p>
        <p className="text-sm font-medium text-orange-600 mb-4">
          Obrigatório: no mínimo {MIN_PHOTOS} fotos desta peça, de ângulos diferentes.
        </p>

        <form onSubmit={submit} className="space-y-4">
          <label className="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-gray-200 rounded-xl py-8 cursor-pointer hover:border-orange-400 transition-colors">
            <Camera size={28} className="text-gray-400" />
            <span className="text-sm text-gray-600">
              {files.length > 0
                ? `${files.length}/${MIN_PHOTOS} foto(s) selecionada(s)${files.length >= MIN_PHOTOS ? ' — pronto' : ''}`
                : 'Toque para tirar foto ou escolher da galeria'}
            </span>
            <input
              type="file" multiple accept="image/*" capture="environment"
              className="hidden"
              onChange={(e) => setFiles(Array.from(e.target.files || []))}
            />
          </label>

          {files.length > 0 && (
            <div className="grid grid-cols-4 gap-2">
              {files.map((f, i) => (
                <img key={i} src={URL.createObjectURL(f)} alt="" className="w-full aspect-square object-cover rounded-lg border border-gray-200" />
              ))}
            </div>
          )}

          {err && <p className="text-red-500 text-sm">{err}</p>}

          <button type="submit" disabled={mutation.isPending}
            className="w-full flex items-center justify-center gap-2 bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white py-3 rounded-lg font-medium transition-colors">
            {mutation.isPending ? <><Loader2 size={16} className="animate-spin" /> Enviando...</> : 'Enviar pra esteira automática'}
          </button>
        </form>
      </div>
    </div>
  )
}

const EMPTY = { title: '', code_internal: '', brand: '', condition: 'used', quantity: 1, sale_price: '', cost_price: '' }

function NewPartModal({ onClose }) {
  const [form, setForm] = useState(EMPTY)
  const [err, setErr] = useState('')
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: createPart,
    onSuccess: () => { qc.invalidateQueries(['parts']); onClose() },
    onError: e => setErr(e?.response?.data?.detail || 'Erro ao salvar'),
  })

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const submit = (e) => {
    e.preventDefault()
    if (!form.title.trim()) return setErr('Título obrigatório')
    setErr('')
    mutation.mutate({
      ...form,
      quantity: Number(form.quantity) || 0,
      sale_price: Number(form.sale_price) || 0,
      cost_price: Number(form.cost_price) || 0,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white w-full md:max-w-lg md:rounded-2xl rounded-t-2xl p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-bold text-gray-900">Nova peça</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Título *</label>
            <input value={form.title} onChange={e => set('title', e.target.value)}
              placeholder="Ex: Tampa Motor Fiat Uno 2010"
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Código interno</label>
              <input value={form.code_internal} onChange={e => set('code_internal', e.target.value)}
                placeholder="EST-001"
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Marca</label>
              <input value={form.brand} onChange={e => set('brand', e.target.value)}
                placeholder="Fiat"
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Estado</label>
              <select value={form.condition} onChange={e => set('condition', e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500">
                <option value="used">Usado</option>
                <option value="new">Novo</option>
                <option value="reconditioned">Recondicionado</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Quantidade</label>
              <input type="number" min="0" value={form.quantity} onChange={e => set('quantity', e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Preço de venda (R$)</label>
              <input type="number" step="0.01" min="0" value={form.sale_price} onChange={e => set('sale_price', e.target.value)}
                placeholder="0,00"
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Custo (R$)</label>
              <input type="number" step="0.01" min="0" value={form.cost_price} onChange={e => set('cost_price', e.target.value)}
                placeholder="0,00"
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
            </div>
          </div>

          {err && <p className="text-red-500 text-sm">{err}</p>}

          <button type="submit" disabled={mutation.isPending}
            className="w-full bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white py-3 rounded-lg font-medium transition-colors">
            {mutation.isPending ? 'Salvando...' : 'Salvar peça'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default function Parts() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('')
  const [showNew, setShowNew] = useState(false)
  const [showUpload, setShowUpload] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['parts', q],
    queryFn: () => getParts({ q: q || undefined, limit: 100 }),
  })

  const parts = data?.items ?? []

  return (
    <div className="p-4 md:p-8">
      {showNew && <NewPartModal onClose={() => setShowNew(false)} />}
      {showUpload && <PhotoUploadModal onClose={() => setShowUpload(false)} />}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Estoque</h2>
          <p className="text-gray-500 text-sm mt-1">{data?.total ?? 0} peças cadastradas</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowUpload(true)}
            className="flex items-center gap-2 bg-gray-900 hover:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            <Camera size={16} /> Tirar foto — anunciar sozinho
          </button>
          <button onClick={() => setShowNew(true)}
            className="flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            <Plus size={16} /> Nova peça
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-100">
          <form onSubmit={(e) => { e.preventDefault(); setQ(search) }} className="flex gap-2">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Buscar por código, título ou marca..."
                className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
              />
            </div>
            <button type="submit" className="px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-700 transition-colors">
              Buscar
            </button>
          </form>
        </div>

        {isLoading ? (
          <div className="p-12 text-center text-gray-400">Carregando...</div>
        ) : parts.length === 0 ? (
          <div className="p-12 text-center">
            <Package size={40} className="text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">Nenhuma peça encontrada</p>
            <p className="text-gray-400 text-sm mt-1">Importe do Mercado Livre ou cadastre manualmente</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3 text-left">Peça</th>
                <th className="px-4 py-3 text-left">Código</th>
                <th className="px-4 py-3 text-left">Estado</th>
                <th className="px-4 py-3 text-left">Plataformas</th>
                <th className="px-4 py-3 text-right">Estoque</th>
                <th className="px-4 py-3 text-right">Preço</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {parts.map(p => (
                <tr key={p.id} onClick={() => navigate(`/parts/${p.id}`)}
                  className={`hover:bg-gray-50 transition-colors cursor-pointer ${!p.has_listings ? 'bg-red-50/40' : ''}`}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      {p.photos?.[0] ? (
                        <img src={p.photos[0]} alt="" className="w-10 h-10 object-cover rounded-lg border border-gray-200 flex-shrink-0" />
                      ) : (
                        <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center flex-shrink-0">
                          <Package size={16} className="text-gray-400" />
                        </div>
                      )}
                      <span className="font-medium text-gray-900 line-clamp-1">{p.title}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-500 font-mono text-xs">{p.code_internal || p.code || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      p.condition === 'new' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                    }`}>
                      {p.condition === 'new' ? 'Novo' : p.condition === 'used' ? 'Usado' : 'Recondicionado'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {p.has_listings ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                        Anunciado
                      </span>
                    ) : p.status === 'draft' || p.status === 'processing' ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                        <Loader2 size={10} className="animate-spin" /> Na esteira automática
                      </span>
                    ) : p.status === 'error' ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                        Erro na esteira — ver relatório
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                        <WifiOff size={10} /> Sem anúncio
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={`font-medium ${p.quantity <= (p.min_quantity ?? 1) ? 'text-red-600' : 'text-gray-900'}`}>
                      {p.quantity}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-gray-900">
                    {p.sale_price > 0 ? `R$ ${p.sale_price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
