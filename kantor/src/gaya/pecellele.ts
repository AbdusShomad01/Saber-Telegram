/**
 * Paduan: Warung Tenda Pecel Lele. Dinding jadi terpal oranye dengan spanduk lukis besar, meja panjang & bangku plastik,
 * gerobak penggorengan berwajan, lampu neon tabung, tiang listrik dengan kabel semrawut, trotoar malam.
 */
import { Vector3 } from 'three';
import { acak, buatKit, pelacak } from './alat';
import { bahanKakiLima, papanKapur, perabot, spanduk, tanahJalan, tekstur, warnaKakiLima, Y } from './kakilima';
import type { PembangunGaya } from './tipe';

export const pecellele: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    const r = acak(37);
    const X = tekstur(s, r);
    const terpal = X.terpal('#e8742a', '#d8641e');
    terpal.repeat.set(5, 1);
    const pav = X.paving(['#8a857c', '#7d786f', '#95907f']);
    pav.repeat.set(4, 3);
    const meja = X.kayu('#e6d6b8', '#b8a07a');
    const peta = { lantai: pav, karpet: pav, garis: pav, dinding: terpal, meja, kayu: meja, alas: pav, papan: papanKapur(s, r, 'PESANAN HARI INI') };
    return buatKit(s, {
      selaluMalam: true,
      warna: warnaKakiLima(peta),
      bahan: bahanKakiLima(s, X.kuas, peta, true),
      cahaya: { langit: '#b8c4ff', bumi: '#3a2a30', kuat: 1.6, matahari: '#e8f4ff', mKuat: 0.9 },
      kabut: ['#1d2440', '#1d2440'],
      dunia: (c) => {
        const P = perabot(s, c, X.kuas, true);
        P.terang('#e8f0ff', '#3a2a30', 1.3);
        tanahJalan(c, P, X.aspal('#30333c'), X.paving(['#6e6a64', '#77736c', '#625f59']), '#2a2a2a', '#f2efe2');
        // Rangka tenda + spanduk lukis besar di atas dinding belakang.
        const tp = P.M('#ffffff', { map: X.terpal('#e8742a', '#f4f0e6') });
        for (const x of [-7.4, -2.5, 2.5, 7.4]) {
          P.T(0.06, 0.06, 5.6, '#c0c4c8', x, Y + 2.8, -3.85);
          P.T(0.06, 0.06, 3.9, '#c0c4c8', x, Y + 1.95 + 0.65, 3.4);
        }
        P.B(15.2, 0.06, 2.6, tp, 0, 5.0, -4.7).rotation.x = -0.35;
        P.B(15, 0.08, 0.08, '#c0c4c8', 0, 3.35, 3.4);
        const sp = spanduk(
          s,
          [
            { t: 'PECEL LELE · AYAM GORENG · SEAFOOD', c: '#a02a1a', f: 'bold 78px Impact, sans-serif' },
            { t: 'sambal terasi · lalapan · nasi uduk', c: '#1f5a8a', f: 'italic bold 52px Georgia' },
          ],
          '#fff4dc',
          '#a02a1a',
          1536,
          320,
        );
        P.P(13.6, 2.6, sp, 0, 4.25, -3.62, 0, false);
        // Gambar lele & ayam di spanduk sisi kiri (lukisan sederhana).
        P.P(4.6, 2.4, spanduk(s, [{ t: 'LELE', c: '#3a5a2a', f: 'bold 120px Impact' }, { t: 'ayam · bebek · cumi', c: '#a02a1a', f: 'bold 48px Georgia' }], '#fff4dc', '#3a5a2a', 512, 256), -7.25, 1.6, 0, Math.PI / 2, false);
        // Meja panjang & bangku plastik di depan tenda.
        const mt = P.M('#ffffff', { map: meja });
        P.B(9, 0.08, 0.9, mt, 0, Y + 0.85, 4.6);
        for (const x of [-4.2, 0, 4.2]) P.B(0.1, 0.8, 0.7, '#8a8f96', x, Y + 0.42, 4.6);
        const warnaBangku = ['#d22a2a', '#1f6ad2', '#d22a2a', '#2aa04a', '#1f6ad2', '#d22a2a'];
        for (let i = 0; i < 6; i++) {
          P.bangkuPlastik(-3.8 + i * 1.5, 3.85, warnaBangku[i]!);
          P.bangkuPlastik(-3.8 + i * 1.5, 5.35, warnaBangku[5 - i]!);
        }
        for (let i = 0; i < 4; i++) {
          P.T(0.2, 0.17, 0.04, '#f4f0e6', -3 + i * 2, Y + 0.91, 4.6);
          P.gelas(-2.6 + i * 2, Y + 0.89, 4.6, '#c9862a');
        }
        P.T(0.08, 0.08, 0.2, '#d22a2a', 0.6, Y + 0.99, 4.6);
        // Gerobak penggorengan (kaca, wajan di atas kompor menyala).
        P.grup(9.4, 0, -Math.PI / 2, () => {
          P.B(3.2, 1.0, 1.3, '#d8dde2', 0, 1.0, 0);
          P.B(3.2, 0.7, 1.3, P.M('#bfe3ff', { op: 0.35, basic: true }), 0, 1.85, 0);
          P.B(3.3, 0.06, 1.4, '#a8adb2', 0, 2.22, 0);
          P.P(3, 0.8, spanduk(s, [{ t: 'PECEL LELE', c: '#a02a1a', f: 'bold 90px Impact' }, { t: 'CAK MALIK', c: '#1f5a8a', f: 'bold 50px Georgia' }], '#fff4dc', '#a02a1a', 512, 220), 0, 1.0, 0.66, 0, false);
          for (const a of [-1.1, 1.1]) P.roda(0.4, 0.07, a, 0.42, 0.7);
          for (let i = 0; i < 6; i++) P.S(0.12, i % 2 ? '#c88a3a' : '#e0a050', -1.1 + i * 0.35, 1.7, 0);
          P.T(0.6, 0.55, 0.7, '#3a3a3a', -2.4, 0.35, 0);
          P.T(0.7, 0.35, 0.22, '#2a2a2a', -2.4, 0.82, 0);
          P.T(0.62, 0.62, 0.04, '#c88a2a', -2.4, 0.92, 0, { em: '#6a3a0a' });
          P.cahaya(-2.4, 1.3, 0, '#ff8a3a', 3, 4);
        });
        // Lampu neon tabung putih di rangka tenda.
        for (const x of [-5, 0, 5]) {
          P.B(1.4, 0.08, 0.08, '#f4fbff', x, 3.25, 3.3, { basic: true });
          P.cahaya(x, 3.5, 2.8, '#eaf6ff', 6, 10);
          P.B(1.4, 0.08, 0.08, '#f4fbff', x, 3.4, -3.3, { basic: true });
          P.cahaya(x, 3.2, -2.8, '#eaf6ff', 5, 9);
        }
        // Tiang listrik + kabel semrawut.
        const t1 = P.tiang(-9.5, 6.2), t2 = P.tiang(11, 6.2), t3 = P.tiang(-10, -6.5, 8);
        P.kabel(t1, t2, 1.1);
        P.kabel(t1.clone().add(new Vector3(0.7, 0, 0)), t2.clone().add(new Vector3(0.7, 0, 0)), 1.4);
        P.kabel(t1.clone().add(new Vector3(-0.7, 0, 0)), t2.clone().add(new Vector3(-0.7, 0, 0)), 0.8);
        P.kabel(t1, t3, 0.9);
        P.kabel(t1, new Vector3(-7.4, 3.9, 3.4), 0.5);
        P.kabel(t2, new Vector3(7.4, 3.9, 3.4), 0.6);
        P.motor(-9.6, 2.6, 0.4, '#2a2a2a');
        P.motor(-9.2, 0.4, 0.3, '#c8a02a');
        P.motor(12.4, 1, -0.3, '#b42a2a');
        return { gantiLuar: true, lebar: 1.15, zoomJauh: 0.85 };
      },
    });
  },
};
