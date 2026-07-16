import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getPendingUsers, approveUser, rejectUser } from '../api'
import { UserCheck, UserX, Clock } from 'lucide-react'

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
      <h1 className="text-lg font-bold text-gray-900 mb-1">Usuários pendentes</h1>
      <p className="text-gray-500 text-sm mb-6">
        Só você (administrador) pode liberar acesso de novas pessoas ao Pitbox.
      </p>

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
