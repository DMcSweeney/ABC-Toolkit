<script>
import axios from 'axios';
import moment from 'moment';
import Plotly from 'plotly.js-dist-min';


export default {
    name: 'PatientPage',
    data() {
        return {
            showBodyCompTrend: true,
            patientID: this.$route.params.patientID,
            vertebra: 'C3',
            compartment: 'skeletal_muscle',
            weight: Number,
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
            console.log(`Submitting ${this.weight} & ${this.date}`)
            const today = new Date()
            today.setHours(0, 0, 0, 0);

            if (this.weight < 0) {
                alert("Weight can't be negative");
                return false;
            }

            if (moment(this.date) > today) {
                alert("Assessment date can't be in the future");
                return false;
            }
            // If passes checks, insert into database 
            const path = `${import.meta.env.VITE_BACKEND_URI}/api/weights/post_weight?patient_id=${this.patientID}&weight=${this.weight}&date=${this.date}`
            axios.post(path)
                .then(async (res) => {
                    await this.fetchWeights();
                    this.plotChange(this.weight_dates, this.weight_changes);
                })
                .catch((err) => {
                    alert(err);
                })
        },
        DeleteWeight(date){            
            const path = `${import.meta.env.VITE_BACKEND_URI}/api/weights/delete_weight?_id=${this.patientID}&date=${date}`
            axios.post(path)
            .then(async (res) => {
                console.log('Successfully deleted entry');
                await this.fetchWeights();
                this.plotChange(this.weight_dates, this.weight_changes);
            
            })  
            .catch((err) => {
                alert(err);
                return false;
            })

        },
        fetchWeights(){
            const path = `${import.meta.env.VITE_BACKEND_URI}/api/weights/fetch_weights?_id=${this.patientID}`
            return axios.get(path)
            .then((res) => {
                this.weights = res.data.data;
                for (var item of this.weights) {
                    this.weight_dates.push(item[0])
                    this.weight_changes.push(Number(item[2]))
                }
                 
            })
            .catch((err) => {
                console.log(err);
                alert(err);
            })

        },
        fetchBodyComp(){
            // Fetch body comp metrics from segmented scans
            const path = `${import.meta.env.VITE_BACKEND_URI}/api/post_process/get_stats_for_patient?project=${this.$route.params.project}&patient_id=${this.patientID}&vertebra=${this.vertebra}&compartment=${this.compartment}`
            return axios.get(path)
            .then((res) => {
                this.bodyComp = res.data.data;
                for (var item of this.bodyComp) {
                    this.bodyComp_dates.push(item[0])
                    this.bodyComp_changes.push(item[1])
                }
            })
            .catch((err) => {
                alert(err);
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
                type:'lines+markers'
            };
            if (this.showBodyCompTrend) {
                var bodyComp =  {
                x: [...this.bodyComp_dates],
                y: [...this.bodyComp_changes],
                name: `${this.compartment}@${this.vertebra}`,
                type:'lines+markers'
                };


                var data = [weights, bodyComp];
            } else {
                var data = [weights];
            }
            
            var layout = {
                showlegend: true,
                legend: {x: 0., y: 1.2}
            };

            Plotly.newPlot(plot, data, layout);
        }
    },
    created: async function() {
    await this.fetchData()
    .then(() => {
        this.plotChange();
    }).catch((err) => {
        alert(err);
    })
    },
    mounted(){
        
    },
    props: [],
}

</script>

<template>

<div class="relative flex justify-center items-center w-full p-8 content-center mx-auto">
    <div class="inline-block grow text-indigo-200 text-xl flex-1"> Patient ID: 
        <div class="inline-block text-stone-200">
            {{ patientID }}
        </div>
    </div>
    <div class="inline-block grow text-bold text-indigo-200 hover:text-white text-xl flex-1">
        <button class="text-sm rounded ml-3 p-2 bg-stone-200 text-stone-200 border-white hover:border hover:border-blue hover:text-blue bg-indigo-700">
             View predictions
        </button>
    </div>  
</div>
<div>
    <!-- Add + delete weight -->
    <div class="relative flex items-center w-full p-8 content-center mx-auto">
        <div class="inline-block grow text-indigo-200 text-l flex-1"> Add weight (in kg) and assessment date : 
            <form @submit.prevent="addWeight();"> 
            <input v-model=this.weight type="number" class="bg-stone-200 border-gray-300 text-zinc-900 text-sm" required/>
            <input v-model=this.date type="date" class="ml-3 bg-stone-200 border-gray-300 text-zinc-900 text-sm" required/>
            <button type="submit"
            class="text-sm rounded ml-3 p-2 bg-stone-200 text-stone-200 border-white hover:border hover:border-blue hover:text-blue bg-indigo-700"
             value="Add entry"> Add Entry
            </button>
            </form>

        </div>
    </div>
</div>

<!-- Weight Table -->


<div class="relative align-center overflow-x-auto p-3">
    <table class="w-3/4 text-sm text-left text-gray-500 border-zinc-900 bg-zinc-900">
        <thead class="text-sm text-stone-200">
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
        <tbody class="text-sm text-zinc-900 bg-white">
            <!-- Rows go here -->
            <tr v-for="item in this.weights">
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
                    <a class="text-blue font-bold hover:text-blue hover:font-bold" @click="DeleteWeight(item[0]);">DELETE</a>
                </th>
            </tr>
        </tbody>
    </table>

</div>


<div id="plot">
    
</div>



<!-- List images available -->

</template>


<style scoped>
</style>