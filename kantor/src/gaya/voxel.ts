/** Voxel: semua objek jadi balok, tekstur piksel 16×16 (tanpa penghalusan). */
import { BoxGeometry, MeshLambertMaterial } from 'three';
import { acak, buatKit, kanvas, pelacak, skalaUV, type BagianKit, type Pelacak } from './alat';
import type { PembangunGaya } from './tipe';

export function bagianVoxel(s: Pelacak): BagianKit {
  const r = acak(3);
  const blok = kanvas(s, 16, 16, (g) => {
    g.fillStyle = '#fff';
    g.fillRect(0, 0, 16, 16);
    for (let i = 0; i < 40; i++) {
      g.fillStyle = `rgba(0,0,0,${0.03 + r() * 0.07})`;
      g.fillRect((r() * 16) | 0, (r() * 16) | 0, 1, 1);
    }
    g.fillStyle = 'rgba(0,0,0,.16)';
    g.fillRect(0, 15, 16, 1);
    g.fillRect(15, 0, 1, 16);
    g.fillStyle = 'rgba(255,255,255,.3)';
    g.fillRect(0, 0, 16, 1);
    g.fillRect(0, 0, 1, 16);
  }, { piksel: true });
  const kotak = (w: number, h: number, d: number) => skalaUV(new BoxGeometry(w, h, d), w, h, d, 0.5);
  return {
    bahan: (c, p) => new MeshLambertMaterial({ color: c, map: p === 'layar' || p === 'kaca' ? null : blok }),
    kotak,
    bola: (rad, _p, kubah) => {
      if (!kubah) return kotak(rad * 1.8, rad * 1.8, rad * 1.8);
      const g = kotak(rad * 2, rad * 0.9, rad * 2);
      g.translate(0, rad * 0.6, 0);
      return g;
    },
    tabung: (rt, rb, h) => kotak(Math.max(rt, rb) * 1.8, h, Math.max(rt, rb) * 1.8),
    kerucut: (rad, h) => kotak(rad * 1.5, h * 0.8, rad * 1.5),
    kapsul: (rad, len) => kotak(rad * 2, len + rad * 2, rad * 2),
    cahaya: { langit: '#ffffff', bumi: '#7a9a6a', kuat: 1.4, matahari: '#fffaf0', mKuat: 1.8 },
    luar: { awan: true },
    kabut: ['#cfeeff', '#0b1430'],
  };
}

export const voxel: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    return buatKit(s, bagianVoxel(s));
  },
};
