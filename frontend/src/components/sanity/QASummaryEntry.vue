<script>
import { MagnifyingGlassIcon} from '@heroicons/vue/24/solid'

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
    components: {MagnifyingGlassIcon}
}


</script>

<template>

    <div
        class="w-5/6 h-16 text-stone-200 text-xl font-bold hover:border hover:border-black bg-zinc-900 hover:bg-zinc-800 rounded flex justify-center my-2">
        <!-- Project name -->
        <div class="align-start content-center ml-3 ">
            {{ level }}
        </div>
        <!-- Number of patients -->
        <div class="content-center mx-auto text-green-500">
            {{ num_pass }}
        </div>
        <!-- Number of images -->
        <div class="content-center mx-auto text-red-500">
            {{ num_fail }}
        </div>
        <div class="content-center mx-auto text-zinc-500">
            {{ num_todo }}
        </div>
        <!-- Links to project -->
        <div class="flex m-auto justify-end hover:text-indigo-400 mr-3">
            <p class="">
                <a :href="`/${this.projectName}/patient_qa/${level}`">
                    <MagnifyingGlassIcon class="size-6 text-stone-200 hover:text-indigo-400" />
                </a>
            </p>
        </div>
    </div>

</template>



<style scoped>
</style>