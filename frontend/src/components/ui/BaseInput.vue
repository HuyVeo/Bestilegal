<script setup lang="ts">
defineProps<{
  modelValue: string
  type?: string
  placeholder?: string
  label?: string
  error?: string
  disabled?: boolean
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label v-if="label" class="text-sm font-semibold text-text-primary dark:text-gray-200">
      {{ label }}
    </label>
    <input
      :value="modelValue"
      :type="type || 'text'"
      :placeholder="placeholder"
      :disabled="disabled"
      class="w-full px-4 py-2.5 rounded-xl border border-border-light dark:border-gray-600 bg-white dark:bg-gray-800 text-text-body dark:text-gray-200 text-sm font-medium
        placeholder:text-text-light dark:placeholder:text-gray-500
        focus:outline-none focus:ring-2 focus:ring-brand-blue/30 focus:border-brand-blue
        disabled:opacity-50 disabled:cursor-not-allowed
        transition-all duration-200"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
    <p v-if="error" class="text-xs text-accent-red font-medium">{{ error }}</p>
  </div>
</template>
