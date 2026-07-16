import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getDailyReport } from '../api'
import { CheckCircle2, XCircle, Calendar } from 'lucide-react'

const todayStr = () => new Date().toISOString().slice(0, 10)

export default function DailyReport() {
  const [date, setDate] = useState(todayStr())
  const { data, isLoading } = useQuery({
    queryKey: ['daily-report', date],
    queryFn: () => getDailyReport(date),
  })

  return (
    <div className="p-6 max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-bold text-gray-900">Relatório diário — esteira automática</h1>
          <p className="text-gray-500 text-sm">O que foi identificado, pesquisado e publicado sozinho no Mercado Livre.</p>
        </div>
        <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-lg px-3 py-1.5">
          <Calendar size={14} className="text-gray-400" />
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="text-sm outline-none" />
        </div>
      </div>

      {isLoading && <p className="text-gray-400 text-sm">Carregando...</p>}

      {data && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-white border border-gray-100 rounded-xl p-4">
              <p className="text-xs text-gray-500">Publicados</p>
              <p className="text-2xl font-bold text-gray-900">{data.published_count}</p>
            </div>
            <div className="bg-white border border-gray-100 rounded-xl p-4">
              <p className="text-xs text-gray-500">Valor total</p>
              <p className="text-2xl font-bold text-green-600">
                {data.total_value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
              </p>
            </div>
            <div className="bg-white border border-gray-100 rounded-xl p-4">
              <p className="text-xs text-gray-500">Erros (não publicados)</p>
              <p className="text-2xl font-bold text-red-500">{data.error_count}</p>
            </div>
          </div>

          <h2 className="text-sm font-semibold text-gray-700 mb-2">Publicados</h2>
          <div className="space-y-2 mb-6">
            {data.published.map((p, i) => (
              <a key={i} href={p.url} target="_blank" rel="noreferrer"
                className="flex items-center justify-between bg-white border border-gray-100 rounded-lg px-4 py-2.5 hover:border-orange-300 transition-colors">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-green-500" />
                  <span className="text-sm text-gray-800">{p.title}</span>
                </div>
                <span className="text-sm font-medium text-gray-900">
                  {(p.price || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                </span>
              </a>
            ))}
            {data.published.length === 0 && <p className="text-gray-400 text-sm">Nenhum anúncio publicado neste dia.</p>}
          </div>

          <h2 className="text-sm font-semibold text-gray-700 mb-2">Erros — precisam de atenção</h2>
          <div className="space-y-2">
            {data.errors.map((e, i) => (
              <div key={i} className="bg-red-50 border border-red-100 rounded-lg px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <XCircle size={16} className="text-red-500" />
                  <span className="text-sm text-gray-800">{e.title}</span>
                </div>
                <pre className="text-xs text-red-700 mt-1 whitespace-pre-wrap">{JSON.stringify(e.log, null, 2)}</pre>
              </div>
            ))}
            {data.errors.length === 0 && <p className="text-gray-400 text-sm">Nenhum erro neste dia.</p>}
          </div>
        </>
      )}
    </div>
  )
}
