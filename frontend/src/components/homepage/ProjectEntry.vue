<script>
import { FolderOpenIcon, TrashIcon, ArrowDownTrayIcon, PencilIcon } from '@heroicons/vue/24/solid'
import axios from 'axios';
import PopupViewer from '../popupViewer.vue';

export default {
    name: 'ProjectEntry',
    data() {
        return {
            renameProjectWindow: false,
            projectName: null,
            newProjectName: null,
        }
    },
    methods: {
        DeleteProject(project){

            if(confirm(`Do you really want to delete project: ${project}?`)) {
                console.log("Deleting project");
                // TODO actually delete project in db and output dirv (or move to an archive?)
            }
            
        },
        DownloadResults(name){
            //const payload = {"project": name, "format": "metric", "download": "True"};
            const path = `${import.meta.env.VITE_BACKEND_URI}/api/post_process/get_stats_for_project_v2?project=${name}&download=True`;
            axios({url: path, method: "GET", responseType: 'blob'})
            .then((response) => {
                console.log(response);
                // create file link in browser's memory
                const href = URL.createObjectURL(response.data);

                // create "a" HTML element with href to file & click
                const link = document.createElement('a');
                link.href = href;
                link.setAttribute('download', `${name}_statistics.csv`); //or any other extension
                document.body.appendChild(link);
                link.click();

                // clean up "a" element & remove ObjectURL
                document.body.removeChild(link);
                URL.revokeObjectURL(href);
            })
            
        },
        RenameProject(){
            console.log(`Changing project ${this.projectName} to ${this.newProjectName}`)
            console.log(typeof(this.newProjectName))
            if (this.isValid(this.newProjectName)) {
                console.log("Valid input")
            } else {
                window.alert("Invalid input: no spaces or special chars allowed");
            }

            const payload = {'_id': '*', 'current_project': this.projectName, 'new_project': this.newProjectName}
            const path = `${import.meta.env.VITE_BACKEND_URI}/api/database/change_project`
            console.log(`Sending ${payload} to ${path}`)
            axios.post(path, payload, {headers: {'Content-Type': 'application/json',}})
            .then((res) => {
                console.log(res)
                this.renameProjectWindow = false;
                this.$router.go(); // Reload page
            })
            .catch((err) => {
                console.log(err)
            })


        },
        isValid (text) {
            
            // Check not empty AND matches only alphanumeric (no spaces/special chars)
            return text.length > 0 && /^[a-zA-Z0-9]+$/.test(text)
        },
    },
    props: ['name', 'num_patients', 'num_images'],
    components: { PopupViewer, FolderOpenIcon, TrashIcon, ArrowDownTrayIcon, PencilIcon}
}


</script>

<template>
    <PopupViewer v-show="renameProjectWindow" :height="'200px'">
        <button class="absolute top-10 text-zinc-950 rounded bg-white h-6" @click="renameProjectWindow = false"> 
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
            <path stroke-linecap="round" stroke-linejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
        
        </button>

            <div class="flex justify-center w-full h-20">
                <div class="flex justify-center items-center">
                <p class="text-stone-200 text-xl">Rename Project: <a class="text-green-400"> {{ this.projectName }} </a> </p>
                <input v-model="newProjectName" placeholder="New project name" class="border border-gray-300 rounded w-full max-w-md h-10" />
                <div class="flex">
                    <button class="bg-green-400 hover:bg-green-600 text-zinc-900 h-10 w-20 rounded shadow-green-300 font-extrabold" @click="RenameProject()">Change</button>
                </div>
                
            </div>
        </div>

        
        
        


    </PopupViewer>

    <div
        class="w-5/6 h-12 text-stone-200 hover:border hover:border-black bg-zinc-800 hover:bg-zinc-800 inline-block rounded grid grid-cols-4">
        <!-- Project name -->
        <div class="align-start content-center ml-3 ">
            {{ name }}
        </div>
        <!-- Number of patients -->
        <div class="content-center ml-3">
            {{ num_patients }}
        </div>
        <!-- Number of images -->
        <div class="content-center ml-3">
            {{ num_images }}
        </div>
        <!-- Links to project -->
        <div class="flex m-auto justify-end hover:text-indigo-400 mr-3">
            <p class="">
                <a :href="'/' + name">
                    <FolderOpenIcon class="size-6 text-stone-200 hover:text-indigo-400" />
                </a>
            </p>
            <p class="pl-3">
                <a @click="DownloadResults(name);">
                    <ArrowDownTrayIcon class="size-6 text-stone-200 hover:text-indigo-400" />
                </a>
            </p>
            <p class="pl-3">
                <a @click="renameProjectWindow=true; projectName=name">
                    <PencilIcon class="size-6 text-stone-200 hover:text-indigo-400" />
                </a>
            </p>
            <p class="pl-3">
                <a @click="DeleteProject(name);">
                    <TrashIcon class="size-6 text-stone-200 hover:text-indigo-400" />
                </a>
            </p>

        </div>
    </div>

</template>



<style scoped>
</style>