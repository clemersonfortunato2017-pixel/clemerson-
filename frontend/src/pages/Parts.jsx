import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Search, Plus, Package, WifiOff } from 'lucide-react'
import { getParts } from '../api'

export default function Parts() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['parts', q],
    queryFn: () => getParts({ q: q || undefined, limit: 100 }),
  })

  const parts = data?.items ?? []

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Estoque</h2>
          <p className="text-gray-500 text-sm mt-1">{data?.total ?? 0} peças cadastradas</p>
        </div>
        <button className="flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
          <Plus size={16} /> Nova peça
        </button>
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
