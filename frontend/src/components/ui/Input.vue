<script setup>
import { useId } from 'vue'

const props = defineProps({
    modelValue: { type: [String, Number], default: '' },
    modelModifiers: { type: Object, default: () => ({}) },
    label: { type: String, default: '' },
    type: { type: String, default: 'text' },
    placeholder: { type: String, default: '' },
    required: { type: Boolean, default: false },
    error: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const inputId = useId()

function onInput(event) {
    let value = event.target.value
    if (props.modelModifiers?.number) value = event.target.valueAsNumber || 0
    else if (props.modelModifiers?.trim) value = value.trim()
    emit('update:modelValue', value)
}
</script>

<template>
    <div>
        <label v-if="label" :for="inputId" class="block text-ink-secondary text-sm pb-1">{{ label }}</label>
        <input
            :id="inputId"
            :value="modelValue"
            :type="type"
            :placeholder="placeholder"
            :required="required"
            class="rounded text-xl px-2 bg-surface-raised text-ink-primary placeholder:text-ink-muted h-10 w-full border border-line-subtle focus:outline-none focus:ring-2 focus:ring-brand-500"
            :class="error && 'border-red-500'"
            @input="onInput"
        >
        <p v-if="error" class="text-red-400 text-xs pt-1">{{ error }}</p>
    </div>
</template>
