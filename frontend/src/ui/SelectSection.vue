<template><optgroup :label="label"><slot /></optgroup></template>
<script setup>
defineProps({ label: { type: String, default: '' } })
</script>
