import { useQuery } from '@tanstack/react-query'
import { BarChart2, TrendingUp, Package, AlertCircle } from 'lucide-react'
import { getAbcCurve } from '../api'
import { useNavigate } from 'react-router-dom'

function fmt(v) { return `R$ ${Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` }

const CURVE_COLORS = {
  A: { bg: 'bg-green-100', text: 'text-green-800', bar: 'bg-green-500', label: 'A — Alto giro' },
  B: { bg: 'bg-yellow-100', text: 'text-yellow-800', bar: 'bg-yellow-400', label: 'B — Médio giro' },
  C: { bg: 'bg-red-100', text: 'text-red-700', bar: 'bg-red-400', label: 'C — Baixo giro / parado' },
}

export default function AbcCurve() {
  const navigate = useNavigate()
  const { data: items = [], isLoading } = useQuery({ queryKey: ['abc'], queryFn: getAbcCurve })

  const maxSold = Math.max(...items.map(i => i.total_sold), 1)
  const totalA = items.filter(i => i.curve === 'A')
  const totalB = items.filter(i => i.curve === 'B')
  const totalC = items.filter(i => i.curve === 'C')

  const capitalC = totalC.reduce((s, i) => s + (i.sale_price || 0) * (i.stock || 0), 0)

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Curva ABC</h2>
        <p className="text-gray-500 text-sm mt-1">Análise de giro — quais peças vendem mais e quais estão paradas</p>
      </div>

      {/* Resumo */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          { curve: 'A', items: totalA, desc: '80% do faturamento', icon: TrendingUp },
          { curve: 'B', items: totalB, desc: '15% do faturamento', icon: BarChart2 },
          { curve: 'C', items: totalC, desc: `Capital parado: ${fmt(capitalC)}`, icon: AlertCircle },
        ].map(({ curve, items: its, desc, icon: Icon }) => (
          <div key={curve} className={`rounded-xl p-5 border ${CURVE_COLORS[curve].bg} border-opacity-50`}>
            <div className="flex items-center justify-between mb-2">
              <span className={`text-lg font-black ${CURVE_COLORS[curve].text}`}>{CURVE_COLORS[curve].label}</span>
              <Icon size={20} className={CURVE_COLORS[curve].text} />
            </div>
            <p className={`text-3xl font-bold ${CURVE_COLORS[curve].text}`}>{its.length}</p>
            <p className={`text-xs mt-1 ${CURVE_COLORS[curve].text} opacity-70`}>{desc}</p>
          </div>
        ))}
      </div>

      {/* Tabela */}
      {isLoading
        ? <p className="text-gray-400 text-center py-16">Carregando...</p>
        : (
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide w-8">#</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Peça</th>
                  <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide w-12">Curva</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Vendido</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Qtd</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Estoque</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Margem</th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide w-32">Giro</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {items.map((item, idx) => (
                  <tr key={item.id} onClick={() => navigate(`/parts/${item.id}`)}
                    className="hover:bg-gray-50 cursor-pointer transition-colors">
                    <td className="px-4 py-3 text-xs text-gray-400">{idx + 1}</td>
                    <td className="px-4 py-3">
                      <p className="font-medium text-gray-900 truncate max-w-xs">{item.title}</p>
                      {item.code && <p className="text-xs text-gray-400 font-mono">{item.code}</p>}
                    </td>
                    <td className="px-3 py-3 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${CURVE_COLORS[item.curve].bg} ${CURVE_COLORS[item.curve].text}`}>
                        {item.curve}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-gray-900">{fmt(item.total_sold)}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{item.units_sold}</td>
                    <td className={`px-4 py-3 text-right font-medium ${item.stock <= 0 ? 'text-red-500' : 'text-gray-600'}`}>{item.stock}</td>
                    <td className="px-4 py-3 text-right">
                      {item.margin_percent > 0
                        ? <span className="text-green-600 font-medium">{item.margin_percent?.toFixed(1)}%</span>
                        : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="w-full bg-gray-100 rounded-full h-1.5">
                        <div className={`h-1.5 rounded-full ${CURVE_COLORS[item.curve].bar}`}
                          style={{ width: `${Math.min(100, (item.total_sold / maxSold) * 100)}%` }} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      }
    </div>
  )
}
