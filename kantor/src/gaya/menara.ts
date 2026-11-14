/** Paduan: neon + bangunan bertumpuk (kantor di puncak tiga lantai bergeser, tepi neon, tangga zigzag, papan AGEN). */
import {
  BufferGeometry,
  EdgesGeometry,
  Float32BufferAttribute,
  GridHelper,
  LineBasicMaterial,
  LineSegments,
  MeshBasicMaterial,
  MeshPhongMaterial,
  PlaneGeometry,
  PointLight,
  Points,
  PointsMaterial,
  Color,
} from 'three';
import { acak, buatKit, kanvas, pelacak } from './alat';
import type { PembangunGaya } from './tipe';

const TEPI = ['dinding', 'meja', 'papan', 'sofa', 'alas', 'kursi'];

export const menara: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    const r = acak(23);
    const tepi = s.simpan(new LineBasicMaterial({ color: '#00e5ff' }));
    const tepiPink = s.simpan(new LineBasicMaterial({ color: '#ff3df2' }));
    return buatKit(s, {
      selaluMalam: true,
      bahan: (c, p) => {
        const k = new Color(c);
        const terang = p === 'layar' || p === 'lampu' || p === 'catatan' || p === 'neon';
        return new MeshPhongMaterial({
          color: k.clone().multiplyScalar(0.45),
          emissive: k.clone().multiplyScalar(terang ? 0.6 : p === 'baju' || p === 'kulit' ? 0.25 : 0.1),
          shininess: 60,
          transparent: p === 'kaca',
          opacity: p === 'kaca' ? 0.35 : 1,
        });
      },
      hias: (m, p) => {
        if (!TEPI.includes(p)) return;
        m.add(new LineSegments(s.simpan(new EdgesGeometry(m.geometry, 30)), p === 'meja' || p === 'kursi' ? tepiPink : tepi));
      },
      cahaya: { langit: '#6a6ad0', bumi: '#100018', kuat: 1.2, matahari: '#8fa2ff', mKuat: 0.8 },
      kabut: null,
      dunia: ({ kantor, K, pasang }) => {
        const FH = 3.8;
        const Y = -0.65;
        const warna = ['#00e5ff', '#ff3df2', '#00e5ff'];
        const neon = (c: string) => s.simpan(new MeshBasicMaterial({ color: c }));
        const garis = (g: BufferGeometry, c: string) => new LineSegments(s.simpan(new EdgesGeometry(g)), s.simpan(new LineBasicMaterial({ color: c })));
        for (let k = 0; k < 3; k++) {
          const y0 = Y - FH * (k + 1);
          const dx = k % 2 ? -0.6 : 0.5;
          const c = warna[k]!;
          const lantai = pasang(K.kotak(14.6, 0.3, 7.1, 'neon'), K.bahan('#0c1022', 'alas'), dx, y0 + 0.15, -0.25);
          lantai.add(garis(lantai.geometry, c));
          const bel = pasang(K.kotak(14.6, FH - 0.3, 0.2, 'neon'), K.bahan('#101830', 'dinding'), dx, y0 + FH / 2 + 0.15, -3.7);
          bel.add(garis(bel.geometry, c));
          pasang(K.kotak(0.2, FH - 0.3, 7.1, 'neon'), K.bahan('#101830', 'dinding'), dx - 7.2, y0 + FH / 2 + 0.15, -0.25);
          for (let w = 0; w < 8; w++) pasang(s.simpan(new PlaneGeometry(1.2, 1.6)), neon(r() > 0.4 ? '#1fd8ff' : '#ff6af2'), dx - 6 + w * 1.7, y0 + 1.9, -3.58);
          const kaca = pasang(K.kotak(14.6, FH - 0.3, 0.05, 'kaca'), K.bahan('#8888ff', 'kaca'), dx, y0 + FH / 2 + 0.15, 3.3);
          kaca.add(garis(kaca.geometry, c));
          pasang(K.kotak(14.8, 0.12, 0.12, 'neon'), neon(c), dx, y0 + FH - 0.1, 3.35);
          pasang(K.kotak(0.12, 0.12, 7.3, 'neon'), neon(c), dx + 7.35, y0 + FH - 0.1, -0.25);
          for (const x of [-4, 0.5, 4.5]) {
            pasang(K.kotak(1.8, 0.1, 0.9, 'meja'), K.bahan('#222233', 'meja'), dx + x, y0 + 1.1, -0.5);
            pasang(s.simpan(new PlaneGeometry(0.8, 0.45)), neon('#7dff6a'), dx + x, y0 + 1.6, -0.9);
          }
          const l = new PointLight(c, 3, 10, 1.6);
          l.position.set(dx, y0 + 2, 1);
          kantor.add(l);
          s.simpan({ dispose: () => l.removeFromParent() });
          for (let t = 0; t < 10; t++) pasang(K.kotak(1.2, 0.12, 0.5, 'neon'), K.bahan('#2a2f50', 'alas'), dx + 8.2, y0 + 0.3 + (t * FH) / 10, (k % 2 ? 2.5 : -2.5) + (k % 2 ? -1 : 1) * t * 0.5);
        }
        // tanah kisi, bintang, papan AGEN, gedung latar
        const dasar = Y - FH * 3;
        const kisi = new GridHelper(90, 45, '#ff3df2', '#3a0a5a');
        kisi.position.y = dasar + 0.01;
        kantor.add(kisi);
        s.simpan({ dispose: () => (kisi.geometry.dispose(), (kisi.material as LineBasicMaterial).dispose()) });
        pasang(K.kotak(90, 0.1, 90, 'jalan'), neon('#08061a'), 0, dasar - 0.06, 0);
        const bintang = s.simpan(new BufferGeometry());
        const a: number[] = [];
        for (let i = 0; i < 600; i++) a.push((r() - 0.5) * 140, dasar + 10 + r() * 60, -30 - r() * 40);
        bintang.setAttribute('position', new Float32BufferAttribute(a, 3));
        kantor.add(new Points(bintang, s.simpan(new PointsMaterial({ color: '#cfd8ff', size: 0.15 }))));
        const teks = kanvas(s, 128, 512, (g, w, h) => {
          g.fillStyle = '#14001f';
          g.fillRect(0, 0, w, h);
          g.fillStyle = '#ff3df2';
          g.shadowColor = '#ff3df2';
          g.shadowBlur = 20;
          g.font = 'bold 76px Helvetica, Arial';
          g.textAlign = 'center';
          'AGEN'.split('').forEach((c, i) => g.fillText(c, w / 2, 95 + i * 115));
        }, { warna: true });
        pasang(s.simpan(new PlaneGeometry(1.4, 5.6)), s.simpan(new MeshBasicMaterial({ map: teks })), -7.9, Y - 4.2, 3.2).rotation.y = Math.PI / 2;
        for (let k = 0; k < 16; k++) {
          const h = 6 + r() * 20;
          const g = pasang(K.kotak(3, h, 3, 'neon'), K.bahan('#120a28', 'dinding'), -32 + k * 4.2, dasar + h / 2, -18 - r() * 8);
          g.add(garis(g.geometry, k % 2 ? '#3a1060' : '#0a3a66'));
        }
        return { gantiLuar: true, tinggi: FH * 3 + 0.65, lebar: 1.35, zoomJauh: 0.6 };
      },
    });
  },
};
