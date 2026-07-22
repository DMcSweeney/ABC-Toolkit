<script>
// QA page organised by patient
// Should be able to access all predictions for a patient from here 
// Add patientID arg in path to allow for searching specific patients
import api from '@/api/client';
import Modal from '../ui/Modal.vue';
import Spinner from '../ui/Spinner.vue';
import Badge from '../ui/Badge.vue';
import failureForm from './FailureForm_v2.vue';
import Multiselect from 'vue-multiselect';
import { useToastStore } from '@/stores/toast';

export default {
    name: 'PatientPredictions',
    setup() {
        return { toast: useToastStore() };
    },
    data() {
        return {
            imageObj: Object(), // Object where keys: patientIDs, values: list of ids for that patient
            imageLoading: false, // Whether the main QA image is currently being fetched
            statusObj: {'to-do': [], 'passed': [], 'failed': []}, //Object where keys: oneof ['to-do', 'failed', 'passed'] and values are arrays of patient IDs in each category
            statusOptions: ['to-do', 'failed', 'passed'],
            filterStatus: Object(), // Object for keeping track of filtering 
            patientList: Array(), // List of patients
            idList: Array(), // Object of image ids: acquisition dates for this patient
            currentPID: '', //String: Current patient ID
            patientIdx: 0, // Index to use to iterate through patients
            seriesIdx: 0, // Index to use to iterate through series_uuids for currentpID
            disableSpine: false, // Bool to enable/disable spine pop-up
            showSpineSanity: false, // Display spine QA image -- this displays the popup vs disableSpine that disables/enables it
            spineSrc: '', // Src for spine image
            disableRegistration: false, // Bool to enable/disable registration pop-up
            showRegistrationSanity: false, // Display registration QC image -- this displays the popup vs disableRegistration that disables/enables it
            registrationSrc: '', // Src for registration QC image
            QAsrc: '', // Src for QA image
            project: this.$route.params.project, // Get project name from route
            vertebra: this.$route.params.vertebra,
            // Image specific info 
            status: 2,
            input_path: '',
            acquisition_date: '',
            compartments: Array(), // List of compartments with QA image
            current_uuid: '',
            qcReady: false,
            qc_report: Object(),// Object for holding values of the QC report -- e.g. failure modes, notes, etc...
            total_images: 0,
            passed_images: 0, // Num images that passed QA
            pass_rate: 0 // Placeholder for the image pass rate (num. images passed QA / total images)
        }
    },

    methods: {
        parseAcquisitionDate(dateStr) {
            // Dates are stored/displayed as dd-mm-YYYY — parse explicitly rather than
            // relying on string sort, which would order by day-of-month first.
            const [day, month, year] = dateStr.split('-').map(Number);
            return new Date(year, month - 1, day);
        },
        sortedIdList(patientID) {
            return Object.keys(this.imageObj[patientID]).sort((a, b) =>
                this.parseAcquisitionDate(this.imageObj[patientID][a]) - this.parseAcquisitionDate(this.imageObj[patientID][b])
            );
        },
        async fetchPatientList() {
            // Get JSON object of ALL patients and their images 
            // TODO only fetch patient IDs? then make another call to fetch UIDs for that patient? Currently, might take up a lot of mem. on big projects...
            await api.get('/api/patient_qa/fetch_patient_list', { params: { project: this.project, vertebra: this.vertebra } })
                .then((res) => {
                this.imageObj = res.data.image_dict;
                this.patientList = Object.keys(this.imageObj);
                if (Object.keys(this.$route.params.patient_id).length !== 0) {
                    // if patient id in query string
                    this.currentPID = this.$route.params.patient_id;
                } else{
                    // Filter based on TODO/success/fail and select a random patient
                    this.patientIdx = Math.floor(Math.random()*this.patientList.length)
                    this.currentPID = this.patientList[this.patientIdx]; // Select a random patient to show first
                }
                this.idList = this.sortedIdList(this.currentPID);
            })
                .catch(() => {
                // Error already surfaced via toast by the shared api client.
            });

            // Also fetch the statuses linked with patient IDs and use these to filter search
            this.fetchFilteredList();
        },
        fetchFilteredList(){
            api.get('/api/patient_qa/get_filtered_patient_list', { params: { project: this.project, vertebra: this.vertebra } })
                .then((res) => {
                    this.statusObj= res.data.status_dict;
                    // If to-do list is not empty, select a patient at random
                    if (this.statusObj['to-do'].length !== 0) {
                        this.patientIdx = Math.floor(Math.random()*this.statusObj['to-do'].length)
                        this.currentPID = this.statusObj['to-do'][this.patientIdx]; // Select a random patient to show first
                    } else if (this.statusObj['failed'].length !== 0) { // Otheriwse get a patient who failed
                        this.patientIdx = Math.floor(Math.random()*this.statusObj['failed'].length)
                        this.currentPID = this.statusObj['failed'][this.patientIdx]; // Select a random patient to show first
                    } else {
                        this.patientIdx = Math.floor(Math.random()*this.statusObj['passed'].length)
                        this.currentPID = this.statusObj['passed'][this.patientIdx]; // Select a random patient to show first
                    }
                })
                .catch(() => {
                    // Error already surfaced via toast by the shared api client.
            });
        },
        GetQAImage(_id) {
            // Wait for patient list to run, then request the relevant image, given the _id

            this.current_uuid = _id;
            this.GetSpine(_id)
            this.GetRegistration(_id)
            this.getQCReport(_id)
            this.getImagePassRate();
            this.imageLoading = true;
            api.get('/api/patient_qa/fetch_image_by_id', { params: { project: this.project, _id: _id, vertebra: this.vertebra } })
                .then((res) => {
                this.QAsrc = `data:image/png;base64, ` + res.data.image;
                this.status = res.data.status;
                this.input_path = res.data.input_path;
                this.acquisition_date = res.data.acquisition_date;
                this.compartments = res.data.compartments;
            })
                .catch(() => {
                // Error already surfaced via toast by the shared api client.
            })
                .finally(() => {
                this.imageLoading = false;
            });
        },
        NextImage(){
            var _id;
            this.seriesIdx++;
            if (this.seriesIdx <= this.idList.length - 1) {
                _id = this.idList[this.seriesIdx];
            }
            else {
                this.seriesIdx = 0;
                this.NextPatient();
            }
            this.GetQAImage(_id);
        },
        NextPatient(){
            this.patientIdx++;
            if (this.patientIdx <= this.patientList.length - 1) {
                this.currentPID = this.patientList[this.patientIdx];
            }
            else {
                this.patientIdx--;
                this.toast.info('That was the last patient!');
                return;
            }
            this.idList = this.sortedIdList(this.currentPID);
            this.GetQAImage(this.idList[0]);
        },
        PreviousImage() {
            // Fetch previous image
            var _id;
            this.seriesIdx--;
            if (this.seriesIdx >= 0) {
                _id = this.idList[this.seriesIdx];
            }
            else {
                this.seriesIdx = 0;
                this.PreviousPatient();
            }
            this.GetQAImage(_id);
        },
        PreviousPatient(){
            this.patientIdx--;
            if (this.patientIdx >= 0) {
                this.currentPID = this.patientList[this.patientIdx];
            }
            else {
                this.patientIdx = 0
                this.toast.info("You've reached the start");
                return;
            }
            this.idList = this.sortedIdList(this.currentPID);
            this.GetQAImage(this.idList[0]);
        },
        GetSpine(_id) {
            // Get the spine QC image and display
            api.post('/api/sanity/fetch_spine_by_id', null, { params: { project: this.project, _id: _id, vertebra: this.vertebra }, skipErrorToast: true })
                .then((res) => {
                this.spineSrc = `data:image/png;base64, ` + res.data.image;
                this.disableSpine = false;
            })
                .catch(() => {
                    // Not every scan has a spine QA image (e.g. segmentation-only pipelines) —
                    // disabling the button is a normal, expected outcome here, not an error.
                    this.disableSpine = true;
            });
        },
        GetRegistration(_id) {
            // Get the registration QC image (if this scan reused another scan's spine labelling
            // via registration, e.g. a CBCT) and display
            api.post('/api/sanity/fetch_registration_by_id', null, { params: { project: this.project, _id: _id, vertebra: this.vertebra }, skipErrorToast: true })
                .then((res) => {
                this.registrationSrc = `data:image/png;base64, ` + res.data.image;
                this.disableRegistration = false;
            })
                .catch(() => {
                    // Most scans (e.g. planning CTs) have no registration QC image - disabling
                    // the button is a normal, expected outcome here, not an error.
                    this.disableRegistration = true;
            });
        },
        getQCReport(_id){
            // Get the spine QC image and display
            api.get('/api/database/get_qc_report', { params: { project: this.project, _id: _id } })
                .then((res) => {
                    if (!!res.data.reports) { // If not null
                        this.qc_report = res.data.reports[0][1][this.vertebra];
                        this.qcReady = true;
                    } else {
                        this.qc_report = null;
                        this.qcReady = true;
                    }
                })
        },
        PassQA() {
            // Record QA pass
            api.post('/api/patient_qa/pass_qa', null, { params: { project: this.project, _id: this.current_uuid, vertebra: this.vertebra } })
                .then(() => {
                this.NextImage();
            })
                .catch(() => {
                // Error already surfaced via toast by the shared api client.
            });
        },
        ShowSpine() {
            // Reveal spine prediction
            this.showSpineSanity = true;
        },
        ShowRegistration() {
            // Reveal registration QC image
            this.showRegistrationSanity = true;
        },
        showFailForm() {
            this.$refs.failureFormComponent.showFailureForm = true;
        },
        active_uid(elem) {
            return this.current_uuid === elem;
        },
        changePatient(elem){
            this.currentPID = elem;
            this.seriesIdx = 0; 
            this.idList = this.sortedIdList(this.currentPID);
            const _id = this.idList[this.seriesIdx];
            this.GetQAImage(_id);
            this.$router.push({name: this.$router.currentRoute.name, params: {patient_id:elem}});  
        },
        filterPatients(){
            // Where filterstatus is true
            var keys = Object.keys(this.filterStatus).filter(k => this.filterStatus[k]);
            var patList = Array();
            for (var key of keys) {
                patList = patList.concat(this.statusObj[key]);
            }
            if (patList.length === 0) {
                this.toast.info(`No patients meeting criteria: ${keys}`);
                return;
            }
            // Then overwrite the patientList and reset indices
            this.patientList = patList;
            this.patientIdx = 0;
            this.currentPID = this.patientList[this.patientIdx];
            this.idList = this.sortedIdList(this.currentPID);
            this.seriesIdx = 0;
            this.GetQAImage(this.idList[this.seriesIdx]);
        },
        getImagePassRate(){
            // Method for querying current image pass rate -- should be done everytime a new image is displayed
            api.get('/api/patient_qa/get_image_pass_rate', { params: { project: this.project, vertebra: this.vertebra } })
            .then((res) => {
                this.total_images = res.data.total;
                this.passed_images = res.data.passed;
                this.pass_rate = res.data.pass_rate;
            })
            .catch(() => {
                // Error already surfaced via toast by the shared api client.
            })
        }
    },
    async created() {
        await this.fetchPatientList();
        const _id = this.idList[this.seriesIdx];
        this.GetQAImage(_id);
    },
    mounted() {
    },
    components: {Modal, Spinner, Badge, failureForm, Multiselect}
}


</script>


<template>
<!-- SPINE POP-UP -->
<Modal v-model="showSpineSanity" title="Spine QA" size="lg">
    <img class="m-auto h-full" alt="Spine labelling QA image" :src="spineSrc">
</Modal>

<!-- REGISTRATION POP-UP -->
<Modal v-model="showRegistrationSanity" title="Registration QA" size="lg">
    <img class="m-auto h-full" alt="CBCT-to-CT registration QA image" :src="registrationSrc">
</Modal>

    <!-- FAILURE POP-UP -->
<div v-if=this.qcReady :key=this.qc_report>
    <failureForm ref="failureFormComponent" :_id=this.current_uuid :project=this.project :qc_report=this.qc_report></failureForm>
</div>

<div class="flex mx-auto w-3/4 mt-8">
<div class="grid grid-cols-7 gap-8 w-full place-items-center">
        <div class="">
            <button
             class="bg-surface-raised hover:bg-line-default text-ink-primary h-10 w-36 border border-line-subtle rounded shadow-inner shadow-black/30 transition-colors duration-150"
              @click="PreviousPatient()"> Previous Patient</button>
        </div>
        <div class="px-8"><button
         class="bg-surface-raised hover:bg-line-default text-ink-primary h-10 w-32 border border-line-subtle rounded shadow-inner shadow-black/30 transition-colors duration-150"
          @click="PreviousImage()"> Previous Image</button>
        </div>
        <div class="col-span-2 grid text-accent-400 text-xl w-full">
            <multiselect v-model="this.currentPID" :options="this.patientList" :close-on-select="true" :allow-empty="false" @select="changePatient"></multiselect>
        </div>

        <div class="justify-center grid w-full">
            <button id="dropdownBgHoverButton" data-dropdown-toggle="dropdownBgHover"
            class="text-ink-primary bg-brand-600 hover:bg-brand-700 h-10 w-40 font-medium border border-line-subtle shadow-inner rounded inline-flex text-center p-4 items-center justify-center transition-colors duration-150" type="button">Filter patients by
            </button>

            <!-- Dropdown menu -->
            <div id="dropdownBgHover" class="z-10 hidden w-48 bg-surface-card rounded-lg shadow-lg shadow-black/40 border border-line-subtle">
                <ul class="p-3 space-y-1 text-sm text-ink-secondary" aria-labelledby="dropdownBgHoverButton">
                <li v-for="elem in this.statusOptions">
                    <div class="flex items-center p-2 rounded-sm hover:bg-brand-600/20">
                    <input id="checkbox-item" type="checkbox" v-model="this.filterStatus[elem]" class="w-4 h-4 text-brand-500 bg-surface-raised border-line-subtle rounded-sm">
                    <label for="checkbox-item" class="w-full ms-2 text-sm font-medium text-ink-primary rounded-sm">{{elem}}</label>
                    </div>
                </li>
                </ul>
                <div class="flex content-center justify-center pb-2">
                    <button class="text-ink-primary bg-brand-600 hover:bg-brand-700 w-1/3 h-8 font-medium rounded text-center transition-colors duration-150" type="button" @click="filterPatients();">Submit
                    </button>
                </div>
            </div>

        </div>

        <div class="">
            <button
             class="bg-surface-raised hover:bg-line-default text-ink-primary h-10 w-32 border border-line-subtle rounded shadow-inner shadow-black/30 transition-colors duration-150"
              @click="NextImage()"> Next Image</button>
        </div>
        <div class="">
            <button
             class="bg-surface-raised hover:bg-line-default text-ink-primary h-10 w-36 border border-line-subtle rounded shadow-inner shadow-black/30 transition-colors duration-150"
              @click="NextPatient()"> Next Patient</button>
        </div>

</div>
</div>



<!-- Selector for cycling through images for this patient-->
<div class="bg-surface-header flex-grow mt-6">
    <div class="mt-6">
    <p class="text-ink-muted text-xs px-2 pb-1 text-center">{{ idList.length }} scan{{ idList.length === 1 ? '' : 's' }} for this patient, oldest to newest</p>
    <div class="flex gap-2 overflow-x-auto pb-2 px-2 justify-center">
        <button v-for="item in this.idList" :key="item" type="button"
            class="shrink-0 px-4 h-10 rounded-full border font-bold whitespace-nowrap transition-colors duration-150"
            :class="active_uid(item) ? 'bg-brand-500/15 border-brand-400 text-brand-300' : 'bg-surface-raised border-line-subtle text-ink-secondary hover:text-brand-400 hover:border-brand-400/50'"
            :id="item" @click="this.GetQAImage(item);">
            {{this.imageObj[this.currentPID][item]}}
        </button>
    </div>
    <!-- Image -->

    <div class="relative mt-4">
        <div v-if="imageLoading" class="absolute inset-0 flex items-center justify-center">
            <Spinner size="lg" />
        </div>
        <img :src="this.QAsrc" :alt="`Segmentation QA image for patient ${currentPID}`">
    </div>

</div>

<div class="flex content-center items-center mx-auto w-3/4 py-4">
    <div class="grid grid-cols-4 gap-4 w-full place-items-center">
        <div> <a class="text-accent-400">Input Path: </a> <a class="text-ink-muted "> {{ this.input_path }}</a> </div>
        <div class="grid col-span-2"> <a class="text-accent-400">Acquisition Date: </a> <a class="text-ink-muted "> {{ this.acquisition_date }}  </a> </div>
        <div class="flex-1"> <a class="text-accent-400">Level: </a> <a class="text-ink-muted "> {{ this.vertebra }}  </a> </div>

    </div>

</div>

</div>

<div class="flex mx-auto w-3/4 mt-2">
    <div class="grid-cols-4">
        <div class="">
            <a class="text-ink-secondary italic">If any tissue failed:</a>
        </div>
    </div>

</div>
<div class="flex mx-auto w-3/4 mt-1">
    <div class="grid grid-cols-4 gap-4 place-items-center w-full">
        <div class=""> <button class="bg-red-400 hover:bg-red-500 text-zinc-900 h-10
            w-40 border border-line-subtle rounded shadow-sm shadow-red-300/40 font-extrabold transition-colors duration-150" @click="this.showFailForm()">Fail
        </button>
        </div>
        <div class="grid">
            <button @click="ShowSpine();" :disabled="disableSpine"
                class="bg-surface-raised hover:bg-line-default text-ink-primary h-10 w-40 border border-line-subtle rounded shadow-inner shadow-black/30 font-extrabold transition-colors duration-150"> Show spine</button>
        </div>

        <div class="grid">
            <button @click="ShowRegistration();" :disabled="disableRegistration"
                class="bg-surface-raised hover:bg-line-default text-ink-primary h-10 w-40 border border-line-subtle rounded shadow-inner shadow-black/30 font-extrabold transition-colors duration-150"> Show registration</button>
        </div>

        <div class="">
            <button class="bg-brand-400 hover:bg-brand-500 text-zinc-900 h-10 w-40 border border-line-subtle rounded shadow-sm shadow-brand-300/40 font-extrabold transition-colors duration-150" @click="PassQA()">Pass</button>
        </div>
    </div>

</div>

<div class="grid grid-cols-3 items-center absolute bottom-0 px-2 py-1 bg-surface-header mt-20 w-full text-sm font-bold">
    <div class="inline-flex items-center gap-2">
        <a class="text-accent-400"> Series UUID: </a>
        <Badge :variant="status == 1 ? 'pass' : status == 0 ? 'fail' : 'todo'">{{ this.current_uuid }}</Badge>
    </div>

    <div class="text-center">
        <a class="text-ink-muted italic"></a>
    </div>

    <div class="text-right">
        <a class="text-ink-primary"> Image pass rate: {{this.passed_images}}/{{this.total_images}} ({{this.pass_rate}} %)</a>
    </div>

</div>



</template>
<style src="vue-multiselect/dist/vue-multiselect.min.css"></style>
