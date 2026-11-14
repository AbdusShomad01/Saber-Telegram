/** Clay / plastisin: semua sudut membulat tebal, bekas jari (bump), warna pastel hangat. */
import { MeshStandardMaterial, SphereGeometry } from 'three';
import { acak, buatKit, campur, kanvas, kotakBulat, pelacak, tabungBulat, type BagianKit, type Pelacak } from './alat';
import type { PembangunGaya } from './tipe';

export function bagianClay(s: Pelacak): BagianKit {
  const r = acak(5);
  const jari = kanvas(s, 256, 256, (g, w, h) => {
    g.fillStyle = '#808080';
    g.fillRect(0, 0, w, h);
    for (let k = 0; k < 26; k++) {
      const x = r() * w, y = r() * h, a = r() * 3;
      for (let rr = 3; rr < 26; rr += 3) {
        g.strokeStyle = rr % 2 ? 'rgba(255,255,255,.22)' : 'rgba(0,0,0,.22)';
        g.lineWidth = 1.5;
        g.beginPath();
        g.ellipse(x, y, rr * 1.4, rr, a, 0, 4.2);
        g.stroke();
      }
    }
    for (let i = 0; i < 900; i++) {
      g.fillStyle = r() > 0.5 ? 'rgba(255,255,255,.1)' : 'rgba(0,0,0,.1)';
      g.fillRect(r() * w, r() * h, 3, 3);
    }
  });
  return {
    warna: (c) => campur(c, '#fff2e0', 0.08),
    bahan: (c) => new MeshStandardMaterial({ color: c, roughness: 0.92, bumpMap: jari, bumpScale: 1.2 }),
    kotak: (w, h, d) => kotakBulat(w, h, d, Math.min(w, h, d) * 0.42),
    tabung: (rt, rb, h) => tabungBulat(rt, rb, h, Math.min(rt, rb, h) * 0.4),
    bola: (rad, _p, kubah) => (kubah ? new SphereGeometry(rad, 22, 16, 0, Math.PI * 2, 0, Math.PI / 1.8) : new SphereGeometry(rad, 22, 16)),
    cahaya: { langit: '#fff4e8', bumi: '#b89a80', kuat: 1.35, matahari: '#ffe8cc', mKuat: 1.9 },
    luar: { awan: true },
    kabut: ['#efe3cf', '#120d22'],
  };
}

export const clay: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    return buatKit(s, bagianClay(s));
  },
};
