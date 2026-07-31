const fs = require('fs');
let code = fs.readFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/HeroSelect.vue', 'utf8');

// remove v-if="$slots.default" altogether
code = code.replace('<slot v-if="$slots.default"></slot>\n        <template v-else>', '        <template>');

fs.writeFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/HeroSelect.vue', code);
