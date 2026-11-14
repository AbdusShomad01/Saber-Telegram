// Tes logika kantor: node scripts/test.mjs
import assert from 'node:assert/strict';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { runnerImport } from 'vite';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const O = (await runnerImport(path.join(root, 'src/office.ts'), { root, configFile: false, cacheDir: path.join(os.tmpdir(), 'kantor-vite'), logLevel: 'error' })).module;

let n = 0;
const t = (name, fn) => {
  fn();
  n++;
};
t('jadwal pagi, laporan, belajar, libur', () => {
  assert.equal(O.agentDoing('screener', 1, '06:15').label, 'scanning 900+ saham IHSG pagi…');
  assert.equal(O.agentDoing('monitor', 1, '09:30').activity, 'kerja');
  assert.equal(O.agentDoing('bsjp', 1, '16:35').activity, 'laporan');
  assert.equal(O.agentDoing('optimizer', 6, '20:30').activity, 'belajar');
  assert.equal(O.agentDoing('screener', 1, '10:00').activity, 'siaga');
  assert.equal(O.agentDoing('screener', 1, '23:00').activity, 'pulang');
  assert.equal(O.agentDoing('screener', 6, '06:15').activity, 'pulang');
  assert.equal(O.agentDoing('screener', 6, '06:15', true).activity, 'kerja');
});
t('timelapse tiga babak, berulang', () => {
  assert.equal(O.LAPSE_SECONDS, 30);
  assert.equal(O.lapseAt(0).time, '06:00');
  assert.equal(O.lapseAt(16).act, 1);
  assert.equal(O.lapseAt(30).time, '06:00');
});
t('agen santai pergi dan kembali', () => {
  const seen = new Set();
  for (let x = 0; x < 48; x += 0.5) seen.add(O.idleAt('screener', x).spot);
  assert.ok(seen.has('meja') && seen.size >= 3);
});
t('meja dan Mission Board', () => {
  const desks = O.officeDesks(1, '10:00');
  assert.equal(desks.length, 6);
  assert.ok(desks.every((d) => d.bubble));
  assert.ok(O.missionBoard(desks).items.length >= 4);
});
t('parameter URL', () => {
  assert.deepEqual(O.params(new URLSearchParams('timelapse=1&rekam=1&jam=08.10')), { lapse: true, rec: true, time: '08:10', alwaysWork: true });
});
const G = (await runnerImport(path.join(root, 'src/gaya/daftar.ts'), { root, configFile: false, cacheDir: path.join(os.tmpdir(), 'kantor-vite'), logLevel: 'error' })).module;
t('16 gaya + asli, urutan pilihan gaya', () => {
  assert.equal(G.DAFTAR_GAYA.length, 17);
  assert.equal(new Set(G.DAFTAR_GAYA.map((g) => g.id)).size, 17);
  assert.equal(G.DAFTAR_GAYA.filter((g) => g.jenis === 'paduan').length, 9);
  assert.equal(G.gayaAwal('clay', 'voxel', 'asli'), 'clay');
  assert.equal(G.gayaAwal('ngawur', 'voxel', 'asli'), 'voxel');
  assert.equal(G.gayaAwal(null, null, 'taman'), 'taman');
  assert.equal(G.gayaAwal(null, 'x', 'y'), 'asli');
  assert.equal(G.cariGaya('ngawur').id, 'asli');
});
console.log(`${n} tes lulus`);
