/** Felt / wol: serat kain, warna kusam lembut, jahitan putus-putus di tepi meja, karpet, kursi, papan. */
import { BufferAttribute, BufferGeometry, LineDashedMaterial, LineLoop, MeshStandardMaterial } from 'three';
import { acak, buatKit, campur, kanvas, kotakBulat, pelacak, tabungBulat } from './alat';
import type { PembangunGaya } from './tipe';

export const felt: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    const r = acak(7);
    const serat = kanvas(s, 256, 256, (g, w, h) => {
      g.fillStyle = '#e8e8e8';
      g.fillRect(0, 0, w, h);
      for (let i = 0; i < 4000; i++) {
        const x = r() * w, y = r() * h, a = r() * 7, l = 3 + r() * 7;
        g.strokeStyle = r() > 0.5 ? 'rgba(255,255,255,.55)' : 'rgba(90,90,90,.35)';
        g.lineWidth = 0.8;
        g.beginPath();
        g.moveTo(x, y);
        g.quadraticCurveTo(x + r() * 4, y + r() * 4, x + Math.cos(a) * l, y + Math.sin(a) * l);
        g.stroke();
      }
    }, { warna: true });
    const jahit = new Map<string, LineDashedMaterial>();
    return buatKit(s, {
      warna: (c) => campur(c, '#d8c8b8', 0.28),
      bahan: (c) => new MeshStandardMaterial({ color: c, map: serat, bumpMap: serat, bumpScale: 2, roughness: 1 }),
      kotak: (w, h, d) => kotakBulat(w, h, d, Math.min(w, h, d) * 0.28),
      tabung: (rt, rb, h) => tabungBulat(rt, rb, h, Math.min(rt, rb, h) * 0.25),
      hias: (m, p) => {
        if (!['meja', 'karpet', 'kursi', 'papan', 'sofa'].includes(p)) return;
        m.geometry.computeBoundingBox();
        const b = m.geometry.boundingBox!;
        const w = b.max.x - b.min.x, h = b.max.y - b.min.y, d = b.max.z - b.min.z;
        if (w < 0.3) return;
        const tegak = d < 0.15; // papan/sandaran: jahitan di muka depan
        const ins = 0.06;
        const y = b.max.y + 0.004, z = b.max.z + 0.004;
        const pts = tegak
          ? [b.min.x + ins, b.min.y + ins, z, b.max.x - ins, b.min.y + ins, z, b.max.x - ins, b.max.y - ins, z, b.min.x + ins, b.max.y - ins, z]
          : [b.min.x + ins, y, b.min.z + ins, b.max.x - ins, y, b.min.z + ins, b.max.x - ins, y, b.max.z - ins, b.min.x + ins, y, b.max.z - ins];
        if (tegak && h < 0.3) return;
        const g = s.simpan(new BufferGeometry());
        g.setAttribute('position', new BufferAttribute(new Float32Array(pts), 3));
        const c = `#${(m.material as MeshStandardMaterial).color.getHexString()}`;
        let lm = jahit.get(c);
        if (!lm) jahit.set(c, (lm = s.simpan(new LineDashedMaterial({ color: campur(c, '#ffffff', 0.6), dashSize: 0.05, gapSize: 0.04 }))));
        const l = new LineLoop(g, lm);
        l.computeLineDistances();
        m.add(l);
      },
      cahaya: { langit: '#fff3e2', bumi: '#a8907a', kuat: 1.4, matahari: '#ffe6c8', mKuat: 1.6 },
      luar: { awan: true },
      kabut: ['#e7ddcc', '#120d22'],
    });
  },
};
