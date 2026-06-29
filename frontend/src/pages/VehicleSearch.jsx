import { useState } from 'react'
import { Car, Package, Search } from 'lucide-react'
import { searchByVehicle } from '../api'
import { useNavigate } from 'react-router-dom'

export default function VehicleSearch() {
  const [brand, setBrand] = useState('')
  const [model, setModel] = useState('')
  const [year, setYear] = useState('')
  const [parts, setParts] = useState(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function handleSearch(e) {
    e.preventDefault()
    if (!brand || !model) return
    setLoading(true)
    try {
      const result = await searchByVehicle({ brand, model, year: year || undefined })
      setParts(result)
    } catch {
      setParts([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Busca por Veículo</h2>
        <p className="text-gray-500 text-sm mt-1">Encontre peças compatíveis com um veículo específico</p>
      </div>

      <form onSubmit={handleSearch} className="bg-white border border-gray-200 rounded-xl p-6 mb-8 max-w-2xl">
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Marca</label>
            <input value={brand} onChange={e => setBrand(e.target.value)}
              placeholder="Ex: Volkswagen"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Modelo</label>
            <input value={model} onChange={e => setModel(e.target.value)}
              placeholder="Ex: Gol"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Ano (opcional)</label>
            <input value={year} onChange={e => setYear(e.target.value)}
              placeholder="Ex: 2015" type="number" min="1990" max="2030"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
          </div>
        </div>
        <button type="submit" disabled={!brand || !model || loading}
          className="flex items-center gap-2 bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors">
          <Search size={15} />
          {loading ? 'Buscando...' : 'Buscar peças'}
        </button>
      </form>

      {parts !== null && (
        <div>
          <p className="text-sm text-gray-500 mb-4">
            {parts.length === 0 ? 'Nenhuma peça compatível encontrada em estoque' : `${parts.length} peça(s) compatível(is) em estoque`}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {parts.map(p => (
              <div key={p.id} onClick={() => navigate(`/parts/${p.id}`)}
                className="bg-white border border-gray-200 rounded-xl p-4 cursor-pointer hover:border-orange-300 transition-all">
                <div className="flex gap-3">
                  {p.photos?.[0] ? (
                    <img src={p.photos[0]} alt="" className="w-14 h-14 object-cover rounded-lg border border-gray-100 flex-shrink-0" />
                  ) : (
                    <div className="w-14 h-14 bg-gray-100 rounded-lg flex items-center justify-center flex-shrink-0">
                      <Package size={18} className="text-gray-300" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 text-sm line-clamp-2">{p.title}</p>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs text-green-600 font-medium">{p.quantity} un.</span>
                      <span className="text-sm font-bold text-gray-900">
                        R$ {p.sale_price?.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {parts === null && (
        <div className="text-center py-16 text-gray-400">
          <Car size={48} className="mx-auto mb-4 text-gray-200" />
          <p>Informe marca e modelo para buscar peças compatíveis</p>
        </div>
      )}
    </div>
  )
}
