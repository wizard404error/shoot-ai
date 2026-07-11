#!/usr/bin/env node
import * as esbuild from 'esbuild';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const webDir = resolve(__dirname, '../src/kawkab/web');
const htmlPath = resolve(webDir, 'index.html');

const html = await readFile(htmlPath, 'utf-8');

const scriptRegex = /<script[^>]*src="([^"]+)"[^>]*><\/script>/g;
const scripts = [];
let match;
while ((match = scriptRegex.exec(html)) !== null) {
  scripts.push({
    src: match[1],
    fullTag: match[0],
    isDefer: /defer/i.test(match[0]),
    isModule: /type="module"/i.test(match[0]),
  });
}

const toBundle = scripts.filter(s =>
  !s.src.startsWith('vendor/') &&
  !s.src.startsWith('dist/') &&
  !s.isModule &&
  s.src !== 'js/qwebchannel.js'
);

console.log(`Found ${scripts.length} script tags`);
console.log(`Bundling ${toBundle.length} files (excluding vendor, module, qwebchannel)`);

let raw = '';
for (const s of toBundle) {
  const filePath = resolve(webDir, s.src);
  let content = await readFile(filePath, 'utf-8');
  content = content.replace(/\/\/# sourceMappingURL.*/g, '');
  raw += `// ${s.src}\n${content}\n\n`;
}

const distDir = resolve(webDir, 'dist');
await mkdir(distDir, { recursive: true });

const result = await esbuild.transform(raw, {
  minify: true,
  target: 'es2020',
  sourcemap: true,
});

const bundlePath = resolve(distDir, 'app.bundle.min.js');
await writeFile(bundlePath, result.code);
if (result.map) {
  await writeFile(resolve(distDir, 'app.bundle.min.js.map'), JSON.stringify(result.map));
}

const bundleRel = 'dist/app.bundle.min.js';
const bundleTag = '<script defer src="' + bundleRel + '"></script>';

let updated = html;
for (const s of toBundle) {
  updated = updated.replace(s.fullTag, '');
}
updated = updated.replace('</body>', '  ' + bundleTag + '\n</body>');

const updatedPath = resolve(webDir, 'index.html');
await writeFile(updatedPath, updated);

const savedBytes = Buffer.byteLength(raw) - result.code.length;
const savedPct = ((1 - result.code.length / Buffer.byteLength(raw)) * 100).toFixed(1);
console.log(`\u2713 Bundle written to dist/app.bundle.min.js`);
console.log(`  ${toBundle.length} files concatenated`);
console.log(`  ${Buffer.byteLength(raw).toLocaleString()} B \u2192 ${result.code.length.toLocaleString()} B (${savedPct}% reduction)`);
console.log(`\u2713 index.html updated: ${toBundle.length} tags replaced with 1 defer bundle`);
