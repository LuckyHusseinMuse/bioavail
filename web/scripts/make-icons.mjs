// Generates PNG app icons with no dependencies (raw PNG encoder + zlib).
// Run: npm run icons   -> public/icons/icon-192.png, icon-512.png, maskable-512.png, badge-72.png
import { deflateSync } from "node:zlib";
import { mkdirSync, writeFileSync } from "node:fs";

const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
const crc = (buf) => { let c = 0xffffffff; for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
const chunk = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type), data]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };

function png(size, pixel) {
  const raw = Buffer.alloc((size * 4 + 1) * size);
  for (let y = 0; y < size; y++) {
    raw[y * (size * 4 + 1)] = 0;
    for (let x = 0; x < size; x++) { const [r, g, b, a] = pixel(x / size, y / size); const o = y * (size * 4 + 1) + 1 + x * 4; raw[o] = r; raw[o + 1] = g; raw[o + 2] = b; raw[o + 3] = a; }
  }
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(size, 0); ihdr.writeUInt32BE(size, 4); ihdr[8] = 8; ihdr[9] = 6;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}

// A droplet: circle bottom + triangle top, white on brand blue.
const inDrop = (x, y, s = 1) => {
  const cx = 0.5, cy = 0.58, r = 0.2 * s;
  const dx = x - cx, dy = y - cy;
  if (dx * dx + dy * dy < r * r) return true;
  const top = cy - 0.36 * s;
  if (y >= top && y <= cy) { const half = ((y - top) / (cy - top)) * r * 0.98; return Math.abs(dx) < half; }
  return false;
};
const BLUE = [42, 120, 214, 255], WHITE = [255, 255, 255, 255], CLEAR = [0, 0, 0, 0];
const rounded = (x, y, rad) => { const qx = Math.min(x, 1 - x), qy = Math.min(y, 1 - y); if (qx >= rad || qy >= rad) return true; const dx = rad - qx, dy = rad - qy; return dx * dx + dy * dy <= rad * rad; };

mkdirSync("public/icons", { recursive: true });
writeFileSync("public/icons/icon-192.png", png(192, (x, y) => (!rounded(x, y, 0.2) ? CLEAR : inDrop(x, y) ? WHITE : BLUE)));
writeFileSync("public/icons/icon-512.png", png(512, (x, y) => (!rounded(x, y, 0.2) ? CLEAR : inDrop(x, y) ? WHITE : BLUE)));
writeFileSync("public/icons/maskable-512.png", png(512, (x, y) => (inDrop(x, y, 0.75) ? WHITE : BLUE)));
writeFileSync("public/icons/badge-72.png", png(72, (x, y) => (inDrop(x, y, 1.2) ? WHITE : CLEAR)));
writeFileSync("public/icons/apple-touch-icon.png", png(180, (x, y) => (inDrop(x, y, 0.85) ? WHITE : BLUE)));
console.log("icons written to public/icons/");
