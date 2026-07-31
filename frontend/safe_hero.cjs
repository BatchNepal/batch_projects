const fs = require('fs');
let code = fs.readFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/HeroSelect.vue', 'utf8');

// Fix the computed property
code = code.replace(`opts = opts.filter(o => o.label?.toLowerCase().includes(q) || String(o.value).toLowerCase().includes(q))`, `opts = opts.filter(o => (o.label && String(o.label).toLowerCase().includes(q)) || (o.value && String(o.value).toLowerCase().includes(q)))`);

fs.writeFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/HeroSelect.vue', code);
