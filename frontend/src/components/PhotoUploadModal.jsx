import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Camera, Loader2, X } from 'lucide-react'
import { uploadPhotos } from '../api'

export const MIN_PHOTOS = 4 // reduzido de 6 pra 4 em 2026-07-23 (Clemerson) — menos fotos = menos custo de IA na identificação

export default function PhotoUploadModal({ onClose }) {
  const [files, setFiles] = useState([])
  const [err, setErr] = useState('')
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: uploadPhotos,
    onSuccess: () => { qc.invalidateQueries(['parts']); setFiles([]); onClose() },
    onError: e => setErr(e?.response?.data?.detail || 'Erro ao enviar fotos'),
  })

  const submit = (e) => {
    e.preventDefault()
    if (files.length < MIN_PHOTOS) {
      return setErr(`Envie no mínimo ${MIN_PHOTOS} fotos desta peça (${files.length} selecionada${files.length === 1 ? '' : 's'} até agora).`)
    }
    setErr('')
    if (!window.confirm('Tem certeza que deseja anunciar esta peça?')) return
    mutation.mutate(files)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white w-full md:max-w-lg md:rounded-2xl rounded-t-2xl p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-bold text-gray-900">Tirar/enviar foto da peça</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>

        <p className="text-sm text-gray-500 mb-4">
          A esteira automática identifica a peça, pesquisa compatibilidade/preço e publica
          no Mercado Livre sozinha — sem revisão antes de publicar. Acompanhe no Relatório Diário.
        </p>
        <p className="text-sm font-medium text-orange-600 mb-4">
          Obrigatório: no mínimo {MIN_PHOTOS} fotos desta peça, de ângulos diferentes.
        </p>

        <form onSubmit={submit} className="space-y-4">
          <label className="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-gray-200 rounded-xl py-8 cursor-pointer hover:border-orange-400 transition-colors">
            <Camera size={28} className="text-gray-400" />
            <span className="text-sm text-gray-600">
              {files.length > 0
                ? `${files.length}/${MIN_PHOTOS} foto(s) selecionada(s)${files.length >= MIN_PHOTOS ? ' — pronto' : ''}`
                : 'Toque para tirar foto ou escolher da galeria'}
            </span>
            <input
              type="file" multiple accept="image/*" capture="environment"
              className="hidden"
              onChange={(e) => {
                // A câmera do celular abre uma foto por vez e o input troca o
                // FileList inteiro a cada captura — sem acumular aqui, cada
                // foto nova apagava a anterior.
                const novasFotos = Array.from(e.target.files || [])
                setFiles((atuais) => [...atuais, ...novasFotos])
                e.target.value = ''
              }}
            />
          </label>

          {files.length > 0 && (
            <div className="grid grid-cols-4 gap-2">
              {files.map((f, i) => (
                <img key={i} src={URL.createObjectURL(f)} alt="" className="w-full aspect-square object-cover rounded-lg border border-gray-200" />
              ))}
            </div>
          )}

          {err && <p className="text-red-500 text-sm">{err}</p>}

          <button type="submit" disabled={mutation.isPending}
            className="w-full flex items-center justify-center gap-2 bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white py-3 rounded-lg font-medium transition-colors">
            {mutation.isPending ? <><Loader2 size={16} className="animate-spin" /> Enviando...</> : 'Enviar pra esteira automática'}
          </button>
        </form>
      </div>
    </div>
  )
}
