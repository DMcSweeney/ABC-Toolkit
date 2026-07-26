<script>
import { Niivue } from '@niivue/niivue';
import api from '@/api/client';
import { useToastStore } from '@/stores/toast';
import Button from '../ui/Button.vue';
import Card from '../ui/Card.vue';
import Modal from '../ui/Modal.vue';
import LoadingState from '../ui/LoadingState.vue';
import Badge from '../ui/Badge.vue';
import EmptyState from '../ui/EmptyState.vue';

// Tools map onto NiiVue's drawing pen: value 1 paints "this compartment", 0 erases.
const TOOLS = [
    { key: 'brush', label: 'Brush', penValue: 1, isFilledPen: false },
    { key: 'eraser', label: 'Eraser', penValue: 0, isFilledPen: false },
    { key: 'fill', label: 'Fill', penValue: 1, isFilledPen: true },
];

const DEFAULT_PEN_SIZE = 5;

// Mirrors engine.py's _get_window_level() settings bank closely enough to be a sensible
// starting point per modality (that function is actually keyed per-vertebra too, but CT is
// window:400/level:50 for nearly every vertebra in model_bank, so a per-modality default
// covers the common case well).
const WINDOW_LEVEL_DEFAULTS = {
    CT: { window: 400, level: 50 },
    CBCT: { window: 400, level: 50 },
    LowDoseCT: { window: 400, level: 50 },
    MR: { window: 2693, level: 307 },
};
const DEFAULT_WINDOW_LEVEL = { window: 400, level: 50 };

// IMAT is derived from skeletal_muscle (see engine.py's extract_imat) rather than being an
// independently drawn compartment - the backend (api/editor.py) exposes their union as a
// single 'total_muscle' compartment, which is also the exact compartment name engine.py
// expects to re-derive both files from an edited mask, so no frontend-side translation needed.
const COMPARTMENT_LABELS = {
    total_muscle: 'Muscle (incl. IMAT)',
};

export default {
    name: 'ContourEditor',
    components: { Button, Card, Modal, LoadingState, Badge, EmptyState },
    setup() {
        return { toast: useToastStore() };
    },
    data() {
        return {
            project: this.$route.params.project,
            vertebra: this.$route.params.vertebra,
            patientId: this.$route.params.patient_id,
            seriesUuid: this.$route.query.series || null,
            noScansFound: false,

            nv: null,
            compartments: [], // [{name, has_mask, has_backup, original_mask_path}]
            activeCompartment: null,

            loadingPage: true,
            loadingCompartment: false,
            saving: false,
            reverting: false,

            tools: TOOLS,
            activeTool: 'brush',
            penSize: DEFAULT_PEN_SIZE,

            currentSlice: 0,
            totalSlices: 0,

            modality: null,
            windowWidth: DEFAULT_WINDOW_LEVEL.window,
            windowLevel: DEFAULT_WINDOW_LEVEL.level,

            unsavedChanges: false,
            pendingCompartment: null,
            showDiscardModal: false,
            showRevertModal: false,

            // A toast alone is easy to miss while focused on the canvas - this banner is the
            // unmissable "your save/recompute actually finished" signal, with a direct link to
            // go see the result on the sanity/QA page.
            showSaveSuccess: false,
            saveSuccessMessage: '',
        };
    },
    computed: {
        backendUrl() {
            return import.meta.env.VITE_BACKEND_URI;
        },
        activeCompartmentInfo() {
            return this.compartments.find((c) => c.name === this.activeCompartment) || null;
        },
    },
    methods: {
        scanUrl() {
            const params = new URLSearchParams({ project: this.project, _id: this.seriesUuid });
            return `${this.backendUrl}/api/editor/scan?${params.toString()}`;
        },
        maskUrl(compartment, variant = 'current') {
            const params = new URLSearchParams({
                project: this.project,
                _id: this.seriesUuid,
                vertebra: this.vertebra,
                compartment,
            });
            if (variant === 'original') params.set('variant', 'original');
            return `${this.backendUrl}/api/editor/mask?${params.toString()}`;
        },
        parseAcquisitionDate(dateStr) {
            // Mirrors PatientPredictions.vue - dates are stored/displayed as dd-mm-YYYY.
            const [day, month, year] = dateStr.split('-').map(Number);
            return new Date(year, month - 1, day);
        },
        async resolveSeriesUuid() {
            // Reached without a ?series= query param (e.g. a generic "Edit contour" link from
            // PatientPage that isn't tied to one specific scan) - pick this patient's most
            // recent scan for the requested vertebra, the same data fetch_patient_list already
            // exposes for PatientPredictions.vue's own patient/series picker.
            const res = await api.get('/api/patient_qa/fetch_patient_list', {
                params: { project: this.project, vertebra: this.vertebra },
            });
            const seriesForPatient = res.data.image_dict?.[this.patientId];
            if (!seriesForPatient || !Object.keys(seriesForPatient).length) {
                this.noScansFound = true;
                return;
            }
            const sorted = Object.keys(seriesForPatient).sort(
                (a, b) => this.parseAcquisitionDate(seriesForPatient[a]) - this.parseAcquisitionDate(seriesForPatient[b])
            );
            this.seriesUuid = sorted[sorted.length - 1];
        },
        async loadMetadata() {
            const res = await api.get('/api/editor/get_metadata', {
                params: { project: this.project, _id: this.seriesUuid, vertebra: this.vertebra },
            });
            this.compartments = res.data.compartments;
            this.modality = res.data.modality;
            const defaults = WINDOW_LEVEL_DEFAULTS[this.modality] || DEFAULT_WINDOW_LEVEL;
            this.windowWidth = defaults.window;
            this.windowLevel = defaults.level;
            if (!this.activeCompartment && this.compartments.length) {
                this.activeCompartment = this.compartments.find((c) => c.has_mask)?.name ?? this.compartments[0].name;
            }
        },
        async initViewer() {
            this.nv = new Niivue({ isResizeCanvas: true });
            await this.nv.attachToCanvas(this.$refs.canvas);
            // A single 2D slice view is what makes sense for contour editing - NiiVue's default
            // multiplanar layout (4 small axial/coronal/sagittal/render panes) is what produced
            // the malformed-looking tiny thumbnail strip.
            this.nv.setSliceType(this.nv.sliceTypeAxial);
            // "load"/"close" fire when we programmatically swap masks in loadActiveCompartmentMask
            // (which resets unsavedChanges itself afterwards) - only "draw"/"undo" reflect an
            // actual user edit.
            this.nv.onDrawingChanged = (action) => {
                if (action === 'draw' || action === 'undo') {
                    this.unsavedChanges = true;
                    this.showSaveSuccess = false;
                }
            };
            // Keeps the slice counter live as the user scrolls/clicks/drags through slices -
            // `location.vox` is the same voxel coordinate space frac2vox/vox2frac already use.
            this.nv.onLocationChange = (location) => {
                this.currentSlice = location.vox[2];
            };
            await this.nv.loadVolumes([{ url: this.scanUrl(), colormap: 'gray' }]);
            this.totalSlices = this.nv.back.hdr.dims[3];
            this.applyWindowLevel();
            // The canvas's on-screen size can change right after this (the compartment tabs and
            // tool panel only appear once loadingPage flips false, growing/shrinking the space
            // available to the canvas) - force NiiVue to recompute against the final layout
            // rather than whatever size existed when it first attached.
            await this.$nextTick();
            this.nv.resizeListener();
            await this.loadActiveCompartmentMask();
        },
        centerOnMask() {
            // Jump the crosshair (and therefore the displayed slice) to the middle of the
            // loaded compartment's non-empty voxel range, so the editor opens on a slice that
            // actually shows the segmentation instead of NiiVue's default (volume centre/slice 0).
            const dims = this.nv.back?.hdr?.dims;
            const bitmap = this.nv.drawBitmap;
            if (!dims || !bitmap) return;
            const [nx, ny, nz] = [dims[1], dims[2], dims[3]];
            const sliceSize = nx * ny;
            let minZ = null;
            let maxZ = null;
            for (let z = 0; z < nz; z++) {
                const offset = z * sliceSize;
                let hasVoxel = false;
                for (let i = 0; i < sliceSize; i++) {
                    if (bitmap[offset + i] !== 0) { hasVoxel = true; break; }
                }
                if (hasVoxel) {
                    if (minZ === null) minZ = z;
                    maxZ = z;
                }
            }
            if (minZ === null) return;
            const vox = this.nv.frac2vox(this.nv.scene.crosshairPos);
            vox[2] = Math.round((minZ + maxZ) / 2);
            this.nv.scene.crosshairPos = this.nv.vox2frac(vox);
            this.nv.updateGLVolume();
            // Setting crosshairPos directly (vs. a real user interaction) doesn't fire
            // onLocationChange, so keep the slice counter in sync manually here.
            this.currentSlice = vox[2];
        },
        async loadActiveCompartmentMask() {
            if (!this.activeCompartment || !this.nv) return;
            const info = this.activeCompartmentInfo;
            this.loadingCompartment = true;
            this.nv.setDrawingEnabled(false);
            try {
                if (info?.has_mask) {
                    await this.nv.loadDrawingFromUrl(this.maskUrl(this.activeCompartment));
                    this.centerOnMask();
                } else {
                    this.toast.info(`No existing mask for ${this.activeCompartment} yet — starting from a blank layer.`);
                    this.nv.createEmptyDrawing();
                }
                this.nv.setDrawOpacity(0.5);
                this.nv.setDrawingEnabled(true);
                this.applyTool(this.activeTool);
                this.nv.opts.penSize = this.penSize;
                this.unsavedChanges = false;
            } finally {
                this.loadingCompartment = false;
            }
        },
        selectCompartment(name) {
            if (name === this.activeCompartment || this.loadingCompartment) return;
            if (this.unsavedChanges) {
                this.pendingCompartment = name;
                this.showDiscardModal = true;
                return;
            }
            this.activeCompartment = name;
            this.showSaveSuccess = false;
            this.loadActiveCompartmentMask();
        },
        confirmDiscardAndSwitch() {
            this.showDiscardModal = false;
            this.activeCompartment = this.pendingCompartment;
            this.pendingCompartment = null;
            this.showSaveSuccess = false;
            this.loadActiveCompartmentMask();
        },
        cancelSwitch() {
            this.showDiscardModal = false;
            this.pendingCompartment = null;
        },
        applyTool(key) {
            this.activeTool = key;
            const tool = this.tools.find((t) => t.key === key);
            this.nv.setPenValue(tool.penValue, tool.isFilledPen);
        },
        setPenSize(size) {
            this.penSize = size;
            if (this.nv) this.nv.opts.penSize = size;
        },
        undo() {
            this.nv?.drawUndo();
        },
        compartmentLabel(name) {
            return COMPARTMENT_LABELS[name] || name;
        },
        zoomBy(factor) {
            // Mirrors NiiVue's own scroll-to-zoom math (calculateZoom/calculatePanOffsetAfterZoom
            // in niivue's wheelListener) so the buttons zoom around the crosshair exactly like
            // scrolling would, rather than just scaling in place.
            if (!this.nv) return;
            const scene = this.nv.scene;
            const currentZoom = scene.pan2Dxyzmm[3];
            const newZoom = Math.round(currentZoom * factor * 10) / 10;
            const zoomChange = currentZoom - newZoom;
            const mm = this.nv.frac2mm(scene.crosshairPos);
            scene.pan2Dxyzmm[3] = newZoom;
            scene.pan2Dxyzmm[0] += zoomChange * mm[0];
            scene.pan2Dxyzmm[1] += zoomChange * mm[1];
            scene.pan2Dxyzmm[2] += zoomChange * mm[2];
            this.nv.drawScene();
        },
        zoomIn() {
            this.zoomBy(1.1);
        },
        zoomOut() {
            this.zoomBy(1 / 1.1);
        },
        resetZoom() {
            if (!this.nv) return;
            this.nv.scene.pan2Dxyzmm = [0, 0, 0, 1];
            this.nv.drawScene();
        },
        applyWindowLevel() {
            if (!this.nv?.volumes?.[0]) return;
            const vol = this.nv.volumes[0];
            vol.cal_min = this.windowLevel - this.windowWidth / 2;
            vol.cal_max = this.windowLevel + this.windowWidth / 2;
            this.nv.updateGLVolume();
        },
        resetWindowLevel() {
            const defaults = WINDOW_LEVEL_DEFAULTS[this.modality] || DEFAULT_WINDOW_LEVEL;
            this.windowWidth = defaults.window;
            this.windowLevel = defaults.level;
            this.applyWindowLevel();
        },
        onKeydown(e) {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
                e.preventDefault();
                this.undo();
                return;
            }
            if (e.key === '+' || e.key === '=') {
                e.preventDefault();
                this.zoomIn();
            } else if (e.key === '-' || e.key === '_') {
                e.preventDefault();
                this.zoomOut();
            }
        },
        async gzipEncode(bytes) {
            // NiiVue only gzip-compresses saveImage()'s output when given a filename ending in
            // .gz, but a real filename also triggers a browser file-download side effect we
            // don't want here - so we ask for the raw (uncompressed) bytes instead and gzip
            // them ourselves before upload, using the browser's native CompressionStream.
            const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream('gzip'));
            return await new Response(stream).blob();
        },
        async pollJob(jobId) {
            const POLL_MS = 2000;
            const MAX_ATTEMPTS = 150; // ~5 min, matches the 300s job_timeout used server-side
            for (let i = 0; i < MAX_ATTEMPTS; i++) {
                const res = await api.get('/api/jobs/query_job', { params: { id: jobId } });
                const status = res.data.status;
                if (status === 'Type.SUCCESSFUL') return res.data;
                if (status === 'Type.FAILED') throw new Error(res.data.result || 'Job failed');
                await new Promise((resolve) => setTimeout(resolve, POLL_MS));
            }
            throw new Error('Timed out waiting for stats to recompute.');
        },
        async saveMask() {
            if (!this.activeCompartment || this.saving) return;
            this.saving = true;
            try {
                const raw = await this.nv.saveImage({ filename: '', isSaveDrawing: true });
                if (!raw || raw === true) {
                    this.toast.error('Nothing to save — no drawing is open.');
                    return;
                }
                const blob = await this.gzipEncode(raw);

                const formData = new FormData();
                formData.append('project', this.project);
                formData.append('_id', this.seriesUuid);
                formData.append('vertebra', this.vertebra);
                formData.append('compartment', this.activeCompartment);
                formData.append('mask', blob, `${this.activeCompartment}.nii.gz`);

                const saveRes = await api.post('/api/editor/save_mask', formData);

                const jobRes = await api.post('/api/database/extract_stats_from_mask', {
                    _id: this.seriesUuid,
                    project: this.project,
                    vertebra: this.vertebra,
                    compartment: this.activeCompartment,
                    mask_path: saveRes.data.mask_path,
                    is_edit: true,
                });

                await this.pollJob(jobRes.data['job-ID']);
                const message = `Stats recomputed for ${this.compartmentLabel(this.activeCompartment)}.`;
                this.toast.success(message);
                this.saveSuccessMessage = message;
                this.showSaveSuccess = true;
                this.unsavedChanges = false;
                await this.loadMetadata();
            } catch (e) {
                if (!e.response) this.toast.error(`Could not save mask: ${e.message}`);
            } finally {
                this.saving = false;
            }
        },
        confirmRevert() {
            this.showRevertModal = true;
        },
        async revertToOriginal() {
            this.showRevertModal = false;
            const info = this.activeCompartmentInfo;
            if (!info?.original_mask_path) return;
            this.reverting = true;
            try {
                const jobRes = await api.post('/api/database/extract_stats_from_mask', {
                    _id: this.seriesUuid,
                    project: this.project,
                    vertebra: this.vertebra,
                    compartment: this.activeCompartment,
                    mask_path: info.original_mask_path,
                    is_edit: true,
                });
                await this.pollJob(jobRes.data['job-ID']);
                const message = `Reverted ${this.compartmentLabel(this.activeCompartment)} to the AI prediction.`;
                this.toast.success(message);
                this.saveSuccessMessage = message;
                this.showSaveSuccess = true;
                await this.loadMetadata();
                await this.loadActiveCompartmentMask();
            } catch (e) {
                if (!e.response) this.toast.error(`Could not revert: ${e.message}`);
            } finally {
                this.reverting = false;
            }
        },
        backToPatient() {
            if (this.patientId) {
                this.$router.push({ name: 'patientPage', params: { project: this.project, patientID: this.patientId } });
            } else {
                this.$router.push({ name: 'project', params: { project: this.project } });
            }
        },
        viewSanityImage() {
            this.$router.push({
                name: 'patientPredictions',
                params: { project: this.project, vertebra: this.vertebra, patient_id: this.patientId },
                query: { series: this.seriesUuid },
            });
        },
    },
    async mounted() {
        window.addEventListener('keydown', this.onKeydown);
        try {
            if (!this.seriesUuid) {
                await this.resolveSeriesUuid();
                if (!this.seriesUuid) return;
            }
            await this.loadMetadata();
            await this.initViewer();
        } finally {
            this.loadingPage = false;
        }
    },
    beforeUnmount() {
        window.removeEventListener('keydown', this.onKeydown);
    },
    beforeRouteLeave(to, from, next) {
        if (this.unsavedChanges && !window.confirm('You have unsaved contour edits. Leave anyway?')) {
            next(false);
        } else {
            next();
        }
    },
};
</script>

<template>
<div class="flex flex-col h-[calc(100vh-8rem)] px-4 py-4 gap-4">

    <!-- DISCARD-ON-SWITCH CONFIRM -->
    <Modal v-model="showDiscardModal" title="Discard unsaved edits?" size="md">
        <p class="text-ink-secondary mb-4">
            Switching compartments will discard your unsaved edits to <span class="font-bold">{{ activeCompartment }}</span>.
        </p>
        <div class="flex justify-end gap-3">
            <Button variant="secondary" @click="cancelSwitch">Cancel</Button>
            <Button variant="fail" @click="confirmDiscardAndSwitch">Discard and switch</Button>
        </div>
    </Modal>

    <!-- REVERT CONFIRM -->
    <Modal v-model="showRevertModal" title="Revert to AI prediction?" size="md">
        <p class="text-ink-secondary mb-4">
            This restores <span class="font-bold">{{ activeCompartment }}</span> to the original model prediction and recomputes its statistics. Your edits to this compartment will be lost.
        </p>
        <div class="flex justify-end gap-3">
            <Button variant="secondary" @click="showRevertModal = false">Cancel</Button>
            <Button variant="fail" @click="revertToOriginal">Revert</Button>
        </div>
    </Modal>

    <!-- HEADER -->
    <div class="flex items-center justify-between flex-wrap gap-3">
        <div>
            <p class="text-ink-primary font-bold text-lg">Edit {{ vertebra }} contour</p>
            <p class="text-ink-muted text-sm">Patient {{ patientId }} · Series {{ seriesUuid }}</p>
        </div>
        <div class="flex items-center gap-3">
            <Badge v-if="unsavedChanges" variant="fail">Unsaved changes</Badge>
            <Button variant="ghost" @click="backToPatient">Back to patient</Button>
        </div>
    </div>

    <!-- Unmissable "your save/recompute actually finished" confirmation - a toast alone is
         easy to miss while focused on the canvas. -->
    <div v-if="showSaveSuccess" class="flex items-center justify-between gap-3 bg-brand-500/15 border border-brand-400 rounded px-4 py-3">
        <div class="flex items-center gap-2">
            <span class="text-brand-300 font-bold">✓</span>
            <span class="text-ink-primary">{{ saveSuccessMessage }}</span>
        </div>
        <div class="flex items-center gap-2">
            <Button variant="secondary" size="sm" @click="viewSanityImage">View sanity image</Button>
            <button class="text-ink-muted hover:text-ink-secondary font-bold px-2" @click="showSaveSuccess = false">&times;</button>
        </div>
    </div>

    <EmptyState
        v-if="noScansFound"
        title="No scans found"
        :message="`Patient ${patientId} has no scans labelled ${vertebra} in this project.`"
    />

    <template v-else>
    <!-- COMPARTMENT TABS -->
    <div v-if="!loadingPage" class="flex gap-2 flex-wrap">
        <Button
            v-for="c in compartments" :key="c.name"
            :variant="c.name === activeCompartment ? 'primary' : 'secondary'"
            size="sm"
            @click="selectCompartment(c.name)"
        >
            {{ compartmentLabel(c.name) }}
            <span v-if="!c.has_mask" class="text-xs opacity-70">(no mask)</span>
        </Button>
    </div>

    <div class="flex flex-1 gap-4 min-h-0">
        <!-- VIEWER. The canvas is always rendered (never behind a v-if) so its ref exists as
             soon as mounted() runs and attaches NiiVue to it - the loading states are drawn as
             an overlay on top instead of replacing it. Not using <Card> here: its slot content
             sits inside an extra wrapper div with no explicit height, which breaks the
             height:100% chain the canvas relies on to fill this flex-1 container - so this div
             copies Card's visual styling directly instead, with the canvas as a direct child. -->
        <div class="relative flex-1 min-h-0 overflow-hidden bg-surface-card border border-line-subtle border-t-white/5 rounded shadow-lg shadow-black/30">
            <div v-if="loadingPage || loadingCompartment" class="absolute inset-0 z-10 flex items-center justify-center bg-black/40">
                <LoadingState :label="loadingPage ? 'Loading scan and predictions...' : 'Loading mask...'" />
            </div>
            <!-- Same raw 0-indexed slice numbering the sanity PNGs use (e.g. "Slice 16"), so
                 the two can be compared directly. -->
            <div v-if="!loadingPage" class="absolute top-2 left-2 z-10 bg-black/60 text-white text-sm font-bold rounded px-2 py-1">
                Slice {{ currentSlice }} / {{ totalSlices - 1 }}
            </div>
            <canvas ref="canvas" class="w-full h-full"></canvas>
        </div>

        <!-- TOOL PANEL -->
        <Card v-if="!loadingPage" class="w-64 shrink-0 flex flex-col gap-4">
            <div>
                <p class="text-ink-primary font-bold mb-2">Tools</p>
                <div class="flex flex-col gap-2">
                    <Button
                        v-for="t in tools" :key="t.key"
                        :variant="activeTool === t.key ? 'primary' : 'secondary'"
                        size="sm"
                        @click="applyTool(t.key)"
                    >
                        {{ t.label }}
                    </Button>
                    <Button variant="secondary" size="sm" @click="undo">Undo (Ctrl+Z)</Button>
                </div>
            </div>

            <div>
                <p class="text-ink-primary font-bold mb-2">Zoom</p>
                <div class="flex gap-2">
                    <Button variant="secondary" size="sm" @click="zoomOut" title="Zoom out (-)">−</Button>
                    <Button variant="secondary" size="sm" @click="resetZoom" title="Reset zoom">Reset</Button>
                    <Button variant="secondary" size="sm" @click="zoomIn" title="Zoom in (+)">+</Button>
                </div>
            </div>

            <div>
                <label class="text-ink-primary font-bold text-sm">Pen size: {{ penSize }}</label>
                <input
                    type="range" min="1" max="10" step="1"
                    :value="penSize"
                    @input="setPenSize(Number($event.target.value))"
                    class="w-full"
                >
            </div>

            <div>
                <div class="flex items-center justify-between mb-2">
                    <p class="text-ink-primary font-bold">Window / Level</p>
                    <button @click="resetWindowLevel" title="Reset window/level"
                        class="text-ink-secondary hover:text-ink-primary text-xs font-bold underline">Reset</button>
                </div>
                <label class="text-ink-secondary text-xs">Window: {{ windowWidth }}</label>
                <input
                    type="range" min="1" max="2000" step="10"
                    :value="windowWidth"
                    @input="windowWidth = Number($event.target.value); applyWindowLevel();"
                    class="w-full"
                >
                <label class="text-ink-secondary text-xs">Level: {{ windowLevel }}</label>
                <input
                    type="range" min="-1000" max="1000" step="10"
                    :value="windowLevel"
                    @input="windowLevel = Number($event.target.value); applyWindowLevel();"
                    class="w-full"
                >
            </div>

            <div class="mt-auto flex flex-col gap-2">
                <Button
                    variant="primary"
                    :loading="saving"
                    :disabled="!unsavedChanges"
                    @click="saveMask"
                >
                    Save &amp; recompute stats
                </Button>
                <Button
                    variant="fail"
                    :loading="reverting"
                    :disabled="!activeCompartmentInfo?.has_backup"
                    @click="confirmRevert"
                >
                    Revert to AI prediction
                </Button>
            </div>
        </Card>
    </div>
    </template>

</div>
</template>
