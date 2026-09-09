import { mkdir, readFile, copyFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';
import { execFileSync } from 'node:child_process';

const root = dirname(fileURLToPath(import.meta.url));
const files = ['index.html', 'styles.css', 'app.js', 'data.js', 'favicon.svg'];
for (const file of ['app.js','data.js']) execFileSync(process.execPath, ['--check', join(root,file)], { stdio:'inherit' });
const html = await readFile(join(root,'index.html'),'utf8');
for (const match of html.matchAll(/(?:src|href)="\/([^"?#]+)"/g)) {
  if (!files.includes(match[1])) throw new Error(`Undeclared frontend asset: ${match[1]}`);
}
await mkdir(join(root,'dist'),{recursive:true});
for (const file of files) await copyFile(join(root,file),join(root,'dist',file));
console.log('Built Apex Session Studio: frontend/dist (5 static assets, no external dependencies).');
