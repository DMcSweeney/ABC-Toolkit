<script setup>
// Modal popup for Vue.js 
defineProps({
    height: "100%",
})


</script>


<template>
    <div class="w-full flex absolute z-50" :style="{height: height}">
        <div class="w-2/3 h-2/3 flex flex-col justify-center bg-black border border-white z-50 mx-auto my-10 rounded shadow-sm shadow-white">
            <slot></slot>
        </div>
    </div>    
</template>

<style>
</style>