<script setup>
defineProps({
    variant: { type: String, default: 'info' }, // pass | fail | todo | info
})

const variantClasses = {
    pass: 'bg-brand-500/15 text-brand-300',
    fail: 'bg-red-500/15 text-red-700 dark:text-red-300',
    todo: 'bg-surface-raised text-ink-muted',
    info: 'bg-accent-500/15 text-accent-300',
}
</script>

<template>
    <span
        class="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-bold"
        :class="variantClasses[variant]"
    >
        <slot></slot>
    </span>
</template>
