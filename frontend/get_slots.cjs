const fs = require('fs');
let code = fs.readFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/ProjectHeader.vue', 'utf8');

console.log(code.includes("<HeroSelect"));
