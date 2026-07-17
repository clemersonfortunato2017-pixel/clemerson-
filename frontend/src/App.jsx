import { useState } from 'react'
import { Routes, Route, Navigate, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Package, LayoutDashboard, Download, DollarSign, Search, Car, ShoppingCart, BarChart2, Menu, X, Camera, Users, LogOut, PlusSquare } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import Parts from './pages/Parts'
import Import from './pages/Import'
import Financial from './pages/Financial'
import QuickSearch from './pages/QuickSearch'
import PartDetail from './pages/PartDetail'
import VehicleSearch from './pages/VehicleSearch'
import PDV from './pages/PDV'
import AbcCurve from './pages/AbcCurve'
import Login from './pages/Login'
import PendingUsers from './pages/PendingUsers'
import DailyReport from './pages/DailyReport'
import AcceptInvite from './pages/AcceptInvite'
import InstallApp from './pages/InstallApp'
import { getPendingUsers } from './api'

const PUBLIC_PATHS = ['/login', '/aceitar-convite']

export default function App() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const isPublicPage = PUBLIC_PATHS.includes(location.pathname)
  const token = localStorage.getItem('pitbox_token')
  const user = JSON.parse(localStorage.getItem('pitbox_user') || 'null')
  const isAdmin = user?.role === 'admin'

  const { data: pending = [] } = useQuery({
    queryKey: ['pending-users'],
    queryFn: getPendingUsers,
    enabled: isAdmin && !isPublicPage,
    refetchInterval: 20000,
  })

  const logout = () => {
    localStorage.removeItem('pitbox_token')
    localStorage.removeItem('pitbox_user')
    navigate('/login')
  }

  if (isPublicPage) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/aceitar-convite" element={<AcceptInvite />} />
      </Routes>
    )
  }

  if (!token) return <Navigate to="/login" replace />

  const nav = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/pdv', icon: ShoppingCart, label: 'PDV' },
    { to: '/parts', icon: Package, label: 'Estoque' },
    { to: '/relatorio-diario', icon: Camera, label: 'Esteira automática' },
    { to: '/search', icon: Search, label: 'Busca Rápida' },
    { to: '/vehicle', icon: Car, label: 'Por Veículo' },
    { to: '/financial', icon: DollarSign, label: 'Financeiro' },
    { to: '/abc', icon: BarChart2, label: 'Curva ABC' },
    { to: '/import', icon: Download, label: 'Importar' },
    { to: '/instalar', icon: PlusSquare, label: 'Instalar app' },
    ...(isAdmin ? [{ to: '/usuarios-pendentes', icon: Users, label: 'Usuários', badge: pending.length }] : []),
  ]

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar desktop */}
      <aside className="hidden md:flex w-56 bg-gray-900 flex-col">
        <div className="px-6 py-5 border-b border-gray-800">
          <h1 className="text-white text-xl font-bold tracking-tight">🏁 Pitbox</h1>
          <p className="text-gray-400 text-xs mt-0.5">Gestão de Autopeças</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {nav.map(({ to, icon: Icon, label, badge }) => (
            <NavLink key={to} to={to} end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive ? 'bg-orange-500 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`
              }>
              <Icon size={16} /><span className="flex-1">{label}</span>
              {!!badge && <span className="bg-red-500 text-white text-[10px] font-bold rounded-full px-1.5 py-0.5">{badge}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-gray-800">
          <p className="text-gray-500 text-xs mb-2">{user?.name || 'Fortunato Auto Parts'}</p>
          <button onClick={logout} className="flex items-center gap-2 text-gray-400 hover:text-white text-xs">
            <LogOut size={13} /> Sair
          </button>
        </div>
      </aside>

      {/* Mobile layout */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top bar mobile */}
        <header className="md:hidden flex items-center justify-between bg-gray-900 px-4 py-3">
          <div>
            <h1 className="text-white text-lg font-bold">🏁 Pitbox</h1>
          </div>
          <button onClick={() => setOpen(true)} className="text-white">
            <Menu size={24} />
          </button>
        </header>

        {/* Drawer mobile */}
        {open && (
          <div className="fixed inset-0 z-50 flex">
            <div className="w-64 bg-gray-900 flex flex-col h-full">
              <div className="px-6 py-5 border-b border-gray-800 flex items-center justify-between">
                <div>
                  <h1 className="text-white text-xl font-bold">🏁 Pitbox</h1>
                  <p className="text-gray-400 text-xs mt-0.5">Gestão de Autopeças</p>
                </div>
                <button onClick={() => setOpen(false)} className="text-gray-400">
                  <X size={20} />
                </button>
              </div>
              <nav className="flex-1 px-3 py-4 space-y-1">
                {nav.map(({ to, icon: Icon, label, badge }) => (
                  <NavLink key={to} to={to} end={to === '/'}
                    onClick={() => setOpen(false)}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                        isActive ? 'bg-orange-500 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'
                      }`
                    }>
                    <Icon size={16} /><span className="flex-1">{label}</span>
                    {!!badge && <span className="bg-red-500 text-white text-[10px] font-bold rounded-full px-1.5 py-0.5">{badge}</span>}
                  </NavLink>
                ))}
              </nav>
              <div className="px-4 py-3 border-t border-gray-800">
                <p className="text-gray-500 text-xs mb-2">{user?.name || 'Fortunato Auto Parts'}</p>
                <button onClick={logout} className="flex items-center gap-2 text-gray-400 hover:text-white text-xs">
                  <LogOut size={13} /> Sair
                </button>
              </div>
            </div>
            <div className="flex-1 bg-black bg-opacity-50" onClick={() => setOpen(false)} />
          </div>
        )}

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
            <Route path="/instalar" element={<InstallApp />} />
            <Route path="/relatorio-diario" element={<DailyReport />} />
            <Route path="/usuarios-pendentes" element={<PendingUsers />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
