import { defineStore } from 'pinia'

export const useThemeStore = defineStore('theme', {
    state: () => ({
        // The bootstrap script in index.html already set this on <html> before first paint
        // (reading localStorage, falling back to prefers-color-scheme) — mirror it here
        // rather than re-deriving it, so the store and the DOM never disagree.
        theme: document.documentElement.getAttribute('data-theme') || 'light',
    }),
    actions: {
        toggle() {
            this.setTheme(this.theme === 'dark' ? 'light' : 'dark')
        },
        setTheme(theme) {
            this.theme = theme
            localStorage.setItem('theme', theme)
            document.documentElement.setAttribute('data-theme', theme)
        },
    },
})
