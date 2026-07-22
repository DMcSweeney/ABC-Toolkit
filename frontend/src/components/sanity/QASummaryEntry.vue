<script>
import { MagnifyingGlassIcon} from '@heroicons/vue/24/solid'
import Badge from '../ui/Badge.vue'

export default {
    name: 'QASummaryEntry',
    data() {
        return {
            projectName: this.$route.params.project,
            path: this.$route
        }
    },
    methods: {
    },
    props: ['level', 'num_pass', 'num_fail', 'num_todo'],
    components: {MagnifyingGlassIcon, Badge}
}


</script>

<template>

    <div
        class="w-5/6 h-16 text-ink-primary text-xl font-bold border border-line-subtle hover:border-line-default bg-surface-card hover:bg-surface-raised rounded flex justify-center items-center my-2 transition-colors duration-150">
        <!-- Project name -->
        <div class="align-start content-center ml-3 ">
            {{ level }}
        </div>
        <!-- Number of patients -->
        <div class="content-center mx-auto">
            <Badge variant="pass">{{ num_pass }}</Badge>
        </div>
        <!-- Number of images -->
        <div class="content-center mx-auto">
            <Badge variant="fail">{{ num_fail }}</Badge>
        </div>
        <div class="content-center mx-auto">
            <Badge variant="todo">{{ num_todo }}</Badge>
        </div>
        <!-- Links to project -->
        <div class="flex m-auto justify-end hover:text-brand-400 mr-3">
            <p class="">
                <router-link :to="`/${this.projectName}/patient_qa/${level}`" :aria-label="`Inspect QA for level ${level}`">
                    <MagnifyingGlassIcon class="size-6 text-ink-secondary hover:text-brand-400" />
                </router-link>
            </p>
        </div>
    </div>

</template>



<style scoped>
</style>
