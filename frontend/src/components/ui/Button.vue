<script setup>
import { computed } from 'vue'
import Spinner from './Spinner.vue'

const props = defineProps({
    variant: { type: String, default: 'secondary' }, // primary | secondary | pass | fail | ghost
    size: { type: String, default: 'md' }, // sm | md
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    to: { type: String, default: '' },
    type: { type: String, default: 'button' },
})

const variantClasses = {
    primary: 'bg-brand-600 hover:bg-brand-700 disabled:bg-surface-raised disabled:text-ink-muted text-ink-primary font-bold',
    secondary: 'bg-surface-raised hover:bg-line-default border border-line-subtle disabled:text-ink-muted text-ink-primary font-bold',
    pass: 'bg-brand-400 hover:bg-brand-500 disabled:bg-surface-raised disabled:text-ink-muted text-zinc-900 font-extrabold shadow-sm shadow-brand-300/40',
    fail: 'bg-red-400 hover:bg-red-500 disabled:bg-surface-raised disabled:text-ink-muted text-zinc-900 font-extrabold shadow-sm shadow-red-300/40',
    ghost: 'bg-transparent hover:bg-surface-raised text-ink-secondary hover:text-ink-primary disabled:text-ink-muted font-bold',
}

const sizeClasses = {
    sm: 'h-8 px-3 text-sm',
    md: 'h-10 px-4 text-base',
}

const isDisabled = computed(() => props.disabled || props.loading)
const tag = computed(() => (props.to ? 'router-link' : 'button'))
</script>

<template>
    <component
        :is="tag"
        :to="to || undefined"
        :type="!to ? type : undefined"
        :disabled="!to ? isDisabled : undefined"
        class="inline-flex items-center justify-center gap-2 rounded transition-all duration-150 active:scale-[0.97] focus:outline-none focus:ring-2 focus:ring-brand-500"
        :class="[variantClasses[variant], sizeClasses[size], isDisabled && 'pointer-events-none opacity-70']"
    >
        <Spinner v-if="loading" size="sm" />
        <slot></slot>
    </component>
</template>
