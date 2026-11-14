/** Paduan: hand-painted + toko di trotoar (jalan, trotoar, lampu jalan, pot, papan nama, atap, bangunan tetangga). */
import { MeshBasicMaterial, MeshLambertMaterial, PlaneGeometry, PointLight } from 'three';
import { KANTOR } from '../config';
import { acak, buatKit, kanvas, papanNama, pelacak } from './alat';
import type { PembangunGaya } from './tipe';

export const toko: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    const r = acak(17);
    // Sapuan kuas abu-abu: dikali warna bahan, jadi warna malam tetap bisa diganti.
    const kuas = kanvas(s, 128, 128, (g, w, h) => {
      g.fillStyle = '#e6e6e6';
      g.fillRect(0, 0, w, h);
      for (let i = 0; i < 220; i++) {
        g.globalAlpha = 0.08 + r() * 0.08;
        g.strokeStyle = r() > 0.5 ? '#ffffff' : '#7a6a5a';
        g.lineWidth = 2 + r() * 5;
        g.lineCap = 'round';
        const x = r() * w, y = r() * h, a = r() * 0.6 - 0.3;
        g.beginPath();
        g.moveTo(x, y);
        g.lineTo(x + Math.cos(a) * (10 + r() * 20), y + Math.sin(a) * (10 + r() * 20));
        g.stroke();
      }
    }, { warna: true });
    return buatKit(s, {
      bahan: (c) => new MeshLambertMaterial({ color: c, map: kuas }),
      cahaya: { langit: '#fff0d8', bumi: '#c09060', kuat: 1.4, matahari: '#ffcf96', mKuat: 1.8 },
      kabut: ['#f3e2c0', '#1a1430'],
      dunia: ({ K, pasang, kantor }) => {
        const Y = -0.65;
        const bx = (w: number, h: number, d: number, c: string, x: number, y: number, z: number, p: Parameters<typeof K.bahan>[1] = 'jalan') => pasang(K.kotak(w, h, d, p), K.bahan(c, p), x, y, z);
        bx(70, 0.2, 70, '#c9b48a', 0, Y - 0.1, 0, 'tanah');
        bx(70, 0.12, 4.4, '#5d5560', 0, Y + 0.01, 8.4);
        const marka = s.simpan(new MeshBasicMaterial({ color: '#f2e4c4' }));
        for (let k = -9; k < 10; k++) pasang(K.kotak(1.6, 0.02, 0.18, 'jalan'), marka, k * 3.4, Y + 0.08, 8.4);
        bx(70, 0.3, 2.6, '#d9c09a', 0, Y + 0.1, 4.9);
        for (let k = -12; k < 13; k++) bx(0.05, 0.31, 2.6, '#b89a74', k * 2.6, Y + 0.11, 4.9);
        // atap miring di belakang + papan nama
        const atap = bx(15.4, 0.25, 3.2, '#b4523a', 0, 3.75, -4.6, 'kayu');
        atap.rotation.x = -0.5;
        bx(14.6, 0.9, 0.3, '#f2dcb8', 0, 3.4, -3.75, 'dinding');
        bx(5.6, 1.4, 0.14, '#6b4a32', 0.1, 4.6, -3.95, 'kayu');
        const nama = pasang(s.simpan(new PlaneGeometry(5.3, 1.15)), s.simpan(new MeshBasicMaterial({ map: papanNama(s, KANTOR.nama, '#3d5a4a', '#ffe7b0') })), 0.1, 4.6, -3.87);
        nama.renderOrder = 1;
        for (const x of [-2.3, 2.5]) bx(0.15, 1.6, 0.15, '#6b4a32', x, 3.6, -4.0, 'kayu');
        // kanopi bergaris di atas jendela belakang
        for (let k = 0; k < 8; k++) bx(1.75, 0.06, 0.8, k % 2 ? '#f4e6c8' : '#d9734e', -6.1 + k * 1.75, 2.9, -3.15, 'karpet').rotation.x = 0.4;
        // lampu jalan, pot, bangku
        const lampu: PointLight[] = [];
        for (const x of [-8.5, 8.5]) {
          bx(0.18, 5, 0.18, '#3e3a40', x, Y + 2.6, 5.8, 'logam');
          bx(0.9, 0.1, 0.3, '#3e3a40', x - 0.35, Y + 5.1, 5.8, 'logam');
          pasang(K.bola(0.28, 'lampu'), K.bahan('#ffe2a0', 'lampu', '#ffcf80'), x - 0.7, Y + 4.85, 5.8);
          const l = new PointLight('#ffcf80', 0, 9, 1.6);
          l.position.set(x - 0.7, Y + 4.6, 5.8);
          kantor.add(l);
          lampu.push(l);
        }
        for (const [x, c] of [[-6, '#7fa060'], [-2.5, '#94b06a'], [3, '#6f9a5a'], [6, '#a0b870']] as const) {
          pasang(K.tabung(0.4, 0.3, 0.7, 'pot'), K.bahan('#c06a3e', 'pot'), x, Y + 0.6, 4.6);
          pasang(K.bola(0.6, 'daun'), K.bahan(c, 'daun'), x, Y + 1.35, 4.6);
        }
        bx(1.8, 0.15, 0.6, '#8a5a3a', 0.5, Y + 0.75, 5.4, 'kayu');
        bx(1.8, 0.6, 0.1, '#8a5a3a', 0.5, Y + 1.05, 5.7, 'kayu');
        // bangunan tetangga (belakang, tidak menutupi kantor)
        bx(6, 7, 6, '#e6b98a', -11.5, Y + 3.5, -5, 'dinding');
        bx(6, 5, 6, '#9fb8a0', 11.5, Y + 2.5, -6, 'dinding');
        bx(6.4, 0.4, 6.4, '#8a4a32', -11.5, Y + 7.2, -5, 'kayu');
        return {
          gantiLuar: true,
          lebar: 1.2,
          zoomJauh: 0.85,
          malam: (m) => lampu.forEach((l) => (l.intensity = m ? 3 : 0)),
        };
      },
    });
  },
};
