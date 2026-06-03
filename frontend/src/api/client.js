import axios from 'axios'
import toast from 'react-hot-toast'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 0, // disable for chunked uploads
  headers: { 'Content-Type': 'application/json' },
})

// Response interceptor — global error toast
client.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg =
      err.response?.data?.detail ||
      err.response?.data?.message ||
      err.message ||
      'Request failed'
    if (err.response?.status !== 404) {
      toast.error(String(msg).slice(0, 120))
    }
    return Promise.reject(err)
  },
)

export default client
