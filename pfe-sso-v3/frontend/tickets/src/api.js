import axios from 'axios'

let _kc = null
export function setKeycloak(kc) { _kc = kc }

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
})

api.interceptors.request.use((config) => {
  if (_kc?.token) {
    config.headers.Authorization = `Bearer ${_kc.token}`
  }
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) _kc?.login()
    return Promise.reject(err)
  }
)
