<script>
import axios from 'axios';
import PatientTable from './PatientTable.vue';

export default {
    name: 'ProjectPage',
    data() {
        return {
            patient_info: new Object(),
            project: this.$route.params.project,
            sanity_route: `${this.$route.path}/sanity/ `
        }
    },
    methods: {
        FetchPatients(){
            const url = `${import.meta.env.VITE_BACKEND_URI}/api/database/get_patients_in_project?project=${this.project}`
            axios.get(url).then( (res) => {
                this.patient_info=res.data.data
            }).catch((err) => {
                console.log(err);
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
    components: {PatientTable}
}

</script>


<template>
    <div class="flex flex-grid mx-auto pt-5 w-4/5 pb-5 justify-center font-bold">
        <p class="text-stone-200 text-2xl">Project: <a class="text-green-400"> {{ project }} </a></p>
        <button @click="gotoSanity();" class="font-normal bg-green-400 rounded mx-10 py-1 px-2 text-xl hover:border hover:border-black hover:font-bold"> Check predictions </button>
    </div>
    <div>
        <PatientTable :patients=patient_info />
    </div>
    


</template>


<style scoped>
</style>