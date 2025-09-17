<script>
import axios from 'axios';
import PatientTable from './PatientTable.vue';

export default {
    name: 'ProjectPage',
    data() {
        return {
            patients: '',
            project: this.$route.params.project,
            sanity_route: `${this.$route.path}/sanity/ `
        }
    },
    methods: {
        FetchPatients(){
            const url = `${import.meta.env.VITE_BACKEND_URI}/api/database/get_patients_in_project?project=${this.project}`
            axios.get(url).then( (res) => {
                
                this.patients=res.data.data
            }).catch((err) => {
                console.log(err);
            })

        }

    },
    created() {
        this.FetchPatients();
    },      
    props: [],
    components: {PatientTable}
}

</script>


<template>
    <div class="flex mx-auto pt-5 w-full pb-5 justify-center grid-cols-3 content-center">
        <div class="row">
            <div class="col"></div>
            <div class="col">
                <p class="text-stone-200 text-2xl align-center mx-auto">Project: {{ project }} </p>
                <a :href=sanity_route class="text-green-500 text-2xl hover:text-white"> Check predictions </a>
            </div>
            <div class="col">
                <div class="mx-auto">
                
                </div>
            </div>

        </div>
    </div>
    <div class="row">
            <div class="col"></div>
            <div class="col">
                <!-- Patients -->
                <PatientTable :patients=patients />
            </div>
            <div class="col"></div>
        </div>


</template>


<style scoped>
</style>