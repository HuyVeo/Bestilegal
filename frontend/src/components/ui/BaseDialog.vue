<script setup lang="ts">
defineEmits<{
  close: []
}>()

defineProps<{
  title: string
  maxWidth?: string
}>()
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <!-- Backdrop -->
      <div
        class="absolute inset-0 bg-black/40 backdrop-blur-sm"
        @click="$emit('close')"
      />
      <!-- Panel -->
      <div
        :class="['relative bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full animate-fade-up overflow-hidden', maxWidth || 'max-w-md']"
      >
        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-border-light dark:border-gray-700">
          <h3 class="text-lg font-heading font-bold text-text-primary dark:text-gray-100">
            {{ title }}
          </h3>
          <button
            class="w-8 h-8 flex items-center justify-center rounded-lg text-text-muted hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            @click="$emit('close')"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <!-- Body -->
        <div class="px-6 py-5">
          <slot />
        </div>
      </div>
    </div>
  </Teleport>
</template>
