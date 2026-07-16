import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register } from '../api'

export default function Login() {
  const [mode, setMode] = useState('login') // login | register
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setInfo('')
    setLoading(true)
    try {
      if (mode === 'login') {
        const data = await login({ email, password })
        localStorage.setItem('pitbox_token', data.access_token)
        localStorage.setItem('pitbox_user', JSON.stringify(data.user))
        navigate('/')
      } else {
        await register({ name, email, password })
        setInfo('Cadastro enviado. Aguarde o administrador aprovar seu acesso.')
        setMode('login')
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao processar')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        <h1 className="text-xl font-bold text-gray-900 mb-1">🏁 Pitbox</h1>
        <p className="text-gray-500 text-sm mb-6">
          {mode === 'login' ? 'Entrar na sua conta' : 'Solicitar acesso'}
        </p>

        {error && <div className="mb-4 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}
        {info && <div className="mb-4 text-sm text-green-700 bg-green-50 rounded-lg px-3 py-2">{info}</div>}

        <form onSubmit={handleSubmit} className="space-y-3">
          {mode === 'register' && (
            <input
              type="text" placeholder="Nome completo" value={name}
              onChange={(e) => setName(e.target.value)} required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
            />
          )}
          <input
            type="email" placeholder="E-mail" value={email}
            onChange={(e) => setEmail(e.target.value)} required
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
          />
          <input
            type="password" placeholder="Senha" value={password}
            onChange={(e) => setPassword(e.target.value)} required minLength={6}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
          />
          <button
            type="submit" disabled={loading}
            className="w-full bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white font-medium rounded-lg px-3 py-2 text-sm transition-colors"
          >
            {loading ? 'Aguarde...' : mode === 'login' ? 'Entrar' : 'Solicitar acesso'}
          </button>
        </form>

        <button
          onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); setInfo('') }}
          className="w-full text-center text-xs text-gray-500 hover:text-gray-700 mt-4"
        >
          {mode === 'login' ? 'Não tem acesso? Solicitar cadastro' : 'Já tem conta? Entrar'}
        </button>
      </div>
    </div>
  )
}
