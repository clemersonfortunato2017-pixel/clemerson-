import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Package } from 'lucide-react'
import { getParts } from '../api'
import { useNavigate } from 'react-router-dom'

export default function QuickSearch() {
  const [input, setInput] = useState('')
  const navigate = useNavigate()

  const { data, isFetching } = useQuery({
    queryKey: ['quick-search', input],
    queryFn: () => getParts({ q: input, limit: 30 }),
    enabled: input.length >= 2,
  })

  const parts = data?.items ?? []

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Busca Rápida</h2>
        <p className="text-gray-500 text-sm mt-1">Digite 2 ou mais letras para buscar</p>
      </div>

      <div className="relative max-w-xl mb-8">
        <Search size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          autoFocus
          value={input}
          onChange={e => setInput(e.target.value)}
          maxLength={60}
          placeholder="Ex: altern, radiado, amortec..."
          className="w-full pl-12 pr-4 py-3 text-lg border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-500 bg-white"
        />
        {isFetching && (
          <span className="absolute right-4 top-1/2 -translate-y-1/2 text-xs text-gray-400">buscando...</span>
        )}
      </div>

      {input.length >= 2 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {parts.length === 0 && !isFetching && (
            <div className="col-span-3 text-center py-16 text-gray-400">
              <Package size={40} className="mx-auto mb-3 text-gray-300" />
              Nenhuma peça encontrada para "{input}"
            </div>
          )}
          {parts.map(p => (
            <div
              key={p.id}
              onClick={() => navigate(`/parts/${p.id}`)}
              className="bg-white border border-gray-200 rounded-xl p-4 cursor-pointer hover:border-orange-300 hover:shadow-sm transition-all"
            >
              <div className="flex gap-3">
                {p.photos?.[0] ? (
                  <img src={p.photos[0]} alt="" className="w-16 h-16 object-cover rounded-lg border border-gray-100 flex-shrink-0" />
                ) : (
                  <div className="w-16 h-16 bg-gray-100 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Package size={20} className="text-gray-300" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 text-sm line-clamp-2">{p.title}</p>
                  <p className="text-xs text-gray-400 font-mono mt-1">{p.code}</p>
                  <div className="flex items-center justify-between mt-2">
                    <span className={`text-xs font-medium ${p.quantity > 0 ? 'text-green-600' : 'text-red-500'}`}>
                      {p.quantity > 0 ? `${p.quantity} em estoque` : 'Sem estoque'}
                    </span>
                    <span className="text-sm font-bold text-gray-900">
                      {p.sale_price > 0 ? `R$ ${p.sale_price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '—'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {input.length === 0 && (
        <div className="text-center py-20 text-gray-400">
          <Search size={48} className="mx-auto mb-4 text-gray-200" />
          <p>Comece a digitar o nome da peça</p>
        </div>
      )}
    </div>
  )
}
