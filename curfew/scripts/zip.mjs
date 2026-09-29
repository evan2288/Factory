// Zips dist/ with index.html at the root, as the CrazyGames uploader expects.
import { execSync } from 'node:child_process';
import fs from 'node:fs';
if (!fs.existsSync('dist/index.html')) { console.error('run npm run build first'); process.exit(1); }
fs.rmSync('curfew-crazygames.zip', { force: true });
execSync('cd dist && zip -qr ../curfew-crazygames.zip .', { stdio: 'inherit' });
const kb = Math.round(fs.statSync('curfew-crazygames.zip').size / 1024);
console.log(`curfew-crazygames.zip: ${kb} KB, ${fs.readdirSync('dist/assets').length + 1} files`);
