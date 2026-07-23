<script>
import api from '@/api/client';
import Modal from '../ui/Modal.vue';
import Spinner from '../ui/Spinner.vue';
import Badge from '../ui/Badge.vue';
import Popover from '../ui/Popover.vue';
import failureForm from './FailureForm.vue';
import { useToastStore } from '@/stores/toast';


export default {
    name: 'SanityPage',
    setup() {
        return { toast: useToastStore() };
    },
    data() {
        return {
            src: '', // Src for segmentation QA
            spineSrc: '', //Src for spine QA
            imageLoading: false, // Whether the main QA image is currently being fetched
            patientID: '', // PatientID
            seriesUUID: '', //Series UUID
            acquisitionDate: '', // Acquisition date
            vertebra: this.$route.params.vertebra, // Level of interest
            inputPath: '', //Input data path (in container)
            showSpineSanity: true, // Display spine sanity at first
            disableSpinePopup: false, // Whether or not to show the spine image when new scan is loaded
            // showFailureForm: true,
            idList: '',
            idx: 0,
            status: 2, // 2 = unrated; 1=passed; 0=failed ,
            disableSpine: false,
            project: this.$route.params.project,
            num_pass: 0,
            num_fail: 0,
            num_todo: 0,
            num_total: 0,
            qcReady: false,
            patientList: Object(), // Contains all patient IDs
            imageDict: Object(), // Keys= pids, Values = list of image ids in db
            debugInfoCache: {}, // Raw images-doc info for the "more info" popover, keyed by series uuid
            debugInfoLoading: false,

        };
    },
    computed: {
        debugInfo() {
            return this.debugInfoCache[this.idList[this.idx]] || null;
        },
    },
    methods: {
        displayFirstImage() {
                        // Fetch next image
            var _id;
            this.idx++;
            if (this.idx <= this.idList.length - 1) {
                _id = this.idList[this.idx];
            }
            else {
                this.idx--;
                this.toast.info('That was the last image!');
                return;
            }
            this.imageLoading = true;
            api.post('/api/sanity/fetch_image_by_id', null, { params: { project: this.project, _id: _id, vertebra: this.vertebra } })
                .then((res) => {
                this.src = `data:image/png;base64, ` + res.data.image;
                this.patientID = res.data.patient_id;
                this.status = res.data.status;
                this.seriesUUID = res.data.series_uuid;
                this.acquisitionDate = res.data.acquisition_date;
                this.inputPath = res.data.input_path;
                this.vertebra = res.data.vertebra;
                this.getSummary();
                this.GetSpine();
                this.getQCReport();
                if (this.disableSpinePopup) {
                    this.showSpineSanity = false;
                } else {
                    this.showSpineSanity = true;
                }


            })
                .catch(() => {
                // Error already surfaced via toast by the shared api client.
            })
                .finally(() => {
                this.imageLoading = false;
            });
        },
        fetchFirstImage() {
            // Fetch first image to rate
            this.imageLoading = true;
            api.post('/api/sanity/fetch_first_image', null, { params: { project: this.project, vertebra: this.vertebra } })
                .then((res) => {
                this.src = `data:image/png;base64, ` + res.data.image;
                this.patientID = res.data.patient_id;
                this.status = res.data.status;
                this.seriesUUID = res.data.series_uuid;
                this.acquisitionDate = res.data.acquisition_date;
                this.inputPath = res.data.input_path;
            }).catch(() => {
                    // Error already surfaced via toast by the shared api client.
            })
                .finally(() => {
                this.imageLoading = false;
            });
        },

        // TOD
        fetchPatientList() {
            // Get JSON object of patients and their images
            // Better solution when multiple images per patient 
            api.get('/api/sanity/fetch_patient_list', { params: { project: this.project, vertebra: this.vertebra } })
                .then((res) => {

                this.imageDict = res.data.image_dict;
                this.patientList = Object.keys(this.imageDict);
                this.GetSpine();
                this.getQCReport();
            })
                .catch(() => {
                // Error already surfaced via toast by the shared api client.
            });
        },
        fetchImageList() {
            // Fetch list of available images
            api.post('/api/sanity/fetch_image_list', null, { params: { project: this.project, vertebra: this.vertebra } })
                .then((res) => {
                this.idList = res.data.id_list;
                this.GetSpine();
                this.getQCReport();
            })
                .catch(() => {
                // Error already surfaced via toast by the shared api client.
            });
        },
        NextImage() {
            // Fetch next image
            var _id;
            this.idx++;
            if (this.idx <= this.idList.length - 1) {
                _id = this.idList[this.idx];
            }
            else {
                this.idx--;
                this.toast.info('That was the last image!');
                return;
            }
            this.imageLoading = true;
            api.post('/api/sanity/fetch_image_by_id', null, { params: { project: this.project, _id: _id, vertebra: this.vertebra } })
                .then((res) => {
                this.src = `data:image/png;base64, ` + res.data.image;
                this.patientID = res.data.patient_id;
                this.status = res.data.status;
                this.seriesUUID = res.data.series_uuid;
                this.acquisitionDate = res.data.acquisition_date;
                this.inputPath = res.data.input_path;
                this.vertebra = res.data.vertebra;
                this.getSummary();
                this.GetSpine();
                this.getQCReport();
                if (this.disableSpinePopup) {
                    this.showSpineSanity = false;
                } else {
                    this.showSpineSanity = true;
                }


            })
                .catch(() => {
                // Error already surfaced via toast by the shared api client.
            })
                .finally(() => {
                this.imageLoading = false;
            });
        },
        PreviousImage() {
            // Fetch previous image
            var _id;
            this.idx--;
            if (this.idx >= 0) {
                _id = this.idList[this.idx];
            }
            else {
                this.idx = 0
                this.toast.info("You've reached the start");
                return;
            }
            this.imageLoading = true;
            api.post('/api/sanity/fetch_image_by_id', null, { params: { project: this.project, _id: _id, vertebra: this.vertebra } })
                .then((res) => {
                this.src = `data:image/png;base64, ` + res.data.image;
                this.patientID = res.data.patient_id;
                this.status = res.data.status;
                this.seriesUUID = res.data.series_uuid;
                this.acquisitionDate = res.data.acquisition_date;
                this.inputPath = res.data.input_path;
                this.vertebra = res.data.vertebra;
                this.getSummary();
                this.GetSpine();
                this.getQCReport();
            })
                .catch(() => {
                // Error already surfaced via toast by the shared api client.
            })
                .finally(() => {
                this.imageLoading = false;
            });
        },
        PassQA() {
            // Record QA pass
            const _id = this.idList[this.idx];
            api.post('/api/sanity/pass_qa', null, { params: { project: this.project, _id: _id, vertebra: this.vertebra } })
                .then(() => {
                this.NextImage();
            })
                .catch(() => {
                // Error already surfaced via toast by the shared api client.
            });
        },
        FailQA(mode) {
            // Record QA fail (both segmentation and labelling fail)
            const _id = this.idList[this.idx];
            api.post('/api/sanity/fail_qa', null, { params: { project: this.project, _id: _id, mode: mode, vertebra: this.vertebra } })
                .then(() => {
                this.NextImage();
            })
                .catch(() => {
                // Error already surfaced via toast by the shared api client.
            });
        },
        GetSpine() {
            const _id = this.idList[this.idx];
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
        ShowSpine() {
            // Reveal spine prediction
            this.showSpineSanity = true;
        },
        getSummary(){
            api.get('/api/sanity/get_summary', { params: { project: this.project, vertebra: this.vertebra } })
                .then((res) => {
                this.num_pass = res.data.pass;
                this.num_fail = res.data.fail;
                this.num_todo = res.data.todo;
                this.num_total = res.data.total;
            })
                .catch(() => {
                // Error already surfaced via toast by the shared api client.
            });
        },
        showFailForm() {
            this.$refs.failureFormComponent.showFailureForm = true;
        },
        getQCReport(){
            const _id = this.idList[this.idx];
            api.get('/api/database/get_qc_report', { params: { project: this.project, _id: _id } })
                .then((res) => {
                    if (!!res.data.reports) { // If not null
                        this.qc_report = res.data.reports[0][1];
                        this.qcReady = true;
                    } else {
                        this.qc_report = null;
                        this.qcReady = true;
                    }

                })
        },
        fetchDebugInfo() {
            // Lazily fetch the raw images-collection doc for the "more info" popover, cached
            // per scan so re-opening/re-hovering doesn't refetch.
            const _id = this.idList[this.idx];
            if (this.debugInfoCache[_id]) return;
            this.debugInfoLoading = true;
            api.get('/api/database/get_input_args', { params: { _id: _id, project: this.project } })
                .then((res) => {
                    this.debugInfoCache[_id] = res.data.data;
                })
                .catch(() => {
                    // Error already surfaced via toast by the shared api client.
                })
                .finally(() => {
                    this.debugInfoLoading = false;
                });
        },
    },
    created() {
        // Query what image needs to be displayed first
        this.fetchFirstImage();
        this.getSummary();
    },
    mounted() {
        // Get list of images in sequence - to make fast transition
        this.fetchImageList();       
        // this.fetchPatientList();
        
    },
    components: { Modal, Spinner, Badge, Popover, failureForm}
};

</script>


<template>
    <!-- SPINE POP-UP -->
    <Modal v-model="showSpineSanity" title="Spine QA" size="lg">
        <img class="m-auto h-full" alt="Spine labelling QA image" v-bind:src="spineSrc">
    </Modal>
    <!-- FAILURE POP-UP -->
    <div v-if=this.qcReady :key=this.qc_report>
        <failureForm ref="failureFormComponent" :_id=this.idList[this.idx] :project=this.project :qc_report=this.qc_report></failureForm>
    </div>

    <!-- MAIN PAGE -->
    <div class="relative flex items-center w-full p-8 content-center">
        

        <div class="inline-block flex-1"><button
         class="bg-surface-raised hover:bg-line-default text-ink-primary h-10 w-20 border border-line-subtle rounded shadow-inner shadow-black/30 transition-colors duration-150"
          @click="PreviousImage()"> Previous</button>
        </div>

        <div class="inline-flex items-center gap-2 grow text-accent-400 text-xl flex-1"> Patient ID:
            <Badge :variant="status == 1 ? 'pass' : status == 0 ? 'fail' : 'todo'">{{ patientID }}</Badge>
        </div>

        <div class="inline-block flex-0">
            <button
             class="bg-surface-raised hover:bg-line-default text-ink-primary h-10 w-20 border border-line-subtle rounded shadow-inner shadow-black/30 transition-colors duration-150"
              @click="NextImage()"> Next</button>
        </div>

    </div>

    <div class="relative flex justify-center items-center w-full px-40 content-center ">
        <Popover align="left" @open="fetchDebugInfo">
            <template #content>
                <p class="text-ink-primary font-bold pb-2">Scan details</p>
                <div v-if="debugInfoLoading" class="text-ink-muted">Loading...</div>
                <dl v-else-if="debugInfo" class="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1.5">
                    <dt class="text-accent-400 font-bold">Input path</dt><dd class="text-ink-secondary break-all">{{ debugInfo.input_path }}</dd>
                    <dt class="text-accent-400 font-bold">Study ID</dt><dd class="text-ink-secondary break-all">{{ debugInfo.study_uuid }}</dd>
                    <dt class="text-accent-400 font-bold">Series ID</dt><dd class="text-ink-secondary break-all">{{ seriesUUID }}</dd>
                    <dt class="text-accent-400 font-bold">Modality</dt><dd class="text-ink-secondary">{{ debugInfo.modality }}</dd>
                    <dt class="text-accent-400 font-bold">Study date</dt><dd class="text-ink-secondary">{{ debugInfo.study_date }}</dd>
                    <dt class="text-accent-400 font-bold">Series date</dt><dd class="text-ink-secondary">{{ debugInfo.series_date }}</dd>
                    <dt class="text-accent-400 font-bold">Acquisition date</dt><dd class="text-ink-secondary">{{ debugInfo.acquisition_date }}</dd>
                    <dt class="text-accent-400 font-bold">Level</dt><dd class="text-ink-secondary">{{ vertebra }}</dd>
                    <dt class="text-accent-400 font-bold">Pixel spacing</dt><dd class="text-ink-secondary">{{ debugInfo.X_spacing }} × {{ debugInfo.Y_spacing }}</dd>
                    <dt class="text-accent-400 font-bold">Slice thickness</dt><dd class="text-ink-secondary">{{ debugInfo.slice_thickness }}</dd>
                    <dt class="text-accent-400 font-bold">Labelling done</dt><dd class="text-ink-secondary">{{ debugInfo.labelling_done ? 'Yes' : 'No' }}</dd>
                    <dt class="text-accent-400 font-bold">Segmentation done</dt><dd class="text-ink-secondary">{{ debugInfo.segmentation_done ? 'Yes' : 'No' }}</dd>
                    <template v-if="debugInfo.rtstruct_path">
                        <dt class="text-accent-400 font-bold">RTSTRUCT</dt><dd class="text-ink-secondary break-all">{{ debugInfo.rtstruct_path }}</dd>
                    </template>
                </dl>
                <div v-else class="text-ink-muted">No info available.</div>
            </template>
        </Popover>
    </div>

    <!-- Wrap image in tabs based on acquisition date & modality-->


    <!-- MAIN IMAGE -->
    <div class="relative flex w-full justify-center p-5 hover:h-full ">
        <div class="relative inline-block object-fill h-full hover:border hover:border-line-default">
            <div v-if="imageLoading" class="absolute inset-0 flex items-center justify-center">
                <Spinner size="lg" />
            </div>
            <img v-bind:src="src" :alt="`Segmentation QA image for patient ${patientID}`">
        </div>
    </div>
    <!-- MAIN IMAGE -->

    <div class="relative flex items-center w-full p-5 px-40 m-auto content-center">
        <div class="inline-block flex-0"> <button class="bg-red-400 hover:bg-red-500 text-zinc-900 h-10
             w-40 border border-line-subtle rounded shadow-sm shadow-red-300/40 font-extrabold transition-colors duration-150" @click="showFailForm()">Fail
            </button>
        </div>
        <div class="inline-block m-auto">
            <button @click="ShowSpine();" :disabled="disableSpine"
             class="bg-surface-raised hover:bg-line-default text-ink-primary h-10 w-40 border border-line-subtle rounded shadow-inner shadow-black/30 font-extrabold transition-colors duration-150"> Show spine</button>
        </div>

        <div class="inline-block flex-0"> <button class="bg-brand-400 hover:bg-brand-500 text-zinc-900 h-10 w-20 border border-line-subtle rounded shadow-sm shadow-brand-300/40 font-extrabold transition-colors duration-150" @click="PassQA()">Pass</button></div>
    </div>


    <div class="absolute items-bottom w-full bottom-0">
        <div class="align-end">
                <input id="disable-spine-checkbox" type="checkbox" class="w-4 h-4 text-brand-500 bg-surface-raised" v-model="this.disableSpinePopup">
                <label for="disable-spine-checkbox" class="pl-3 text-ink-secondary text-xl">Disable spine popup</label>
        </div>
        <div class="inline-flex gap-3 text-xl flex-0 w-full px-2" >
            <Badge variant="pass">Pass: {{ this.num_pass }}</Badge>
            <Badge variant="fail">Fail: {{ this.num_fail }}</Badge>
            <Badge variant="todo">To-do: {{ this.num_todo }}</Badge>
        </div>


        <hr class="h-px my-2 bg-line-default border-0 ">
        <div class="flex">
            <a class="text-accent-400"> Series UUID: </a> <a class="text-ink-muted "> {{ seriesUUID }}  </a>
        </div>

    </div>

</template>


<style>

</style>