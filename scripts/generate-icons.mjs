// Rasterizes extension/icon.svg into the PNG sizes the Chrome Web Store needs.
// Run with: npm run icons
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const src = resolve(root, "extension/icon.svg");
const outDir = resolve(root, "extension/public/icons");
const sizes = [16, 32, 48, 128];

const svg = await readFile(src);
await mkdir(outDir, { recursive: true });

for (const size of sizes) {
  const out = resolve(outDir, `icon-${size}.png`);
  await sharp(svg, { density: 384 })
    .resize(size, size, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .png()
    .toFile(out);
  console.log(`wrote icons/icon-${size}.png`);
}
