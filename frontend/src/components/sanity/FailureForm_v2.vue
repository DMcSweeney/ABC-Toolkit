<script>
//  Failure form in vue.js
import api from '@/api/client';
import Multiselect from 'vue-multiselect';

function initialState() {
    return {
        showFailureForm: false,
        failMode:'', // Select failure mode (badSegmentation, wrongLevel, etc...)
        segmentError:'', // How did segmentation fail?
        notes: '', // Additional notes?
        altInput: '', // Alternative input if issues with scan
        failedCompartments: '' // Compartments to mark as failed, others marked as pass
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
                'failedCompartments': this.failedCompartments,
                'altInput': this.altInput,
                'notes': this.notes
            }
            // Send post request to server
            api.post('/api/patient_qa/fail_qa_report', payload, { params: { _id: this._id, project: this.project, vertebra: this.$parent.vertebra } })
            .then(() => {
                // Clear data and move to next patient
                Object.assign(this.$data, initialState());
                this.$parent.NextImage();
            })
            .catch(() => {
                // Error already surfaced via toast by the shared api client.
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
        'this.$parent.qc_report'() {
            this.updateQCReport()
        }
    },
    components: {Multiselect},
    props: ['_id', 'project', 'qc_report']
}


</script>

<template>
    <div v-show="this.showFailureForm" id="failure-form" class="w-full h-full flex absolute z-50 bg-black/60">
        <div class="w-1/2 h-2/3 flex bg-surface-card border border-line-subtle z-50 mx-auto my-10 rounded shadow-lg shadow-black/40">

        <button class="flex text-ink-secondary hover:text-ink-primary rounded p-1 h-6 focus:outline-none focus:ring-2 focus:ring-brand-500" aria-label="Close" @click="closeFailForm();"> <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
            <path stroke-linecap="round" stroke-linejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
        </button>

        <div class="w-full">
            <!-- TITLE -->
            <div class="relative flex grow justify-center">
                <div class="text-2xl py-5 font-extrabold text-ink-primary"> Report failure </div>
            </div>

            <form id="failure-form">
                <div class="relative w-full justify-center">

                    <!-- Select Failure mode -->
                    <div class="relative inline-block w-full pr-10">
                        <div class="text-ink-secondary text-xl font-bold pb-3">
                            <p class="text-accent-400">Select failure mode</p>
                        </div>
                        <select v-model="failMode" class="relative w-full h-8 rounded-md bg-surface-raised text-ink-primary shadow-lg font-bold px-2 ring-1 ring-line-subtle focus:outline-none focus:ring-2 focus:ring-brand-500 cursor-pointer"
                        placeholder="Select a failure mode">
                            <option value="badSegmentation">Bad Segmentation</option>
                            <option value="wrongLevel">Wrong Level</option>
                            <option value="scanIssue">Issue with Scan</option>
                            <option value="other">Other</option>
                        </select>
                    </div>


                    <!-- If else based on failure mode -->
                    <div class="inline-block pt-5 justify-center">
                        <div v-if="failMode == 'badSegmentation'" class="text-ink-primary">
                            <!-- What compartment? -->
                            <div class="font-bold pb-3 w-3/4">
                                <p class="text-accent-400"> Select all tissues that failed:</p>
                                    <multiselect class="h-4" v-model="failedCompartments" :value="this.failedCompartments" :options="this.$parent.compartments" :close-on-select="false" :multiple="true" :clear-on-select="false">
                                    </multiselect>
                            </div>


                            <!-- OVER/UNDER SEGMENTED -->
                            <div class="font-bold pb-3">
                                <p class="text-accent-400">How did it fail?</p>
                            </div>
                            <ul class="grid grid-cols-3 gap-2 justify-center">
                                <li>
                                    <input type="radio" v-model="segmentError" value="over" id="over-segment" class="hidden peer" required>
                                    <label for="over-segment" class="relative inline-flex items-center justify-center p-2 w-full text-ink-secondary bg-surface-raised border border-line-subtle rounded-lg cursor-pointer  peer-checked:border-brand-400 peer-checked:text-brand-300 hover:text-brand-400 hover:bg-line-subtle ">
                                        <div class="block">
                                            <div class="w-full font-semibold">Over-segmented</div>
                                        </div>
                                    </label>
                                </li>
                                <li>
                                    <input type="radio" v-model="segmentError" value="under" id="under-segment" class="hidden peer">
                                    <label for="under-segment" class="relative inline-flex items-center justify-center w-full p-2 text-ink-secondary bg-surface-raised border border-line-subtle rounded-lg cursor-pointer  peer-checked:border-brand-400 peer-checked:text-brand-300 hover:text-brand-400 hover:bg-line-subtle">
                                        <div class="block">
                                            <div class="w-full font-semibold">Under-segmented</div>
                                        </div>
                                    </label>
                                </li>
                                <li>
                                    <input type="radio" v-model="segmentError" value="neither" id="neither" class="hidden peer">
                                    <label for="neither" class="relative inline-flex items-center justify-center p-2 w-full text-ink-secondary bg-surface-raised border border-line-subtle rounded-lg cursor-pointer  peer-checked:border-brand-400 peer-checked:text-brand-300 hover:text-brand-400 hover:bg-line-subtle">
                                        <div class="block">
                                            <div class="w-full font-semibold">Way off</div>
                                        </div>
                                    </label>
                                </li>
                            </ul>
                            <!-- IF OVER  -->

                        </div>

                        <div v-if="failMode == 'wrongLevel'" class="text-accent-400 text-sm">
                            <p>One day I'll let you select a new slice.<br>
                                 For now, leave a note (e.g. SLICE_NUMBER:25).
                            </p>
                        </div>
                        <div v-if="failMode == 'scanIssue'" class="w-full">
                            <label for="neither" class="flex text-accent-400 font-bold text-sm pb-2">
                                Add path to alternative scan. Start with: <p class="text-brand-300 font-mono"> /data/inputs</p>
                            </label>
                            <input type="text" v-model="altInput" id="altInput" class="w-full bg-surface-raised text-ink-primary rounded px-2 h-8 focus:outline-none focus:ring-2 focus:ring-brand-500">

                        </div>
                        <div v-if="failMode == 'other'" class="text-accent-400">
                            <p>Please leave a note with the issue.</p>
                        </div>
                    </div>


                    <!-- Notes section -->
                    <div class="inline-block w-full pt-5 pr-10">
                        <div class="text-xl font-bold pb-3">
                            <p class="text-accent-400">Additional Notes</p>
                        </div>
                        <textarea v-model="notes" placeholder="Add notes here if needed" class="w-full h-20 px-2 rounded-md bg-surface-raised text-ink-primary placeholder:text-ink-muted shadow-lg ring-1 ring-line-subtle focus:outline-none focus:ring-2 focus:ring-brand-500"></textarea>
                    </div>

                    <div class="relative flex w-full justify-center py-10">
                        <button type="button" class="bg-brand-600 rounded w-1/4 h-10 text-ink-primary font-bold hover:bg-brand-700 hover:font-extrabold transition-colors duration-150" @click="SubmitForm()">Submit</button>
                    </div>
                </div>
            </form>
        </div>


    </div>
    </div>


</template>
<style src="vue-multiselect/dist/vue-multiselect.min.css"></style>
<style>


</style>