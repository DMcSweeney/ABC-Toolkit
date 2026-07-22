<script>
import { FolderOpenIcon, TrashIcon, ArrowDownTrayIcon, PencilIcon } from '@heroicons/vue/24/solid'
import api from '@/api/client';
import { useToastStore } from '@/stores/toast';
import Modal from '../ui/Modal.vue';
import Button from '../ui/Button.vue';
import Input from '../ui/Input.vue';

export default {
    name: 'ProjectEntry',
    setup() {
        return { toast: useToastStore() };
    },
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
                this.toast.error("Deleting projects isn't available yet — contact an admin.");
            }
        },
        DownloadResults(name){
            api({url: '/api/post_process/get_stats_for_project_v2', method: "GET", params: {project: name, download: "True"}, responseType: 'blob'})
            .then((response) => {
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
            .catch(() => {
                // Error already surfaced via toast by the shared api client.
            })
        },
        RenameProject(){
            if (!this.isValid(this.newProjectName)) {
                this.toast.error("Invalid input: no spaces or special chars allowed");
                return;
            }

            const payload = {'_id': '*', 'current_project': this.projectName, 'new_project': this.newProjectName}
            api.post('/api/database/change_project', payload)
            .then(() => {
                this.renameProjectWindow = false;
                this.$router.go(); // Reload page
            })
            .catch(() => {
                // Error already surfaced via toast by the shared api client.
            })


        },
        isValid (text) {
            
            // Check not empty AND matches only alphanumeric (no spaces/special chars)
            return text.length > 0 && /^[a-zA-Z0-9]+$/.test(text)
        },
    },
    props: ['name', 'num_patients', 'num_images'],
    components: { Modal, Button, Input, FolderOpenIcon, TrashIcon, ArrowDownTrayIcon, PencilIcon}
}


</script>

<template>
    <Modal v-model="renameProjectWindow" title="Rename project" size="md">
        <div class="flex justify-center items-center gap-3 h-full">
            <p class="text-ink-primary text-xl">Rename project: <span class="text-green-400">{{ projectName }}</span></p>
            <Input v-model="newProjectName" placeholder="New project name" class="max-w-md" />
            <Button variant="pass" @click="RenameProject()">Change</Button>
        </div>
    </Modal>

    <div
        class="w-5/6 h-12 text-ink-primary hover:border hover:border-line-default bg-surface-card hover:bg-surface-raised inline-block rounded grid grid-cols-4">
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
        <div class="flex m-auto justify-end hover:text-brand-400 mr-3">
            <p class="">
                <router-link :to="'/' + name" :aria-label="`Open project ${name}`">
                    <FolderOpenIcon class="size-6 text-ink-secondary hover:text-brand-400" />
                </router-link>
            </p>
            <p class="pl-3">
                <button type="button" :aria-label="`Download results for ${name}`" @click="DownloadResults(name);">
                    <ArrowDownTrayIcon class="size-6 text-ink-secondary hover:text-brand-400" />
                </button>
            </p>
            <p class="pl-3">
                <button type="button" :aria-label="`Rename project ${name}`" @click="renameProjectWindow=true; projectName=name">
                    <PencilIcon class="size-6 text-ink-secondary hover:text-brand-400" />
                </button>
            </p>
            <p class="pl-3">
                <button type="button" :aria-label="`Delete project ${name}`" @click="DeleteProject(name);">
                    <TrashIcon class="size-6 text-ink-secondary hover:text-brand-400" />
                </button>
            </p>

        </div>
    </div>

</template>



<style scoped>
</style>