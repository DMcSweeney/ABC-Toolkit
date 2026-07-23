<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { SunIcon, MoonIcon } from '@heroicons/vue/24/outline'

const route = useRoute()
const themeStore = useThemeStore()

const db_url = import.meta.env.VITE_BACKEND_URI.replace(import.meta.env.VITE_BACKEND_PORT, import.meta.env.VITE_MONGO_EXPRESS_PORT)
const jobs_url = `${import.meta.env.VITE_BACKEND_URI}/rq-dashboard`

const activeProject = computed(() => route.params.project)
</script>


<template>
    <header>
        <nav class="relative flex w-full bg-surface-header h-20 shadow-md shadow-black/30 items-center px-2">
        <div class="flex w-full items-center">
            <router-link to="/"><img src="../assets/ABC_logo.png" id="icon" class="h-20" alt="ABC home"> </router-link>
            <p class="text-ink-secondary px-2 text-3xl font-bold tracking-tight">ABC</p>
            <p v-if="activeProject" class="text-brand-300 px-2 text-xl font-bold border-l border-line-subtle ml-2 pl-4">{{ activeProject }}</p>
        </div>
        <div class="flex items-center align-end m-auto mr-5">
            <a class="text-ink-secondary px-2 font-bold hover:text-brand-400 transition-colors duration-150" :href="`${db_url}`" target="_blank" rel="noopener noreferrer" aria-label="Open database viewer (opens in a new tab)">Database</a>
            <a class="text-ink-secondary px-2 font-bold hover:text-brand-400 transition-colors duration-150" :href="`${jobs_url}`" target="_blank" rel="noopener noreferrer" aria-label="Open job queue dashboard (opens in a new tab)">Jobs</a>
            <button type="button"
                class="ml-2 p-1.5 rounded text-ink-secondary hover:text-brand-400 hover:bg-surface-raised transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500"
                :aria-label="themeStore.theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'"
                @click="themeStore.toggle()">
                <SunIcon v-if="themeStore.theme === 'dark'" class="size-6" />
                <MoonIcon v-else class="size-6" />
            </button>
        </div>

        </nav>
        <div class="h-px w-full bg-gradient-to-r from-transparent via-brand-500/40 to-transparent"></div>
    </header>

</template>

<style scoped>
</style>
