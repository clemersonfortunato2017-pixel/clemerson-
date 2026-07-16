import axios from 'axios'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('pitbox_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('pitbox_token')
      localStorage.removeItem('pitbox_user')
      if (location.pathname !== '/login') location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth
export const login = (data) => api.post('/auth/login', data).then(r => r.data)
export const register = (data) => api.post('/auth/register', data).then(r => r.data)
export const getMe = () => api.get('/auth/me').then(r => r.data)
export const getPendingUsers = () => api.get('/auth/pending').then(r => r.data)
export const approveUser = (id) => api.post(`/auth/${id}/approve`).then(r => r.data)
export const rejectUser = (id) => api.post(`/auth/${id}/reject`).then(r => r.data)
export const inviteUser = (data) => api.post('/auth/invite', data).then(r => r.data)
export const acceptInvite = (data) => api.post('/auth/accept-invite', data).then(r => r.data)
export const loginWithGoogle = (credential) => api.post('/auth/google', { credential }).then(r => r.data)

// Esteira automática
export const uploadPhotos = (files) => {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  return api.post('/parts/upload-photos', form, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
}
export const getDailyReport = (date) => api.get('/reports/daily', { params: date ? { date } : {} }).then(r => r.data)

export const getParts = (params) => api.get('/parts/', { params }).then(r => r.data)
export const getPart = (id) => api.get(`/parts/${id}`).then(r => r.data)
export const createPart = (data) => api.post('/parts/', data).then(r => r.data)
export const updatePart = (id, data) => api.put(`/parts/${id}`, data).then(r => r.data)
export const deletePart = (id) => api.delete(`/parts/${id}`).then(r => r.data)
export const adjustStock = (id, data) => api.post(`/parts/${id}/stock`, data).then(r => r.data)
export const importFromML = () => api.post('/import/mercadolivre').then(r => r.data)
export const syncCompatibility = () => api.post('/import/sync-compatibility').then(r => r.data)
export const getSyncStatus = () => api.get('/import/sync-compatibility/status').then(r => r.data)
export const syncCompatFromTitles = () => api.post('/import/sync-compatibility-titles').then(r => r.data)

export const getSales = (params) => api.get('/sales/', { params }).then(r => r.data)
export const createSale = (data) => api.post('/sales/', data).then(r => r.data)
export const getMonthlyFinancial = (params) => api.get('/sales/financial/monthly', { params }).then(r => r.data)

export const getPartCompatibility = (partId) => api.get(`/compatibility/parts/${partId}`).then(r => r.data)
export const addCompatibility = (data) => api.post('/compatibility/', data).then(r => r.data)
export const removeCompatibility = (id) => api.delete(`/compatibility/${id}`).then(r => r.data)
export const searchVehicles = (q) => api.get('/compatibility/vehicles', { params: { q } }).then(r => r.data)
export const createVehicle = (data) => api.post('/compatibility/vehicles', data).then(r => r.data)
export const searchByVehicle = (params) => api.get('/compatibility/search-by-vehicle', { params }).then(r => r.data)

export const getLowStockAlerts = () => api.get('/parts/alerts/low-stock').then(r => r.data)
export const getAbcCurve = () => api.get('/parts/reports/abc').then(r => r.data)
export const getSimilarParts = (id) => api.get(`/parts/similar/${id}`).then(r => r.data)

export const getPlatformsStatus = () => api.get('/platforms/status').then(r => r.data)
export const soldAtCounter = (id) => api.post(`/platforms/parts/${id}/sold-balcao`).then(r => r.data)
export const publishToAll = (id) => api.post(`/platforms/parts/${id}/publish-all`).then(r => r.data)
export const reactivatePart = (id) => api.post(`/platforms/parts/${id}/reactivate`).then(r => r.data)

export default api
