const fs = require('fs');
let code = fs.readFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/HeroSelect.vue', 'utf8');

// replace the <slot> wrapper fully with explicit v-if="$slots.default" vs v-else
const startStr = "<slot>\n          <li";
const newStr = `<slot v-if="$slots.default"></slot>\n        <template v-else>\n          <li`;

code = code.replace(startStr, newStr);

const endStr = `        </slot>\n      </ul>`;
const newEndStr = `        </template>\n      </ul>`;
code = code.replace(endStr, newEndStr);

fs.writeFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/HeroSelect.vue', code);
