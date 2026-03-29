<script setup lang="ts">
import { cn } from '@/lib/cn'

const props = withDefaults(defineProps<{
  initials: string
  variant?: 'blue' | 'navy' | 'white'
  size?: 'sm' | 'md' | 'lg'
}>(), {
  variant: 'blue',
  size: 'md',
})

const classes = cn(
  'rounded-full flex items-center justify-center font-bold select-none flex-shrink-0',
  {
    'bg-brand-blue text-white': props.variant === 'blue',
    'bg-navy text-white': props.variant === 'navy',
    'bg-white text-navy border-2 border-border-light shadow-sm': props.variant === 'white',
  },
  {
    'w-7 h-7 text-xs': props.size === 'sm',
    'w-9 h-9 text-sm': props.size === 'md',
    'w-12 h-12 text-base': props.size === 'lg',
  },
)
</script>

<template>
  <div :class="classes">
    {{ initials }}
  </div>
</template>
