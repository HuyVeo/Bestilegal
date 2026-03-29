<script setup lang="ts">
defineProps<{
  width?: string
  height?: string
  rounded?: string
}>()
</script>

<template>
  <div
    class="animate-pulse bg-gray-200 dark:bg-gray-700"
    :style="{
      width: width || '100%',
      height: height || '16px',
      borderRadius: rounded || '8px',
    }"
  />
</template>
