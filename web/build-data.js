#!/usr/bin/env node
/**
 * build-data.js — แยก clusters-data.js เป็นข้อมูลแบบ lazy load
 *
 *   node build-data.js clusters-data.js ./out
 *
 * ผลลัพธ์:
 *   out/clusters-core.js   โหลดพร้อมหน้าเว็บ — hull, สถิติ, แผ่นเปลือกโลก, จุดภาพรวมโลกแบบลดความละเอียด
 *   out/pts/<slug>.json    โหลดเมื่อผู้ใช้เลือกประเทศ — จุดครบความละเอียดของประเทศนั้น
 *
 * รันใหม่ทุกครั้งที่อัปเดต clusters-data.js
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = process.argv[2] || 'clusters-data.js';
const OUT = process.argv[3] || './out';

/** ขนาดช่องกริดสำหรับลดความละเอียดของภาพรวมโลก (องศา)
 *  ยิ่งเล็ก = จุดเยอะ ไฟล์ใหญ่ แต่ละเอียดขึ้น  0.35° ≈ 1 จุดต่อ 1 พิกเซลที่ zoom 2 */
const GRID = 0.35;
/** ทศนิยมของพิกัดในไฟล์ภาพรวม — 1 ตำแหน่งพอสำหรับ zoom ต่ำ (~11 กม.) */
const OV_DP = 1;

// ---------- อ่านข้อมูลต้นทาง ----------
const src = fs.readFileSync(SRC, 'utf8');
const sandbox = {};
vm.runInNewContext(src + ';this.__x={CLDATA,PLATES,SPLATES,PLABELS,PAVG};', sandbox);
const { CLDATA, PLATES, SPLATES, PLABELS, PAVG } = sandbox.__x;

// ---------- ชื่อไฟล์ที่ปลอดภัยสำหรับทุกระบบไฟล์/URL ----------
const used = new Set();
function slugify(name) {
  let s = name.normalize('NFD').replace(/[̀-ͯ]/g, '')
              .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  if (!s) s = 'c';
  let out = s, i = 2;
  while (used.has(out)) out = s + '-' + i++;
  used.add(out);
  return out;
}

const round = (v, dp) => { const f = 10 ** dp; return Math.round(v * f) / f; };

// ---------- 1. แกนหลัก: ทุกอย่างยกเว้น pts ----------
const CLCORE = {}, CLFILE = {};
for (const [country, v] of Object.entries(CLDATA)) {
  const o = { center: v.center, clusters: {} };
  for (const [k, c] of Object.entries(v.clusters || {})) {
    const { pts, ...rest } = c;           // เก็บ n, magMin, magMax, magMean, y0, y1, hull
    o.clusters[k] = rest;
  }
  CLCORE[country] = o;
  CLFILE[country] = slugify(country);
}

// ---------- 2. ภาพรวมโลกแบบลดความละเอียด ----------
// แบ่งพื้นที่เป็นตารางกริด แต่ละช่อง (ต่อหมายเลขกลุ่ม) เก็บเฉพาะจุดที่แมกนิจูดสูงสุด
const cells = new Map();
for (const v of Object.values(CLDATA)) {
  for (const [k, c] of Object.entries(v.clusters || {})) {
    for (const p of c.pts || []) {
      const key = Math.round(p[0] / GRID) + '|' + Math.round(p[1] / GRID) + '|' + k;
      const cur = cells.get(key);
      if (!cur || p[2] > cur[2]) cells.set(key, [round(p[0], OV_DP), round(p[1], OV_DP), p[2], +k]);
    }
  }
}
const CLOVER = [...cells.values()];

// ---------- 3. จุดรายประเทศ ----------
fs.mkdirSync(path.join(OUT, 'pts'), { recursive: true });
let ptsTotal = 0, ptsBytes = 0;
const perCountry = [];
for (const [country, v] of Object.entries(CLDATA)) {
  const o = {};
  for (const [k, c] of Object.entries(v.clusters || {})) {
    o[k] = c.pts || [];
    ptsTotal += o[k].length;
  }
  const json = JSON.stringify(o);
  const file = path.join(OUT, 'pts', CLFILE[country] + '.json');
  fs.writeFileSync(file, json);
  ptsBytes += json.length;
  perCountry.push([country, json.length]);
}

// ---------- เขียนไฟล์แกนหลัก ----------
const core =
`/* สร้างโดย build-data.js — อย่าแก้ไฟล์นี้ด้วยมือ
   ต้นทาง: ${path.basename(SRC)} · กริดภาพรวม ${GRID}° · ${CLOVER.length} จุด จาก ${ptsTotal} จุด */
const CLCORE=${JSON.stringify(CLCORE)};
const CLFILE=${JSON.stringify(CLFILE)};
const CLOVER=${JSON.stringify(CLOVER)};
const PLATES=${JSON.stringify(PLATES)};
const SPLATES=${JSON.stringify(SPLATES)};
const PLABELS=${JSON.stringify(PLABELS)};
const PAVG=${JSON.stringify(PAVG)};
`;
fs.writeFileSync(path.join(OUT, 'clusters-core.js'), core);

// ---------- รายงาน ----------
const zlib = require('zlib');
const br = s => zlib.brotliCompressSync(Buffer.from(s),
  { params: { [zlib.constants.BROTLI_PARAM_QUALITY]: 11 } }).length;
const KB = n => (n / 1024).toFixed(0) + ' KB';
perCountry.sort((a, b) => b[1] - a[1]);

console.log('ต้นทาง            ' + KB(src.length) + ' → brotli ' + KB(br(src)) +
            '   (' + ptsTotal.toLocaleString() + ' จุด, ' + Object.keys(CLDATA).length + ' ประเทศ)');
console.log('clusters-core.js  ' + KB(core.length) + ' → brotli ' + KB(br(core)) +
            '   (' + CLOVER.length.toLocaleString() + ' จุดภาพรวม = ' +
            (100 * CLOVER.length / ptsTotal).toFixed(0) + '%)');
console.log('pts/ 28 ไฟล์      ' + KB(ptsBytes) + ' รวม — ใหญ่สุด ' +
            perCountry[0][0] + ' ' + KB(perCountry[0][1]) +
            ' (brotli ' + KB(br(fs.readFileSync(path.join(OUT, 'pts', CLFILE[perCountry[0][0]] + '.json')))) + ')');
console.log('ลดขนาดหน้าแรกลง   ' + (100 - 100 * br(core) / br(src)).toFixed(0) + '%');
