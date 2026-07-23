<script>
import api from '@/api/client';
import moment from 'moment';
import Plotly from 'plotly.js-dist-min';
import Multiselect from 'vue-multiselect';
import { useToastStore } from '@/stores/toast';
import { useThemeStore } from '@/stores/theme';
import Button from '../ui/Button.vue';
import Select from '../ui/Select.vue';
import LoadingState from '../ui/LoadingState.vue';

const METRIC_OPTIONS = [
    { value: 'area_pct_change', label: '% Change (Area)' },
    { value: 'area', label: 'Area (cm²)' },
    { value: 'density', label: 'Density (HU)' },
];

export default {
    name: 'PatientPage',
    components: { Button, Select, Multiselect, LoadingState },
    setup() {
        return { toast: useToastStore(), themeStore: useThemeStore() };
    },
    data() {
        return {
            patientID: this.$route.params.patientID,
            weight: new Number(),
            date: new Date(),
            weights: new Array(),
            weight_dates: new Array(),
            weight_changes: new Array(),

            // Body composition filter state -- populated dynamically from what this patient
            // actually has data for, rather than hardcoded (see get_patient_filter_options).
            filterOptions: [],
            filterOptionsLoading: false,
            selectedVertebrae: [],
            selectedCompartments: [],
            selectedModality: '',
            metric: 'area_pct_change',
            metricOptions: METRIC_OPTIONS,

            // Keyed by combo key ("VERTEBRA · compartment") -> array of data points.
            trendData: {},
            populationData: {},
            bodyCompLoading: false,

            reportLoading: false,
        }
    },
    computed: {
        availableVertebrae() {
            return [...new Set(this.filterOptions.map(o => o.vertebra))].sort();
        },
        availableModalities() {
            const relevant = this.selectedVertebrae.length
                ? this.filterOptions.filter(o => this.selectedVertebrae.includes(o.vertebra))
                : this.filterOptions;
            return [...new Set(relevant.map(o => o.modality))].sort();
        },
        availableCompartments() {
            const relevant = this.filterOptions.filter(o =>
                (!this.selectedVertebrae.length || this.selectedVertebrae.includes(o.vertebra)) &&
                (!this.selectedModality || o.modality === this.selectedModality)
            );
            return [...new Set(relevant.map(o => o.compartment))].sort();
        },
        // Cartesian product of selected vertebrae x selected compartments, at the single
        // selected modality -- combos with no underlying data are silently skipped, since not
        // every pairing a multi-select produces is guaranteed to exist for this patient.
        combos() {
            const combos = [];
            for (const vertebra of this.selectedVertebrae) {
                for (const compartment of this.selectedCompartments) {
                    const exists = this.filterOptions.some(o =>
                        o.vertebra === vertebra && o.compartment === compartment && o.modality === this.selectedModality
                    );
                    if (exists) {
                        combos.push({ vertebra, compartment, modality: this.selectedModality, key: `${vertebra} · ${compartment}` });
                    }
                }
            }
            return combos;
        },
        // Single watchable source combining all three filter selections, so a change to any of
        // them triggers exactly one re-fetch instead of one per changed selection.
        filterSelection() {
            return { vertebrae: this.selectedVertebrae, compartments: this.selectedCompartments, modality: this.selectedModality };
        },
        metricUnit() {
            return { area_pct_change: '%', area: 'cm²', density: 'HU' }[this.metric];
        },
        metricAxisLabel() {
            return { area_pct_change: 'Area % change from baseline', area: 'Area (cm²)', density: 'Density (HU)' }[this.metric];
        },
        // The population endpoint only ever returns absolute area/density (comparing % change
        // across patients with different baselines isn't meaningful), so % change falls back to area.
        populationMetricField() {
            return this.metric === 'density' ? 'density' : 'area';
        },
        percentileCallouts() {
            const field = this.populationMetricField;
            const unit = field === 'density' ? 'HU' : 'cm²';
            return this.combos.map(combo => {
                const population = (this.populationData[combo.key] || []).map(p => p[field]).filter(v => v !== null && v !== undefined);
                const patientPoints = this.trendData[combo.key] || [];
                if (!population.length || !patientPoints.length) return null;
                const latest = patientPoints[patientPoints.length - 1];
                const value = latest[field];
                const rank = population.filter(v => v <= value).length;
                const percentile = Math.round((rank / population.length) * 100);
                return { key: combo.key, value, percentile, unit };
            }).filter(Boolean);
        },
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
                    this.plotWeightChange();
                })
                .catch(() => {
                    // Error already surfaced via toast by the shared api client.
                })
        },
        DeleteWeight(date){
            api.post('/api/weights/delete_weight', null, { params: { _id: this.patientID, date: date } })
            .then(async () => {
                await this.fetchWeights();
                this.plotWeightChange();
            })
            .catch(() => {
                // Error already surfaced via toast by the shared api client.
            })

        },
        fetchWeights(){
            this.weight_dates = [];
            this.weight_changes = [];
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
        parseDDMMYYYY(dateStr) {
            const [day, month, year] = dateStr.split('-').map(Number);
            return new Date(year, month - 1, day);
        },
        fetchFilterOptions() {
            this.filterOptionsLoading = true;
            return api.get('/api/database/get_patient_filter_options', {
                params: { project: this.$route.params.project, patient_id: this.patientID }
            })
                .then((res) => {
                    this.filterOptions = res.data.data;
                    this.selectDefaultCombo();
                })
                .catch(() => {
                    // Error already surfaced via toast by the shared api client.
                })
                .finally(() => {
                    this.filterOptionsLoading = false;
                });
        },
        selectDefaultCombo() {
            // Default to whichever combo belongs to this patient's most recently acquired scan.
            if (!this.filterOptions.length) return;
            const mostRecent = this.filterOptions.reduce((latest, o) =>
                this.parseDDMMYYYY(o.acquisition_date) > this.parseDDMMYYYY(latest.acquisition_date) ? o : latest
            );
            this.selectedVertebrae = [mostRecent.vertebra];
            this.selectedModality = mostRecent.modality;
            this.selectedCompartments = [mostRecent.compartment];
        },
        fetchComboData(combo) {
            const params = { project: this.$route.params.project, patient_id: this.patientID, vertebra: combo.vertebra, compartment: combo.compartment, modality: combo.modality };
            return Promise.all([
                api.get('/api/post_process/get_stats_for_patient', { params }).then(res => res.data.data).catch(() => []),
                api.get('/api/post_process/get_population_stats', { params }).then(res => res.data.data).catch(() => []),
            ]).then(([trend, population]) => ({ trend, population }));
        },
        fetchBodyCompCombos() {
            if (!this.combos.length) {
                this.trendData = {};
                this.populationData = {};
                this.plotBodyComp();
                this.plotPopulation();
                return Promise.resolve();
            }
            this.bodyCompLoading = true;
            return Promise.all(this.combos.map(combo => this.fetchComboData(combo)))
                .then((results) => {
                    const trendData = {};
                    const populationData = {};
                    this.combos.forEach((combo, i) => {
                        trendData[combo.key] = results[i].trend;
                        populationData[combo.key] = results[i].population;
                    });
                    this.trendData = trendData;
                    this.populationData = populationData;
                })
                .finally(() => {
                    this.bodyCompLoading = false;
                    // Wait for the v-show DOM patch to actually remove display:none before
                    // Plotly measures the container -- otherwise it draws into a 0x0 box and
                    // never re-detects the real size once the div becomes visible again.
                    this.$nextTick(() => {
                        this.plotBodyComp();
                        this.plotPopulation();
                    });
                });
        },
        async fetchData(){
            await this.fetchFilterOptions();
            await Promise.all([this.fetchWeights(), this.fetchBodyCompCombos()]);
        },
        getPlotColors() {
            // Plotly renders to SVG and can't read CSS variables, so it needs its own literal
            // hex palette per theme, matching the surface/ink/line/brand/accent token values.
            if (this.themeStore.theme === 'light') {
                return {
                    background: '#ffffff', font: '#475569', grid: '#cbd5e1', zeroline: '#94a3b8',
                    weightLine: '#0284c7', qcPass: '#059669', qcTodo: '#94a3b8', patientMarker: '#dc2626',
                };
            }
            return {
                background: '#334155', font: '#cbd5e1', grid: '#475569', zeroline: '#64748b',
                weightLine: '#38bdf8', qcPass: '#34d399', qcTodo: '#94a3b8', patientMarker: '#f87171',
            };
        },
        getCategoricalPalette() {
            // Cycling categorical palette for an arbitrary number of trend lines / combos.
            if (this.themeStore.theme === 'light') {
                return ['#0284c7', '#059669', '#d97706', '#7c3aed', '#db2777', '#0891b2'];
            }
            return ['#38bdf8', '#34d399', '#fbbf24', '#a78bfa', '#f472b6', '#22d3ee'];
        },
        plotWeightChange(){
            const plot = document.getElementById("plot");
            if (!plot) return;
            const colors = this.getPlotColors();

            var weights =  {
                x: [...this.weight_dates],
                y: [...this.weight_changes],
                name: 'Weight',
                type:'lines+markers',
                line: { color: colors.weightLine, width: 2 },
                marker: { color: colors.weightLine, size: 6 },
            };

            var layout = {
                showlegend: true,
                legend: {x: 0., y: 1.2, font: { color: colors.font }},
                paper_bgcolor: colors.background,
                plot_bgcolor: colors.background,
                font: { color: colors.font },
                xaxis: { title: 'Date', gridcolor: colors.grid, zerolinecolor: colors.zeroline },
                yaxis: { title: '% change from first measurement', gridcolor: colors.grid, zerolinecolor: colors.zeroline },
                margin: { t: 30 },
            };

            Plotly.newPlot(plot, [weights], layout);
        },
        plotBodyComp(){
            const plot = document.getElementById("bodycomp-plot");
            if (!plot) return;
            const colors = this.getPlotColors();
            const palette = this.getCategoricalPalette();

            const traces = this.combos.map((combo, i) => {
                const points = this.trendData[combo.key] || [];
                const traceColor = palette[i % palette.length];
                return {
                    x: points.map(p => p.date),
                    y: points.map(p => p[this.metric]),
                    customdata: points.map(p => ({ series_uuid: p.series_uuid, vertebra: combo.vertebra })),
                    name: combo.key,
                    type: 'scatter',
                    mode: 'lines+markers',
                    line: { color: traceColor, width: 1.5 },
                    marker: {
                        color: points.map(p => p.qc_status === 1 ? colors.qcPass : colors.qcTodo),
                        size: 9,
                        line: { color: traceColor, width: 1.5 },
                    },
                };
            });

            var layout = {
                showlegend: true,
                legend: {x: 0., y: 1.2, font: { color: colors.font }},
                paper_bgcolor: colors.background,
                plot_bgcolor: colors.background,
                font: { color: colors.font },
                xaxis: { title: 'Date', gridcolor: colors.grid, zerolinecolor: colors.zeroline },
                yaxis: { title: `${this.metricAxisLabel} (${this.metricUnit})`, gridcolor: colors.grid, zerolinecolor: colors.zeroline },
                margin: { t: 30 },
            };

            Plotly.newPlot(plot, traces, layout, { responsive: true });
            plot.removeAllListeners('plotly_click');
            plot.on('plotly_click', (evt) => this.handlePointClick(evt));
        },
        plotPopulation(){
            const plot = document.getElementById("population-plot");
            if (!plot) return;
            const colors = this.getPlotColors();
            const palette = this.getCategoricalPalette();
            const field = this.populationMetricField;
            const unitLabel = field === 'density' ? 'Density (HU)' : 'Area (cm²)';
            const comboKeys = this.combos.map(c => c.key);
            const traces = [];

            this.combos.forEach((combo, i) => {
                const population = this.populationData[combo.key] || [];
                const traceColor = palette[i % palette.length];
                if (population.length) {
                    traces.push({
                        x: population.map(() => combo.key),
                        y: population.map(p => p[field]),
                        type: 'violin',
                        name: combo.key,
                        legendgroup: combo.key,
                        showlegend: false,
                        box: { visible: true },
                        meanline: { visible: true },
                        points: false,
                        line: { color: traceColor },
                        fillcolor: traceColor,
                        opacity: 0.5,
                    });
                }
                const patientPoints = this.trendData[combo.key] || [];
                if (patientPoints.length) {
                    traces.push({
                        x: patientPoints.map(() => combo.key),
                        y: patientPoints.map(p => p[field]),
                        customdata: patientPoints.map(p => ({ series_uuid: p.series_uuid, vertebra: combo.vertebra })),
                        type: 'scatter',
                        mode: 'markers',
                        name: `${combo.key} (this patient)`,
                        legendgroup: combo.key,
                        showlegend: false,
                        marker: { color: colors.patientMarker, size: 11, symbol: 'diamond', line: { color: colors.background, width: 1 } },
                    });
                }
            });

            var layout = {
                showlegend: false,
                paper_bgcolor: colors.background,
                plot_bgcolor: colors.background,
                font: { color: colors.font },
                xaxis: { gridcolor: colors.grid, zerolinecolor: colors.zeroline, categoryorder: 'array', categoryarray: comboKeys },
                yaxis: { title: unitLabel, gridcolor: colors.grid, zerolinecolor: colors.zeroline },
                violingap: 0.4,
                margin: { t: 30 },
            };

            Plotly.newPlot(plot, traces, layout, { responsive: true });
            plot.removeAllListeners('plotly_click');
            plot.on('plotly_click', (evt) => this.handlePointClick(evt));
        },
        handlePointClick(evt){
            const point = evt.points && evt.points[0];
            if (!point || !point.customdata || !point.customdata.series_uuid) return;
            const { series_uuid, vertebra } = point.customdata;
            this.$router.push({
                name: 'patientPredictions',
                params: { project: this.$route.params.project, vertebra, patient_id: this.patientID },
                query: { series: series_uuid },
            });
        },
        viewPredictions(){
            const vertebra = this.selectedVertebrae[0] || 'C3';
            this.$router.push({ name: 'patientPredictions', params: { project: this.$route.params.project, vertebra, patient_id: this.patientID}})
        },
        generateReport(){
            if (!this.combos.length) {
                this.toast.error('Select at least one vertebra/compartment combination first');
                return;
            }
            this.reportLoading = true;
            api({
                url: '/api/post_process/generate_report',
                method: 'POST',
                data: {
                    project: this.$route.params.project,
                    patient_id: this.patientID,
                    combos: this.combos.map(c => ({ vertebra: c.vertebra, compartment: c.compartment, modality: c.modality })),
                },
                responseType: 'blob',
            })
                .then((response) => {
                    const href = URL.createObjectURL(response.data);
                    const link = document.createElement('a');
                    link.href = href;
                    link.setAttribute('download', `${this.patientID}_report.pdf`);
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    URL.revokeObjectURL(href);
                })
                .catch(() => {
                    // Error already surfaced via toast by the shared api client.
                })
                .finally(() => {
                    this.reportLoading = false;
                });
        },
    },
    created: async function() {
        await this.fetchData();
        this.plotWeightChange();
    },
    watch: {
        'themeStore.theme'() {
            // Re-render the charts with the new theme's colors instead of requiring a reload.
            if (this.weight_dates.length) this.plotWeightChange();
            if (this.combos.length) { this.plotBodyComp(); this.plotPopulation(); }
        },
        metric() {
            this.plotBodyComp();
            this.plotPopulation();
        },
        filterSelection: {
            handler() {
                this.fetchBodyCompCombos();
            },
            deep: true,
        },
    },
    props: [],
}

</script>

<template>

<div class="w-3/4 mx-auto p-6">

    <!-- Page header -->
    <div class="flex items-end justify-between gap-4 pb-6 mb-6 border-b border-line-subtle">
        <div>
            <p class="text-ink-muted text-xs font-bold uppercase tracking-wide">Patient</p>
            <p class="text-ink-primary text-3xl font-bold tracking-tight">{{ patientID }}</p>
        </div>
        <div class="flex gap-3">
            <Button variant="secondary" :loading="reportLoading" @click="generateReport();">
                 Generate report
            </Button>
            <Button variant="secondary" @click="viewPredictions();">
                 View predictions
            </Button>
        </div>
    </div>

    <!-- Add weight -->
    <div class="bg-surface-card border border-line-subtle rounded p-4 mb-6">
        <p class="text-ink-secondary text-sm font-bold pb-3">Add weight entry</p>
        <form @submit.prevent="addWeight();" class="flex flex-wrap items-end gap-3">
            <div>
                <label class="block text-ink-muted text-xs pb-1">Weight (kg)</label>
                <input v-model=this.weight step="any" type="number" class="bg-surface-raised border border-line-subtle rounded text-ink-primary text-sm h-10 px-2 focus:outline-none focus:ring-2 focus:ring-brand-500" required/>
            </div>
            <div>
                <label class="block text-ink-muted text-xs pb-1">Assessment date</label>
                <input v-model=this.date type="date" class="bg-surface-raised border border-line-subtle rounded text-ink-primary text-sm h-10 px-2 focus:outline-none focus:ring-2 focus:ring-brand-500" required/>
            </div>
            <Button type="submit" variant="primary"> Add Entry </Button>
        </form>
    </div>

    <!-- Weight Table -->
    <div class="overflow-x-auto mb-6">
        <table class="w-full text-sm text-left border-line-subtle bg-surface-card">
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
                        <button type="button" class="text-red-600 dark:text-red-400 font-bold hover:text-red-500 dark:hover:text-red-300" :aria-label="`Delete weight entry from ${item[0]}`" @click="DeleteWeight(item[0]);">DELETE</button>
                    </th>
                </tr>
            </tbody>
        </table>
    </div>

    <div class="mb-6">
        <div id="plot" class="h-[450px] rounded overflow-hidden border border-line-subtle"></div>
    </div>

    <!-- Body composition filters -->
    <div>
        <div v-if="filterOptionsLoading">
            <LoadingState label="Loading available scan data..." />
        </div>
        <div v-else-if="!filterOptions.length" class="text-ink-muted text-sm py-4">
            No completed segmentations found for this patient yet.
        </div>
        <div v-else class="bg-surface-card border border-line-subtle rounded p-4">
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                    <label class="block text-ink-secondary text-sm pb-1">Vertebra</label>
                    <Multiselect
                        v-model="selectedVertebrae"
                        :options="availableVertebrae"
                        :multiple="true"
                        :close-on-select="false"
                        :clear-on-select="false"
                        placeholder="Select vertebrae"
                    />
                </div>
                <div>
                    <label class="block text-ink-secondary text-sm pb-1">Compartment</label>
                    <Multiselect
                        v-model="selectedCompartments"
                        :options="availableCompartments"
                        :multiple="true"
                        :close-on-select="false"
                        :clear-on-select="false"
                        placeholder="Select compartments"
                    />
                </div>
                <div>
                    <Select v-model="selectedModality" label="Modality" :options="availableModalities" placeholder="Select modality" />
                </div>
                <div>
                    <Select v-model="metric" label="Metric" :options="metricOptions" />
                </div>
            </div>
        </div>

        <!-- Body composition trend chart -->
        <div class="mt-4">
            <div v-if="bodyCompLoading">
                <LoadingState label="Loading body composition trend..." />
            </div>
            <div v-else-if="!combos.length" class="text-ink-muted text-sm py-4">
                Select at least one vertebra and compartment to plot a trend.
            </div>
            <div v-show="!bodyCompLoading && combos.length" id="bodycomp-plot" class="h-[450px] rounded overflow-hidden border border-line-subtle"></div>
        </div>

        <!-- Population comparison chart -->
        <div class="mt-6">
            <div class="text-ink-secondary text-sm pb-2">How this patient compares to the rest of the project</div>
            <div v-show="!bodyCompLoading && combos.length" id="population-plot" class="h-[400px] rounded overflow-hidden border border-line-subtle"></div>
            <div v-if="percentileCallouts.length" class="flex flex-wrap gap-4 pt-3 text-sm text-ink-secondary">
                <div v-for="c in percentileCallouts" :key="c.key">
                    <span class="text-accent-400 font-bold">{{ c.key }}</span> — latest measurement: {{ c.value.toFixed(1) }} {{ c.unit }}, {{ c.percentile }}th percentile for this project
                </div>
            </div>
        </div>
    </div>

</div>

</template>


<style scoped>
</style>
<style src="vue-multiselect/dist/vue-multiselect.min.css"></style>
<style>
/* vue-multiselect's bundled CSS hardcodes a white/light look, so it needs its own dark-theme
   overrides here -- the library has no theme awareness of its own. */
:root[data-theme="dark"] .multiselect__tags,
:root[data-theme="dark"] .multiselect__content-wrapper {
    background-color: rgb(var(--color-surface-raised));
    border-color: rgb(var(--color-line-subtle));
    color: rgb(var(--color-ink-primary));
}
:root[data-theme="dark"] .multiselect__input,
:root[data-theme="dark"] .multiselect__single {
    background: rgb(var(--color-surface-raised));
    color: rgb(var(--color-ink-primary));
}
:root[data-theme="dark"] .multiselect__placeholder {
    color: rgb(var(--color-ink-muted));
}
:root[data-theme="dark"] .multiselect__option {
    color: rgb(var(--color-ink-primary));
}
:root[data-theme="dark"] .multiselect__option--highlight {
    background: rgb(var(--color-brand-600));
    color: rgb(var(--color-ink-primary));
}
:root[data-theme="dark"] .multiselect__option--selected {
    background: rgb(var(--color-surface-card));
}
</style>
