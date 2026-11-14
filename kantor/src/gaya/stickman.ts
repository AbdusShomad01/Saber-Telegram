/** Stickman 3D: dunia putih bergaris tinta, agen dari batang tipis + kepala bulat hitam, aksen warna baju. */
import { CapsuleGeometry, CylinderGeometry, EdgesGeometry, IcosahedronGeometry, LineBasicMaterial, LineSegments, MeshLambertMaterial } from 'three';
import { buatKit, pelacak } from './alat';
import type { PembangunGaya } from './tipe';

const TINTA = '#1c1c1e';
const HITAM = ['kulit', 'rambut', 'celana', 'logam', 'bingkai', 'kaki', 'batang'];
const WARNA = ['layar', 'catatan', 'baju', 'lampu', 'buku', 'karpet', 'air'];

export const stickman: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    const garis = s.simpan(new LineBasicMaterial({ color: TINTA }));
    return buatKit(s, {
      warna: (c, p) => (HITAM.includes(p) ? TINTA : WARNA.includes(p) ? c : p === 'lantai' || p === 'tanah' ? '#fbfbf9' : '#ffffff'),
      bahan: (c) => new MeshLambertMaterial({ color: c }),
      kapsul: (r, len, p) => (p === 'baju' && len > 0.38 ? new CapsuleGeometry(r * 0.32, len, 3, 8) : new CylinderGeometry(r * 0.32, r * 0.32, len + r * 2, 6)),
      bola: (r, p, kubah) => (p === 'daun' ? new IcosahedronGeometry(r, 1) : kubah ? new CylinderGeometry(0.001, 0.001, 0.001, 3) : new IcosahedronGeometry(r, 3)),
      hias: (m, p) => {
        if (HITAM.includes(p) || p === 'kulit' || p === 'garis' || p === 'layar' || p === 'baju') return;
        const e = s.simpan(new EdgesGeometry(m.geometry, 25));
        m.add(new LineSegments(e, garis));
      },
      cahaya: { langit: '#ffffff', bumi: '#dddddd', kuat: 1.6, matahari: '#ffffff', mKuat: 0.9 },
      kabut: ['#f6f6f4', '#121216'],
    });
  },
};
