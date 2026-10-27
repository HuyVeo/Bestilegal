<script setup lang="ts">
import { cn } from '@/lib/cn'

const props = withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  disabled?: boolean
}>(), {
  variant: 'primary',
  size: 'md',
  loading: false,
  disabled: false,
})

const classes = cn(
  'inline-flex items-center justify-center font-semibold rounded-xl transition-all duration-200 cursor-pointer select-none',
  'disabled:opacity-50 disabled:cursor-not-allowed',
  {
    'bg-brand-blue text-white hover:bg-brand-blue-light active:scale-[0.98] shadow-sm': props.variant === 'primary',
    'bg-white dark:bg-gray-800 text-text-primary dark:text-gray-200 border border-border-light dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700': props.variant === 'secondary',
    'bg-transparent text-text-muted hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-text-primary dark:hover:text-gray-200': props.variant === 'ghost',
    'bg-accent-red text-white hover:bg-red-700 active:scale-[0.98]': props.variant === 'danger',
  },
  {
    'text-xs px-3 py-1.5 gap-1.5': props.size === 'sm',
    'text-sm px-4 py-2.5 gap-2': props.size === 'md',
    'text-base px-6 py-3 gap-2.5': props.size === 'lg',
  },
)
</script>

<template>
  <button :class="classes" :disabled="disabled || loading">
    <svg v-if="loading" class="animate-spin -ml-1 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
    <slot />
  </button>
</template>
