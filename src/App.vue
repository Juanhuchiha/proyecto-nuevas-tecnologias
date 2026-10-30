<script setup>
import { useRoute } from 'vue-router'
import Navbar from './components/Navbar.vue'

const route = useRoute()
</script>

<template>
  <Navbar v-if="route.path !== '/'" />
  <div :class="{ 'authenticated-layout': route.path !== '/' }">
    <RouterView />
  </div>
</template>
