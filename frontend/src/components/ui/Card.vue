<script setup>
defineProps({
    padding: { type: String, default: 'md' }, // none | sm | md
})

const paddingClasses = {
    none: '',
    sm: 'p-3',
    md: 'p-6',
}
</script>

<template>
    <div class="bg-surface-card border border-line-subtle border-t-white/5 rounded shadow-lg shadow-black/30">
        <div v-if="$slots.header" class="border-b border-line-subtle px-6 py-3">
            <slot name="header"></slot>
        </div>
        <div :class="paddingClasses[padding]">
            <slot></slot>
        </div>
    </div>
</template>
