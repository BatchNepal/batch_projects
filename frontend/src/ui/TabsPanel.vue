<template><div v-if="modelValue === value" :class="$attrs.class"><slot /></div></template>
<script setup>
defineProps({ modelValue: { default: '' }, value: { default: '' } })
</script>
