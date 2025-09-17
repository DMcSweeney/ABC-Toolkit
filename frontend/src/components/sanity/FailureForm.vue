<script>
//  Failure form in vue.js
import axios from 'axios';

function initialState() {
    return {
        showFailureForm: false,
        failMode:'', // Select failure mode (badSegmentation, wrongLevel, etc...)
        segmentError:'', // How did segmentation fail?
        notes: '', // Additional notes?
        altInput: '', // Alternative input if issues with scan
    }
}

export default {
    name: 'failureForm',
    data(){
        return initialState();
    },
    methods: {
        showFailForm() {
            this.showFailureForm = true;
        },
        closeFailForm() {
            this.showFailureForm = false;
        },
        SubmitForm(){
            var payload = {
                'failMode': this.failMode,
                'segmentError': this.segmentError,
                'altInput': this.altInput,
                'notes': this.notes
            }
            const url = `${import.meta.env.VITE_BACKEND_URI}/api/sanity/fail_qa_report?_id=${this._id}&project=${this.project}&vertebra=${this.$parent.vertebra}`
            // Send post request to server
            axios.post(url, payload)
            .then((res) => {
                console.log(res.data);
                // Clear data and move to next patient
                Object.assign(this.$data, initialState());
                this.$parent.NextImage();
            })
            .catch((err) => {
                console.log(err);
            })
        },
        updateQCReport(){
            if (!!this.$parent.qc_report) { // Check not null
                // Update form values
                for (var key in this.$parent.qc_report) {
                    this[key] = this.$parent.qc_report[key];
                }
            } 
        }
    },
    mounted(){
        this.updateQCReport();
    },
    watch: {
        'this.$parent.qc_report'(newVal) {
            console.log("Updating value");
            this.updateQCReport()
        }
    },
    components: {},
    props: ['_id', 'project', 'qc_report']
}


</script>

<template>
    <div v-show="this.showFailureForm" id="failure-form" class="w-full h-full flex absolute z-50 bg-black bg-transparent ">
        <div class="w-1/2 h-2/3 flex bg-black border border-white z-50 mx-auto my-10 rounded shadow-sm shadow-white">
  
        <button class="flex text-zinc-950 rounded bg-white h-6" @click="closeFailForm();"> <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
            <path stroke-linecap="round" stroke-linejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
        </button>
        
        <div class="w-full">
            <!-- TITLE -->
            <div class="relative flex grow justify-center">
                <div class="text-2xl py-5 font-extrabold text-stone-200"> Report failure </div>
            </div>

            <form id="failure-form">
                <div class="relative w-full justify-center">

                    <!-- Select Failure mode -->
                    <div class="relative inline-block w-full pr-10">
                        <div class="text-gray-200 text-xl font-bold pb-3">
                            <p class="text-indigo-200">Select failure mode</p>
                        </div>
                        <select v-model="failMode" class="relative w-full h-8 rounded-md bg-white shadow-lg font-bold px-2 ring-1 ring-black ring-opacity-5 focus:outline-none cursor-pointer" 
                        placeholder="Select a failure mode">
                            <!-- Active: "bg-gray-100 text-gray-900", Not Active: "text-gray-700" -->
                            <option value="badSegmentation">Bad Segmentation</option>
                            <option value="wrongLevel">Wrong Level</option>
                            <option value="scanIssue">Issue with Scan</option>
                            <option value="other">Other</option>
                        </select>
                    </div>
                    
                    
                    <!-- If else based on failure mode -->
                    <div class="inline-block pt-5 justify-center">
                        <div v-if="failMode == 'badSegmentation'" class="text-stone-200">
                            <!-- OVER/UNDER SEGMENTED -->
                            <div class="font-bold pb-3">
                                <p class="text-indigo-200">How did it fail?</p>
                            </div>
                            <ul class="grid grid-cols-3 gap-2 justify-center">
                                <li>
                                    <input type="radio" v-model="segmentError" value="over" id="over-segment" class="hidden peer" required>
                                    <label for="over-segment" class="relative inline-flex items-center justify-center p-2 w-full text-indigo-100 bg-zinc-900 border border-indigo-200 rounded-lg cursor-pointer  peer-checked:border-indigo-500 peer-checked:text-indigo-300 hover:text-indigo-600 hover:bg-zinc-700 ">                           
                                        <div class="block">
                                            <div class="w-full font-semibold">Over-segmented</div>
                                        </div>
                                    </label>
                                </li>
                                <li>
                                    <input type="radio" v-model="segmentError" value="under" id="under-segment" class="hidden peer">
                                    <label for="under-segment" class="relative inline-flex items-center justify-center w-full p-2 text-indigo-100 bg-zinc-900 border border-indigo-200 rounded-lg cursor-pointer  peer-checked:border-indigo-500 peer-checked:text-indigo-300 hover:text-indigo-600 hover:bg-zinc-700">                           
                                        <div class="block">
                                            <div class="w-full font-semibold">Under-segmented</div>
                                        </div>
                                    </label>
                                </li>
                                <li>
                                    <input type="radio" v-model="segmentError" value="neither" id="neither" class="hidden peer">
                                    <label for="neither" class="relative inline-flex items-center justify-center p-2 w-full text-indigo-100 bg-zinc-900 border border-indigo-200 rounded-lg cursor-pointer  peer-checked:border-indigo-500 peer-checked:text-indigo-300 hover:text-indigo-600 hover:bg-zinc-700">                           
                                        <div class="block">
                                            <div class="w-full font-semibold">Way off</div>
                                        </div>
                                    </label>
                                </li>
                            </ul>
                            <!-- IF OVER  -->

                        </div>
                    
                        <div v-if="failMode == 'wrongLevel'" class="text-indigo-200 text-sm">
                            <p>One day I'll let you select a new slice.<br>
                                 For now, leave a note (e.g. SLICE_NUMBER:25).
                            </p>
                        </div>
                        <div v-if="failMode == 'scanIssue'" class="w-full">
                            <label for="neither" class="flex text-indigo-200 font-bold text-sm pb-2">                           
                                Add path to alternative scan. Start with: <p class="text-green-300 font-mono"> /data/inputs</p>
                            </label>
                            <input type="text" v-model="altInput" id="altInput" class="w-full">
                            
                        </div>
                        <div v-if="failMode == 'other'" class="text-indigo-200">
                            <p>Please leave a note with the issue.</p>
                        </div>
                    </div>
              
                    
                    <!-- Notes section -->
                    <div class="inline-block w-full pt-5 pr-10">
                        <div class="text-xl font-bold pb-3">
                            <p class="text-indigo-200">Additional Notes</p>
                        </div>
                        <textarea v-model="notes" placeholder="Add notes here if needed" class="w-full h-20 px-2 rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none"></textarea>
                    </div>
                    
                    <div class="relative flex w-full justify-center py-10">
                        <button type="button" class="bg-indigo-700 rounded w-1/4 h-10 text-stone-200 font-bold hover:bg-indigo-800 hover:font-extrabold" @click="SubmitForm()">Submit</button>
                    </div>
                </div>
            </form>
        </div>
        

    </div>
    </div>  


</template>

<style>


</style>