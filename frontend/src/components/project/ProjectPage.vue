<script>
import api from '@/api/client';
import PatientTable from './PatientTable.vue';
import Button from '../ui/Button.vue';
import LoadingState from '../ui/LoadingState.vue';
import EmptyState from '../ui/EmptyState.vue';

export default {
    name: 'ProjectPage',
    data() {
        return {
            patient_info: {},
            loading: true,
            project: this.$route.params.project,
            sanity_route: `${this.$route.path}/sanity/ `
        }
    },
    methods: {
        FetchPatients(){
            this.loading = true;
            api.get('/api/database/get_patients_in_project', { params: { project: this.project } })
                .then((res) => {
                    this.patient_info = res.data.data;
                }).catch(() => {
                    // Error already surfaced via toast by the shared api client.
                }).finally(() => {
                    this.loading = false;
                })
        },
        gotoSanity(){
            this.$router.push(`${this.$route.path}/sanity/`)
        }

    },
    created() {
        this.FetchPatients();
    },
    props: [],
    components: {PatientTable, Button, LoadingState, EmptyState}
}

</script>


<template>
    <div class="flex flex-grid mx-auto pt-5 w-4/5 pb-5 justify-center font-bold">
        <p class="text-ink-primary text-2xl">Project: <a class="text-green-400"> {{ project }} </a></p>
        <Button variant="pass" @click="gotoSanity();" class="mx-10"> Check predictions </Button>
    </div>
    <LoadingState v-if="loading" label="Loading patients..." />
    <EmptyState
        v-else-if="!Object.keys(patient_info).length"
        title="No patients found"
        message="No patients have been submitted to this project yet."
    />
    <div v-else>
        <PatientTable :patients=patient_info />
    </div>


</template>


<style scoped>
</style>