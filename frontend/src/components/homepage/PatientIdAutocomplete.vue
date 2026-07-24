<script>
import { useId } from 'vue';
import api from '@/api/client';

// Debounced patient-id type-ahead, backed by GET /api/database/search_patients.
// Reused by both AssignToProject.vue (search a patient to reassign) and HomePage.vue
// (jump straight to a patient's page) - anywhere a user needs to find a patient by id
// without already knowing which project they're in.
export default {
    name: 'PatientIdAutocomplete',
    props: {
        modelValue: { type: String, default: '' },
        label: { type: String, default: 'Patient ID' },
        placeholder: { type: String, default: '12345' },
    },
    emits: ['update:modelValue', 'select', 'enter'],
    data() {
        return {
            inputId: useId(),
            suggestions: [],
            open: false,
            highlightedIndex: -1,
            debounceHandle: null,
        }
    },
    methods: {
        onInput(event) {
            const value = event.target.value;
            this.$emit('update:modelValue', value);
            this.highlightedIndex = -1;
            clearTimeout(this.debounceHandle);
            if (!value.trim()) {
                this.suggestions = [];
                this.open = false;
                return;
            }
            this.debounceHandle = setTimeout(() => this.fetchSuggestions(value), 250);
        },
        async fetchSuggestions(value) {
            try {
                const res = await api.get('/api/database/search_patients', {
                    params: { q: value, limit: 8 },
                    skipErrorToast: true,
                });
                // The value may have changed again while this request was in flight.
                if (value !== this.modelValue) return;
                this.suggestions = res.data.patient_ids || [];
                this.open = this.suggestions.length > 0;
            } catch (err) {
                this.suggestions = [];
                this.open = false;
            }
        },
        selectSuggestion(patientId) {
            this.$emit('update:modelValue', patientId);
            this.suggestions = [];
            this.open = false;
            this.highlightedIndex = -1;
            this.$emit('select', patientId);
        },
        onKeydown(event) {
            if (!this.open || !this.suggestions.length) {
                if (event.key === 'Enter') this.$emit('enter', this.modelValue);
                return;
            }
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                this.highlightedIndex = (this.highlightedIndex + 1) % this.suggestions.length;
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                this.highlightedIndex = (this.highlightedIndex - 1 + this.suggestions.length) % this.suggestions.length;
            } else if (event.key === 'Enter') {
                event.preventDefault();
                if (this.highlightedIndex >= 0) {
                    this.selectSuggestion(this.suggestions[this.highlightedIndex]);
                } else {
                    this.open = false;
                    this.$emit('enter', this.modelValue);
                }
            } else if (event.key === 'Escape') {
                this.open = false;
            }
        },
        onFocus() {
            if (this.suggestions.length) this.open = true;
        },
        onBlur() {
            // Delay closing so a click on a suggestion (which blurs the input first) still registers.
            setTimeout(() => { this.open = false; }, 150);
        },
    },
}
</script>

<template>
    <div class="relative">
        <label v-if="label" :for="inputId" class="block text-ink-secondary text-sm pb-1">{{ label }}</label>
        <input
            :id="inputId"
            :value="modelValue"
            type="text"
            autocomplete="off"
            :placeholder="placeholder"
            class="rounded text-xl px-2 bg-surface-raised text-ink-primary placeholder:text-ink-muted h-10 w-full border border-line-subtle focus:outline-none focus:ring-2 focus:ring-brand-500"
            @input="onInput"
            @keydown="onKeydown"
            @focus="onFocus"
            @blur="onBlur"
        >
        <ul v-if="open" class="absolute z-20 mt-1 w-full bg-surface-card border border-line-subtle rounded shadow-lg shadow-black/30 max-h-56 overflow-y-auto">
            <li v-for="(suggestion, i) in suggestions" :key="suggestion">
                <button type="button"
                    class="block w-full text-left px-3 py-2 text-ink-primary"
                    :class="i === highlightedIndex ? 'bg-brand-600/20' : 'hover:bg-surface-raised'"
                    @mousedown.prevent="selectSuggestion(suggestion)"
                    @mouseenter="highlightedIndex = i"
                >
                    {{ suggestion }}
                </button>
            </li>
        </ul>
    </div>
</template>
