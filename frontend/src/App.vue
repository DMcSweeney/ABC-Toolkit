<script setup>
import { RouterView } from 'vue-router'
import HeaderTab from './components/HeaderTab.vue';
import ToastContainer from './components/ToastContainer.vue';
import Breadcrumb from './components/ui/Breadcrumb.vue';
</script>

<template>
    <HeaderTab />
    <ToastContainer />
    <Breadcrumb />
    <RouterView />
</template>
