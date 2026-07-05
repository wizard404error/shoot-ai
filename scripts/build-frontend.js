/**
 * Kawkab AI Frontend Build Script
 * 
 * Reads script load order from index.html, concatenates JS files in dependency
 * order, optionally minifies with terser, and copies assets to dist/.
 * 
 * Usage: node scripts/build-frontend.js
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const WEB_DIR = path.resolve(__dirname, '..', 'src', 'kawkab', 'web');
const DIST_DIR = path.resolve(__dirname, '..', 'dist');
const JS_DIST_DIR = path.join(DIST_DIR, 'js');
const CSS_DIST_DIR = path.join(DIST_DIR, 'css');

// Step 1: Parse index.html for script tags in load order
const indexHtml = fs.readFileSync(path.join(WEB_DIR, 'index.html'), 'utf-8');
const scriptRegex = /<script\s+src="(js\/[^"]+)"/g;
const scriptSrcs = [];
let match;
while ((match = scriptRegex.exec(indexHtml)) !== null) {
    scriptSrcs.push(match[1]);
}
console.log(`Found ${scriptSrcs.length} script tags in load order.`);

// Step 2: Concatenate all JS files in order
let bundle = '';
const preamble = `/* Kawkab AI — Frontend Bundle */
/* Generated $(new Date().toISOString()) */
/* DO NOT EDIT — auto-generated from individual source files */\n\n`;
bundle += preamble;

for (const src of scriptSrcs) {
    const filePath = path.join(WEB_DIR, src.replace(/\?.*$/, ''));
    if (!fs.existsSync(filePath)) {
        console.warn(`  WARNING: ${src} not found, skipping.`);
        continue;
    }
    const content = fs.readFileSync(filePath, 'utf-8');
    bundle += `\n/* --- ${src} --- */\n${content}\n`;
    console.log(`  + ${src} (${(content.length / 1024).toFixed(1)} KB)`);
}

console.log(`\nConcatenated bundle: ${(bundle.length / 1024).toFixed(1)} KB`);

// Step 3: Try to minify with terser (optional)
let minified = null;
try {
    execSync('npx terser --version', { stdio: 'ignore', cwd: WEB_DIR });
    const result = execSync(
        `npx terser --compress passes=2,drop_console --mangle --output "${path.join(JS_DIST_DIR, 'bundle.min.js')}"`,
        { input: bundle, cwd: WEB_DIR, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }
    );
    minified = result.stdout || result;
    console.log('Minified with terser successfully.');
} catch (e) {
    console.warn('terser not available — skipping minification.');
}

// Step 4: Write output files
fs.mkdirSync(JS_DIST_DIR, { recursive: true });
fs.mkdirSync(CSS_DIST_DIR, { recursive: true });

fs.writeFileSync(path.join(JS_DIST_DIR, 'bundle.js'), bundle, 'utf-8');
console.log(`Written: dist/js/bundle.js`);

if (minified) {
    // terser writes directly to the file when using --output
    const minPath = path.join(JS_DIST_DIR, 'bundle.min.js');
    if (fs.existsSync(minPath)) {
        const stats = fs.statSync(minPath);
        console.log(`Written: dist/js/bundle.min.js (${(stats.size / 1024).toFixed(1)} KB, ${((1 - stats.size / bundle.length) * 100).toFixed(1)}% smaller)`);
    }
}

// Step 5: Copy index.html (replace script tags with bundle.js)
let bundledHtml = indexHtml.replace(
    /<script\s+src="js\/[^"]+"\s*>(\s*)<\/script>\s*/g,
    ''
);
bundledHtml = bundledHtml.replace(
    '</head>',
    '    <script defer src="js/bundle.js"></script>\n</head>'
);
fs.writeFileSync(path.join(DIST_DIR, 'index.html'), bundledHtml, 'utf-8');
console.log('Written: dist/index.html (scripts replaced with bundle.js)');

// Step 6: Copy CSS directory
copyDirSync(path.join(WEB_DIR, 'css'), CSS_DIST_DIR);
console.log('Copied: dist/css/');

// Step 7: Copy other assets (locales, icons, img, vendor)
copyAssets();

console.log('\nBuild complete. dist/ is ready for deployment.\n');

function copyDirSync(src, dest) {
    if (!fs.existsSync(src)) return;
    fs.mkdirSync(dest, { recursive: true });
    for (const entry of fs.readdirSync(src)) {
        const srcPath = path.join(src, entry);
        const destPath = path.join(dest, entry);
        if (fs.statSync(srcPath).isDirectory()) {
            copyDirSync(srcPath, destPath);
        } else {
            fs.copyFileSync(srcPath, destPath);
        }
    }
}

function copyAssets() {
    const assetDirs = ['locales', 'icons', 'img', 'vendor'];
    for (const dir of assetDirs) {
        const src = path.join(WEB_DIR, dir);
        const dest = path.join(DIST_DIR, dir);
        if (fs.existsSync(src)) {
            copyDirSync(src, dest);
            console.log(`Copied: dist/${dir}/`);
        }
    }
    // Also copy manifest.json, sw.js, offline.html if they exist
    for (const file of ['manifest.json', 'sw.js', 'offline.html']) {
        const src = path.join(WEB_DIR, file);
        if (fs.existsSync(src)) {
            fs.copyFileSync(src, path.join(DIST_DIR, file));
            console.log(`Copied: dist/${file}`);
        }
    }
}
