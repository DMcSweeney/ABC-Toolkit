<script setup>
import { useToastStore } from '@/stores/toast'

const toastStore = useToastStore()
</script>

<template>
    <div class="fixed top-20 right-4 z-[100] flex flex-col gap-2 w-96 max-w-[90vw]">
        <div v-for="toast in toastStore.toasts" :key="toast.id"
            class="flex items-start justify-between rounded shadow-lg shadow-black border bg-zinc-900 p-3 text-sm"
            :class="{
                'border-red-500 text-red-300': toast.type === 'error',
                'border-green-500 text-green-300': toast.type === 'success',
                'border-indigo-500 text-indigo-200': toast.type === 'info',
            }">
            <span class="pr-2 break-words">{{ toast.message }}</span>
            <button class="text-stone-400 hover:text-stone-200 font-bold shrink-0" @click="toastStore.dismiss(toast.id)">
                &times;
            </button>
        </div>
    </div>
</template>

<style scoped>
</style>
