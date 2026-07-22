<script>
import api from '@/api/client';
import ProjectEntry from './ProjectEntry.vue';
import Card from '../ui/Card.vue';
import Button from '../ui/Button.vue';
import LoadingState from '../ui/LoadingState.vue';
import EmptyState from '../ui/EmptyState.vue';
import { FolderIcon } from '@heroicons/vue/24/outline';


export default {
    name: 'HomePage',
    data() {
        return {
            projectInfo: [],
            loading: true,
            FolderIcon,
        }
    },
    methods: {
        fetchProjectList() {
            this.loading = true;
            api.get('/api/database/get_project_info')
                .then((res) => {
                    this.projectInfo = res.data.data;
                }).catch(() => {
                    // Error already surfaced via toast by the shared api client.
                }).finally(() => {
                    this.loading = false;
                })
        },
    },
    created() {
        // Get a list of projects
        this.fetchProjectList();
    },
    components: {ProjectEntry, Card, Button, LoadingState, EmptyState},
}

</script>


<template>

    <div class="flex m-auto pt-5 w-full pb-5">
        <p class="text-ink-primary text-4xl font-bold tracking-tight align-center mx-auto"> Projects </p>
    </div>
    <Card padding="sm" class="m-auto w-2/3">
        <LoadingState v-if="loading" label="Loading projects..." />
        <EmptyState
            v-else-if="!projectInfo.length"
            title="No projects yet"
            message="Submit a job to create your first project."
            actionLabel="Submit a job"
            actionTo="/submit_job"
            :icon="FolderIcon"
        />
        <template v-else>
            <div class="w-5/6 flex m-auto pt-2 text-xl text-ink-primary grid grid-cols-4 px-2">
                <div class="content-center"> Name </div>
                <div class="content-center"> # patients </div>
                <div class="content-center"> # images </div>
                <div class="content-right align-end">
                    <Button to="/submit_job" variant="ghost" class="w-full text-brand-400 hover:text-brand-300">
                        Submit Jobs
                    </Button>
                </div>
            </div>
            <ul>
                <li v-for="project in projectInfo" :key="project.name" class="flex justify-center m-auto pb-2">
                    <ProjectEntry :name=project.name :num_patients=project.num_patients :num_images=project.num_images>
                    </ProjectEntry>
                </li>
            </ul>
        </template>
    </Card>



</template>


<style scoped>

</style>