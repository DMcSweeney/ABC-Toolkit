<script>
import api from '@/api/client';
import QASummaryEntry from './QASummaryEntry.vue';

export default {
    name: 'SanityHomePage',
    data() {
        return {
            project:this.$route.params.project,
            levels: null,
            qc_summary: Object,
            ready: false,
            loadError: false,
        }
    },
    methods: {
        async FetchPatients(){
            await api.get('/api/database/get_levels_to_QA', { params: { project: this.project } }).then( (res) => {
                this.levels=res.data.data
            }).catch(() => {
                // Error already surfaced via toast by the shared api client.
                this.loadError = true;
            })

        },
        async getSummary(vertebra){
            await api.get('/api/sanity/get_summary', { params: { project: this.project, vertebra: vertebra } })
                .then((res) => {
                // Fails are reported as "both", "segmentation" or "spine" failures, need to sum them all
                //var fails = Object.values(res.data.fail).reduce((acc, val) => acc + val, 0);
                this.qc_summary[vertebra] = {'pass': res.data.pass, 'fail':res.data.fail, 'todo': res.data.todo, 'total': res.data.total};
            })
                .catch(() => {
                this.loadError = true;
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
        if (this.levels) {
            await this.getAllSummaries();
        }
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

<div v-if="!ready" class="m-auto w-2/3 p-3 text-center text-stone-400 text-xl">
    Loading...
</div>

<div v-else-if="loadError" class="m-auto w-2/3 p-3 text-center text-red-400 text-xl">
    Couldn't load the QA summary for this project. See the error notification for details, or try reloading the page.
</div>

<div v-else-if="ready" class="m-auto w-2/3 p-3">
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