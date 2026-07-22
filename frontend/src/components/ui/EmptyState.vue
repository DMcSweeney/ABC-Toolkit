<script setup>
import Button from './Button.vue'

defineProps({
    title: { type: String, required: true },
    message: { type: String, default: '' },
    actionLabel: { type: String, default: '' },
    actionTo: { type: String, default: '' },
    icon: { type: [Object, Function], default: null },
})
</script>

<template>
    <div class="flex flex-col items-center justify-center gap-2 py-12 text-center">
        <div v-if="icon" class="bg-brand-500/10 rounded-full p-4 mb-1">
            <component :is="icon" class="size-8 text-brand-400" />
        </div>
        <p class="text-ink-primary text-lg font-bold">{{ title }}</p>
        <p v-if="message" class="text-ink-muted text-sm max-w-md">{{ message }}</p>
        <Button v-if="actionLabel && actionTo" :to="actionTo" variant="primary" class="mt-2">
            {{ actionLabel }}
        </Button>
    </div>
</template>
