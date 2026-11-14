/**
 * Paduan: Hologram Blueprint Malam (acuan hero laman AI Agent). Malam biru-hitam, lantai grid cyan bercahaya, dinding kaca
 * tipis berangka, meja & agen low-poly gelap bertepi garis cyan, monitor menyala, Mission Board hologram kuning,
 * partikel data mengalir dari meja ke board.
 */
import {
  AdditiveBlending,
  BufferGeometry,
  Color,
  DoubleSide,
  EdgesGeometry,
  Float32BufferAttribute,
  GridHelper,
  LineBasicMaterial,
  LineSegments,
  MeshBasicMaterial,
  MeshLambertMaterial,
  PlaneGeometry,
  Points,
  PointsMaterial,
  Vector3,
  type Mesh,
} from 'three';
import { acak, buatKit, pelacak } from './alat';
import type { PembangunGaya } from './tipe';

const CYAN = '#22d3ee';
const AMBER = '#fbbf24';
const GELAP = '#07111f';
/** Peran bertepi garis cahaya. */
const TEPI = ['alas', 'meja', 'kursi', 'sofa', 'baju', 'celana', 'kulit', 'rambut', 'dinding', 'bingkai', 'kaki', 'pot', 'buku', 'logam'];
/** Peran yang tetap menyala (bukan dibuat gelap). */
const TERANG = ['layar', 'lampu', 'catatan', 'neon'];

export const hologram: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    const r = acak(41);
    const tepi = s.simpan(new LineBasicMaterial({ color: CYAN, transparent: true, opacity: 0.75 }));
    const tepiAmber = s.simpan(new LineBasicMaterial({ color: AMBER }));
    return buatKit(s, {
      selaluMalam: true,
      warna: (c, p) => (p === 'lantai' || p === 'karpet' ? '#041022' : p === 'garis' ? '#0b2a3a' : c),
      bahan: (c, p) => {
        if (p === 'kaca' || p === 'dinding')
          return new MeshLambertMaterial({ color: '#0e7490', transparent: true, opacity: p === 'kaca' ? 0.08 : 0.12, side: DoubleSide, depthWrite: false });
        if (p === 'papan') return new MeshLambertMaterial({ color: '#3a2a06', emissive: '#3a2a06', transparent: true, opacity: 0.55, side: DoubleSide, depthWrite: false });
        if (p === 'catatan') return new MeshLambertMaterial({ color: AMBER, emissive: AMBER });
        if (p === 'lantai' || p === 'garis' || p === 'karpet') return new MeshLambertMaterial({ color: '#041022', emissive: '#020812' });
        if (TERANG.includes(p)) return new MeshLambertMaterial({ color: new Color(c).multiplyScalar(0.5), emissive: c });
        // Semua benda lain: low-poly gelap kebiruan, sedikit beda nada dari warna aslinya.
        return new MeshLambertMaterial({ color: new Color(GELAP).lerp(new Color(c), p === 'kulit' || p === 'baju' ? 0.22 : 0.1), emissive: '#030a16' });
      },
      hias: (m, p) => {
        if (p === 'catatan') {
          const b = m.material as MeshLambertMaterial;
          b.color.set(AMBER);
          b.emissive.set(AMBER);
          b.emissiveIntensity = 0.6;
          return void m.scale.set(1.1, 0.35, 1);
        }
        if (p === 'papan') return void m.add(new LineSegments(s.simpan(new EdgesGeometry(m.geometry)), tepiAmber));
        if (!TEPI.includes(p)) return;
        m.add(new LineSegments(s.simpan(new EdgesGeometry(m.geometry, 30)), tepi));
      },
      agen: { kepala: 1, badan: 1 },
      cahaya: { langit: '#6b8cff', bumi: '#03060d', kuat: 1.1, matahari: '#9be7ff', mKuat: 0.7 },
      kabut: ['#03060d', '#03060d'],
      dunia: ({ kantor, K, pasang }) => {
        const Y = -0.65;
        // Lantai grid cyan di dalam kantor + grid luas redup di luar.
        const kisi = new GridHelper(15, 30, CYAN, '#0e4a5e');
        kisi.position.set(-0.3, 0.03, -0.2);
        const luas = new GridHelper(120, 60, '#0b3a4a', '#0a2233');
        luas.position.y = Y - 0.02;
        kantor.add(kisi, luas);
        for (const g of [kisi, luas]) {
          (g.material as LineBasicMaterial).transparent = true;
          (g.material as LineBasicMaterial).opacity = g === kisi ? 0.6 : 0.5;
          s.simpan({ dispose: () => (g.geometry.dispose(), (g.material as LineBasicMaterial).dispose(), g.removeFromParent()) });
        }
        pasang(s.simpan(new PlaneGeometry(120, 120)), s.simpan(new MeshBasicMaterial({ color: '#02060d' })), 0, Y - 0.04, 0).rotation.x = -Math.PI / 2;
        // Partikel data: dari tiap meja (dicari saat render pertama) naik melengkung ke Mission Board.
        const N = 160;
        const geo = s.simpan(new BufferGeometry());
        const pos = new Float32Array(N * 3);
        geo.setAttribute('position', new Float32BufferAttribute(pos, 3));
        const titik = new Points(geo, s.simpan(new PointsMaterial({ color: '#a5f3fc', size: 0.09, transparent: true, opacity: 0.95, depthWrite: false, blending: AdditiveBlending })));
        titik.frustumCulled = false;
        kantor.add(titik);
        s.simpan({ dispose: () => titik.removeFromParent() });
        const board = new Vector3(0.1, 1.75, -3.3);
        const asal: Vector3[] = [];
        const fase = Array.from({ length: N }, () => r());
        const jalur = Array.from({ length: N }, () => r());
        const tmp = new Vector3();
        titik.onBeforeRender = () => {
          if (!asal.length) {
            kantor.traverse((o) => {
              const m = o as Mesh;
              if (m.isMesh && (m.material as { userData?: { peran?: string } }).userData?.peran === 'layar') asal.push(m.position.clone());
            });
            if (!asal.length) asal.push(new Vector3(-4, 1.1, 0), new Vector3(4, 1.1, 0));
          }
          const t = performance.now() / 1000;
          for (let i = 0; i < N; i++) {
            const a = asal[Math.floor(jalur[i]! * asal.length)]!;
            const u = (t * 0.22 + fase[i]!) % 1;
            tmp.lerpVectors(a, board, u);
            tmp.y += Math.sin(u * Math.PI) * 1.2;
            pos[i * 3] = tmp.x;
            pos[i * 3 + 1] = tmp.y;
            pos[i * 3 + 2] = tmp.z;
          }
          geo.attributes.position!.needsUpdate = true;
        };
        return { gantiLuar: true, lebar: 1.05 };
      },
    });
  },
};
