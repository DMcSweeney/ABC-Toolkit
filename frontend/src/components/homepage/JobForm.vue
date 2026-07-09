<script>
import api from '@/api/client';
import { useToastStore } from '@/stores/toast';

// Mirrors the vertebral levels registered in backend/src/abcTK/segment/model_bank.py.
// There's no endpoint that lists them dynamically, so this needs a manual update if that
// file's keys change.
const KNOWN_VERTEBRAE = ['C3', 'T4', 'T9', 'T12', 'L3', 'L5', 'Sacrum', 'Thigh'];

export default {
    name: 'JobForm',
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
    <p class="text-stone-200 text-4xl align-center mx-auto"> Submit jobs </p>
</div>

<div class="m-auto bg-zinc-900 w-1/2 border shadow shadow-black border-black p-6 flex-1 rounded">

    <!-- Mode toggle -->
    <div class="flex justify-center gap-2 pb-6">
        <button type="button" @click="mode = 'single'"
            class="rounded px-4 py-2 font-bold"
            :class="mode === 'single' ? 'bg-indigo-700 text-stone-200' : 'bg-zinc-800 text-stone-400 hover:bg-zinc-700'">
            Single scan
        </button>
        <button type="button" @click="mode = 'csv'"
            class="rounded px-4 py-2 font-bold"
            :class="mode === 'csv' ? 'bg-indigo-700 text-stone-200' : 'bg-zinc-800 text-stone-400 hover:bg-zinc-700'">
            Batch (CSV)
        </button>
    </div>

    <!-- SINGLE SCAN FORM -->
    <form v-if="mode === 'single'" @submit.prevent="submitSingleJob" class="flex flex-col gap-4">
        <div>
            <label class="block text-stone-300 text-sm pb-1">Project name</label>
            <input v-model="singleProject" type="text" placeholder="my_project"
                class="rounded text-xl px-2 bg-white h-10 w-full" required>
        </div>
        <div>
            <label class="block text-stone-300 text-sm pb-1">Input path (as seen inside the container, e.g. /data/inputs/patient_01)</label>
            <input v-model="inputPath" type="text" placeholder="/data/inputs/patient_01"
                class="rounded text-xl px-2 bg-white h-10 w-full font-mono" required>
        </div>
        <div class="flex gap-4">
            <div class="flex-1">
                <label class="block text-stone-300 text-sm pb-1">Vertebral level</label>
                <select v-model="vertebra" class="rounded text-xl px-2 bg-white h-10 w-full" required>
                    <option value="" disabled>Select a level</option>
                    <option v-for="level in knownVertebrae" :key="level" :value="level">{{ level }}</option>
                </select>
            </div>
            <div class="w-1/3">
                <label class="block text-stone-300 text-sm pb-1">Extra slices each side</label>
                <input v-model.number="numSlices" type="number" min="0"
                    class="rounded text-xl px-2 bg-white h-10 w-full">
            </div>
        </div>
        <p class="text-stone-500 text-xs">
            Submits a spine-labelling job, then a dependent segmentation job at the chosen level once labelling finishes.
        </p>
        <button type="submit" :disabled="submitting"
            class="mx-auto bg-green-500 hover:bg-green-600 disabled:bg-zinc-700 disabled:text-stone-500 text-zinc-900 font-bold rounded h-10 w-40">
            {{ submitting ? 'Submitting...' : 'Submit job' }}
        </button>
    </form>

    <!-- CSV BATCH FORM -->
    <form v-else @submit.prevent="submitCsvJobs" class="flex flex-col gap-4">
        <div>
            <label class="block text-stone-300 text-sm pb-1">Project name</label>
            <input v-model="csvProject" type="text" placeholder="my_project"
                class="rounded text-xl px-2 bg-white h-10 w-full" required>
        </div>
        <div>
            <label class="block text-stone-300 text-sm pb-1">
                CSV file (one row per scan; required column "input_path"; optional "job_type" of spine/segment/full, plus any other request argument as a column)
            </label>
            <label class="inline-block bg-black hover:border hover:border-white hover:cursor-pointer hover:bg-zinc-800 rounded h-10 leading-10 px-4 text-green-500 font-bold text-xl" for="file-input">
                {{ csvFile ? csvFile.name : 'Choose CSV file' }}
            </label>
            <input ref="csvFileInput" id="file-input" type="file" @change="handleFileSelect" accept="text/csv,.csv" hidden>
        </div>
        <div v-if="submitting && uploadPercent > 0" class="text-stone-400 text-sm">
            Uploading: {{ uploadPercent }}%
        </div>
        <button type="submit" :disabled="submitting"
            class="mx-auto bg-green-500 hover:bg-green-600 disabled:bg-zinc-700 disabled:text-stone-500 text-zinc-900 font-bold rounded h-10 w-40">
            {{ submitting ? 'Submitting...' : 'Upload & submit' }}
        </button>
    </form>

</div>

</template>


<style scoped>

</style>
