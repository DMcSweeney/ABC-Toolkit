<script>
import api from '@/api/client';
import popupViewer from '../popupViewer.vue';
import failureForm from './FailureForm.vue';


export default {
    name: 'SanityPage',
    data() {
        return {
            src: '', // Src for segmentation QA
            spineSrc: '', //Src for spine QA
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
            imageDict: Object() // Keys= pids, Values = list of image ids in db


        };
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
                window.alert('That was the last image!');
                return;
            }
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
            });
        },
        fetchFirstImage() {
            // Fetch first image to rate
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
                window.alert('That was the last image!');
                return;
            }
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
                window.alert("You've reached the start");
                return;
            }
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
        closeSpine(){
            this.showSpineSanity = false;
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
    components: { popupViewer , failureForm}
};

</script>


<template>
    <!-- SPINE POP-UP -->
    <popupViewer v-show="showSpineSanity" id="spine-sanity"> 
        <button class="flex text-zinc-950 rounded bg-white h-6" @click="closeSpine();"> 
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
            <path stroke-linecap="round" stroke-linejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
            </button>
        <img class="m-auto h-full" v-bind:src="spineSrc">
    </popupViewer> 
    <!-- FAILURE POP-UP -->
    <div v-if=this.qcReady :key=this.qc_report>
        <failureForm ref="failureFormComponent" :_id=this.idList[this.idx] :project=this.project :qc_report=this.qc_report></failureForm>
    </div>

    <!-- MAIN PAGE -->
    <div class="relative flex items-center w-full p-8 content-center">
        

        <div class="inline-block flex-1"><button
         class="bg-zinc-700 hover:bg-zinc-400 text-stone-200 hover:text-stone-900 h-10 w-20 border border-slate-900 rounded shadow-inner shadow-zinc-600"
          @click="PreviousImage()"> Previous</button>
        </div>

        <div class="inline-block grow text-indigo-200 text-xl flex-1"> Patient ID:
            <div v-if="status == 2" class="inline-block text-stone-200">
                {{ patientID }}
            </div> 
            <div v-else-if="status == 1" class="inline-block text-green-400">
                {{ patientID }}
            </div> 
            <div v-else-if="status == 0" class="inline-block text-red-400">
                {{ patientID }}
            </div> 
        </div>
        
        <div class="inline-block flex-0">
            <button
             class="bg-zinc-700 hover:bg-zinc-400 text-stone-200 hover:text-stone-900 h-10 w-20 border border-slate-900 rounded shadow-inner shadow-zinc-600"
              @click="NextImage()"> Next</button>
        </div>

    </div>

    <div class="relative flex items-center w-full px-40 content-center ">

        <div class="inline-block grow"> <a class="text-indigo-300">Input Path: </a> <a class="text-zinc-500 "> {{ inputPath }}  </a> </div>
        <div class="inline-block grow"> <a class="text-indigo-300">Acquisition Date: </a> <a class="text-zinc-500 "> {{ acquisitionDate }}  </a> </div>
        <div class="inline-block grow"> <a class="text-indigo-300">Level: </a> <a class="text-zinc-500 "> {{ vertebra }}  </a> </div>
    </div>

    <!-- Wrap image in tabs based on acquisition date & modality-->


    <!-- MAIN IMAGE -->
    <div class="relative flex w-full p-5 hover:h-full ">
        <div class="inline-block object-fill h-full hover:border hover:border-stone-500">
            <img v-bind:src="src">    
        </div>
    </div>
    <!-- MAIN IMAGE -->

    <div class="relative flex items-center w-full p-5 px-40 m-auto content-center">
        <div class="inline-block flex-0"> <button class="bg-red-400 hover:bg-red-500 text-zinc-900 h-10
             w-40 border border-slate-900 rounded shadow-sm shadow-red-300 font-extrabold" @click="showFailForm()">Fail
            </button>
        </div>
        <div class="inline-block m-auto">
            <button @click="ShowSpine();" :disabled="disableSpine"
             class="bg-zinc-700 hover:bg-zinc-400 text-stone-200 hover:text-stone-900 h-10 w-40 border border-slate-900 rounded shadow-inner shadow-zinc-600 font-extrabold"> Show spine</button>
        </div>
        
        <div class="inline-block flex-0"> <button class="bg-green-400 hover:bg-green-600 text-zinc-900 h-10 w-20 border border-slate-900 rounded shadow-sm shadow-green-300 font-extrabold" @click="PassQA()">Pass</button></div>
    </div>


    <div class="absolute items-bottom w-full bottom-0">
        <div class="align-end">
                <input id="disable-spine-checkbox" type="checkbox" class="w-4 h-4 text-blue-600 bg-gray-100" v-model="this.disableSpinePopup">
                <label for="disable-spine-checkbox" class="pl-3 text-slate-200 text-xl">Disable spine popup</label>
        </div>
        <div class="inline-block text-2xl flex-0 w-full" >
            <a class="text-green-500 pr-2"> Pass: {{ this.num_pass }}</a>
            <a class="text-red-500 pr-2"> Fail: {{ this.num_fail }} </a>
            <a class="text-zinc-500 pr-2"> To-do: {{ this.num_todo }} </a>
            <!-- <a class="text-stone-200 pr-2"> Total: {{ this.num_total }}</a> -->
        </div>
                

        <hr class="h-px my-2 bg-slate-400 border-0 ">
        <div class="flex">
            <a class="text-indigo-500"> Series UUID: </a> <a class="text-zinc-500 "> {{ seriesUUID }}  </a>
        </div>
        
    </div>

</template>


<style>

</style>