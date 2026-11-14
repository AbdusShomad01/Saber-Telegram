/**
 * Alat bersama tiga gaya kaki lima (angkringan, pecellele, bakso): tekstur kanvas buatan sendiri (tikar, terpal, kayu,
 * aspal, paving, papan kapur, spanduk lukis) dan perabot jalanan (gerobak, motor, sepeda, tiang listrik, bohlam, pohon).
 */
import {
  BufferGeometry,
  Group,
  HemisphereLight,
  Line,
  LineBasicMaterial,
  MeshBasicMaterial,
  MeshLambertMaterial,
  PlaneGeometry,
  PointLight,
  TorusGeometry,
  Vector3,
  DoubleSide,
  type Material,
  type Texture,
} from 'three';
import { kanvas, type KonteksDunia, type Pelacak } from './alat';

export const Y = -0.65;

export function tekstur(s: Pelacak, r: () => number) {
  const kuas = kanvas(s, 128, 128, (g, w, h) => {
    g.fillStyle = '#ececec';
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 180; i++) {
      g.globalAlpha = 0.06 + r() * 0.07;
      g.strokeStyle = r() > 0.5 ? '#ffffff' : '#6a5440';
      g.lineWidth = 2 + r() * 4;
      g.lineCap = 'round';
      const x = r() * w, y = r() * h;
      g.beginPath();
      g.moveTo(x, y);
      g.lineTo(x + 8 + r() * 18, y + r() * 6 - 3);
      g.stroke();
    }
  }, { warna: true });
  const tikar = kanvas(s, 128, 128, (g, w, h) => {
    for (let y = 0; y < 16; y++)
      for (let x = 0; x < 16; x++) {
        g.fillStyle = (x + y) % 2 ? '#e0bb72' : '#c99f55';
        g.fillRect(x * 8, y * 8, 8, 8);
        g.fillStyle = 'rgba(120,70,20,.35)';
        if ((x + y) % 2) g.fillRect(x * 8, y * 8 + 3, 8, 1);
        else g.fillRect(x * 8 + 3, y * 8, 1, 8);
      }
    g.fillStyle = '#a8342a';
    g.fillRect(0, 0, w, 5);
    g.fillRect(0, h - 5, w, 5);
  }, { warna: true });
  const terpal = (a: string, b: string) =>
    kanvas(s, 128, 128, (g, w, h) => {
      for (let i = 0; i < 8; i++) {
        g.fillStyle = i % 2 ? a : b;
        g.fillRect(i * 16, 0, 16, h);
      }
      for (let i = 0; i < 700; i++) {
        g.fillStyle = `rgba(0,0,0,${r() * 0.06})`;
        g.fillRect(r() * w, r() * h, 3, 1);
      }
    }, { warna: true });
  const kayu = (a: string, b: string) =>
    kanvas(s, 128, 128, (g, w, h) => {
      g.fillStyle = a;
      g.fillRect(0, 0, w, h);
      g.strokeStyle = b;
      g.globalAlpha = 0.5;
      for (let i = 0; i < 14; i++) {
        g.beginPath();
        g.moveTo(0, i * 9 + r() * 3);
        g.bezierCurveTo(40, i * 9 + r() * 6, 80, i * 9 - r() * 6, 128, i * 9);
        g.stroke();
      }
    }, { warna: true });
  const aspal = (dasar: string) =>
    kanvas(s, 256, 256, (g, w, h) => {
      g.fillStyle = dasar;
      g.fillRect(0, 0, w, h);
      for (let i = 0; i < 5000; i++) {
        const v = r() > 0.5 ? 255 : 0;
        g.fillStyle = `rgba(${v},${v},${v},${r() * 0.08})`;
        g.fillRect(r() * w, r() * h, 2, 2);
      }
    }, { warna: true });
  const paving = (cs: string[]) =>
    kanvas(s, 256, 256, (g) => {
      g.fillStyle = '#00000033';
      g.fillRect(0, 0, 256, 256);
      for (let y = 0; y < 8; y++)
        for (let x = -1; x < 8; x++) {
          g.fillStyle = cs[(x * 3 + y * 5 + 24) % cs.length]!;
          g.fillRect(x * 32 + (y % 2) * 16 + 1, y * 32 + 1, 30, 30);
        }
    }, { warna: true });
  return { kuas, tikar, terpal, kayu, aspal, paving };
}

/** Tekstur papan kapur Mission Board (judul + garis, tanpa butir: butir tetap kertas tempel dari template). */
export const papanKapur = (s: Pelacak, r: () => number, judul: string) =>
  kanvas(s, 512, 256, (g, w, h) => {
    g.fillStyle = '#24382c';
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 260; i++) {
      g.fillStyle = `rgba(255,255,255,${r() * 0.05})`;
      g.fillRect(r() * w, r() * h, 20, 2);
    }
    g.fillStyle = '#f6f1e0';
    g.font = 'bold 34px "Comic Sans MS", cursive';
    g.fillText(judul, 20, 40);
    g.fillRect(20, 50, w - 40, 3);
  }, { warna: true });

/** Spanduk lukis (latar, garis tepi, beberapa baris teks besar). */
export const spanduk = (s: Pelacak, baris: { t: string; c: string; f: string }[], latar: string, tepi: string, w = 1024, h = 256) =>
  kanvas(s, w, h, (g) => {
    g.fillStyle = latar;
    g.fillRect(0, 0, w, h);
    g.strokeStyle = tepi;
    g.lineWidth = 10;
    g.strokeRect(10, 10, w - 20, h - 20);
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    baris.forEach((b, i) => {
      g.fillStyle = b.c;
      g.font = b.f;
      g.fillText(b.t, w / 2, (h / (baris.length + 1)) * (i + 1), w - 60);
    });
  }, { warna: true });

/** Perabot jalanan; semua dipasang ke grup kantor (koordinat lokal kantor). */
export function perabot(s: Pelacak, c: KonteksDunia, kuas: Texture, malam: boolean) {
  const { K, pasang, kantor } = c;
  let induk: Group = kantor;
  const cache = new Map<string, Material>();
  const M = (w: string, o: { map?: Texture; em?: string; basic?: boolean; op?: number } = {}) => {
    const k = `${w}|${o.map?.uuid ?? ''}|${o.em ?? ''}|${o.basic ? 1 : 0}|${o.op ?? 1}`;
    if (!cache.has(k))
      cache.set(
        k,
        s.simpan(
          o.basic
            ? new MeshBasicMaterial({ color: w, map: o.map ?? null, transparent: !!o.op, opacity: o.op ?? 1, side: DoubleSide })
            : new MeshLambertMaterial({ color: w, map: o.map ?? kuas, emissive: o.em ?? (malam ? '#0a0604' : '#000000'), transparent: !!o.op, opacity: o.op ?? 1 }),
        ),
      );
    return cache.get(k)!;
  };
  const mat = (w: string | Material, o?: Parameters<typeof M>[1]) => (typeof w === 'string' ? M(w, o) : w);
  const B = (w: number, h: number, d: number, col: string | Material, x: number, y: number, z: number, o?: Parameters<typeof M>[1]) => pasang(K.kotak(w, h, d, 'kayu'), mat(col, o), x, y, z, induk);
  const T = (a: number, b: number, h: number, col: string | Material, x: number, y: number, z: number, o?: Parameters<typeof M>[1]) => pasang(K.tabung(a, b, h, 'logam'), mat(col, o), x, y, z, induk);
  const S = (rr: number, col: string | Material, x: number, y: number, z: number, o?: Parameters<typeof M>[1]) => pasang(K.bola(rr, 'daun'), mat(col, o), x, y, z, induk);
  const P = (w: number, h: number, map: Texture, x: number, y: number, z: number, ry = 0, basic = true) => {
    const m = pasang(s.simpan(new PlaneGeometry(w, h)), s.simpan(basic ? new MeshBasicMaterial({ map, side: DoubleSide }) : new MeshLambertMaterial({ map, side: DoubleSide })), x, y, z, induk);
    m.rotation.y = ry;
    return m;
  };
  const grup = (x: number, z: number, ry: number, f: () => void, y = Y) => {
    const g = new Group();
    g.position.set(x, y, z);
    g.rotation.y = ry;
    induk.add(g);
    const lama = induk;
    induk = g;
    f();
    induk = lama;
    return g;
  };
  const roda = (rr: number, tebal: number, x: number, y: number, z: number) => {
    const m = pasang(s.simpan(new TorusGeometry(rr, tebal, 8, 18)), M('#1a1a1a'), x, y, z, induk);
    m.rotation.y = Math.PI / 2;
    return m;
  };
  const garisKabel = s.simpan(new LineBasicMaterial({ color: '#111111' }));
  const lampu: PointLight[] = [];
  const cahaya = (x: number, y: number, z: number, w: string, i: number, d = 10) => {
    const l = new PointLight(w, i, d, 1.2);
    l.position.set(x, y, z);
    kantor.add(l);
    s.simpan({ dispose: () => l.removeFromParent() });
    lampu.push(l);
    return l;
  };
  /** Cahaya langit tambahan supaya adegan malam tetap terbaca. */
  const terang = (langit: string, bumi: string, i: number) => {
    const h = new HemisphereLight(langit, bumi, i);
    kantor.add(h);
    s.simpan({ dispose: () => h.removeFromParent() });
    return h;
  };
  const bohlam = (x: number, y: number, z: number, w = '#ffd27a', i = 6, d = 9) => {
    T(0.01, 0.01, 0.6, '#111', x, y + 0.3, z);
    S(0.14, w, x, y, z, { basic: true });
    cahaya(x, y - 0.15, z, w, i, d);
  };
  const motor = (x: number, z: number, ry: number, w: string) =>
    grup(x, z, ry, () => {
      for (const a of [-0.65, 0.65]) roda(0.26, 0.09, a, 0.33, 0);
      B(1.2, 0.25, 0.3, w, 0, 0.6, 0);
      B(0.6, 0.18, 0.34, '#1d1d1d', -0.15, 0.82, 0);
      B(0.25, 0.6, 0.3, w, 0.55, 0.75, 0);
      T(0.03, 0.03, 0.7, '#888', 0.62, 1.1, 0).rotation.x = Math.PI / 2;
      S(0.09, '#fff6c0', 0.72, 0.95, 0, { em: '#ffe080' });
    });
  const sepeda = (x: number, z: number, ry: number, w: string) =>
    grup(x, z, ry, () => {
      for (const a of [-0.5, 0.5]) roda(0.32, 0.03, a, 0.35, 0);
      B(1, 0.05, 0.05, w, 0, 0.55, 0);
      B(0.05, 0.45, 0.05, w, -0.15, 0.65, 0);
      B(0.25, 0.06, 0.12, '#222', -0.15, 0.9, 0);
      B(0.05, 0.4, 0.05, w, 0.4, 0.7, 0);
      B(0.05, 0.05, 0.45, '#555', 0.42, 0.92, 0);
    });
  const tiang = (x: number, z: number, h = 7.5) => {
    T(0.13, 0.17, h, '#7d8085', x, Y + h / 2, z);
    B(1.8, 0.1, 0.1, '#5d6065', x, Y + h - 0.6, z);
    B(0.4, 0.6, 0.35, '#a6a9ae', x + 0.25, Y + h - 1.4, z);
    return new Vector3(x, Y + h - 0.55, z);
  };
  const kabel = (a: Vector3, b: Vector3, kendur = 1) => {
    const pts: Vector3[] = [];
    for (let i = 0; i <= 20; i++) {
      const t = i / 20;
      pts.push(new Vector3().lerpVectors(a, b, t).add(new Vector3(0, -kendur * 4 * t * (1 - t), 0)));
    }
    const l = new Line(s.simpan(new BufferGeometry().setFromPoints(pts)), garisKabel);
    kantor.add(l);
    s.simpan({ dispose: () => l.removeFromParent() });
  };
  const pohon = (x: number, z: number, k = 1, r = Math.random) =>
    grup(x, z, 0, () => {
      T(0.2 * k, 0.32 * k, 2.8 * k, '#6a4528', 0, 1.4 * k, 0);
      for (let i = 0; i < 6; i++) S((1 + r() * 0.5) * k, ['#3f8a3a', '#4f9e42', '#6aaa48'][i % 3]!, (r() - 0.5) * 1.8 * k, (2.9 + r() * 1.1) * k, (r() - 0.5) * 1.8 * k);
    });
  const bangkuPlastik = (x: number, z: number, w: string) =>
    grup(x, z, 0, () => {
      T(0.22, 0.19, 0.05, w, 0, 0.47, 0);
      for (const [a, b] of [[-0.14, -0.14], [0.14, -0.14], [-0.14, 0.14], [0.14, 0.14]] as const) T(0.03, 0.04, 0.46, w, a, 0.23, b);
    });
  const teko = (x: number, y: number, z: number, w = '#c9c3b5') => {
    T(0.16, 0.2, 0.3, w, x, y + 0.15, z);
    T(0.03, 0.04, 0.26, w, x + 0.22, y + 0.2, z).rotation.z = -0.9;
  };
  const gelas = (x: number, y: number, z: number, w = '#d6a04a') => T(0.07, 0.06, 0.18, w, x, y + 0.09, z);
  return { M, B, T, S, P, grup, roda, cahaya, terang, bohlam, motor, sepeda, tiang, kabel, pohon, bangkuPlastik, teko, gelas, lampu };
}

/** Lantai jalan (aspal tidak dominan: hanya pita di depan) + trotoar paving di sekeliling kantor. */
export function tanahJalan(c: KonteksDunia, P: ReturnType<typeof perabot>, aspal: Texture, paving: Texture, dasar: string, marka: string) {
  aspal.repeat.set(10, 1.2);
  paving.repeat.set(14, 9);
  P.B(46, 0.2, 34, P.M('#ffffff', { map: paving }), 0, Y - 0.1, -2);
  P.B(46, 0.06, 5, P.M('#ffffff', { map: aspal }), 0, Y + 0.03, 8.2);
  for (let k = -9; k < 10; k++) P.B(1.4, 0.02, 0.16, P.M(marka, { basic: true }), k * 2.6, Y + 0.07, 8.2);
  for (let k = -22; k < 23; k++) P.B(1, 0.22, 0.25, k % 2 ? '#f0f0f0' : dasar, k, Y + 0.08, 5.6);
  void c;
}

/** Bahan kantor yang diganti per peran (lantai jadi tikar/paving, dinding jadi papan/terpal, Mission Board jadi papan kapur). */
export function bahanKakiLima(s: Pelacak, kuas: Texture, peta: Partial<Record<string, Texture>>, malam: boolean) {
  return (w: string, p: string): MeshLambertMaterial => {
    const map = peta[p];
    if (p === 'kaca') return new MeshLambertMaterial({ color: malam ? '#ffcf7a' : '#cfe9ff', emissive: malam ? '#7a4a14' : '#203040' });
    if (p === 'lampu' || p === 'layar' || p === 'catatan' || p === 'neon') return new MeshLambertMaterial({ color: w, map: kuas });
    return new MeshLambertMaterial({ color: map ? '#ffffff' : w, map: map ?? kuas, emissive: malam ? '#140c06' : '#000000' });
  };
}
/** Warna tetap putih untuk peran bertekstur (supaya warna malam template tidak menggelapkan tikar/paving). */
export const warnaKakiLima = (peta: Partial<Record<string, unknown>>) => (w: string, p: string) => (peta[p] ? '#ffffff' : w);
