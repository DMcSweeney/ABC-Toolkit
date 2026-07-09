<script setup>
import { RouterView } from 'vue-router'
import HeaderTab from './components/HeaderTab.vue';
import ToastContainer from './components/ToastContainer.vue';
</script>

<template>
    <HeaderTab />
    <ToastContainer />
    <RouterView />
</template>
