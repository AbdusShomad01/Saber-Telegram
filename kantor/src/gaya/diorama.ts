/** Diorama miniatur: kayu, kain, plester, rumput asli (tekstur kanvas), alas kayu, cahaya hangat, kabur tilt-shift. */
import { MeshStandardMaterial } from 'three';
import { acak, buatKit, campur, kanvas, pelacak } from './alat';
import type { PembangunGaya } from './tipe';

export const diorama: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    const r = acak(9);
    const kayu = kanvas(s, 256, 256, (g, w, h) => {
      g.fillStyle = '#c8a070';
      g.fillRect(0, 0, w, h);
      for (let i = 0; i < 80; i++) {
        g.strokeStyle = `rgba(${r() > 0.5 ? 60 : 190},${r() > 0.5 ? 35 : 130},20,${0.12 + r() * 0.2})`;
        g.lineWidth = 0.5 + r() * 2;
        g.beginPath();
        const y = r() * h;
        g.moveTo(0, y);
        for (let x = 0; x <= w; x += 12) g.lineTo(x, y + Math.sin(x * 0.02 + i) * 4);
        g.stroke();
      }
      for (let i = 0; i < 6; i++) {
        g.fillStyle = 'rgba(40,20,5,.35)';
        g.fillRect(0, i * 43, w, 1.2);
      }
    }, { warna: true });
    const kain = kanvas(s, 128, 128, (g, w, h) => {
      g.fillStyle = '#ddd';
      g.fillRect(0, 0, w, h);
      for (let i = 0; i < w; i += 3) {
        g.fillStyle = 'rgba(255,255,255,.2)';
        g.fillRect(i, 0, 1.5, h);
        g.fillStyle = 'rgba(0,0,0,.14)';
        g.fillRect(0, i, w, 1.5);
      }
    }, { warna: true });
    const plester = kanvas(s, 256, 256, (g, w, h) => {
      g.fillStyle = '#f2ece2';
      g.fillRect(0, 0, w, h);
      for (let i = 0; i < 3000; i++) {
        g.fillStyle = r() > 0.5 ? 'rgba(255,255,255,.2)' : 'rgba(120,100,80,.12)';
        g.fillRect(r() * w, r() * h, 2, 2);
      }
    }, { warna: true });
    const rumput = kanvas(s, 256, 256, (g, w, h) => {
      g.fillStyle = '#9ab070';
      g.fillRect(0, 0, w, h);
      for (let i = 0; i < 6000; i++) {
        g.fillStyle = `hsla(${70 + r() * 40},${35 + r() * 25}%,${35 + r() * 30}%,.7)`;
        g.fillRect(r() * w, r() * h, 1.5, 3);
      }
    }, { warna: true });
    rumput.repeat.set(8, 8);
    const peta: Record<string, typeof kayu> = { meja: kayu, lantai: kayu, alas: kayu, kayu, kaki: kayu, kursi: kain, karpet: kain, baju: kain, celana: kain, sofa: kain, dinding: plester, tanah: rumput };
    return buatKit(s, {
      warna: (c) => campur(c, '#8a7a6a', 0.18),
      bahan: (c, p) =>
        new MeshStandardMaterial({
          color: c,
          map: peta[p] ?? null,
          roughness: p === 'kaca' ? 0.1 : p === 'layar' ? 0.4 : 0.8,
          metalness: p === 'logam' || p === 'bingkai' ? 0.3 : 0,
          transparent: p === 'kaca',
          opacity: p === 'kaca' ? 0.5 : 1,
        }),
      luar: { ukuran: 24, alas: '#5a3a20' },
      cahaya: { langit: '#fff0dc', bumi: '#5a4a3a', kuat: 1.1, matahari: '#ffe2bc', mKuat: 2.0 },
      kabut: null,
    });
  },
};
