<script setup lang="ts">
import { cn } from '@/lib/cn'

const props = withDefaults(defineProps<{
  variant?: 'blue' | 'green' | 'red' | 'yellow' | 'gray'
}>(), {
  variant: 'blue',
})

const classes = cn(
  'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold',
  {
    'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300': props.variant === 'blue',
    'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300': props.variant === 'green',
    'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300': props.variant === 'red',
    'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300': props.variant === 'yellow',
    'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300': props.variant === 'gray',
  },
)
</script>

<template>
  <span :class="classes"><slot /></span>
</template>
