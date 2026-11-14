/**
 * Paduan: Gerobak Bakso & Es di depan sekolah (siang). Trotoar paving terang, pagar & gerbang sekolah di belakang,
 * gerobak bakso berkaca dengan dandang, gerobak es warna-warni, payung pelangi, pohon peneduh, sepeda & motor.
 */
import { acak, buatKit, pelacak } from './alat';
import { bahanKakiLima, papanKapur, perabot, spanduk, tanahJalan, tekstur, warnaKakiLima, Y } from './kakilima';
import type { PembangunGaya } from './tipe';

export const bakso: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    const r = acak(43);
    const X = tekstur(s, r);
    const pav = X.paving(['#d6c7ad', '#c9b9a0', '#e0d3bb']);
    pav.repeat.set(4, 3);
    const tembok = X.kayu('#f2ead8', '#d8ccb0');
    const meja = X.kayu('#c98a4a', '#8a5a2a');
    const peta = { lantai: pav, karpet: pav, garis: pav, dinding: tembok, meja, kayu: meja, alas: pav, papan: papanKapur(s, r, 'JAJAN HARI INI') };
    return buatKit(s, {
      warna: warnaKakiLima(peta),
      bahan: bahanKakiLima(s, X.kuas, peta, false),
      cahaya: { langit: '#ffffff', bumi: '#b09070', kuat: 1.5, matahari: '#fff1d0', mKuat: 1.8 },
      kabut: ['#cfeeff', '#141a33'],
      dunia: (c) => {
        const P = perabot(s, c, X.kuas, false);
        tanahJalan(c, P, X.aspal('#5a5d64'), X.paving(['#c9b9a0', '#b8a78c', '#d6c7ad']), '#d8a020', '#f2efe2');
        // Pagar & gerbang sekolah di belakang dinding kantor.
        P.B(30, 0.6, 0.4, '#c8c0b0', 0, Y + 0.3, -5.6);
        for (let x = -14.5; x <= 14.5; x += 0.5) if (Math.abs(x) > 1.8) P.B(0.06, 2, 0.06, '#2a6a3a', x, Y + 1.6, -5.6);
        P.B(30, 0.08, 0.08, '#2a6a3a', 0, Y + 2.5, -5.6);
        for (const x of [-1.9, 1.9]) P.B(0.5, 3.4, 0.5, '#e8e0cc', x, Y + 1.7, -5.6);
        P.B(4.4, 0.9, 0.2, '#2a6a3a', 0, Y + 3.7, -5.6);
        P.P(4.2, 0.8, spanduk(s, [{ t: 'SEKOLAH DASAR CERIA', c: '#fffbe8', f: 'bold 64px Georgia' }], '#2a6a3a', '#ffd84a', 768, 150), 0, Y + 3.7, -5.48, 0, false);
        P.B(14, 5, 6, '#f2e2c0', -2, Y + 2.5, -10);
        P.B(14.4, 0.5, 6.4, '#b8523a', -2, Y + 5.2, -10);
        for (let i = 0; i < 6; i++) P.B(1.2, 1.1, 0.05, '#9fd4ff', -7.5 + i * 2.2, Y + 2.8, -6.97, { em: '#203040' });
        // Gerobak bakso berkaca (kanan).
        P.grup(9.6, 0.6, -Math.PI / 2, () => {
          P.B(3, 1.1, 1.3, '#2a7ad2', 0, 1.05, 0);
          P.B(3, 0.9, 1.3, P.M('#dff2ff', { op: 0.3, basic: true }), 0, 2.05, 0);
          P.B(3.1, 0.08, 1.4, '#e8e8e8', 0, 2.54, 0);
          P.P(2.8, 0.8, spanduk(s, [{ t: 'BAKSO', c: '#d22a2a', f: 'bold 110px Impact' }, { t: 'mie ayam · pangsit', c: '#2a2a2a', f: 'bold 44px Georgia' }], '#fffbe8', '#d22a2a', 512, 220), 0, 1.05, 0.66, 0, false);
          for (const a of [-1, 1]) P.roda(0.42, 0.08, a, 0.45, 0.7);
          P.T(0.4, 0.4, 0.7, '#c8ccd0', -0.8, 1.95, 0);
          P.T(0.42, 0.42, 0.06, '#9aa0a6', -0.8, 2.32, 0);
          for (let i = 0; i < 8; i++) P.S(0.1, '#d8c8a8', 0.2 + (i % 4) * 0.25, 1.7, -0.2 + Math.floor(i / 4) * 0.3);
          for (let i = 0; i < 4; i++) P.T(0.16, 0.1, 0.1, ['#f4f0e6', '#7ac0f0', '#f4f0e6', '#f07a7a'][i]!, -0.9 + i * 0.6, 1.66, 0.45);
        });
        // Gerobak es warna-warni (kiri depan).
        P.grup(-9.4, 1.6, Math.PI / 2, () => {
          P.B(2.4, 1, 1.1, '#f2c84a', 0, 1, 0);
          P.P(2.2, 0.7, spanduk(s, [{ t: 'ES CAMPUR', c: '#d22a6a', f: 'bold 80px Impact' }, { t: 'es teh · es jeruk', c: '#2a6a3a', f: 'bold 40px Georgia' }], '#fffbe8', '#d22a6a', 512, 220), 0, 1, 0.56, 0, false);
          for (const a of [-0.8, 0.8]) P.roda(0.35, 0.07, a, 0.38, 0.6);
          ['#ff6a8a', '#ffb84a', '#6ad08a', '#7ac0ff'].forEach((w, i) => P.T(0.18, 0.18, 0.5, w, -0.75 + i * 0.5, 1.75, 0, { op: 0.85 }));
          for (let i = 0; i < 5; i++) P.gelas(-0.9 + i * 0.45, 1.5, 0.35, ['#ff6a8a', '#ffb84a', '#6ad08a', '#c08a4a', '#7ac0ff'][i]);
        });
        // Payung pelangi di atas kedua gerobak.
        const payung = (x: number, z: number) =>
          P.grup(x, z, 0, () => {
            P.T(0.04, 0.04, 3.4, '#e8e8e8', 0, 1.7, 0);
            ['#e83a3a', '#f2a03a', '#f2e04a', '#4ab04a', '#3a8ae8'].forEach((w, i) => P.T(0.02, 1.7 - i * 0.3, 0.12, w, 0, 3.2 + i * 0.1, 0));
          });
        payung(10.6, 0.6);
        payung(-10.2, 1.6);
        // Pohon peneduh, sepeda & motor anak sekolah.
        for (const [x, z, k] of [[-11.5, -2.5, 1.3], [12, -3, 1.4], [-6, -7.4, 1.1], [8, -7.6, 1.2], [13.5, 4, 1.1]] as const) P.pohon(x, z, k, r);
        P.sepeda(-6, 4.4, 0.2, '#d22a2a');
        P.sepeda(-4.6, 4.6, 0.1, '#2a7ad2');
        P.sepeda(5, 4.5, -0.1, '#2aa04a');
        P.motor(7, 4.4, 0.15, '#2a2a2a');
        return { gantiLuar: true, lebar: 1.15, zoomJauh: 0.85 };
      },
    });
  },
};
