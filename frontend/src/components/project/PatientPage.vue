<script>
import api from '@/api/client';
import moment from 'moment';
import Plotly from 'plotly.js-dist-min';
import { useToastStore } from '@/stores/toast';
import Button from '../ui/Button.vue';

export default {
    name: 'PatientPage',
    components: { Button },
    setup() {
        return { toast: useToastStore() };
    },
    data() {
        return {
            showBodyCompTrend: true,
            patientID: this.$route.params.patientID,
            vertebra: 'C3',
            compartment: 'skeletal_muscle',
            weight: new Number(),
            date: new Date(),
            weights: new Array(),
            weight_dates: new Array(),
            weight_changes: new Array(),
            bodyComp: new Array(),
            bodyComp_dates: new Array(),
            bodyComp_changes: new Array(),

        }
    },
    methods: {
        addWeight(){
            const today = new Date()
            today.setHours(0, 0, 0, 0);

            if (this.weight < 0) {
                this.toast.error("Weight can't be negative");
                return false;
            }

            if (moment(this.date) > today) {
                this.toast.error("Assessment date can't be in the future");
                return false;
            }
            // If passes checks, insert into database
            api.post('/api/weights/post_weight', null, {
                params: { patient_id: this.patientID, weight: this.weight, date: this.date }
            })
                .then(async () => {
                    await this.fetchWeights();
                    this.plotChange(this.weight_dates, this.weight_changes);
                })
                .catch(() => {
                    // Error already surfaced via toast by the shared api client.
                })
        },
        DeleteWeight(date){
            api.post('/api/weights/delete_weight', null, { params: { _id: this.patientID, date: date } })
            .then(async () => {
                await this.fetchWeights();
                this.plotChange(this.weight_dates, this.weight_changes);
            })
            .catch(() => {
                // Error already surfaced via toast by the shared api client.
            })

        },
        fetchWeights(){
            return api.get('/api/weights/fetch_weights', { params: { _id: this.patientID } })
            .then((res) => {
                this.weights = res.data.data;
                for (var item of this.weights) {
                    this.weight_dates.push(item[0])
                    this.weight_changes.push(Number(item[2]))
                }

            })
            .catch(() => {
                // Error already surfaced via toast by the shared api client.
            })

        },
        fetchBodyComp(){
            // Fetch body comp metrics from segmented scans
            return api.get('/api/post_process/get_stats_for_patient', {
                params: { project: this.$route.params.project, patient_id: this.patientID, vertebra: this.vertebra, compartment: this.compartment }
            })
            .then((res) => {
                this.bodyComp = res.data.data;
                for (var item of this.bodyComp) {
                    this.bodyComp_dates.push(item[0])
                    this.bodyComp_changes.push(item[1])
                }
            })
            .catch(() => {
                // Error already surfaced via toast by the shared api client.
            })
        },
        async fetchData(){
            await this.fetchBodyComp();
            await this.fetchWeights();
            return
            //  Should return promise
        },
        plotChange(){
            const plot = document.getElementById("plot");

            var weights =  {
                x: [...this.weight_dates],
                y: [...this.weight_changes],
                name: 'Weight',
                type:'lines+markers',
                line: { color: '#38bdf8', width: 2 },
                marker: { color: '#38bdf8', size: 6 },
            };
            if (this.showBodyCompTrend) {
                var bodyComp =  {
                x: [...this.bodyComp_dates],
                y: [...this.bodyComp_changes],
                name: `${this.compartment}@${this.vertebra}`,
                type:'lines+markers',
                line: { color: '#34d399', width: 2 },
                marker: { color: '#34d399', size: 6 },
                };


                var data = [weights, bodyComp];
            } else {
                var data = [weights];
            }

            var layout = {
                showlegend: true,
                legend: {x: 0., y: 1.2, font: { color: '#adbac7' }},
                paper_bgcolor: '#161b22',
                plot_bgcolor: '#161b22',
                font: { color: '#adbac7' },
                xaxis: { gridcolor: '#30363d', zerolinecolor: '#3d444d' },
                yaxis: { gridcolor: '#30363d', zerolinecolor: '#3d444d' },
                margin: { t: 30 },
            };

            Plotly.newPlot(plot, data, layout);
        },
        viewPredictions(){
            this.$router.push({ name: 'patientPredictions', params: { project: this.$route.params.project, vertebra: 'C3', patient_id: this.patientID}})
        }
    },
    created: async function() {
    await this.fetchData()
    .then(() => {
        this.plotChange();
    })
    },
    props: [],
}

</script>

<template>

<div class=" flex justify-center items-center w-full p-8 content-center mx-auto">
    <div class="inline-block grow text-accent-400 text-xl flex-1"> Patient ID:
        <div class="inline-block text-ink-primary">
            {{ patientID }}
        </div>
    </div>
    <div class="align-right">
        <Button variant="secondary" @click="viewPredictions();">
             View predictions
        </Button>
    </div>
</div>
<div>
    <!-- Add + delete weight -->
    <div class="relative flex items-center w-full p-8 content-center mx-auto">
        <div class="inline-block grow text-accent-400 text-l flex-1"> Add weight (in kg) and assessment date :
            <form @submit.prevent="addWeight();" class="inline-flex items-center gap-3">
            <input v-model=this.weight step="any" type="number" class="bg-surface-raised border border-line-subtle rounded text-ink-primary text-sm h-10 px-2 focus:outline-none focus:ring-2 focus:ring-brand-500" required/>
            <input v-model=this.date type="date" class="bg-surface-raised border border-line-subtle rounded text-ink-primary text-sm h-10 px-2 focus:outline-none focus:ring-2 focus:ring-brand-500" required/>
            <Button type="submit" variant="primary"> Add Entry </Button>
            </form>

        </div>
    </div>
</div>

<!-- Weight Table -->


<div class="relative align-center overflow-x-auto p-3">
    <table class="w-3/4 text-sm text-left border-line-subtle bg-surface-card">
        <thead class="text-sm text-ink-primary">
            <tr>
                <th scope="col" class="px-6 py-3">
                    Assessment Date
                </th>
                <th scope="col" class="px-6 py-3">
                    Weight (in kg)
                </th>
                <th scope="col" class="px-6 py-3">
                    % weight change from first measurement
                </th>
                <th scope="col" class="px-6 py-3">

                </th>
            </tr>
        </thead>
        <tbody class="text-sm text-ink-primary bg-surface-raised">
            <!-- Rows go here -->
            <tr v-for="item in this.weights" :key="item[0]">
                <th scope="col" class="px-6 py-3">
                    {{ item[0] }}
                </th>
                <th scope="col" class="px-6 py-3">
                    {{ item[1] }}
                </th>
                <th scope="col" class="px-6 py-3">
                    {{ item[2] }}
                </th>
                <th scope="col" class="px-6 py-3" >
                    <button type="button" class="text-red-400 font-bold hover:text-red-300" :aria-label="`Delete weight entry from ${item[0]}`" @click="DeleteWeight(item[0]);">DELETE</button>
                </th>
            </tr>
        </tbody>
    </table>

</div>


<div class="w-3/4 mx-auto p-3">
    <div id="plot" class="h-[450px] rounded overflow-hidden border border-line-subtle"></div>
</div>



<!-- List images available -->

</template>


<style scoped>
</style>