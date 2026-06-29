import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ShoppingCart, Search, Plus, Minus, Trash2, X, CheckCircle } from 'lucide-react'
import { getParts, createSale, getSimilarParts } from '../api'

const PLATFORM_LABELS = { mercadolivre: 'Mercado Livre', shopee: 'Shopee', amazon: 'Amazon', balcao: 'Balcão' }
const PAYMENT_LABELS = {
  dinheiro: 'Dinheiro', pix: 'Pix', cartao_debito: 'Débito', cartao_credito: 'Crédito', boleto: 'Boleto', prazo: 'A prazo'
}
const PAYMENT_FEES = { dinheiro: 0, pix: 0, cartao_debito: 1.49, cartao_credito: 3.49, boleto: 2.0, prazo: 0 }
const PLATFORM_FEES = { mercadolivre: 14, shopee: 12, amazon: 15, balcao: 0 }

function fmt(v) { return `R$ ${Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` }

export default function PDV() {
  const [q, setQ] = useState('')
  const [cart, setCart] = useState([])
  const [platform, setPlatform] = useState('balcao')
  const [paymentMethod, setPaymentMethod] = useState('dinheiro')
  const [buyerName, setBuyerName] = useState('')
  const [buyerPhone, setBuyerPhone] = useState('')
  const [success, setSuccess] = useState(false)
  const [similarFor, setSimilarFor] = useState(null)
  const qc = useQueryClient()

  const { data } = useQuery({
    queryKey: ['pdv-search', q],
    queryFn: () => getParts({ q, limit: 10 }),
    enabled: q.length >= 2,
  })

  const { data: similars } = useQuery({
    queryKey: ['similar', similarFor?.id],
    queryFn: () => getSimilarParts(similarFor?.id),
    enabled: !!similarFor,
  })

  const saleMut = useMutation({
    mutationFn: createSale,
    onSuccess: () => {
      qc.invalidateQueries(['financial'])
      qc.invalidateQueries(['parts'])
      setCart([])
      setQ('')
      setBuyerName('')
      setBuyerPhone('')
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    },
  })

  function addToCart(part) {
    setCart(c => {
      const ex = c.find(i => i.part_id === part.id)
      if (ex) return c.map(i => i.part_id === part.id ? { ...i, qty: i.qty + 1 } : i)
      return [...c, { part_id: part.id, title: part.title, price: part.sale_price, cost: part.cost_price, qty: 1, max: part.quantity }]
    })
    setQ('')
    setSimilarFor(null)
  }

  function updateQty(part_id, delta) {
    setCart(c => c.map(i => i.part_id === part_id ? { ...i, qty: Math.max(1, Math.min(i.qty + delta, i.max)) } : i))
  }

  function removeItem(part_id) {
    setCart(c => c.filter(i => i.part_id !== part_id))
  }

  const subtotal = cart.reduce((s, i) => s + i.price * i.qty, 0)
  const platformFeePct = PLATFORM_FEES[platform] || 0
  const paymentFeePct = PAYMENT_FEES[paymentMethod] || 0
  const totalFeePct = platformFeePct + paymentFeePct
  const feeValue = subtotal * totalFeePct / 100
  const netTotal = subtotal - feeValue
  const costTotal = cart.reduce((s, i) => s + (i.cost || 0) * i.qty, 0)
  const profit = netTotal - costTotal

  function handleSell() {
    if (!cart.length) return
    saleMut.mutate({
      platform,
      payment_method: paymentMethod,
      buyer_name: buyerName || null,
      buyer_phone: buyerPhone || null,
      items: cart.map(i => ({ part_id: i.part_id, quantity: i.qty, unit_price: i.price })),
    })
  }

  const results = data?.items ?? []
  const outOfStock = results.filter(p => p.quantity <= 0)
  const inStock = results.filter(p => p.quantity > 0)

  return (
    <div className="p-6 flex gap-6 h-full">
      {/* Lado esquerdo: busca + resultados */}
      <div className="flex-1 flex flex-col gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-1">PDV — Venda Rápida</h2>
          <p className="text-gray-500 text-sm">Busque peças e monte o carrinho</p>
        </div>

        <div className="relative">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input autoFocus value={q} onChange={e => setQ(e.target.value)}
            placeholder="Buscar peça por nome ou código..."
            className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-500 bg-white text-sm" />
        </div>

        {/* Resultados em estoque */}
        {inStock.length > 0 && (
          <div className="space-y-2">
            {inStock.map(p => (
              <div key={p.id} className="bg-white border border-gray-200 rounded-xl p-3 flex items-center gap-3 hover:border-orange-300 transition-all cursor-pointer"
                onClick={() => addToCart(p)}>
                {p.photos?.[0]
                  ? <img src={p.photos[0]} alt="" className="w-12 h-12 object-cover rounded-lg border border-gray-100 flex-shrink-0" />
                  : <div className="w-12 h-12 bg-gray-100 rounded-lg flex-shrink-0" />}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{p.title}</p>
                  <p className="text-xs text-gray-400">{p.code_internal || p.code} · {p.quantity} em estoque</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-gray-900">{fmt(p.sale_price)}</p>
                  <button className="text-xs text-orange-500 mt-0.5">+ Add</button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Sem estoque — sugerir similares */}
        {outOfStock.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-red-500 uppercase tracking-wide">Sem estoque</p>
            {outOfStock.map(p => (
              <div key={p.id} className="bg-red-50 border border-red-100 rounded-xl p-3 flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-700 truncate">{p.title}</p>
                  <p className="text-xs text-red-400">0 unidades</p>
                </div>
                <button onClick={() => setSimilarFor(p)}
                  className="text-xs bg-orange-100 text-orange-600 px-3 py-1.5 rounded-lg hover:bg-orange-200 transition-colors whitespace-nowrap">
                  Ver similares
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Similares */}
        {similarFor && similars && (
          <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold text-orange-700">Similares para: {similarFor.title}</p>
              <button onClick={() => setSimilarFor(null)}><X size={14} className="text-orange-400" /></button>
            </div>
            {similars.length === 0
              ? <p className="text-xs text-orange-500">Nenhum similar em estoque.</p>
              : <div className="space-y-2">
                  {similars.map(p => (
                    <div key={p.id} onClick={() => addToCart(p)}
                      className="bg-white border border-orange-100 rounded-lg p-2 flex items-center gap-3 cursor-pointer hover:border-orange-300">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">{p.title}</p>
                        <p className="text-xs text-green-600">{p.quantity} em estoque</p>
                      </div>
                      <p className="text-sm font-bold">{fmt(p.sale_price)}</p>
                    </div>
                  ))}
                </div>
            }
          </div>
        )}

        {q.length >= 2 && inStock.length === 0 && outOfStock.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-8">Nenhuma peça encontrada</p>
        )}
      </div>

      {/* Lado direito: carrinho + finalizar */}
      <div className="w-80 flex flex-col gap-4">
        {success && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-3 flex items-center gap-2 text-green-700">
            <CheckCircle size={18} /> Venda registrada com sucesso!
          </div>
        )}

        {/* Plataforma e pagamento */}
        <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Plataforma</label>
            <select value={platform} onChange={e => setPlatform(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
              {Object.entries(PLATFORM_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Pagamento</label>
            <select value={paymentMethod} onChange={e => setPaymentMethod(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
              {Object.entries(PAYMENT_LABELS).map(([v, l]) => <option key={v} value={v}>{l} {PAYMENT_FEES[v] > 0 ? `(${PAYMENT_FEES[v]}%)` : ''}</option>)}
            </select>
          </div>
          <input value={buyerName} onChange={e => setBuyerName(e.target.value)}
            placeholder="Nome do cliente (opcional)"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
          <input value={buyerPhone} onChange={e => setBuyerPhone(e.target.value)}
            placeholder="Telefone (opcional)"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
        </div>

        {/* Carrinho */}
        <div className="bg-white border border-gray-200 rounded-xl p-4 flex-1">
          <div className="flex items-center gap-2 mb-3">
            <ShoppingCart size={16} className="text-gray-500" />
            <h3 className="font-semibold text-gray-900 text-sm">Carrinho ({cart.length})</h3>
          </div>
          {cart.length === 0
            ? <p className="text-xs text-gray-400 text-center py-6">Adicione peças pela busca</p>
            : <div className="space-y-3">
                {cart.map(item => (
                  <div key={item.part_id} className="flex items-center gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-gray-900 truncate">{item.title}</p>
                      <p className="text-xs text-gray-400">{fmt(item.price)} un.</p>
                    </div>
                    <div className="flex items-center gap-1">
                      <button onClick={() => updateQty(item.part_id, -1)} className="w-6 h-6 border border-gray-200 rounded flex items-center justify-center hover:bg-gray-50">
                        <Minus size={10} />
                      </button>
                      <span className="w-6 text-center text-xs font-medium">{item.qty}</span>
                      <button onClick={() => updateQty(item.part_id, 1)} className="w-6 h-6 border border-gray-200 rounded flex items-center justify-center hover:bg-gray-50">
                        <Plus size={10} />
                      </button>
                    </div>
                    <p className="text-xs font-bold w-16 text-right">{fmt(item.price * item.qty)}</p>
                    <button onClick={() => removeItem(item.part_id)} className="text-gray-300 hover:text-red-500">
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
              </div>
          }
        </div>

        {/* Totais */}
        {cart.length > 0 && (
          <div className="bg-gray-900 rounded-xl p-4 space-y-2">
            <div className="flex justify-between text-gray-400 text-xs">
              <span>Subtotal</span><span>{fmt(subtotal)}</span>
            </div>
            {totalFeePct > 0 && (
              <div className="flex justify-between text-red-400 text-xs">
                <span>Taxas ({totalFeePct.toFixed(1)}%)</span><span>- {fmt(feeValue)}</span>
              </div>
            )}
            <div className="flex justify-between text-white font-bold text-sm border-t border-gray-700 pt-2">
              <span>Líquido</span><span>{fmt(netTotal)}</span>
            </div>
            <div className="flex justify-between text-green-400 text-xs">
              <span>Lucro estimado</span><span>{fmt(profit)}</span>
            </div>
            <button onClick={handleSell} disabled={saleMut.isPending}
              className="w-full bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white py-3 rounded-xl text-sm font-bold transition-colors mt-2">
              {saleMut.isPending ? 'Registrando...' : `Confirmar Venda ${fmt(subtotal)}`}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
