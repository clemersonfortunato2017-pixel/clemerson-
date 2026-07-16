import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getPendingUsers, approveUser, rejectUser, inviteUser } from '../api'
import { UserCheck, UserX, Clock, UserPlus, Copy, Share2, Check } from 'lucide-react'

function InvitePanel() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [link, setLink] = useState('')
  const [copied, setCopied] = useState(false)
  const [err, setErr] = useState('')

  const mutation = useMutation({
    mutationFn: inviteUser,
    onSuccess: (data) => {
      setLink(`${window.location.origin}/aceitar-convite?token=${data.invite_token}`)
      setErr('')
    },
    onError: (e) => setErr(e?.response?.data?.detail || 'Erro ao liberar acesso'),
  })

  const submit = (e) => {
    e.preventDefault()
    if (!name.trim() || !email.trim()) return setErr('Preencha nome e e-mail')
    setErr('')
    setLink('')
    mutation.mutate({ name, email })
  }

  const copyLink = async () => {
    await navigator.clipboard.writeText(link)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const shareLink = async () => {
    if (navigator.share) {
      await navigator.share({ title: 'Acesso ao Pitbox', text: `${name}, aqui está seu acesso ao Pitbox — defina sua senha:`, url: link })
    } else {
      copyLink()
    }
  }

  const novoConvite = () => { setLink(''); setName(''); setEmail('') }

  return (
    <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm mb-6">
      <div className="flex items-center gap-2 mb-1">
        <UserPlus size={18} className="text-orange-500" />
        <h2 className="font-bold text-gray-900">Liberar acesso agora</h2>
      </div>
      <p className="text-gray-500 text-sm mb-4">
        Você libera na hora — a pessoa só precisa definir a própria senha pelo link. Ninguém entra sem passar por aqui.
      </p>

      {!link ? (
        <form onSubmit={submit} className="space-y-3">
          <input
            type="text" placeholder="Nome da pessoa" value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
          />
          <input
            type="email" placeholder="E-mail da pessoa" value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
          />
          {err && <p className="text-red-500 text-sm">{err}</p>}
          <button type="submit" disabled={mutation.isPending}
            className="w-full bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white font-medium rounded-lg px-3 py-2.5 text-sm transition-colors">
            {mutation.isPending ? 'Liberando...' : 'Liberar acesso agora'}
          </button>
        </form>
      ) : (
        <div className="space-y-3">
          <div className="bg-green-50 border border-green-100 rounded-lg px-4 py-3">
            <p className="text-green-800 text-sm font-medium">Acesso liberado para {name}.</p>
            <p className="text-green-700 text-xs mt-1">Manda esse link pra pessoa — ela só define a senha dela e já entra.</p>
          </div>
          <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
            <input readOnly value={link} className="flex-1 bg-transparent text-xs text-gray-600 outline-none" />
          </div>
          <div className="flex gap-2">
            <button onClick={shareLink}
              className="flex-1 flex items-center justify-center gap-2 bg-gray-900 hover:bg-gray-700 text-white text-sm font-medium py-2.5 rounded-lg">
              <Share2 size={14} /> Compartilhar
            </button>
            <button onClick={copyLink}
              className="flex-1 flex items-center justify-center gap-2 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-sm font-medium py-2.5 rounded-lg">
              {copied ? <Check size={14} className="text-green-600" /> : <Copy size={14} />} {copied ? 'Copiado' : 'Copiar link'}
            </button>
          </div>
          <button onClick={novoConvite} className="w-full text-center text-xs text-gray-500 hover:text-gray-700 pt-1">
            Liberar outra pessoa
          </button>
        </div>
      )}
    </div>
  )
}

export default function PendingUsers() {
  const qc = useQueryClient()
  // Polling curto = "tempo real" o suficiente pra aprovação do celular/PC sem precisar de push notification
  const { data: pending = [], isLoading } = useQuery({
    queryKey: ['pending-users'],
    queryFn: getPendingUsers,
    refetchInterval: 20000,
  })

  const handle = async (id, action) => {
    if (action === 'approve') await approveUser(id)
    else await rejectUser(id)
    qc.invalidateQueries({ queryKey: ['pending-users'] })
  }

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-lg font-bold text-gray-900 mb-1">Usuários</h1>
      <p className="text-gray-500 text-sm mb-6">
        Só você (administrador) pode liberar acesso de novas pessoas ao Pitbox.
      </p>

      <InvitePanel />

      <h2 className="font-bold text-gray-900 mb-3 text-sm">Cadastros pendentes (auto-registro)</h2>

      {isLoading && <p className="text-gray-400 text-sm">Carregando...</p>}

      {!isLoading && pending.length === 0 && (
        <div className="text-gray-400 text-sm bg-white border border-gray-100 rounded-xl p-6 text-center">
          Nenhuma solicitação pendente.
        </div>
      )}

      <div className="space-y-2">
        {pending.map((u) => (
          <div key={u.id} className="flex items-center justify-between bg-white border border-gray-100 rounded-xl px-4 py-3 shadow-sm">
            <div>
              <p className="font-medium text-gray-900 text-sm">{u.name}</p>
              <p className="text-gray-500 text-xs">{u.email}</p>
              <p className="text-gray-400 text-xs flex items-center gap-1 mt-0.5">
                <Clock size={11} /> pedido em {new Date(u.created_at).toLocaleString('pt-BR')}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handle(u.id, 'approve')}
                className="flex items-center gap-1 bg-green-500 hover:bg-green-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg"
              >
                <UserCheck size={14} /> Aprovar
              </button>
              <button
                onClick={() => handle(u.id, 'reject')}
                className="flex items-center gap-1 bg-red-50 hover:bg-red-100 text-red-600 text-xs font-medium px-3 py-1.5 rounded-lg"
              >
                <UserX size={14} /> Recusar
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
