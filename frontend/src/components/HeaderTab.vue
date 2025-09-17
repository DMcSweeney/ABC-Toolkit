<script>

export default {
    name: 'HeaderTab',
    data() {
        return {
            db_url: import.meta.env.VITE_BACKEND_URI.replace(import.meta.env.VITE_BACKEND_PORT, import.meta.env.VITE_MONGO_EXPRESS_PORT),
            jobs_url: `${import.meta.env.VITE_BACKEND_URI}/rq-dashboard`,
        }
    }
}

</script>


<template>
    <header> 
        <nav class="relative flex w-full bg-slate-950 h-16 shadow-sm border-black border-8 ">
        <div class="flex w-full items-center"> 
            <a href="/"><img src="../assets/STK_logo.png" id="icon" class="h-20"> </a>
            <p class="text-slate-200 px-2 text-3xl font-bold">ABC</p>
        </div>
        <div class="flex align-end m-auto mr-5">
            <a class="text-slate-200 px-2 font-bold hover:text-slate-500" :href="`${db_url}`">Database</a>
            <a class="text-slate-200 px-2 font-bold hover:text-slate-500" :href="`${jobs_url}`">Jobs</a>
        </div>
    
        </nav>    
    </header>

</template>

<style scoped>
</style>