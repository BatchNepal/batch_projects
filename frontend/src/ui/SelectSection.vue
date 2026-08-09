<template><optgroup class="text-sm font-semibold" :label="label"><slot /></optgroup></template>
<script setup>
defineProps({ label: { type: String, default: '' } })
</script>
