<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ChevronRightIcon } from '@heroicons/vue/24/solid'

const route = useRoute()

const crumbs = computed(() => {
    const build = route.meta?.breadcrumbs
    return typeof build === 'function' ? build(route) : []
})
</script>

<template>
    <nav v-if="crumbs.length" aria-label="Breadcrumb" class="flex items-center gap-1 px-4 py-2 text-sm bg-surface-header text-ink-secondary">
        <template v-for="(crumb, index) in crumbs" :key="index">
            <ChevronRightIcon v-if="index > 0" class="size-3 text-ink-muted shrink-0" />
            <router-link
                v-if="crumb.to && index < crumbs.length - 1"
                :to="crumb.to"
                class="hover:text-brand-400"
            >
                {{ crumb.label }}
            </router-link>
            <span v-else class="text-ink-primary font-bold">{{ crumb.label }}</span>
        </template>
    </nav>
</template>
