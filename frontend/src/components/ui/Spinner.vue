<script setup>
defineProps({
    size: { type: String, default: 'md' }, // sm | md | lg
})

const sizeClasses = {
    sm: 'h-4 w-4 border-2',
    md: 'h-6 w-6 border-2',
    lg: 'h-10 w-10 border-4',
}
</script>

<template>
    <span
        class="inline-block rounded-full border-line-subtle border-t-brand-500 animate-spin"
        :class="sizeClasses[size]"
        role="status"
        aria-label="Loading"
    ></span>
</template>
