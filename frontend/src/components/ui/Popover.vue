<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { InformationCircleIcon } from '@heroicons/vue/24/outline'

const props = defineProps({
    align: { type: String, default: 'left' }, // left | right — which edge the panel anchors to
})

const emit = defineEmits(['open'])

const hovering = ref(false)
const pinned = ref(false)
const open = computed(() => hovering.value || pinned.value)
const root = ref(null)

watch(open, (isOpen) => {
    if (isOpen) emit('open')
})

function togglePin() {
    pinned.value = !pinned.value
}

function handleClickOutside(event) {
    if (pinned.value && root.value && !root.value.contains(event.target)) {
        pinned.value = false
    }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', handleClickOutside))
</script>

<template>
    <div ref="root" class="relative inline-block" @mouseenter="hovering = true" @mouseleave="hovering = false">
        <button type="button"
            class="text-ink-secondary hover:text-brand-400 transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500 rounded"
            aria-label="Show scan details"
            :aria-expanded="open"
            @click="togglePin">
            <InformationCircleIcon class="size-6" />
        </button>
        <div v-if="open"
            class="absolute z-20 mt-2 w-80 bg-surface-card border border-line-subtle rounded-lg shadow-lg shadow-black/40 p-4 text-sm"
            :class="props.align === 'right' ? 'right-0' : 'left-0'">
            <slot name="content"></slot>
        </div>
    </div>
</template>
