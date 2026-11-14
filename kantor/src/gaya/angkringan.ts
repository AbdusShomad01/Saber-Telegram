/**
 * Paduan: Angkringan Malam. Lantai tikar lesehan, dinding papan kayu, gerobak angkringan beratap terpal, tungku arang
 * menyala dengan ceret, untaian bohlam kuning, bangku kayu, trotoar paving, sepotong aspal malam, motor parkir.
 */
import { acak, buatKit, pelacak } from './alat';
import { bahanKakiLima, papanKapur, perabot, spanduk, tanahJalan, tekstur, warnaKakiLima, Y } from './kakilima';
import { Vector3 } from 'three';
import type { PembangunGaya } from './tipe';

export const angkringan: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    const r = acak(31);
    const X = tekstur(s, r);
    const papan = X.kayu('#7a4e2c', '#4a2c14');
    papan.repeat.set(4, 1);
    const kayuMeja = X.kayu('#a8703c', '#6a4220');
    const peta = { lantai: X.tikar, karpet: X.tikar, garis: X.tikar, dinding: papan, kayu: kayuMeja, meja: kayuMeja, kursi: kayuMeja, alas: papan, papan: papanKapur(s, r, 'MENU MALAM INI') };
    return buatKit(s, {
      selaluMalam: true,
      warna: warnaKakiLima(peta),
      bahan: bahanKakiLima(s, X.kuas, peta, true),
      cahaya: { langit: '#b0a0ff', bumi: '#4a2a14', kuat: 1.6, matahari: '#ffd9a0', mKuat: 0.9 },
      kabut: ['#141a33', '#141a33'],
      dunia: (c) => {
        const P = perabot(s, c, X.kuas, true);
        P.terang('#ffd9a8', '#3a2a40', 1.3);
        tanahJalan(c, P, X.aspal('#2c2f38'), X.paving(['#77736c', '#6e6a64', '#827d74']), '#2a2a2a', '#e8e2c8');
        // Gerobak angkringan di kanan kantor (beratap terpal biru, roda kayu, spanduk lukis).
        const terpal = X.terpal('#2f6fb3', '#2a62a0');
        const kg = X.kayu('#8a5a32', '#5a3518');
        P.grup(9.6, 0.4, -Math.PI / 2, () => {
          P.B(4, 1.1, 1.6, P.M('#ffffff', { map: kg }), 0, 1.15, 0);
          P.B(4.3, 0.1, 1.9, P.M('#ffffff', { map: kg }), 0, 1.75, 0);
          for (const a of [-1.9, 1.9]) for (const b of [-0.8, 0.8]) P.T(0.06, 0.06, 1.7, '#5a3518', a, 2.6, b);
          P.B(4.8, 0.08, 2.6, P.M('#ffffff', { map: terpal }), 0, 3.5, 0).rotation.x = -0.1;
          P.B(4.8, 0.4, 0.05, P.M('#ffffff', { map: terpal }), 0, 3.25, 1.3);
          for (const a of [-1.3, 1.3]) P.roda(0.55, 0.08, a, 0.6, 0.85);
          P.P(3.6, 0.8, spanduk(s, [{ t: 'NASI KUCING · WEDANG JAHE', c: '#ffe7a0', f: 'bold 64px Georgia' }, { t: 'sate usus · gorengan · kopi joss', c: '#ffffff', f: 'italic 44px Georgia' }], '#7a1e14', '#ffcf6a'), 0, 1.15, 0.82, 0);
          // Bungkus nasi kucing, tusuk sate, ceret di atas tungku arang menyala.
          for (let i = 0; i < 10; i++) P.B(0.26, 0.12, 0.2, i % 2 ? '#c9a46a' : '#e0d2b0', -1.6 + (i % 5) * 0.32, 1.86, -0.3 + Math.floor(i / 5) * 0.3);
          for (let i = 0; i < 6; i++) P.B(0.05, 0.05, 0.5, '#8a3a1a', 0.2 + i * 0.12, 1.84, 0.2);
          P.T(0.45, 0.4, 0.5, '#3a3430', 1.4, 2.05, 0.1);
          P.T(0.38, 0.38, 0.06, '#ff6a20', 1.4, 2.31, 0.1, { em: '#ff5a10' });
          P.teko(1.25, 2.33, 0.05, '#d8d2c4');
          P.teko(1.6, 2.33, 0.2, '#b8b0a0');
          P.cahaya(1.4, 2.6, 0.4, '#ff7a30', 4, 5);
          P.bohlam(0, 3.05, 0, '#ffd27a', 7, 10);
        });
        // Bangku kayu panjang di depan & lesehan tambahan.
        const bk = X.kayu('#9a6a3a', '#5a3518');
        for (const [x, z] of [[-3.5, 4.2], [3.5, 4.2]] as const) {
          P.B(3, 0.12, 0.5, P.M('#ffffff', { map: bk }), x, Y + 0.55, z);
          for (const a of [-1.3, 1.3]) P.B(0.1, 0.5, 0.4, '#5a3518', x + a, Y + 0.25, z);
        }
        for (const x of [-3.5, 3.5]) {
          P.gelas(x - 0.6, Y + 0.61, 4.2);
          P.gelas(x + 0.5, Y + 0.61, 4.2, '#7a3a1a');
        }
        // Untaian bohlam kuning di atas kantor.
        const a = new Vector3(-7.4, 3.6, -3.5), b = new Vector3(7.4, 3.6, -3.5);
        for (const x of [-7.4, 7.4]) for (const z of [-3.5, 3.4]) P.T(0.07, 0.07, 4.3, '#5a3518', x, Y + 2.15 + 0.1, z);
        P.kabel(a, b, 0.25);
        P.kabel(new Vector3(-7.4, 3.6, 3.4), new Vector3(7.4, 3.6, 3.4), 0.25);
        for (let i = 0; i < 5; i++) {
          P.bohlam(-6 + i * 3, 3.0, -3.0, '#ffcf6a', 4, 8);
          P.bohlam(-6 + i * 3, 3.0, 3.3, '#ffcf6a', 4, 8);
        }
        // Motor parkir, pohon gelap di belakang.
        P.motor(-9.4, 2.5, 0.3, '#b42a2a');
        P.motor(-9.8, 0.2, 0.2, '#2a4ab4');
        P.motor(12.6, 4.6, -0.2, '#2a2a2a');
        for (const [x, z] of [[-10, -6], [-3, -7.5], [5, -7], [11, -5.5]] as const) P.pohon(x, z, 1.1, r);
        return { gantiLuar: true, lebar: 1.15, zoomJauh: 0.85 };
      },
    });
  },
};
