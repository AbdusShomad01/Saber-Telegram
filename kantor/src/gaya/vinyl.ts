/** Mainan vinyl / chibi: plastik mengilap (clearcoat), sudut sangat bulat, kepala agen besar, alas bundar. */
import { MeshPhysicalMaterial, MeshStandardMaterial, SphereGeometry } from 'three';
import { buatKit, campur, kotakBulat, pelacak, tabungBulat } from './alat';
import type { PembangunGaya } from './tipe';

const DOP = ['lantai', 'garis', 'karpet', 'dinding', 'tanah', 'jalan', 'air', 'alas'];

export const vinyl: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    return buatKit(s, {
      warna: (c) => campur(c, '#ffffff', 0.22),
      bahan: (c, p) =>
        DOP.includes(p)
          ? new MeshStandardMaterial({ color: c, roughness: 0.55 })
          : new MeshPhysicalMaterial({ color: c, roughness: p === 'kaca' ? 0.05 : 0.25, clearcoat: 1, clearcoatRoughness: 0.08, transparent: p === 'kaca', opacity: p === 'kaca' ? 0.55 : 1 }),
      kotak: (w, h, d) => kotakBulat(w, h, d, Math.min(w, h, d) * 0.4),
      tabung: (rt, rb, h) => tabungBulat(rt, rb, h, Math.min(rt, rb, h) * 0.35),
      bola: (r, _p, kubah) => (kubah ? new SphereGeometry(r, 24, 16, 0, Math.PI * 2, 0, Math.PI / 1.8) : new SphereGeometry(r, 24, 16)),
      agen: { kepala: 1.55, badan: 0.85 },
      luar: { bentuk: 'bulat', ukuran: 26, awan: true },
      cahaya: { langit: '#ffffff', bumi: '#c8b8d8', kuat: 1.2, matahari: '#fff4fa', mKuat: 1.6 },
      kabut: null,
    });
  },
};
