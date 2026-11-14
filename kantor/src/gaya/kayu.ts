/** Balok kayu mainan: serat kayu, warna cat pudar, agen seperti boneka pasak, pohon kerucut. */
import { ConeGeometry, MeshStandardMaterial, SphereGeometry } from 'three';
import { acak, buatKit, campur, kanvas, kotakBulat, pelacak, tabungBulat } from './alat';
import type { PembangunGaya } from './tipe';

export const kayu: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    const r = acak(13);
    const serat = kanvas(s, 256, 256, (g, w, h) => {
      g.fillStyle = '#f3e6cf';
      g.fillRect(0, 0, w, h);
      for (let i = 0; i < 60; i++) {
        g.strokeStyle = `rgba(120,80,40,${0.08 + r() * 0.15})`;
        g.lineWidth = 0.6 + r() * 1.8;
        g.beginPath();
        const y = r() * h;
        g.moveTo(0, y);
        for (let x = 0; x <= w; x += 16) g.lineTo(x, y + Math.sin(x * 0.03 + i) * 3 + r() * 1.5);
        g.stroke();
      }
    }, { warna: true });
    return buatKit(s, {
      warna: (c) => campur(c, '#e9dcc0', 0.3),
      bahan: (c) => new MeshStandardMaterial({ color: c, map: serat, roughness: 0.65 }),
      kotak: (w, h, d) => kotakBulat(w, h, d, Math.min(0.03, Math.min(w, h, d) * 0.2)),
      tabung: (rt, rb, h) => tabungBulat(rt, rb, h, 0.03),
      kapsul: (rad, len, p) => (p === 'baju' ? tabungBulat(rad, rad * 1.25, len + rad * 2, 0.04) : tabungBulat(rad, rad, len + rad * 2, rad * 0.5)),
      bola: (rad, p, kubah) =>
        p === 'daun' ? new ConeGeometry(rad, rad * 2.2, 16) : kubah ? new SphereGeometry(rad, 18, 14, 0, Math.PI * 2, 0, Math.PI / 1.8) : new SphereGeometry(rad, 18, 14),
      luar: { ukuran: 24, alas: '#c9a06a' },
      cahaya: { langit: '#fff6e6', bumi: '#b8a080', kuat: 1.4, matahari: '#fff0d8', mKuat: 1.7 },
      kabut: null,
    });
  },
};
