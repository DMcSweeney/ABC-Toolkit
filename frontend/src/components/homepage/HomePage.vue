<script>
import axios from 'axios';
import ProjectEntry from './ProjectEntry.vue';
import popupViewer from '../popupViewer.vue';
import { FolderPlusIcon } from '@heroicons/vue/24/solid'
import jobForm from './JobForm.vue';


export default {
    name: 'HomePage',
    data() {
        return {
            projectInfo: '',
            jobForm: true,
        }
    },
    methods: {
        fetchProjectList() {
            console.log("Fetching projects");
            const url = `${import.meta.env.VITE_BACKEND_URI}/api/database/get_project_info`
            axios.get(url)
                .then((res) => {
                    this.projectInfo = res.data.data;
                }).catch((err) => {
                    console.error(err);
                })
        },
        SubmitJob(){
            console.log("Submitting a new job");
            this.jobForm = true;
        },
        closeForm() {
            this.jobForm = false;
        },

    },
    created() {
        // Get a list of projects
        this.fetchProjectList();
    },
    components: {ProjectEntry, FolderPlusIcon, popupViewer, jobForm}
}

</script>


<template>

    <div class="flex m-auto pt-5 w-full pb-5">
        <p class="text-stone-200 text-4xl align-center mx-auto"> Projects </p>
    </div>
    <div class="m-auto bg-zinc-900 w-2/3 border border-black py-3 flex-1 rounded">
        <div class="w-5/6 flex m-auto pt-2 text-xl text-white grid grid-cols-4 px-2">
            <div class="content-center"> Name </div>
            <div class="content-center"> # patients </div>
            <div class="content-center"> # images </div>
            <div class="content-right align-end">
            <router-link :to="'/submit_job'">
                <button @click="SubmitJob();"
                 class="text-xl w-full h-10 hover:border border-stone-400 bg-zinc-900 rounded m-auto
                   text-green-500 hover:text-white hover:font-bold hover:cursor-pointer">
                    Submit Jobs
                </button>
            </router-link>
            
            </div>
        </div>
        <ul v-for="project in projectInfo">
            <div class="flex justify-center m-auto pb-2">
                <ProjectEntry :name=project.name :num_patients=project.num_patients :num_images=project.num_images>
                </ProjectEntry>
            </div>
        </ul>
    </div>



</template>


<style scoped>

</style>