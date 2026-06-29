import { useQuery } from '@tanstack/react-query'
import { Package, AlertTriangle, TrendingUp, ShoppingBag } from 'lucide-react'
import { getParts } from '../api'

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex items-center gap-4">
      <div className={`p-3 rounded-lg ${color}`}>
        <Icon size={20} className="text-white" />
      </div>
      <div>
        <p className="text-sm text-gray-500">{label}</p>
        <p className="text-2xl font-bold text-gray-900">{value ?? '—'}</p>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { data: all } = useQuery({ queryKey: ['parts'], queryFn: () => getParts({ limit: 1000 }) })
  const { data: lowStock } = useQuery({ queryKey: ['parts-low'], queryFn: () => getParts({ low_stock: true, limit: 1000 }) })

  const total = all?.total ?? 0
  const low = lowStock?.total ?? 0
  const items = all?.items ?? []
  const totalValue = items.reduce((acc, p) => acc + (p.sale_price * p.quantity), 0)

  return (
    <div className="p-8">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <p className="text-gray-500 text-sm mt-1">Visão geral do estoque</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard icon={Package} label="Total de peças" value={total} color="bg-blue-500" />
        <StatCard icon={AlertTriangle} label="Estoque baixo" value={low} color="bg-red-500" />
        <StatCard icon={TrendingUp} label="Valor em estoque" value={`R$ ${totalValue.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`} color="bg-green-500" />
        <StatCard icon={ShoppingBag} label="Marketplaces" value="ML" color="bg-orange-500" />
      </div>

      {low > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-5">
          <h3 className="font-semibold text-red-800 mb-3 flex items-center gap-2">
            <AlertTriangle size={16} /> Peças com estoque baixo
          </h3>
          <div className="space-y-2">
            {lowStock?.items?.slice(0, 5).map(p => (
              <div key={p.id} className="flex justify-between text-sm">
                <span className="text-gray-700">{p.title}</span>
                <span className="font-medium text-red-600">{p.quantity} un.</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
