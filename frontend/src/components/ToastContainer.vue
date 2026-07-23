<script setup>
import { useToastStore } from '@/stores/toast'

const toastStore = useToastStore()
</script>

<template>
    <div class="fixed top-20 right-4 z-[100] flex flex-col gap-2 w-96 max-w-[90vw]">
        <div v-for="toast in toastStore.toasts" :key="toast.id"
            class="flex items-start justify-between rounded shadow-lg shadow-black/30 border bg-surface-card p-3 text-sm"
            :class="{
                'border-red-500 text-red-700 dark:text-red-300': toast.type === 'error',
                'border-brand-500 text-brand-400': toast.type === 'success',
                'border-accent-500 text-accent-400': toast.type === 'info',
            }">
            <span class="pr-2 break-words">{{ toast.message }}</span>
            <button class="text-ink-muted hover:text-ink-secondary font-bold shrink-0" @click="toastStore.dismiss(toast.id)">
                &times;
            </button>
        </div>
    </div>
</template>

<style scoped>
</style>
