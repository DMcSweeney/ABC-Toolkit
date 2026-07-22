<script setup>
import Spinner from './Spinner.vue'

defineProps({
    label: { type: String, default: 'Loading...' },
})
</script>

<template>
    <div class="flex flex-col items-center justify-center gap-3 py-12 text-ink-muted">
        <Spinner size="lg" />
        <p class="text-sm">{{ label }}</p>
    </div>
</template>
