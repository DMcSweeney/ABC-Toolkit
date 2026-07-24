<script>
import api from '@/api/client';
import { useToastStore } from '@/stores/toast';
import Card from '../ui/Card.vue';
import Button from '../ui/Button.vue';
import Input from '../ui/Input.vue';

export default {
    name: 'AssignToProject',
    components: { Card, Button, Input },
    setup() {
        return { toast: useToastStore() };
    },
    data() {
        return {
            mode: 'single', // 'single' or 'csv'
            // Single-patient search
            patientId: '',
            searching: false,
            searched: false,
            projectGroups: [], // [{ project, series, selected }]
            targetProject: '',
            assigning: false,
            // CSV batch
            csvCurrentProject: '',
            csvNewProject: '',
            csvFile: null,
            uploadPercent: 0,
            submitting: false,
        }
    },
    methods: {
        isValidProjectName(name) {
            return /^[a-zA-Z0-9]+$/.test(name || '');
        },
        async searchPatient() {
            if (!this.patientId) {
                this.toast.error('Enter a Patient ID to search.');
                return;
            }
            this.searching = true;
            this.searched = false;
            try {
                const res = await api.get('/api/database/find_patient', { params: { patient_id: this.patientId } });
                this.projectGroups = (res.data.projects || []).map((group) => ({ ...group, selected: true }));
                this.searched = true;
                if (!this.projectGroups.length) {
                    this.toast.info(`No data found for patient ${this.patientId}.`);
                }
            } catch (err) {
                // Error already surfaced via toast by the shared api client.
            } finally {
                this.searching = false;
            }
        },
        async assignSelected() {
            if (!this.isValidProjectName(this.targetProject)) {
                this.toast.error('Target project name is required and can only contain letters/numbers.');
                return;
            }
            const groups = this.projectGroups.filter((g) => g.selected && g.project !== this.targetProject);
            if (!groups.length) {
                this.toast.error('Select at least one project group to move.');
                return;
            }

            this.assigning = true;
            let movedCount = 0;
            let skippedCount = 0;
            for (const group of groups) {
                try {
                    const res = await api.post('/api/database/reassign_patient', {
                        patient_id: this.patientId,
                        current_project: group.project,
                        new_project: this.targetProject,
                    }, { skipErrorToast: true });
                    movedCount += (res.data.series_uuids || []).length;
                } catch (err) {
                    skippedCount += 1;
                    const message = err.response?.data?.message || err.response?.data?.error || `Could not move series from ${group.project}.`;
                    this.toast.error(message);
                }
            }
            this.assigning = false;

            if (movedCount) {
                this.toast.success(`Moved ${movedCount} series to ${this.targetProject}.`);
            }
            if (skippedCount && !movedCount) {
                return;
            }
            // Refresh results so the view reflects the new state.
            await this.searchPatient();
        },
        handleFileSelect(event) {
            this.csvFile = event.target.files[0] || null;
        },
        async submitCsv() {
            if (!this.isValidProjectName(this.csvNewProject)) {
                this.toast.error('New project name is required and can only contain letters/numbers.');
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
            if (this.csvCurrentProject) formData.append('current_project', this.csvCurrentProject);
            formData.append('new_project', this.csvNewProject);
            formData.append('file', this.csvFile);

            this.submitting = true;
            this.uploadPercent = 0;
            try {
                const res = await api.post('/api/database/assign_patients_from_csv', formData, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                    onUploadProgress: (progressEvent) => {
                        this.uploadPercent = Math.round((100 * progressEvent.loaded) / progressEvent.total);
                    },
                });
                const results = res.data.results || [];
                const errors = results.filter((r) => r.error);
                const moved = results.length - errors.length;
                this.toast.success(`Assigned ${moved} patient(s) from ${results.length} row(s) in ${this.csvFile.name}.`);
                if (errors.length) {
                    this.toast.error(`${errors.length} row(s) skipped — e.g. ${errors[0].error}`);
                }
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
    <p class="text-ink-primary text-4xl font-bold tracking-tight align-center mx-auto"> Assign to project </p>
</div>

<Card class="m-auto w-1/2">

    <!-- Mode toggle -->
    <div class="flex justify-center gap-2 pb-6">
        <Button type="button" :variant="mode === 'single' ? 'primary' : 'secondary'" @click="mode = 'single'">
            Search patient
        </Button>
        <Button type="button" :variant="mode === 'csv' ? 'primary' : 'secondary'" @click="mode = 'csv'">
            Batch (CSV)
        </Button>
    </div>

    <!-- SINGLE PATIENT SEARCH -->
    <div v-if="mode === 'single'" class="flex flex-col gap-4">
        <form @submit.prevent="searchPatient" class="flex gap-4 items-end">
            <Input v-model="patientId" label="Patient ID" placeholder="12345" class="flex-1" required />
            <Button type="submit" variant="secondary" :loading="searching">Search</Button>
        </form>

        <template v-if="searched && projectGroups.length">
            <div class="flex flex-col gap-2">
                <p class="text-ink-secondary text-sm">Found data in {{ projectGroups.length }} project(s). Uncheck any you don't want to move.</p>
                <label v-for="group in projectGroups" :key="group.project"
                    class="flex items-center gap-3 rounded border border-line-subtle bg-surface-raised px-3 py-2 cursor-pointer">
                    <input type="checkbox" v-model="group.selected" class="size-4">
                    <span class="text-ink-primary font-bold">{{ group.project }}</span>
                    <span class="text-ink-muted text-sm">
                        {{ group.series.length }} series ({{ [...new Set(group.series.map(s => s.modality))].join(', ') }})
                    </span>
                </label>
            </div>

            <Input v-model="targetProject" label="Move to project" placeholder="my_project" required />
            <p class="text-ink-muted text-xs">
                Typing a new project name creates it — projects are auto-created on first use.
            </p>
            <Button type="button" variant="pass" :loading="assigning" class="mx-auto w-40" @click="assignSelected">
                {{ assigning ? 'Assigning...' : 'Assign' }}
            </Button>
        </template>
    </div>

    <!-- CSV BATCH -->
    <form v-else @submit.prevent="submitCsv" class="flex flex-col gap-4">
        <Input v-model="csvCurrentProject" label="Current project (optional — defaults to Unassigned)" placeholder="Unassigned" />
        <Input v-model="csvNewProject" label="Move to project" placeholder="my_project" required />
        <div>
            <label class="block text-ink-secondary text-sm pb-1">
                CSV file (one row per patient; required column "patient_id"; optional per-row "current_project"/"new_project" overrides)
            </label>
            <label class="inline-block bg-surface-raised hover:border hover:border-line-default hover:cursor-pointer hover:bg-line-subtle rounded h-10 leading-10 px-4 text-green-700 dark:text-green-500 font-bold text-xl" for="assign-csv-file-input">
                {{ csvFile ? csvFile.name : 'Choose CSV file' }}
            </label>
            <input ref="csvFileInput" id="assign-csv-file-input" type="file" @change="handleFileSelect" accept="text/csv,.csv" hidden>
        </div>
        <div v-if="submitting && uploadPercent > 0" class="text-ink-muted text-sm">
            Uploading: {{ uploadPercent }}%
        </div>
        <Button type="submit" variant="pass" :loading="submitting" class="mx-auto w-40">
            {{ submitting ? 'Submitting...' : 'Upload & assign' }}
        </Button>
    </form>

</Card>

</template>


<style scoped>

</style>
