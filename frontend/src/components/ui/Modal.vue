<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import { XMarkIcon } from '@heroicons/vue/24/solid'

const props = defineProps({
    modelValue: { type: Boolean, required: true },
    title: { type: String, default: '' },
    size: { type: String, default: 'md' }, // md | lg | full
})

const emit = defineEmits(['update:modelValue'])

const sizeClasses = {
    md: 'w-2/3 h-2/3',
    lg: 'w-4/5 h-4/5',
    full: 'w-full h-full',
}

function close() {
    emit('update:modelValue', false)
}

function onKeydown(event) {
    if (event.key === 'Escape' && props.modelValue) {
        close()
    }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
    <div
        v-if="modelValue"
        class="fixed inset-0 z-50 flex bg-black/60"
        @click.self="close"
    >
        <div
            class="flex flex-col bg-surface-card border border-line-subtle rounded shadow-lg shadow-black mx-auto my-auto"
            :class="sizeClasses[size]"
            role="dialog"
            aria-modal="true"
            :aria-label="title || 'Dialog'"
        >
            <div class="flex items-center justify-between px-4 py-2 border-b border-line-subtle">
                <p class="text-ink-primary font-bold">{{ title }}</p>
                <button
                    class="text-ink-secondary hover:text-ink-primary rounded p-1 focus:outline-none focus:ring-2 focus:ring-brand-500"
                    aria-label="Close"
                    @click="close"
                >
                    <XMarkIcon class="size-6" />
                </button>
            </div>
            <div class="flex-1 overflow-auto p-4">
                <slot></slot>
            </div>
        </div>
    </div>
</template>
