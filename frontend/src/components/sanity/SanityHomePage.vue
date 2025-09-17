<script>
import axios from 'axios';
import QASummaryEntry from './QASummaryEntry.vue';

export default {
    name: 'SanityHomePage',
    data() {
        return {
            project:this.$route.params.project,
            levels: null,
            qc_summary: Object,
            ready: false
        }
    },
    methods: {
        async FetchPatients(){
            const url = `${import.meta.env.VITE_BACKEND_URI}/api/database/get_levels_to_QA?project=${this.project}`
            await axios.get(url).then( (res) => {
                this.levels=res.data.data
            }).catch((err) => {
                console.log(err);
            })

        },
        async getSummary(vertebra){
            const path = `${import.meta.env.VITE_BACKEND_URI}/api/sanity/get_summary?project=${this.project}&vertebra=${vertebra}`;
            await axios.get(path)
                .then((res) => {
                // Fails are reported as "both", "segmentation" or "spine" failures, need to sum them all
                //var fails = Object.values(res.data.fail).reduce((acc, val) => acc + val, 0);
                this.qc_summary[vertebra] = {'pass': res.data.pass, 'fail':res.data.fail, 'todo': res.data.todo, 'total': res.data.total};
            })
                .catch((err) => {
                console.log(`${vertebra} -- ${err}`)
                
            });
        },
        async getAllSummaries() {
            const pendingRequests = [];

            for (const vertebra of this.levels) {
                pendingRequests.push(this.getSummary(vertebra))
            }
            await Promise.all(pendingRequests);
        }

    },
    async created() {
        await this.FetchPatients();
        await this.getAllSummaries();
        this.ready=true;
        
    },      
    props: [],
    components: {QASummaryEntry}
}

</script>

<template>
<div class="h-full w-full flex justify-center my-10">
  <h1 class="text-4xl text-stone-200 font-bold">
    QA summary
  </h1>
</div>



<!-- <div class="h-full w-full absolute my-6 mx-auto">
    <div class="w-3/4 h-6 text-stone-200 m-auto text-xl font-bold flex justify-center">
        <div class="align-start content-center">
            Level
        </div>
        <div class="content-center mx-auto text-green-500">
            Passed
        </div>
        <div class="content-center mx-auto text-red-500">
            Failed
        </div>
        <div class="content-center mx-auto text-zinc-500">
            Todo
        </div>
    </div>
    <ul v-for="level in this.levels">
        <div class="flex justify-center m-auto">
            <QASummaryEntry :level=level :num_pass=100 :num_fail=10 :num_todo=10>
            </QASummaryEntry>
        </div>
    </ul>

</div> -->

<div v-if="ready" class="m-auto w-2/3 p-3">
        <div class="m-auto w-5/6 h-8 text-stone-200 text-xl font-bold rounded flex justify-center">
            <div class="align-start content-center"> Level </div>
            <div class="content-center mx-auto text-green-500"> Passed </div>
            <div class="content-center mx-auto text-red-500">Failed </div>
            <div class="content-center mx-auto text-zinc-500"> TODO </div>
            <div class="flex m-auto justify-end hover:text-indigo-400 mr-3"> Inspect </div>
        </div>
        <ul v-for="[key, value] in Object.entries(this.qc_summary)">
        <div class="flex justify-center m-auto">
            <QASummaryEntry :level=key :num_pass=value.pass :num_fail=value.fail :num_todo=value.todo>
            </QASummaryEntry>
        </div>
    </ul>

</div>


</template>


<style scoped>
</style>