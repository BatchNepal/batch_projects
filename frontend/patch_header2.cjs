const fs = require('fs');
let content = fs.readFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/ProjectHeader.vue', 'utf8');

// Replace filteredLabels with store.projectLabels
content = content.replace(
    ':options="filteredLabels.map',
    ':options="store.projectLabels.map'
);

// Remove the <template #search> block inside Label filter
content = content.replace(/<template #search>[\s\S]*?<\/template>/, '');

content = content.replace("const labelSearchQ = ref('')", "");
content = content.replace(/const filteredLabels = computed\(\(\) => \{[\s\S]*?\}\)/, "");

fs.writeFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/ProjectHeader.vue', content);
console.log("Fixed ProjectHeader.vue");

