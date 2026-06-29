import { Routes, Route, NavLink } from 'react-router-dom'
import { Package, LayoutDashboard, Download, DollarSign, Search, Car, ShoppingCart, BarChart2 } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import Parts from './pages/Parts'
import Import from './pages/Import'
import Financial from './pages/Financial'
import QuickSearch from './pages/QuickSearch'
import PartDetail from './pages/PartDetail'
import VehicleSearch from './pages/VehicleSearch'
import PDV from './pages/PDV'
import AbcCurve from './pages/AbcCurve'

const nav = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/pdv', icon: ShoppingCart, label: 'PDV' },
  { to: '/parts', icon: Package, label: 'Estoque' },
  { to: '/search', icon: Search, label: 'Busca Rápida' },
  { to: '/vehicle', icon: Car, label: 'Por Veículo' },
  { to: '/financial', icon: DollarSign, label: 'Financeiro' },
  { to: '/abc', icon: BarChart2, label: 'Curva ABC' },
  { to: '/import', icon: Download, label: 'Importar' },
]

export default function App() {
  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-56 bg-gray-900 flex flex-col">
        <div className="px-6 py-5 border-b border-gray-800">
          <h1 className="text-white text-xl font-bold tracking-tight">🏁 Pitbox</h1>
          <p className="text-gray-400 text-xs mt-0.5">Gestão de Autopeças</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {nav.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive ? 'bg-orange-500 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`
              }>
              <Icon size={16} />{label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-gray-800">
          <p className="text-gray-500 text-xs">Fortunato Auto Parts</p>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/pdv" element={<PDV />} />
          <Route path="/parts" element={<Parts />} />
          <Route path="/parts/:id" element={<PartDetail />} />
          <Route path="/search" element={<QuickSearch />} />
          <Route path="/vehicle" element={<VehicleSearch />} />
          <Route path="/financial" element={<Financial />} />
          <Route path="/abc" element={<AbcCurve />} />
          <Route path="/import" element={<Import />} />
        </Routes>
      </main>
    </div>
  )
}
