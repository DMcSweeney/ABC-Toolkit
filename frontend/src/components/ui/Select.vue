<script setup>
import { useId } from 'vue'

defineProps({
    modelValue: { type: [String, Number], default: '' },
    label: { type: String, default: '' },
    // Array of plain strings, or {value, label} objects
    options: { type: Array, default: () => [] },
    required: { type: Boolean, default: false },
    placeholder: { type: String, default: 'Select an option' },
})

defineEmits(['update:modelValue'])

const selectId = useId()

function optionValue(option) {
    return typeof option === 'object' ? option.value : option
}

function optionLabel(option) {
    return typeof option === 'object' ? option.label : option
}
</script>

<template>
    <div>
        <label v-if="label" :for="selectId" class="block text-ink-secondary text-sm pb-1">{{ label }}</label>
        <select
            :id="selectId"
            :value="modelValue"
            :required="required"
            class="rounded text-xl px-2 bg-surface-raised text-ink-primary h-10 w-full border border-line-subtle focus:outline-none focus:ring-2 focus:ring-brand-500"
            @change="$emit('update:modelValue', $event.target.value)"
        >
            <option value="" disabled>{{ placeholder }}</option>
            <option v-for="option in options" :key="optionValue(option)" :value="optionValue(option)">
                {{ optionLabel(option) }}
            </option>
        </select>
    </div>
</template>
