<script setup lang="ts">
import { Plus } from 'lucide-vue-next'

defineEmits<{ click: [] }>()
</script>

<template>
  <button
    class="w-full py-2.5 px-4 border border-white/25 rounded-[14px] text-white text-[0.85rem] font-bold
      hover:bg-white/12 hover:border-white/50 transition-all duration-200 flex items-center justify-center gap-2"
    @click="$emit('click')"
  >
    <Plus :size="16" />
    Cuộc hội thoại mới
  </button>
</template>
