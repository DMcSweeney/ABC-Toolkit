import axios from 'axios'
import { useToastStore } from '@/stores/toast'

// Shared axios instance for talking to the backend. Centralising this means every request
// gets the same base URL and the same error-surfacing behaviour, instead of each component
// building its own URL and choosing its own (or no) error handling.
const api = axios.create({
    baseURL: import.meta.env.VITE_BACKEND_URI,
})

function extractErrorMessage(error) {
    // Backend's global error handler (backend/src/app.py) returns {"error": "..."}.
    // Some endpoints written before that still return {"message": "..."} on 4xx — support both.
    const data = error.response?.data
    if (data?.error) return data.error
    if (data?.message) return data.message
    if (error.response) return `Request failed (${error.response.status})`
    return error.message || 'Could not reach the server.'
}

api.interceptors.response.use(
    (response) => response,
    (error) => {
        // Pass `{ skipErrorToast: true }` in a request's config for expected failures a
        // component already handles in its own UI (e.g. disabling a button rather than
        // showing an error) — otherwise every failure gets a toast automatically.
        if (!error.config?.skipErrorToast) {
            const toast = useToastStore()
            toast.error(extractErrorMessage(error))
        }
        return Promise.reject(error)
    }
)

export default api
