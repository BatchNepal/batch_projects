<template>
  <div
    @click="$emit('click')"
    :class="[
      'fd-item flex font-medium items-center gap-2.5 px-2.5 py-1.5 min-h-[30px] text-[13px] rounded-[5px] cursor-pointer select-none',
      active ? 'text-foreground font-semibold' : 'text-foreground',
      'hover:bg-default',
      danger ? '!text-danger hover:!bg-danger-soft' : ''
    ]"
  >
    <slot/>
    <svg v-if="active" class="w-3 h-3 ml-auto shrink-0 text-foreground"
      fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
      <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
    </svg>
  </div>
</template>

<script setup>
defineProps({
  active: Boolean,
  danger: Boolean,
})
defineEmits(['click'])
</script>

<style scoped>
.fd-item { transition: background-color 100ms var(--ease-out), transform 250ms var(--ease-smooth); }
.fd-item:active { transform: scale(0.98); transition: transform 40ms ease-out; }
</style>
