<script>
import api from '@/api/client';
import QASummaryEntry from './QASummaryEntry.vue';
import LoadingState from '../ui/LoadingState.vue';

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
    components: {QASummaryEntry, LoadingState}
}

</script>

<template>
<div class="h-full w-full flex justify-center my-10">
  <h1 class="text-4xl text-ink-primary font-bold tracking-tight">
    QA summary
  </h1>
</div>

<LoadingState v-if="!ready" label="Loading QA summary..." />

<div v-else-if="loadError" class="m-auto w-2/3 p-3 text-center text-red-600 dark:text-red-400 text-xl">
    Couldn't load the QA summary for this project. See the error notification for details, or try reloading the page.
</div>

<div v-else-if="ready" class="m-auto w-2/3 p-3">
        <div class="m-auto w-5/6 h-8 text-ink-primary text-xl font-bold rounded flex justify-center">
            <div class="align-start content-center"> Level </div>
            <div class="content-center mx-auto text-brand-400"> Passed </div>
            <div class="content-center mx-auto text-red-600 dark:text-red-400">Failed </div>
            <div class="content-center mx-auto text-ink-muted"> TODO </div>
            <div class="flex m-auto justify-end hover:text-brand-400 mr-3"> Inspect </div>
        </div>
        <ul>
        <li v-for="[key, value] in Object.entries(this.qc_summary)" :key="key" class="flex justify-center m-auto">
            <QASummaryEntry :level=key :num_pass=value.pass :num_fail=value.fail :num_todo=value.todo>
            </QASummaryEntry>
        </li>
    </ul>

</div>


</template>


<style scoped>
</style>