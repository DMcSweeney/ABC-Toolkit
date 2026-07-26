<script>
import {
  FwbTable,
  FwbTableBody,
  FwbTableCell,
  FwbTableHead,
  FwbTableHeadCell,
  FwbTableRow,
} from 'flowbite-vue'

import {ChevronDoubleRightIcon, CheckCircleIcon, NoSymbolIcon, TrashIcon} from '@heroicons/vue/24/solid'
import api from '@/api/client';
import { useToastStore } from '@/stores/toast';


export default {
    name: 'PatientTable',
    setup() {
        return { toast: useToastStore() };
    },
    data() {
        return {
            //
            project: this.$route.params.project,
            deletingPatientId: null,
        }
    },
    methods: {
        DeletePatient(patientId) {
            if (!confirm(`Do you really want to delete patient ${patientId} from project ${this.project}? This permanently removes all of their data and cannot be undone.`)) {
                return;
            }
            this.deletingPatientId = patientId;
            api.post('/api/database/delete_patient', { patient_id: patientId, project: this.project })
                .then(() => {
                    this.toast.success(`Deleted patient ${patientId}.`);
                    this.$emit('deleted');
                }).catch(() => {
                    // Error already surfaced via toast by the shared api client.
                }).finally(() => {
                    this.deletingPatientId = null;
                })
        },
    },
    props: ['patients'],
    emits: ['deleted'],
    components: {FwbTable, FwbTableBody, FwbTableCell, FwbTableHead, FwbTableHeadCell, FwbTableRow, ChevronDoubleRightIcon, CheckCircleIcon, NoSymbolIcon, TrashIcon},
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
        <div class="flex items-center gap-3">
            <router-link :to="`${this.$route.path}/weights/${key}`" :aria-label="`View weights for patient ${key}`"> <ChevronDoubleRightIcon class="size-6 text-ink-secondary hover:text-brand-400 hover:font-bold" /> </router-link>
            <button type="button" :disabled="deletingPatientId === key" :aria-label="`Delete patient ${key}`" @click="DeletePatient(key)">
                <TrashIcon class="size-6 text-ink-secondary hover:text-red-500" :class="{ 'opacity-50': deletingPatientId === key }" />
            </button>
        </div>
        </fwb-table-cell>
    </fwb-table-row>
</fwb-table-body>
</fwb-table>

</div>

</template>

<style scoped>
</style>