import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Package, Edit2, Check, X, Plus, Link, ShoppingBag, Globe, AlertTriangle } from 'lucide-react'
import { getPart, updatePart, adjustStock, getPartCompatibility, addCompatibility, removeCompatibility, searchVehicles, createVehicle, getSimilarParts, soldAtCounter, publishToAll } from '../api'

function fmt(v) { return v != null ? `R$ ${Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '—' }

function FI({ label, value, onChange, type = 'text', placeholder = '' }) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input type={type} value={value ?? ''} onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
    </div>
  )
}

function EditModal({ part, onSave, onClose, loading }) {
  const [form, setForm] = useState({
    title: part.title ?? '',
    sale_price: part.sale_price ?? '',
    cost_price: part.cost_price ?? '',
    code_internal: part.code_internal ?? '',
    code_oem: part.code_oem ?? '',
    code_manufacturer: part.code_manufacturer ?? '',
    min_quantity: part.min_quantity ?? 1,
    max_quantity: part.max_quantity ?? '',
    loc_corridor: part.loc_corridor ?? '',
    loc_shelf: part.loc_shelf ?? '',
    loc_box: part.loc_box ?? '',
    notes: part.notes ?? '',
  })
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">Editar peça</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700"><X size={20} /></button>
        </div>
        <div className="p-6 space-y-5">

          {/* Título */}
          <FI label="Título" value={form.title} onChange={v => set('title', v)} />

          {/* Preços */}
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Preços</p>
            <div className="grid grid-cols-2 gap-3">
              <FI label="Preço de venda (R$)" value={form.sale_price} onChange={v => set('sale_price', v)} type="number" placeholder="0.00" />
              <FI label="Custo (R$)" value={form.cost_price} onChange={v => set('cost_price', v)} type="number" placeholder="0.00" />
            </div>
            {form.cost_price > 0 && form.sale_price > 0 && (
              <p className="text-xs text-green-600 mt-2">
                Margem estimada: {(((form.sale_price - form.cost_price) / form.cost_price) * 100).toFixed(1)}%
              </p>
            )}
          </div>

          {/* Códigos */}
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Códigos</p>
            <div className="grid grid-cols-3 gap-3">
              <FI label="Código interno" value={form.code_internal} onChange={v => set('code_internal', v)} placeholder="ex: 001" />
              <FI label="Código OEM (original)" value={form.code_oem} onChange={v => set('code_oem', v)} placeholder="ex: 46477795" />
              <FI label="Código do fabricante" value={form.code_manufacturer} onChange={v => set('code_manufacturer', v)} placeholder="ex: ALT-1234" />
            </div>
          </div>

          {/* Localização */}
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Localização física</p>
            <div className="grid grid-cols-3 gap-3">
              <FI label="Corredor" value={form.loc_corridor} onChange={v => set('loc_corridor', v)} placeholder="ex: A" />
              <FI label="Prateleira" value={form.loc_shelf} onChange={v => set('loc_shelf', v)} placeholder="ex: 3" />
              <FI label="Caixa / Posição" value={form.loc_box} onChange={v => set('loc_box', v)} placeholder="ex: 12" />
            </div>
          </div>

          {/* Estoque */}
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Controle de estoque</p>
            <div className="grid grid-cols-2 gap-3">
              <FI label="Estoque mínimo" value={form.min_quantity} onChange={v => set('min_quantity', Number(v))} type="number" placeholder="1" />
              <FI label="Estoque máximo" value={form.max_quantity} onChange={v => set('max_quantity', Number(v))} type="number" placeholder="10" />
            </div>
          </div>

          {/* Observações */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">Observações</label>
            <textarea value={form.notes} onChange={e => set('notes', e.target.value)} rows={3}
              placeholder="Informações adicionais, defeitos, origem..."
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500 resize-none" />
          </div>
        </div>

        <div className="flex justify-end gap-3 p-6 border-t border-gray-100">
          <button onClick={onClose} className="border border-gray-200 px-4 py-2 rounded-lg text-sm text-gray-500 hover:bg-gray-50">Cancelar</button>
          <button onClick={() => onSave(form)} disabled={loading}
            className="bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white px-6 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
            {loading ? 'Salvando...' : <><Check size={14} /> Salvar</>}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, value }) {
  return (
    <div>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-sm font-medium text-gray-900">{value || '—'}</p>
    </div>
  )
}

export default function PartDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [showEdit, setShowEdit] = useState(false)
  const [showSoldConfirm, setShowSoldConfirm] = useState(false)
  const [soldResult, setSoldResult] = useState(null)
  const [publishResult, setPublishResult] = useState(null)
  const [stockQty, setStockQty] = useState(1)
  const [stockType, setStockType] = useState('in')
  const [vehicleSearch, setVehicleSearch] = useState('')
  const [vehicleResults, setVehicleResults] = useState([])
  const [newVehicle, setNewVehicle] = useState({ brand: '', model: '', year_start: '', year_end: '', engine: '' })
  const [showNewVehicle, setShowNewVehicle] = useState(false)

  const { data: part, isLoading } = useQuery({ queryKey: ['part', id], queryFn: () => getPart(id) })
  const { data: compatibilities = [] } = useQuery({ queryKey: ['compat', id], queryFn: () => getPartCompatibility(id) })
  const { data: similars = [] } = useQuery({ queryKey: ['similar', id], queryFn: () => getSimilarParts(id), enabled: !!id })

  const updateMut = useMutation({ mutationFn: (d) => updatePart(id, d), onSuccess: () => { qc.invalidateQueries(['part', id]); setShowEdit(false) } })
  const soldMut = useMutation({ mutationFn: () => soldAtCounter(id), onSuccess: (r) => { setSoldResult(r); setShowSoldConfirm(false); qc.invalidateQueries(['part', id]) } })
  const publishMut = useMutation({ mutationFn: () => publishToAll(id), onSuccess: (r) => { setPublishResult(r); qc.invalidateQueries(['part', id]) } })
  const stockMut = useMutation({ mutationFn: (d) => adjustStock(id, d), onSuccess: () => qc.invalidateQueries(['part', id]) })
  const addCompatMut = useMutation({ mutationFn: addCompatibility, onSuccess: () => qc.invalidateQueries(['compat', id]) })
  const removeCompatMut = useMutation({ mutationFn: removeCompatibility, onSuccess: () => qc.invalidateQueries(['compat', id]) })
  const createVehicleMut = useMutation({ mutationFn: createVehicle })

  if (isLoading) return <div className="p-8 text-gray-400">Carregando...</div>
  if (!part) return <div className="p-8 text-gray-400">Peça não encontrada</div>

  async function searchV(q) {
    setVehicleSearch(q)
    if (q.length < 2) { setVehicleResults([]); return }
    const r = await searchVehicles(q)
    setVehicleResults(r)
  }

  async function handleAddVehicle(vehicleId) {
    await addCompatMut.mutateAsync({ part_id: Number(id), vehicle_id: vehicleId })
    setVehicleSearch('')
    setVehicleResults([])
  }

  async function handleCreateVehicle() {
    if (!newVehicle.brand || !newVehicle.model) return
    const v = await createVehicleMut.mutateAsync({
      brand: newVehicle.brand, model: newVehicle.model,
      year_start: newVehicle.year_start ? Number(newVehicle.year_start) : null,
      year_end: newVehicle.year_end ? Number(newVehicle.year_end) : null,
      engine: newVehicle.engine || null,
    })
    await addCompatMut.mutateAsync({ part_id: Number(id), vehicle_id: v.id })
    setShowNewVehicle(false)
    setNewVehicle({ brand: '', model: '', year_start: '', year_end: '', engine: '' })
  }

  const margin = part.cost_price > 0 ? ((part.sale_price - part.cost_price) / part.cost_price * 100).toFixed(1) : null

  return (
    <div className="p-8">
      {showEdit && (
        <EditModal part={part} onSave={form => updateMut.mutate(form)} onClose={() => setShowEdit(false)} loading={updateMut.isPending} />
      )}

      {/* Modal confirmação venda balcão */}
      {showSoldConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center"><AlertTriangle size={20} className="text-red-600" /></div>
              <h2 className="text-lg font-bold text-gray-900">Confirmar venda no balcão</h2>
            </div>
            <p className="text-sm text-gray-600 mb-2">Esta ação vai:</p>
            <ul className="text-sm text-gray-600 mb-5 space-y-1 list-disc list-inside">
              <li>Zerar o estoque desta peça</li>
              <li>Encerrar o anúncio no <strong>Mercado Livre</strong> e todas as outras plataformas ativas</li>
              <li>Desativar a peça no sistema</li>
            </ul>
            <p className="text-sm font-semibold text-gray-800 mb-5">Peça: <span className="text-orange-600">{part.title}</span></p>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setShowSoldConfirm(false)} className="border border-gray-200 px-4 py-2 rounded-lg text-sm text-gray-500 hover:bg-gray-50">Cancelar</button>
              <button onClick={() => soldMut.mutate()} disabled={soldMut.isPending}
                className="bg-red-500 hover:bg-red-600 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium">
                {soldMut.isPending ? 'Baixando...' : 'Confirmar venda'}
              </button>
            </div>
          </div>
        </div>
      )}

      <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-gray-500 hover:text-gray-900 text-sm mb-6 transition-colors">
        <ArrowLeft size={16} /> Voltar
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Foto */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          {part.photos?.[0] ? (
            <img src={part.photos[0]} alt="" className="w-full aspect-square object-cover rounded-lg mb-4 border border-gray-100" />
          ) : (
            <div className="w-full aspect-square bg-gray-100 rounded-lg flex items-center justify-center mb-4">
              <Package size={48} className="text-gray-300" />
            </div>
          )}
          {part.photos?.length > 1 && (
            <div className="flex gap-2 overflow-x-auto">
              {part.photos.slice(1, 6).map((url, i) => (
                <img key={i} src={url} alt="" className="w-14 h-14 object-cover rounded-lg border border-gray-100 flex-shrink-0" />
              ))}
            </div>
          )}
          {margin && (
            <div className="mt-4 bg-green-50 rounded-lg p-3">
              <p className="text-xs text-gray-500">Margem de lucro</p>
              <p className="text-2xl font-bold text-green-600">{margin}%</p>
              <p className="text-xs text-gray-400 mt-0.5">Custo {fmt(part.cost_price)} → Venda {fmt(part.sale_price)}</p>
            </div>
          )}
        </div>

        {/* Dados */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-gray-900">Dados da peça</h2>
              <div className="flex gap-2">
                <button onClick={() => setShowEdit(true)} className="flex items-center gap-1 border border-gray-200 px-3 py-1.5 rounded-lg text-sm hover:bg-gray-50">
                  <Edit2 size={14} /> Editar
                </button>
                <button onClick={() => publishMut.mutate()} disabled={publishMut.isPending}
                  className="flex items-center gap-1 border border-blue-200 text-blue-600 px-3 py-1.5 rounded-lg text-sm hover:bg-blue-50 disabled:opacity-50">
                  <Globe size={14} /> {publishMut.isPending ? 'Publicando...' : 'Publicar em todas'}
                </button>
                <button onClick={() => setShowSoldConfirm(true)}
                  className="flex items-center gap-1 border border-red-200 text-red-600 px-3 py-1.5 rounded-lg text-sm hover:bg-red-50">
                  <ShoppingBag size={14} /> Vendido no balcão
                </button>
              </div>
            </div>
            {soldResult && (
              <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
                <strong>Peça baixada!</strong> Anúncios encerrados em: {Object.keys(soldResult.platforms || {}).join(', ') || 'nenhuma plataforma ativa'}
              </div>
            )}
            {publishResult && (
              <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
                <strong>Resultado:</strong> {Object.entries(publishResult).map(([k, v]) => `${k}: ${v.status}`).join(' · ')}
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <Field label="Título" value={part.title} />
              </div>
              <Field label="Código interno" value={part.code_internal} />
              <Field label="Código OEM (original)" value={part.code_oem} />
              <Field label="Código do fabricante" value={part.code_manufacturer} />
              <div>
                <p className="text-xs text-gray-500 mb-1">Condição</p>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${part.condition === 'new' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                  {part.condition === 'new' ? 'Novo' : 'Usado'}
                </span>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Preço de venda</p>
                <p className="text-sm font-medium text-gray-900">{part.sale_price ? fmt(part.sale_price) : '—'}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Custo</p>
                <p className="text-sm font-medium text-gray-900">{part.cost_price ? fmt(part.cost_price) : '—'}</p>
              </div>
              <div className="col-span-2">
                <p className="text-xs text-gray-500 mb-1">Localização física</p>
                <p className="text-sm font-medium text-gray-900">
                  {[part.loc_corridor && `Corredor ${part.loc_corridor}`, part.loc_shelf && `Prat. ${part.loc_shelf}`, part.loc_box && `Cx. ${part.loc_box}`].filter(Boolean).join(' · ') || part.location || '—'}
                </p>
              </div>
              <Field label="Estoque mínimo" value={part.min_quantity} />
              <Field label="Estoque máximo" value={part.max_quantity || null} />
              <div className="col-span-2">
                <Field label="Observações" value={part.notes} />
              </div>
            </div>
          </div>

          {/* Estoque */}
          <div className="bg-white border border-gray-200 rounded-xl p-6">
            <h3 className="font-semibold text-gray-900 mb-1">Estoque</h3>
            <div className="flex items-center gap-3 mb-4">
              <span className={`text-3xl font-bold ${part.quantity <= 0 ? 'text-red-500' : part.quantity <= part.min_quantity ? 'text-yellow-500' : 'text-green-600'}`}>
                {part.quantity}
              </span>
              <span className="text-gray-400 text-sm">unidades</span>
              {part.min_quantity > 0 && part.quantity <= part.min_quantity && (
                <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">Abaixo do mínimo ({part.min_quantity})</span>
              )}
            </div>
            <div className="flex gap-3 items-center">
              <select value={stockType} onChange={e => setStockType(e.target.value)}
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                <option value="in">Entrada</option>
                <option value="out">Saída</option>
                <option value="adjustment">Ajuste</option>
              </select>
              <input type="number" min="1" value={stockQty} onChange={e => setStockQty(Number(e.target.value))}
                className="w-20 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
              <button onClick={() => stockMut.mutate({ type: stockType, quantity: stockQty })}
                className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                Confirmar
              </button>
            </div>
          </div>
        </div>

        {/* Compatibilidades */}
        <div className="lg:col-span-3 bg-white border border-gray-200 rounded-xl p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Compatibilidade de veículos</h3>
          {compatibilities.length === 0 ? (
            <p className="text-sm text-gray-400 mb-4">Nenhum veículo cadastrado ainda.</p>
          ) : (
            <div className="flex flex-wrap gap-2 mb-4">
              {compatibilities.map(c => (
                <div key={c.id} className="flex items-center gap-2 bg-gray-100 rounded-lg px-3 py-2 text-sm">
                  <span className="font-medium">{c.vehicle.brand} {c.vehicle.model}</span>
                  {c.vehicle.year_start && <span className="text-gray-500">{c.vehicle.year_start}{c.vehicle.year_end && c.vehicle.year_end !== c.vehicle.year_start ? `–${c.vehicle.year_end}` : ''}</span>}
                  {c.oem_code && <span className="text-xs text-gray-400 font-mono">{c.oem_code}</span>}
                  <button onClick={() => removeCompatMut.mutate(c.id)} className="text-gray-400 hover:text-red-500 transition-colors"><X size={14} /></button>
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-3">
            <div className="relative flex-1 max-w-sm">
              <input value={vehicleSearch} onChange={e => searchV(e.target.value)}
                placeholder="Buscar veículo existente..."
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
              {vehicleResults.length > 0 && (
                <div className="absolute top-full left-0 right-0 bg-white border border-gray-200 rounded-lg shadow-lg mt-1 z-10 max-h-48 overflow-y-auto">
                  {vehicleResults.map(v => (
                    <button key={v.id} onClick={() => handleAddVehicle(v.id)}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex justify-between">
                      <span>{v.brand} {v.model}</span>
                      <span className="text-gray-400 text-xs">{v.year_start}{v.year_end ? `–${v.year_end}` : ''}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button onClick={() => setShowNewVehicle(!showNewVehicle)}
              className="flex items-center gap-2 border border-dashed border-gray-300 text-gray-500 hover:border-orange-400 hover:text-orange-500 px-4 py-2 rounded-lg text-sm transition-colors">
              <Plus size={14} /> Novo veículo
            </button>
          </div>
          {showNewVehicle && (
            <div className="mt-4 p-4 bg-gray-50 rounded-xl border border-gray-200">
              <p className="text-sm font-medium text-gray-700 mb-3">Cadastrar novo veículo</p>
              <div className="grid grid-cols-5 gap-3">
                {['brand', 'model', 'year_start', 'year_end', 'engine'].map(field => (
                  <input key={field} value={newVehicle[field]} onChange={e => setNewVehicle(v => ({ ...v, [field]: e.target.value }))}
                    placeholder={{ brand: 'Marca', model: 'Modelo', year_start: 'Ano inicial', year_end: 'Ano final', engine: 'Motor' }[field]}
                    className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500" />
                ))}
              </div>
              <div className="flex gap-2 mt-3">
                <button onClick={handleCreateVehicle} className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg text-sm font-medium">Adicionar</button>
                <button onClick={() => setShowNewVehicle(false)} className="border border-gray-200 px-4 py-2 rounded-lg text-sm text-gray-500 hover:bg-gray-100">Cancelar</button>
              </div>
            </div>
          )}
        </div>

        {/* Similares */}
        {similars.length > 0 && (
          <div className="lg:col-span-3 bg-white border border-gray-200 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <Link size={16} className="text-orange-500" />
              <h3 className="font-semibold text-gray-900">Peças similares em estoque</h3>
              <span className="text-xs bg-orange-100 text-orange-600 px-2 py-0.5 rounded-full">{similars.length}</span>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {similars.slice(0, 8).map(p => (
                <div key={p.id} onClick={() => navigate(`/parts/${p.id}`)}
                  className="border border-gray-200 rounded-lg p-3 cursor-pointer hover:border-orange-300 transition-all">
                  <p className="text-sm font-medium text-gray-900 line-clamp-2">{p.title}</p>
                  <p className="text-xs text-green-600 mt-1">{p.quantity} un. · {fmt(p.sale_price)}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
