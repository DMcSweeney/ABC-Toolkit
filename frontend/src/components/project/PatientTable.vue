<script>
import {
  FwbTable,
  FwbTableBody,
  FwbTableCell,
  FwbTableHead,
  FwbTableHeadCell,
  FwbTableRow,
} from 'flowbite-vue'

import {ChevronDoubleRightIcon, CheckCircleIcon, NoSymbolIcon} from '@heroicons/vue/24/solid'


export default {
    name: 'PatientTable',
    data() {
        return {
            //
            project: this.$route.params.project
        }
    },
    methods: {
    },
    props: ['patients'],
    components: {FwbTable, FwbTableBody, FwbTableCell, FwbTableHead, FwbTableHeadCell, FwbTableRow, ChevronDoubleRightIcon, CheckCircleIcon, NoSymbolIcon},
}
</script>

<template>
<div class="relative mx-auto w-3/4">

<fwb-table hoverable class="[&_thead]:!bg-surface-raised [&_thead]:!text-ink-primary [&_tbody]:!bg-surface-card [&_tr]:!bg-surface-card [&_tr]:hover:!bg-surface-raised [&_tr]:!border-line-subtle [&_tr]:!transition-colors [&_tr]:!duration-150 [&_td]:!text-ink-primary [&_th]:!text-ink-primary">
<fwb-table-head>
    <fwb-table-head-cell>Patient ID</fwb-table-head-cell>
    <fwb-table-head-cell># series</fwb-table-head-cell>
    <fwb-table-head-cell>Vertebrae</fwb-table-head-cell>
    <fwb-table-head-cell>RTSTRUCT</fwb-table-head-cell>
    <fwb-table-head-cell></fwb-table-head-cell>
</fwb-table-head>

<fwb-table-body>
    <fwb-table-row v-for="(value, key) in this.patients" :key="key">
        <fwb-table-cell> <span class="text-l text-ink-primary font-bold"> {{key}} </span> </fwb-table-cell>
        <fwb-table-cell> <span class="text-sm"> {{value.num_series}} </span></fwb-table-cell>
        <fwb-table-cell> <span class="text-xs text-ink-secondary"> {{value.vertebrae}} </span></fwb-table-cell>


        <fwb-table-cell v-if="value.rtstruct_detected === 'not detected'"> <NoSymbolIcon class="size-6 text-red-600 dark:text-red-400 mx-auto"/>  </fwb-table-cell>
        <fwb-table-cell v-else> <CheckCircleIcon class="size-6 text-brand-400 mx-auto"/> </fwb-table-cell>
        <fwb-table-cell>
        <router-link :to="`${this.$route.path}/weights/${key}`" :aria-label="`View weights for patient ${key}`"> <ChevronDoubleRightIcon class="size-6 text-ink-secondary hover:text-brand-400 hover:font-bold" /> </router-link>
        </fwb-table-cell>
    </fwb-table-row>
</fwb-table-body>
</fwb-table>

</div>

</template>

<style scoped>
</style>