<script>
// QA page organised by patient
// Should be able to access all predictions for a patient from here 
// Add patientID arg in path to allow for searching specific patients
import axios from 'axios';
import popupViewer from '../popupViewer.vue';
import failureForm from './FailureForm_v2.vue';
import Multiselect from 'vue-multiselect';
import { Modal } from 'flowbite';

export default {
    name: 'PatientPredictions',
    data() {
        return {
            imageObj: Object(), // Object where keys: patientIDs, values: list of ids for that patient
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
        async fetchPatientList() {
            // Get JSON object of ALL patients and their images 
            // TODO only fetch patient IDs? then make another call to fetch UIDs for that patient? Currently, might take up a lot of mem. on big projects...
            const path = `${import.meta.env.VITE_BACKEND_URI}/api/patient_qa/fetch_patient_list?project=${this.project}&vertebra=${this.vertebra}`;
            await axios.get(path)
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
                this.idList = Object.keys(this.imageObj[this.currentPID]);
            })
                .catch((err) => {
                console.error(err);
            });

            // Also fetch the statuses linked with patient IDs and use these to filter search
            this.fetchFilteredList();
        },
        fetchFilteredList(){
            const path = `${import.meta.env.VITE_BACKEND_URI}/api/patient_qa/get_filtered_patient_list?project=${this.project}&vertebra=${this.vertebra}`;
            axios.get(path)
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
                .catch((err) => {
                    console.error(err);
            });
        },
        GetQAImage(_id) {
            // Wait for patient list to run, then request the relevant image, given the _id
            
            this.current_uuid = _id;
            this.GetSpine(_id)
            this.getQCReport(_id)
            this.getImagePassRate();
            const path = `${import.meta.env.VITE_BACKEND_URI}/api/patient_qa/fetch_image_by_id?project=${this.project}&_id=${_id}&vertebra=${this.vertebra}`;
            axios.get(path)
                .then((res) => {
                this.QAsrc = `data:image/png;base64, ` + res.data.image;
                this.status = res.data.status;
                this.input_path = res.data.input_path;
                this.acquisition_date = res.data.acquisition_date;
                this.compartments = res.data.compartments;
            })
                .catch((err) => {
                console.error(err);
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
                window.alert('That was the last patient!');
                return;
            }
            this.idList = Object.keys(this.imageObj[this.currentPID]);
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
                window.alert("You've reached the start");
                return;
            }
            this.idList = Object.keys(this.imageObj[this.currentPID]);
            this.GetQAImage(this.idList[0]);
        },
        GetSpine(_id) {
            // Get the spine QC image and display            
            const path = `${import.meta.env.VITE_BACKEND_URI}/api/sanity/fetch_spine_by_id?project=${this.project}&_id=${_id}&vertebra=${this.vertebra}`;
            axios.post(path)
                .then((res) => {
                this.spineSrc = `data:image/png;base64, ` + res.data.image;
                this.disableSpine = false;
            })
                .catch((err) => {
                    console.log(err)
                    this.disableSpine = true;
            });
        },
        getQCReport(_id){
            // Get the spine QC image and display
            const path = `${import.meta.env.VITE_BACKEND_URI}/api/database/get_qc_report?project=${this.project}&_id=${_id}`;
            axios.get(path)
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
            const path = `${import.meta.env.VITE_BACKEND_URI}/api/patient_qa/pass_qa?project=${this.project}&_id=${this.current_uuid}&vertebra=${this.vertebra}`;
            axios.post(path)
                .then((res) => {
                console.log(res.data.message);
                this.NextImage();
            })
                .catch((err) => {
                console.error(err);
            });
        },
        ShowSpine() {
            // Reveal spine prediction
            this.showSpineSanity = true;
        },
        closeSpine(){
            this.showSpineSanity = false;
        },
        showFailForm() {
            this.$refs.failureFormComponent.showFailureForm = true;
        },
        active_uid(elem) {
            return this.current_uuid === elem ? 'underline' : '';
        },
        changePatient(elem){
            this.currentPID = elem;
            this.seriesIdx = 0; 
            this.idList = Object.keys(this.imageObj[this.currentPID]);
            const _id = this.idList[this.seriesIdx];
            this.GetQAImage(_id);
            this.$router.push({name: this.$router.currentRoute.name, params: {patient_id:elem}});  
        },
        filterPatients(){
            console.log(this.filterStatus);
            // Where filterstatus is true 
            var keys = Object.keys(this.filterStatus).filter(k => this.filterStatus[k]);
            var patList = Array();
            for (var key of keys) {
                patList = patList.concat(this.statusObj[key]);
            }
            if (patList.length === 0) {
                window.alert(`No patients meeting criteria: ${keys}`);
                return;
            }
            // Then overwrite the patientList and reset indices
            this.patientList = patList;
            this.patientIdx = 0;
            this.currentPID = this.patientList[this.patientIdx];
            this.idList = Object.keys(this.imageObj[this.currentPID]);
            this.seriesIdx = 0;
            this.GetQAImage(this.idList[this.seriesIdx]);
        },
        getImagePassRate(){
            // Method for querying current image pass rate -- should be done everytime a new image is displayed
            const url = `${import.meta.env.VITE_BACKEND_URI}/api/patient_qa/get_image_pass_rate?project=${this.project}&vertebra=${this.vertebra}`;
            axios.get(url)
            .then((res) => {
                this.total_images = res.data.total;
                this.passed_images = res.data.passed;
                this.pass_rate = res.data.pass_rate;
            })
            .catch((err) => {
                console.log(err);
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
    components: {popupViewer, failureForm, Multiselect}
}


</script>


<template>
<!-- SPINE POP-UP -->
<popupViewer v-show="showSpineSanity" id="spine-sanity"> 
    <button class="flex text-zinc-950 rounded bg-white h-6" @click="closeSpine();"> 
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
        <path stroke-linecap="round" stroke-linejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
        </button>
    <img class="m-auto h-full" :src="spineSrc">
</popupViewer> 

    <!-- FAILURE POP-UP -->
<div v-if=this.qcReady :key=this.qc_report>
    <failureForm ref="failureFormComponent" :_id=this.current_uuid :project=this.project :qc_report=this.qc_report></failureForm>
</div>

<div class="flex mx-auto w-3/4 mt-8">
<div class="grid grid-cols-7 gap-8 w-full place-items-center">
        <div class="">
            <button
             class="bg-zinc-900 hover:bg-zinc-400 text-stone-200 hover:text-stone-900 h-10 w-36 border border-slate-900 rounded shadow-inner shadow-zinc-600"
              @click="PreviousPatient()"> Previous Patient</button>
        </div>
        <div class="px-8"><button
         class="bg-zinc-700 hover:bg-zinc-400 text-stone-200 hover:text-stone-900 h-10 w-32 border border-slate-900 rounded shadow-inner shadow-zinc-600"
          @click="PreviousImage()"> Previous Image</button>
        </div>
        <div class="col-span-2 grid text-indigo-200 text-xl w-full"> 
            <multiselect v-model="this.currentPID" :options="this.patientList" :close-on-select="true" :allow-empty="false" @select="changePatient"></multiselect>
        </div>

        <div class="justify-center grid w-full">
            <button id="dropdownBgHoverButton" data-dropdown-toggle="dropdownBgHover"
            class="text-stone-200 bg-indigo-700 h-10 w-40 font-medium border border-black shadow-inner rounded inline-flex text-center p-4 items-center justify-center" type="button">Filter patients by
            </button>

            <!-- Dropdown menu -->
            <div id="dropdownBgHover" class="z-10 hidden w-48 bg-zinc-950 rounded-lg shadow-sm shadow-white border border-white">
                <ul class="p-3 space-y-1 text-sm text-gray-700 dark:text-gray-200" aria-labelledby="dropdownBgHoverButton">
                <li v-for="elem in this.statusOptions">
                    <div class="flex items-center p-2 rounded-sm hover:bg-indigo-700">
                    <input id="checkbox-item" type="checkbox" v-model="this.filterStatus[elem]" class="w-4 h-4 text-indigo-700 bg-gray-100 border-gray-300 rounded-sm">
                    <label for="checkbox-item" class="w-full ms-2 text-sm font-medium text-white rounded-sm">{{elem}}</label>
                    </div>
                </li>
                </ul>
                <div class="flex content-center justify-center pb-2">
                    <button class="text-stone-200 bg-indigo-700 hover:text-zinc-950 w-1/3 h-8 font-medium rounded text-center" type="button" @click="filterPatients();">Submit
                    </button>
                </div>
            </div>

        </div>

        <div class="">
            <button
             class="bg-zinc-700 hover:bg-zinc-400 text-stone-200 hover:text-stone-900 h-10 w-32 border border-slate-900 rounded shadow-inner shadow-zinc-600"
              @click="NextImage()"> Next Image</button>
        </div>
        <div class="">
            <button
             class="bg-zinc-900 hover:bg-zinc-400 text-stone-200 hover:text-stone-900 h-10 w-36 border border-slate-900 rounded shadow-inner shadow-zinc-600"
              @click="NextPatient()"> Next Patient</button>
        </div>

</div>
</div>



<!-- Button for cycling through images for this patient-->
<div class="bg-black flex-grow mt-6">
    <div class="mt-6">
    <ul class="flex flex-wrap font-medium justify-center">
        <li v-for="item in this.idList" class="me-2">
            <button
             class="bg-zinc-950 border hover:text-indigo-400 hover:cursor-pointer
              border-black text-slate-200 hover:bg-zinc-800 w-32 font-bold rounded h-10 content-center peer-checked:border-indigo-500 peer-checked:text-indigo-300" 
            :id = item type="button" @click="this.GetQAImage(item);" v-bind:class="this.active_uid(item)">
                {{this.imageObj[this.currentPID][item]}}
            </button>
        </li>
    </ul>
    <!-- Image -->

    <div class="mt-4">
        <img :src="this.QAsrc"> 
    </div>

</div>

<div class="flex content-center items-center mx-auto w-3/4 py-4">
    <div class="grid grid-cols-4 gap-4 w-full place-items-center">
        <div> <a class="text-indigo-300">Input Path: </a> <a class="text-zinc-500 "> {{ this.input_path }}</a> </div>
        <div class="grid col-span-2"> <a class="text-indigo-300">Acquisition Date: </a> <a class="text-zinc-500 "> {{ this.acquisition_date }}  </a> </div>
        <div class="flex-1"> <a class="text-indigo-300">Level: </a> <a class="text-zinc-500 "> {{ this.vertebra }}  </a> </div>

    </div>

</div>

</div>

<div class="flex mx-auto w-3/4 mt-2">
    <div class="grid-cols-4">
        <div class="">
            <a class="text-stone-200 italic">If any tissue failed:</a>
        </div>
    </div>

</div>
<div class="flex mx-auto w-3/4 mt-1">
    <div class="grid grid-cols-4 gap-4 place-items-center w-full">
        <div class=""> <button class="bg-red-400 hover:bg-red-500 text-zinc-900 h-10
            w-40 border border-slate-900 rounded shadow-sm shadow-red-300 font-extrabold" @click="this.showFailForm()">Fail
        </button>
        </div>
        <div class="col-span-2 grid">
            <button @click="ShowSpine();" :disabled="disableSpine"
                class="bg-zinc-700 hover:bg-zinc-400 text-stone-200 hover:text-stone-900 h-10 w-40 border border-slate-900 rounded shadow-inner shadow-zinc-600 font-extrabold"> Show spine</button>
        </div>
        
        <div class=""> 
            <button class="bg-green-400 hover:bg-green-600 text-zinc-900 h-10 w-40 border border-slate-900 rounded shadow-sm shadow-green-300 font-extrabold" @click="PassQA()">Pass</button>
        </div>
    </div>

</div>

<div class="grid grid-cols-3 absolute bottom-0 px-2 py-1 bg-slate-950 mt-20 w-full text-sm font-bold">
    <div v-if="this.status === 2"> 
        <a class="text-indigo-300 "> Series UUID: </a> <a class="text-slate-200 italic"> {{ this.current_uuid }}  </a>
    </div>

    <div v-else-if="this.status === 1"> 
        <a class="text-indigo-300 "> Series UUID: </a> <a class="text-green-500 italic"> {{ this.current_uuid }}  </a>
    </div>
    <div v-else> 
        <a class="text-indigo-300 "> Series UUID: </a> <a class="text-red-500 italic"> {{ this.current_uuid }}  </a>
    </div>
    <div class="text-center">
        <a class="text-stone-400 italic"></a>
    </div>

    <div class="text-right">   
        <a class="text-stone-200"> Image pass rate: {{this.passed_images}}/{{this.total_images}} ({{this.pass_rate}} %)</a>
    </div>

</div>



</template>
<style src="vue-multiselect/dist/vue-multiselect.min.css"></style>
