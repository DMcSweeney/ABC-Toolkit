<script>
import api from '@/api/client';
import { useToastStore } from '@/stores/toast';
import Card from '../ui/Card.vue';
import Button from '../ui/Button.vue';
import Input from '../ui/Input.vue';
import Select from '../ui/Select.vue';

// Mirrors the vertebral levels registered in backend/src/abcTK/segment/model_bank.py.
// There's no endpoint that lists them dynamically, so this needs a manual update if that
// file's keys change.
const KNOWN_VERTEBRAE = ['C3', 'T4', 'T9', 'T12', 'L3', 'L5', 'Sacrum', 'Thigh'];

export default {
    name: 'JobForm',
    components: { Card, Button, Input, Select },
    setup() {
        return { toast: useToastStore() };
    },
    data() {
        return {
            mode: 'single', // 'single' or 'csv'
            knownVertebrae: KNOWN_VERTEBRAE,
            submitting: false,
            // Single-scan form fields
            singleProject: '',
            inputPath: '',
            vertebra: '',
            numSlices: 0,
            // CSV form fields
            csvProject: '',
            csvFile: null,
            uploadPercent: 0,
        }
    },
    methods: {
        hasWhiteSpace(s) {
            return s.indexOf(' ') >= 0;
        },
        isValidProjectName(name) {
            return !!name && !this.hasWhiteSpace(name);
        },
        async submitSingleJob() {
            if (!this.isValidProjectName(this.singleProject)) {
                this.toast.error('Project name is required and cannot contain spaces.');
                return;
            }
            if (!this.inputPath) {
                this.toast.error('Input path is required.');
                return;
            }
            if (!this.vertebra) {
                this.toast.error('Select a vertebral level.');
                return;
            }

            this.submitting = true;
            try {
                const spineRes = await api.post('/api/jobs/infer/spine', {
                    project: this.singleProject,
                    input_path: this.inputPath,
                });
                const spineJobId = spineRes.data['job-ID'];

                await api.post('/api/jobs/infer/segment', {
                    project: this.singleProject,
                    input_path: this.inputPath,
                    vertebra: this.vertebra,
                    num_slices: String(this.numSlices),
                    depends_on: spineJobId,
                });

                this.toast.success(`Jobs submitted for ${this.inputPath}. Track progress under Jobs in the header, or via /api/jobs/query_job.`);
                this.inputPath = '';
            } catch (err) {
                // Error already surfaced via toast by the shared api client.
            } finally {
                this.submitting = false;
            }
        },
        handleFileSelect(event) {
            this.csvFile = event.target.files[0] || null;
        },
        async submitCsvJobs() {
            if (!this.isValidProjectName(this.csvProject)) {
                this.toast.error('Project name is required and cannot contain spaces.');
                return;
            }
            if (!this.csvFile) {
                this.toast.error('Choose a CSV file first.');
                return;
            }
            if (this.csvFile.type !== 'text/csv' && !this.csvFile.name.endsWith('.csv')) {
                this.toast.error('Please upload a CSV file.');
                return;
            }

            const formData = new FormData();
            formData.append('project', this.csvProject);
            formData.append('file', this.csvFile);

            this.submitting = true;
            this.uploadPercent = 0;
            try {
                const res = await api.post('/api/jobs/submit_jobs_from_csv', formData, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                    onUploadProgress: (progressEvent) => {
                        this.uploadPercent = Math.round((100 * progressEvent.loaded) / progressEvent.total);
                    },
                });
                const numJobs = res.data.jobs?.length ?? 0;
                this.toast.success(`Submitted jobs for ${numJobs} row(s) from ${this.csvFile.name}.`);
                this.csvFile = null;
                this.$refs.csvFileInput.value = '';
            } catch (err) {
                // Error already surfaced via toast by the shared api client.
            } finally {
                this.submitting = false;
                this.uploadPercent = 0;
            }
        },
    }
}

</script>

<template>

<div class="flex m-auto py-5 w-full">
    <p class="text-ink-primary text-4xl font-bold tracking-tight align-center mx-auto"> Submit jobs </p>
</div>

<Card class="m-auto w-1/2">

    <!-- Mode toggle -->
    <div class="flex justify-center gap-2 pb-6">
        <Button type="button" :variant="mode === 'single' ? 'primary' : 'secondary'" @click="mode = 'single'">
            Single scan
        </Button>
        <Button type="button" :variant="mode === 'csv' ? 'primary' : 'secondary'" @click="mode = 'csv'">
            Batch (CSV)
        </Button>
    </div>

    <!-- SINGLE SCAN FORM -->
    <form v-if="mode === 'single'" @submit.prevent="submitSingleJob" class="flex flex-col gap-4">
        <Input v-model="singleProject" label="Project name" placeholder="my_project" required />
        <Input v-model="inputPath" label="Input path (as seen inside the container, e.g. /data/inputs/patient_01)"
            placeholder="/data/inputs/patient_01" class="font-mono" required />
        <div class="flex gap-4">
            <Select v-model="vertebra" label="Vertebral level" :options="knownVertebrae" placeholder="Select a level"
                class="flex-1" required />
            <Input v-model.number="numSlices" label="Extra slices each side" type="number" class="w-1/3" />
        </div>
        <p class="text-ink-muted text-xs">
            Submits a spine-labelling job, then a dependent segmentation job at the chosen level once labelling finishes.
        </p>
        <Button type="submit" variant="pass" :loading="submitting" class="mx-auto w-40">
            {{ submitting ? 'Submitting...' : 'Submit job' }}
        </Button>
    </form>

    <!-- CSV BATCH FORM -->
    <form v-else @submit.prevent="submitCsvJobs" class="flex flex-col gap-4">
        <Input v-model="csvProject" label="Project name" placeholder="my_project" required />
        <div>
            <label class="block text-ink-secondary text-sm pb-1">
                CSV file (one row per scan; required column "input_path"; optional "job_type" of spine/segment/full, plus any other request argument as a column)
            </label>
            <label class="inline-block bg-surface-raised hover:border hover:border-line-default hover:cursor-pointer hover:bg-line-subtle rounded h-10 leading-10 px-4 text-green-500 font-bold text-xl" for="file-input">
                {{ csvFile ? csvFile.name : 'Choose CSV file' }}
            </label>
            <input ref="csvFileInput" id="file-input" type="file" @change="handleFileSelect" accept="text/csv,.csv" hidden>
        </div>
        <div v-if="submitting && uploadPercent > 0" class="text-ink-muted text-sm">
            Uploading: {{ uploadPercent }}%
        </div>
        <Button type="submit" variant="pass" :loading="submitting" class="mx-auto w-40">
            {{ submitting ? 'Submitting...' : 'Upload & submit' }}
        </Button>
    </form>

</Card>

</template>


<style scoped>

</style>
