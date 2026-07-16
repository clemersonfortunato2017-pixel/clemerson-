import { useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { acceptInvite } from '../api'

export default function AcceptInvite() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < 6) return setError('Senha precisa ter pelo menos 6 caracteres')
    if (password !== confirm) return setError('As senhas não coincidem')
    setLoading(true)
    try {
      const data = await acceptInvite({ token, password })
      localStorage.setItem('pitbox_token', data.access_token)
      localStorage.setItem('pitbox_user', JSON.stringify(data.user))
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Convite inválido ou já utilizado')
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <p className="text-gray-500 text-sm">Link de convite inválido.</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        <h1 className="text-xl font-bold text-gray-900 mb-1">🏁 Pitbox</h1>
        <p className="text-gray-500 text-sm mb-6">Você foi liberado — defina sua senha para entrar.</p>

        {error && <div className="mb-4 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}

        <form onSubmit={submit} className="space-y-3">
          <input
            type="password" placeholder="Crie sua senha" value={password}
            onChange={(e) => setPassword(e.target.value)} required minLength={6}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
          />
          <input
            type="password" placeholder="Confirme sua senha" value={confirm}
            onChange={(e) => setConfirm(e.target.value)} required minLength={6}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
          />
          <button
            type="submit" disabled={loading}
            className="w-full bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white font-medium rounded-lg px-3 py-2 text-sm transition-colors"
          >
            {loading ? 'Aguarde...' : 'Definir senha e entrar'}
          </button>
        </form>
      </div>
    </div>
  )
}
