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
    components: {  
        FwbA,
        FwbTable,
        FwbTableBody,
        FwbTableCell,
        FwbTableHead,
        FwbTableHeadCell,
        FwbTableRow
    }
}
</script>

<template>
<fwb-table hoverable stripped class="w-3/4 mx-auto mt-10 text-left bg-zinc-900">

    <fwb-table-head class="h-10 py-10 bg-zinc-900 text-stone-200 text-4xl">
        <fwb-table-head-cell>Patient ID</fwb-table-head-cell>
        <!-- <fwb-table-head-cell>View</fwb-table-head-cell> -->
    </fwb-table-head>

    <fwb-table-body class="bg-zinc-900 text-black m-auto">
        <fwb-table-row v-for="item in this.patients.slice(0, 10)" class=" bg-black h-8 border border-zinc-800 hover:shadow-lg" :href="`${this.$route.path}/${item.patient_id}`">
            <fwb-table-cell>{{item.patient_id}}</fwb-table-cell>
            <fwb-table-cell>
                <fwb-a :href="`${this.$route.path}/weights/${item.patient_id}`">LINK</fwb-a>    
            </fwb-table-cell>
        </fwb-table-row>
    </fwb-table-body>

</fwb-table>
</template>

<style scoped>
</style>