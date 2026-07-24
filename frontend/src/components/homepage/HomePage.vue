<script>
import api from '@/api/client';
import ProjectEntry from './ProjectEntry.vue';
import Card from '../ui/Card.vue';
import Button from '../ui/Button.vue';
import LoadingState from '../ui/LoadingState.vue';
import EmptyState from '../ui/EmptyState.vue';
import { FolderIcon, PlusIcon, ArrowsRightLeftIcon, CircleStackIcon, QueueListIcon } from '@heroicons/vue/24/outline';


export default {
    name: 'HomePage',
    data() {
        return {
            projectInfo: [],
            loading: true,
            FolderIcon,
            PlusIcon,
            ArrowsRightLeftIcon,
            CircleStackIcon,
            QueueListIcon,
            // Same env-var swap HeaderTab.vue uses to derive the Mongo Express / RQ Dashboard URLs.
            db_url: import.meta.env.VITE_BACKEND_URI.replace(import.meta.env.VITE_BACKEND_PORT, import.meta.env.VITE_MONGO_EXPRESS_PORT),
            jobs_url: `${import.meta.env.VITE_BACKEND_URI}/rq-dashboard`,
        }
    },
    computed: {
        totalPatients() {
            return this.projectInfo.reduce((sum, p) => sum + p.num_patients, 0);
        },
        totalImages() {
            return this.projectInfo.reduce((sum, p) => sum + p.num_images, 0);
        },
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
    components: {ProjectEntry, Card, Button, LoadingState, EmptyState, PlusIcon, ArrowsRightLeftIcon, CircleStackIcon, QueueListIcon},
}

</script>


<template>

    <div class="w-11/12 xl:w-4/5 mx-auto pt-8 pb-10">
        <div class="mb-8">
            <p class="text-ink-primary text-4xl font-bold tracking-tight">ABC Toolkit</p>
            <p class="text-ink-muted text-sm mt-1">Automatic body composition analysis for CT / MR / CBCT scans</p>
        </div>

        <div class="flex flex-col lg:flex-row gap-6 items-start">
            <!-- Main: project list -->
            <div class="flex-1 w-full min-w-0">
                <Card padding="sm">
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
                        <div class="w-5/6 flex m-auto pt-2 text-xl text-ink-primary grid grid-cols-3 px-2">
                            <div class="content-center"> Name </div>
                            <div class="content-center"> # patients </div>
                            <div class="content-center"> # images </div>
                        </div>
                        <ul>
                            <li v-for="project in projectInfo" :key="project.name" class="flex justify-center m-auto pb-2">
                                <ProjectEntry :name=project.name :num_patients=project.num_patients :num_images=project.num_images>
                                </ProjectEntry>
                            </li>
                        </ul>
                    </template>
                </Card>
            </div>

            <!-- Rail: primary CTA, quick links, summary stats -->
            <div class="w-full lg:w-72 flex-shrink-0 flex flex-col gap-4">
                <Card padding="md">
                    <p class="text-ink-primary font-bold pb-1">Process data</p>
                    <p class="text-ink-muted text-sm pb-3">You'll need a CSV with paths to your data. Data should be visible from the tool.</p>
                    <Button to="/submit_job" variant="primary" class="w-full">
                        <PlusIcon class="size-5" /> Create Job
                    </Button>
                    <Button to="/assign_project" variant="secondary" class="w-full mt-2">
                        <ArrowsRightLeftIcon class="size-5" /> Assign to Project
                    </Button>
                </Card>

                <Card padding="sm">
                    <p class="text-ink-secondary text-xs font-bold uppercase tracking-wide pb-2">Quick links</p>
                    <a :href="db_url" target="_blank" rel="noopener noreferrer" class="flex items-center gap-2 py-2 text-ink-secondary hover:text-brand-400 transition-colors duration-150" aria-label="Open database viewer (opens in a new tab)">
                        <CircleStackIcon class="size-5" /> Database
                    </a>
                    <a :href="jobs_url" target="_blank" rel="noopener noreferrer" class="flex items-center gap-2 py-2 text-ink-secondary hover:text-brand-400 transition-colors duration-150" aria-label="Open job queue dashboard (opens in a new tab)">
                        <QueueListIcon class="size-5" /> Job Queue
                    </a>
                </Card>

                <Card v-if="projectInfo.length" padding="sm">
                    <div class="grid grid-cols-3 gap-2 text-center">
                        <div>
                            <p class="text-2xl font-bold text-ink-primary">{{ projectInfo.length }}</p>
                            <p class="text-ink-muted text-xs">Projects</p>
                        </div>
                        <div>
                            <p class="text-2xl font-bold text-ink-primary">{{ totalPatients }}</p>
                            <p class="text-ink-muted text-xs">Patients</p>
                        </div>
                        <div>
                            <p class="text-2xl font-bold text-ink-primary">{{ totalImages }}</p>
                            <p class="text-ink-muted text-xs">Images</p>
                        </div>
                    </div>
                </Card>
            </div>
        </div>
    </div>

</template>


<style scoped>

</style>
