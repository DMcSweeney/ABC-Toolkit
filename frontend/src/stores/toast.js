import { defineStore } from 'pinia'

let nextId = 0

export const useToastStore = defineStore('toast', {
    state: () => ({
        toasts: [],
    }),
    actions: {
        push({ type = 'info', message, timeout = 6000 }) {
            const id = nextId++
            this.toasts.push({ id, type, message })
            if (timeout) {
                setTimeout(() => this.dismiss(id), timeout)
            }
            return id
        },
        success(message, timeout = 4000) {
            return this.push({ type: 'success', message, timeout })
        },
        error(message, timeout = 8000) {
            return this.push({ type: 'error', message, timeout })
        },
        info(message, timeout = 6000) {
            return this.push({ type: 'info', message, timeout })
        },
        dismiss(id) {
            this.toasts = this.toasts.filter((t) => t.id !== id)
        },
    },
})
