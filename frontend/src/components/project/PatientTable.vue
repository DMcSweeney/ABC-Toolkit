<script>
import {
  FwbA,
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
    created() {
        //
    },      
    props: ['patients'],
    components: {FwbA,FwbTable, FwbTableBody, FwbTableCell, FwbTableHead, FwbTableHeadCell, FwbTableRow, ChevronDoubleRightIcon, CheckCircleIcon, NoSymbolIcon},
}
</script>

<template>
<!-- <fwb-table hoverable stripped class="w-3/4 mx-auto mt-10 text-left bg-zinc-900">

    <fwb-table-head class="h-10 py-10 bg-zinc-900 text-stone-200 text-4xl">
        <fwb-table-head-cell>Patient ID</fwb-table-head-cell>
        <fwb-table-head-cell>View</fwb-table-head-cell> 
    </fwb-table-head>

    <fwb-table-body class="bg-zinc-900 text-black m-auto">
        <fwb-table-row v-for="item in this.patients.slice(0, 10)" class=" bg-black h-8 border border-zinc-800 hover:shadow-lg" :href="`${this.$route.path}/${item.patient_id}`">
            <fwb-table-cell>{{item.patient_id}}</fwb-table-cell>
            <fwb-table-cell>
                <fwb-a :href="`${this.$route.path}/weights/${item.patient_id}`">LINK</fwb-a>    
            </fwb-table-cell>
        </fwb-table-row>
    </fwb-table-body>

</fwb-table> -->

<div class="relative mx-auto w-3/4">


<fwb-table hoverable>
<fwb-table-head>
    <!-- <div class="bg-black"> -->
    <fwb-table-head-cell>Patient ID</fwb-table-head-cell>
    <fwb-table-head-cell># series</fwb-table-head-cell>
    <fwb-table-head-cell>Vertebrae</fwb-table-head-cell>
    <fwb-table-head-cell>RTSTRUCT</fwb-table-head-cell>
    <fwb-table-head-cell></fwb-table-head-cell>
    <!-- </div> -->
</fwb-table-head>

<!-- :href="`${this.$route.path}/${item.patient_id}`" -->
<fwb-table-body>
    <fwb-table-row v-for="(value, key) in this.patients">
        <fwb-table-cell> <a class="text-l text-zinc-950 font-bold"> {{key}} </a> </fwb-table-cell>
        <fwb-table-cell> <a class="text-sm"> {{value.num_series}} </a></fwb-table-cell>
        <fwb-table-cell> <a class="text-xs text-grey-950"> {{value.vertebrae}} </a></fwb-table-cell>


        <fwb-table-cell v-if="value.rtstruct_detected === 'not detected'"> <NoSymbolIcon class="size-6 text-red-400 mx-auto"/>  </fwb-table-cell>
        <fwb-table-cell v-else> <CheckCircleIcon class="size-6 text-green-400 mx-auto"/> </fwb-table-cell>
        <fwb-table-cell>
        <fwb-a :href="`${this.$route.path}/weights/${key}`"> <ChevronDoubleRightIcon class="size-6 text-zinc-950 hover:text-indigo-600 hover:font-bold" /> </fwb-a>
        </fwb-table-cell>
    </fwb-table-row>
</fwb-table-body>
</fwb-table>

</div>

</template>

<style scoped>
</style>