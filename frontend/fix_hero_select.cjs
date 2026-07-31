const fs = require('fs');
let code = fs.readFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/HeroSelect.vue', 'utf8');

// remove <template> and </template> around the list
code = code.replace('                <template>\n', '');
code = code.replace('          </li>\n        </template>\n      </ul>', '          </li>\n      </ul>');

fs.writeFileSync('/home/frappe/batcherp/apps/batch_projects/frontend/src/components/HeroSelect.vue', code);
