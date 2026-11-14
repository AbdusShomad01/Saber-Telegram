/**
 * Alat bersama untuk semua gaya 3D: tipe `Kit` (pembangun bahan + geometri + lingkungan), geometri membulat, dan tekstur
 * kanvas (tanpa unduhan aset). Tiap gaya di src/gaya/<id>.ts memanggil `buatKit` dengan bagian yang mau diganti saja.
 */
import {
  BoxGeometry,
  BufferGeometry,
  CanvasTexture,
  CapsuleGeometry,
  Color,
  ConeGeometry,
  CylinderGeometry,
  LatheGeometry,
  MeshLambertMaterial,
  NearestFilter,
  RepeatWrapping,
  SRGBColorSpace,
  SphereGeometry,
  Vector2,
  Vector3,
  type Group,
  type Material,
  type Mesh,
  type MeshPhongMaterial,
  type MeshStandardMaterial,
  type Scene,
} from 'three';

/** Peran objek: gaya memakai ini untuk memilih bentuk dan bahan. */
export type Peran =
  | 'lantai' | 'garis' | 'karpet' | 'dinding' | 'kayu' | 'bingkai' | 'kaca' | 'papan' | 'catatan' | 'buku' | 'pot' | 'daun'
  | 'sofa' | 'kaki' | 'kursi' | 'meja' | 'layar' | 'logam' | 'kertas' | 'lampu' | 'baju' | 'celana' | 'kulit' | 'rambut'
  | 'tanah' | 'batang' | 'batu' | 'air' | 'awan' | 'alas' | 'jalan' | 'neon';

export type Bahan = MeshLambertMaterial | MeshStandardMaterial | MeshPhongMaterial;

export interface Pelacak {
  simpan<T extends { dispose(): void }>(x: T): T;
  buang(): void;
}
export const pelacak = (): Pelacak => {
  const list: { dispose(): void }[] = [];
  return {
    simpan: (x) => (list.push(x), x),
    buang: () => list.splice(0).forEach((x) => x.dispose()),
  };
};

/** Lingkungan pengganti (world building). `tinggi` = kantor diangkat (m), `lebar` = kamera mundur. */
export interface Dunia {
  tinggi?: number;
  lebar?: number;
  /** Pengali zoom untuk shot lebar sutradara (mis. 0.5 = lihat seluruh gedung). */
  zoomJauh?: number;
  /** true = rumput, pohon, dan jalan setapak bawaan tidak dibangun. */
  gantiLuar?: boolean;
  malam?(malam: boolean): void;
}
export interface KonteksDunia {
  scene: Scene;
  /** Grup kantor (koordinat lokal kantor: lantai di y 0, alas sampai y -0.65). */
  kantor: Group;
  K: Kit;
  pasang(g: BufferGeometry, m: Material, x: number, y: number, z: number, induk?: Scene | Group | Mesh): Mesh;
}

export interface Kit {
  warna(c: string, p: Peran): string;
  bahan(c: string, p: Peran, emissive?: string): Bahan;
  kotak(w: number, h: number, d: number, p: Peran): BufferGeometry;
  bola(r: number, p: Peran, kubah?: boolean): BufferGeometry;
  tabung(rt: number, rb: number, h: number, p: Peran): BufferGeometry;
  kerucut(r: number, h: number, p: Peran, terbuka?: boolean): BufferGeometry;
  kapsul(r: number, len: number, p: Peran): BufferGeometry;
  /** Tambahan setelah mesh dibuat (garis tepi, jahitan, dst.). */
  hias?(m: Mesh, p: Peran): void;
  agen: { kepala: number; badan: number };
  luar: { bentuk: 'kotak' | 'bulat'; ukuran: number; alas?: string; awan?: boolean };
  cahaya: { langit: string; bumi: string; kuat: number; matahari: string; mKuat: number };
  /** Warna kabut siang/malam, atau null. */
  kabut: [string, string] | null;
  /** Gaya yang selalu gelap (neon). */
  selaluMalam?: boolean;
  dunia?(c: KonteksDunia): Dunia;
  simpan<T extends { dispose(): void }>(x: T): T;
  dispose(): void;
}

export type BagianKit = Partial<Omit<Kit, 'simpan' | 'dispose' | 'agen' | 'luar' | 'cahaya'>> & {
  agen?: Partial<Kit['agen']>;
  luar?: Partial<Kit['luar']>;
  cahaya?: Partial<Kit['cahaya']>;
};

/** Kit lengkap dari bagian yang diganti; sisanya bentuk dan bahan gaya asli. */
export function buatKit(s: Pelacak, o: BagianKit = {}): Kit {
  const warna = o.warna ?? ((c: string) => c);
  const g = <T extends BufferGeometry>(x: T) => s.simpan(x);
  return {
    warna,
    bahan: (c, p, e) => {
      const cc = warna(c, p);
      const m = s.simpan(o.bahan ? o.bahan(cc, p, e) : new MeshLambertMaterial({ color: cc }));
      m.userData.peran = p;
      if (e) m.emissive.set(e);
      return m;
    },
    kotak: (w, h, d, p) => g(o.kotak ? o.kotak(w, h, d, p) : new BoxGeometry(w, h, d)),
    bola: (r, p, kubah) => g(o.bola ? o.bola(r, p, kubah) : kubah ? new SphereGeometry(r, 18, 14, 0, Math.PI * 2, 0, Math.PI / 1.8) : new SphereGeometry(r, 16, 12)),
    tabung: (rt, rb, h, p) => g(o.tabung ? o.tabung(rt, rb, h, p) : new CylinderGeometry(rt, rb, h, 12)),
    kerucut: (r, h, p, t) => g(o.kerucut ? o.kerucut(r, h, p, t) : new ConeGeometry(r, h, 12, 1, !!t)),
    kapsul: (r, len, p) => g(o.kapsul ? o.kapsul(r, len, p) : new CapsuleGeometry(r, len, 4, 12)),
    hias: o.hias,
    agen: { kepala: 1, badan: 1, ...o.agen },
    luar: { bentuk: 'kotak', ukuran: 60, ...o.luar },
    cahaya: { langit: '#fff6ea', bumi: '#a58b73', kuat: 1.5, matahari: '#ffe2b8', mKuat: 1.7, ...o.cahaya },
    kabut: o.kabut === undefined ? ['#f3e9de', '#120d22'] : o.kabut,
    selaluMalam: o.selaluMalam,
    dunia: o.dunia,
    simpan: s.simpan,
    dispose: s.buang,
  };
}

/* ---------- warna & acak ---------- */

export const campur = (a: string, b: string, t: number) => `#${new Color(a).lerp(new Color(b), t).getHexString()}`;
export const acak = (benih: number) => {
  let x = benih;
  return () => (x = (x * 16807) % 2147483647) / 2147483647;
};

/* ---------- tekstur kanvas ---------- */

export function kanvas(s: Pelacak, w: number, h: number, gambar: (g: CanvasRenderingContext2D, w: number, h: number) => void, o: { piksel?: boolean; warna?: boolean } = {}) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  gambar(c.getContext('2d')!, w, h);
  const t = s.simpan(new CanvasTexture(c));
  t.wrapS = t.wrapT = RepeatWrapping;
  if (o.warna) t.colorSpace = SRGBColorSpace;
  if (o.piksel) {
    t.magFilter = t.minFilter = NearestFilter;
    t.generateMipmaps = false;
  }
  return t;
}

/** UV kotak diskalakan ke ukuran asli (satuan meter per ulangan), supaya tekstur tidak melar di objek besar. */
export function skalaUV(g: BufferGeometry, w: number, h: number, d: number, satuan: number) {
  const uv = g.attributes.uv!;
  const per = uv.count / 6;
  const ukuran = [[d, h], [d, h], [w, d], [w, d], [w, h], [w, h]];
  for (let i = 0; i < uv.count; i++) {
    const [a, b] = ukuran[Math.floor(i / per)]!;
    uv.setXY(i, (uv.getX(i) * a!) / satuan, (uv.getY(i) * b!) / satuan);
  }
  return g;
}

/* ---------- geometri membulat ---------- */

const jepit = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));

/** Kotak bersudut bulat (radius r). */
export function kotakBulat(w: number, h: number, d: number, r: number, seg = 4) {
  r = Math.min(r, w / 2 - 0.001, h / 2 - 0.001, d / 2 - 0.001);
  if (r < 0.004) return new BoxGeometry(w, h, d);
  const g = new BoxGeometry(w, h, d, seg, seg, seg);
  const p = g.attributes.position!;
  const n = g.attributes.normal!;
  const v = new Vector3();
  const c = new Vector3();
  const ix = w / 2 - r, iy = h / 2 - r, iz = d / 2 - r;
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    c.set(jepit(v.x, -ix, ix), jepit(v.y, -iy, iy), jepit(v.z, -iz, iz));
    v.sub(c);
    if (v.lengthSq() < 1e-12) continue;
    v.normalize();
    n.setXYZ(i, v.x, v.y, v.z);
    v.multiplyScalar(r).add(c);
    p.setXYZ(i, v.x, v.y, v.z);
  }
  return g;
}

/** Tabung dengan tepi membulat (bubut). */
export function tabungBulat(rt: number, rb: number, h: number, r: number, seg = 18) {
  r = Math.min(r, rt * 0.9, rb * 0.9, h / 2 - 0.001);
  if (r < 0.004) return new CylinderGeometry(rt, rb, h, seg);
  const pts = [new Vector2(0, -h / 2)];
  for (let i = 0; i <= 4; i++) {
    const a = -Math.PI / 2 + (i / 4) * (Math.PI / 2);
    pts.push(new Vector2(rb - r + Math.cos(a) * r, -h / 2 + r + Math.sin(a) * r));
  }
  for (let i = 0; i <= 4; i++) {
    const a = (i / 4) * (Math.PI / 2);
    pts.push(new Vector2(rt - r + Math.cos(a) * r, h / 2 - r + Math.sin(a) * r));
  }
  pts.push(new Vector2(0, h / 2));
  const g = new LatheGeometry(pts, seg);
  g.computeVertexNormals();
  return g;
}

/** Tekstur papan nama (teks di tengah). */
export function papanNama(s: Pelacak, teks: string, latar: string, tinta: string, font = 'bold 64px Georgia') {
  return kanvas(
    s,
    512,
    128,
    (g, w, h) => {
      g.fillStyle = latar;
      g.fillRect(0, 0, w, h);
      g.fillStyle = tinta;
      g.font = font;
      g.textAlign = 'center';
      g.textBaseline = 'middle';
      g.fillText(teks, w / 2, h / 2 + 4, w - 40);
    },
    { warna: true },
  );
}
