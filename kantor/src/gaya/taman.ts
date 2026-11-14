/** Paduan: low-poly + paviliun taman (tanah segi sembilan bertebing, kolam, jembatan, pergola, cemara, batu). */
import { CapsuleGeometry, CircleGeometry, ConeGeometry, CylinderGeometry, DodecahedronGeometry, MeshLambertMaterial, SphereGeometry } from 'three';
import { acak, buatKit, pelacak } from './alat';
import type { PembangunGaya } from './tipe';

export const taman: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    return buatKit(s, {
      bahan: (c) => new MeshLambertMaterial({ color: c, flatShading: true }),
      bola: (r, _p, kubah) => (kubah ? new SphereGeometry(r, 7, 4, 0, Math.PI * 2, 0, Math.PI / 1.8) : new SphereGeometry(r, 7, 5)),
      tabung: (rt, rb, h) => new CylinderGeometry(rt, rb, h, 6),
      kerucut: (r, h, _p, t) => new ConeGeometry(r, h, 6, 1, !!t),
      kapsul: (r, len) => new CapsuleGeometry(r, len, 2, 6),
      cahaya: { langit: '#fffbe8', bumi: '#8aa070', kuat: 1.4, matahari: '#fff0d0', mKuat: 1.8 },
      kabut: ['#cfe8e4', '#0e1a2a'],
      dunia: ({ K, pasang }) => {
        const r = acak(29);
        const Y = -0.65;
        const tanah = new CircleGeometry(15, 9);
        tanah.rotateX(-Math.PI / 2);
        pasang(s.simpan(tanah), K.bahan('#9cc96b', 'tanah'), 0, Y, 0);
        pasang(s.simpan(new CylinderGeometry(15, 12, 2.5, 9)), K.bahan('#b98a5a', 'tanah'), 0, Y - 1.26, 0);
        pasang(s.simpan(new CylinderGeometry(3.4, 3.4, 0.12, 7)), K.bahan('#5fb6d6', 'air'), 9.2, Y + 0.03, -5);
        pasang(s.simpan(new CylinderGeometry(3.7, 3.7, 0.08, 7)), K.bahan('#c9b78a', 'batu'), 9.2, Y, -5);
        for (let k = 0; k < 6; k++) {
          const t = (k - 2.5) / 2.5;
          pasang(K.kotak(1.4, 0.15, 0.7, 'kayu'), K.bahan('#b0704a', 'kayu'), 9.4, Y + 0.3 + (1 - t * t) * 0.6, -7.6 + k * 0.85);
        }
        // pilar & pergola paviliun
        const kayu = K.bahan('#9a6a44', 'kayu');
        for (const [x, z] of [[-7.4, -3.8], [7.4, -3.8], [-7.4, 3.4], [7.4, 3.4]]) pasang(K.tabung(0.18, 0.22, 4.6, 'kayu'), kayu, x!, Y + 2.3 + 0.4, z!);
        pasang(K.kotak(15.2, 0.25, 0.3, 'kayu'), kayu, 0, 4.2, -3.8);
        pasang(K.kotak(15.2, 0.25, 0.3, 'kayu'), kayu, 0, 4.2, 3.4);
        for (let k = 0; k < 12; k++) pasang(K.kotak(0.18, 0.2, 7.8, 'kayu'), K.bahan('#b88050', 'kayu'), -6.9 + k * 1.25, 4.42, -0.2);
        const cemara = (x: number, z: number, sk: number, c: string) => {
          pasang(K.tabung(0.15 * sk, 0.2 * sk, 0.8 * sk, 'batang'), K.bahan('#7a5232', 'batang'), x, Y + 0.4 * sk, z);
          for (const [rr, h, y] of [[1.1, 1.4, 1.1], [0.85, 1.2, 1.8], [0.6, 1, 2.4]]) pasang(K.kerucut(rr! * sk, h! * sk, 'daun'), K.bahan(c, 'daun'), x, Y + y! * sk, z);
        };
        [[-11, -5], [-10, 4], [-12, 0], [3, -9], [-4, -10], [-8, -8.5], [12, 1], [0, -11.5]].forEach(([x, z], k) => cemara(x!, z!, 1 + r() * 0.5, ['#3f8a4e', '#4f9a58', '#2f7a44'][k % 3]!));
        for (const [x, z, sk] of [[11, -1.5, 1], [5, -9, 0.7], [-9, -2, 0.8], [-6, 8.5, 0.6]]) {
          const b = pasang(s.simpan(new DodecahedronGeometry(sk!, 0)), K.bahan('#a7a9a4', 'batu'), x!, Y + sk! * 0.4, z!);
          b.scale.y = 0.7;
        }
        for (let k = 0; k < 5; k++) pasang(K.tabung(0.45, 0.45, 0.06, 'batu'), K.bahan('#e2d8c4', 'batu'), 3 + k * 0.4, Y + 0.03, 4.4 + k * 0.9);
        return { gantiLuar: true, lebar: 1.3, zoomJauh: 0.75 };
      },
    });
  },
};
