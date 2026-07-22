import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { DollarSign, ShoppingBag, TrendingUp, Plus, X, TrendingDown, Calendar } from 'lucide-react'
import { getMonthlyFinancial, getDailyFinancial, createSale, getParts } from '../api'

const PLATFORM_LABELS = { mercadolivre: 'Mercado Livre', shopee: 'Shopee', amazon: 'Amazon', balcao: 'Balcão' }
const PLATFORM_COLORS = {
  mercadolivre: 'bg-yellow-100 text-yellow-800',
  shopee: 'bg-orange-100 text-orange-800',
  amazon: 'bg-blue-100 text-blue-800',
  balcao: 'bg-green-100 text-green-800',
}

function fmt(v) { return `R$ ${Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` }

export default function Financial() {
  const now = new Date()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year, setYear] = useState(now.getFullYear())
  const [showSale, setShowSale] = useState(false)
  const [saleForm, setSaleForm] = useState({ platform: 'balcao', payment_method: 'dinheiro', buyer_name: '', items: [{ part_id: '', quantity: 1, unit_price: '' }] })
  const [partSearch, setPartSearch] = useState('')
  const qc = useQueryClient()

  const { data: fin, isError: finError, isFetching: finFetching } = useQuery({
    queryKey: ['financial', month, year],
    queryFn: () => getMonthlyFinancial({ month, year }),
    retry: 3,
  })

  const { data: daily, isError: dailyError } = useQuery({
    queryKey: ['financial-daily', month, year],
    queryFn: () => getDailyFinancial({ month, year }),
    retry: 3,
  })

  const { data: partsData } = useQuery({
    queryKey: ['parts-sale', partSearch],
    queryFn: () => getParts({ q: partSearch || undefined, limit: 20 }),
    enabled: partSearch.length >= 2,
  })

  const saleMut = useMutation({
    mutationFn: createSale,
    onSuccess: () => {
      qc.invalidateQueries(['financial'])
      setShowSale(false)
      setSaleForm({ platform: 'balcao', payment_method: 'dinheiro', buyer_name: '', items: [{ part_id: '', quantity: 1, unit_price: '' }] })
    },
  })

  const months = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
  const platforms = ['mercadolivre', 'shopee', 'amazon', 'balcao']

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Financeiro</h2>
          <p className="text-gray-500 text-sm mt-1">Resultado de vendas por plataforma</p>
        </div>
        <button onClick={() => setShowSale(true)}
          className="flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
          <Plus size={16} /> Venda em balcão
        </button>
      </div>

      {/* Seletor de período */}
      <div className="flex gap-3 mb-6 flex-wrap">
        {months.map((m, i) => (
          <button key={i} onClick={() => setMonth(i + 1)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${month === i + 1 ? 'bg-orange-500 text-white' : 'bg-white border border-gray-200 text-gray-600 hover:border-orange-300'}`}>
            {m}
          </button>
        ))}
        <input type="number" value={year} onChange={e => setYear(Number(e.target.value))} min="2024" max="2030"
          className="w-20 border border-gray-200 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
      </div>

      {(finError || dailyError) && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          Não consegui carregar os dados financeiros agora (o servidor pode estar reiniciando após uma atualização).
          Os valores abaixo podem estar incompletos — {finFetching ? 'tentando de novo automaticamente...' : 'recarregue a página em alguns segundos.'}
        </div>
      )}

      {/* Cards de totais globais */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-gray-900 rounded-xl p-5 flex items-center justify-between">
          <div>
            <p className="text-gray-400 text-xs">Faturamento bruto</p>
            <p className="text-white text-2xl font-bold mt-1">{fmt(fin?.total)}</p>
          </div>
          <TrendingUp size={32} className="text-orange-500 opacity-60" />
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-5 flex items-center justify-between">
          <div>
            <p className="text-gray-500 text-xs">Líquido (após taxas)</p>
            <p className="text-gray-900 text-2xl font-bold mt-1">{fmt(fin?.net_total)}</p>
          </div>
          <DollarSign size={32} className="text-blue-400 opacity-60" />
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-5 flex items-center justify-between">
          <div>
            <p className="text-gray-500 text-xs">Lucro bruto estimado</p>
            <p className={`text-2xl font-bold mt-1 ${(fin?.profit || 0) >= 0 ? 'text-green-600' : 'text-red-500'}`}>{fmt(fin?.profit)}</p>
          </div>
          <TrendingDown size={32} className="text-green-400 opacity-60" />
        </div>
      </div>

      {/* Por plataforma */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {platforms.map(p => (
          <div key={p} className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${PLATFORM_COLORS[p]}`}>
                {PLATFORM_LABELS[p]}
              </span>
              <ShoppingBag size={16} className="text-gray-300" />
            </div>
            <p className="text-2xl font-bold text-gray-900">{fmt(fin?.[p]?.total)}</p>
            <p className="text-xs text-gray-400 mt-1">{fin?.[p]?.count || 0} venda(s)</p>
            {(fin?.[p]?.fees || 0) > 0 && (
              <p className="text-xs text-red-400 mt-0.5">- {fmt(fin?.[p]?.fees)} em taxas</p>
            )}
            {(fin?.[p]?.profit || 0) > 0 && (
              <p className="text-xs text-green-600 mt-0.5">Lucro: {fmt(fin?.[p]?.profit)}</p>
            )}
          </div>
        ))}
      </div>

      {/* Vendas por dia */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 mb-8">
        <div className="flex items-center gap-2 mb-4">
          <Calendar size={16} className="text-gray-400" />
          <h3 className="text-sm font-semibold text-gray-900">Vendas por dia — {months[month - 1]}/{year}</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-400 text-xs border-b border-gray-100">
                <th className="py-2 font-medium">Dia</th>
                <th className="py-2 font-medium">Faturamento</th>
                <th className="py-2 font-medium">Líquido</th>
                <th className="py-2 font-medium">Lucro</th>
                <th className="py-2 font-medium">Vendas</th>
              </tr>
            </thead>
            <tbody>
              {daily?.days?.map(d => {
                const isToday = d.day === now.getDate() && month === now.getMonth() + 1 && year === now.getFullYear()
                return (
                  <tr key={d.day} className={`border-b border-gray-50 ${isToday ? 'bg-orange-50' : d.total > 0 ? '' : 'text-gray-300'}`}>
                    <td className="py-2 font-medium text-gray-700">
                      {String(d.day).padStart(2, '0')}
                      {isToday && <span className="ml-2 text-[10px] text-orange-500 font-semibold">HOJE</span>}
                    </td>
                    <td className="py-2">{fmt(d.total)}</td>
                    <td className="py-2 text-gray-500">{fmt(d.net)}</td>
                    <td className={`py-2 ${d.profit >= 0 ? 'text-green-600' : 'text-red-500'}`}>{fmt(d.profit)}</td>
                    <td className="py-2 text-gray-500">{d.count}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal venda balcão */}
      {showSale && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg shadow-xl">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-bold text-gray-900">Registrar venda</h3>
              <button onClick={() => setShowSale(false)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Plataforma</label>
                  <select value={saleForm.platform} onChange={e => setSaleForm(f => ({ ...f, platform: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                    {platforms.map(p => <option key={p} value={p}>{PLATFORM_LABELS[p]}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Pagamento</label>
                  <select value={saleForm.payment_method} onChange={e => setSaleForm(f => ({ ...f, payment_method: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                    {[['dinheiro','Dinheiro'],['pix','Pix'],['cartao_debito','Débito'],['cartao_credito','Crédito'],['boleto','Boleto'],['prazo','A prazo']].map(([v,l]) =>
                      <option key={v} value={v}>{l}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Cliente (opcional)</label>
                <input value={saleForm.buyer_name} onChange={e => setSaleForm(f => ({ ...f, buyer_name: e.target.value }))}
                  placeholder="Nome do cliente"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-2">Peças vendidas</label>
                {saleForm.items.map((item, idx) => (
                  <div key={idx} className="flex gap-2 mb-2">
                    <div className="flex-1 relative">
                      <input placeholder="Buscar peça..." value={partSearch}
                        onChange={e => setPartSearch(e.target.value)}
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
                      {partsData?.items?.length > 0 && !item.part_id && (
                        <div className="absolute top-full left-0 right-0 bg-white border border-gray-200 rounded-lg shadow mt-1 z-10 max-h-36 overflow-y-auto">
                          {partsData.items.map(p => (
                            <button key={p.id} onClick={() => {
                              setSaleForm(f => { const items = [...f.items]; items[idx] = { ...items[idx], part_id: p.id, unit_price: p.sale_price }; return { ...f, items } })
                              setPartSearch(p.title.slice(0, 30))
                            }} className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 flex justify-between">
                              <span className="truncate">{p.title}</span>
                              <span className="text-gray-400 ml-2 flex-shrink-0">R$ {p.sale_price?.toFixed(2)}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    <input type="number" min="1" value={item.quantity}
                      onChange={e => setSaleForm(f => { const items = [...f.items]; items[idx].quantity = Number(e.target.value); return { ...f, items } })}
                      className="w-16 border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none" />
                    <input type="number" step="0.01" value={item.unit_price}
                      onChange={e => setSaleForm(f => { const items = [...f.items]; items[idx].unit_price = e.target.value; return { ...f, items } })}
                      placeholder="Preço"
                      className="w-24 border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none" />
                  </div>
                ))}
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button onClick={() => saleMut.mutate({
                platform: saleForm.platform,
                payment_method: saleForm.payment_method,
                buyer_name: saleForm.buyer_name || null,
                items: saleForm.items.filter(i => i.part_id).map(i => ({ part_id: Number(i.part_id), quantity: Number(i.quantity), unit_price: Number(i.unit_price) }))
              })} disabled={saleMut.isPending}
                className="flex-1 bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white py-2.5 rounded-lg text-sm font-medium transition-colors">
                {saleMut.isPending ? 'Salvando...' : 'Confirmar venda'}
              </button>
              <button onClick={() => setShowSale(false)}
                className="px-4 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-500 hover:bg-gray-50">
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
