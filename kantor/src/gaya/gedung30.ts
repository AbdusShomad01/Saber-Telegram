/**
 * Paduan: voxel + gedung 30 lantai. Kantor ada di lantai 13 (dibuka depan/cutaway), dua lantai di bawahnya juga terbuka
 * dengan meja siluet; lantai lain berjendela piksel. Atap ber-helipad, jalan dan mobil kotak di bawah.
 */
import { BoxGeometry, MeshBasicMaterial, MeshLambertMaterial, NearestFilter } from 'three';
import { acak, buatKit, kanvas, papanNama, pelacak } from './alat';
import { bagianVoxel } from './voxel';
import type { PembangunGaya } from './tipe';

const FH = 3.6;
const LANTAI = 30;
const KANTOR_DI = 12; // indeks lantai (0 = dasar)

export const gedung30: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    const r = acak(31);
    return buatKit(s, {
      ...bagianVoxel(s),
      kabut: null,
      dunia: ({ K, pasang }) => {
        const tinggi = 0.95 + KANTOR_DI * FH; // lantai 13 tepat di bawah alas kantor (y -0.65)
        const Y0 = -tinggi; // tanah, koordinat lokal kantor
        const X0 = -7.6, X1 = 7.6, Z0 = -10, Z1 = 3.6; // tapak gedung
        const BW = X1 - X0, BD = Z1 - Z0, CX = (X0 + X1) / 2, CZ = (Z0 + Z1) / 2;
        const bx = (w: number, h: number, d: number, c: string, x: number, y: number, z: number) => pasang(K.kotak(w, h, d, 'dinding'), K.bahan(c, 'dinding'), x, y, z);
        const jendela: MeshLambertMaterial[] = [];
        const muka = (kol: number, nyala: number) => {
          const t = kanvas(s, kol * 4, 4, (g) => {
            for (let c = 0; c < kol; c++) {
              g.fillStyle = '#3a4a6a';
              g.fillRect(c * 4, 0, 4, 4);
              g.fillStyle = r() < nyala ? (r() < 0.5 ? '#ffe27a' : '#fff2b8') : r() < 0.5 ? '#6f8fc0' : '#8fb4e0';
              g.fillRect(c * 4 + 1, 0, 3, 3);
            }
          }, { piksel: true, warna: true });
          t.magFilter = NearestFilter;
          const m = s.simpan(new MeshLambertMaterial({ map: t, emissive: '#ffffff', emissiveMap: t, emissiveIntensity: 0.15 }));
          jendela.push(m);
          return m;
        };
        const atapM = K.bahan('#555555', 'logam');
        const pelat = (y: number, merah: boolean, x0 = X0, x1 = X1, z0 = Z0, z1 = Z1) => bx(x1 - x0 + 0.4, 0.4, z1 - z0 + 0.4, merah ? '#e05a4a' : '#e8e8e8', (x0 + x1) / 2, y + 0.2, (z0 + z1) / 2);
        const blok = (y: number, x0: number, x1: number, z0: number, z1: number, nyala: number) => {
          const w = x1 - x0 - 0.4, d = z1 - z0 - 0.4;
          const mx = muka(Math.max(2, Math.round(w / 1)), nyala), mz = muka(Math.max(2, Math.round(d / 1)), nyala);
          const g = s.simpan(new BoxGeometry(w, FH - 0.4, d));
          pasang(g, [mz, mz, atapM, atapM, mx, mx] as never, (x0 + x1) / 2, y + FH / 2 + 0.2, (z0 + z1) / 2);
        };
        const meja = K.bahan('#b8682c', 'meja');
        const layar = s.simpan(new MeshBasicMaterial({ color: '#5fd3ff' }));
        for (let f = 0; f < LANTAI; f++) {
          const y = Y0 + 0.3 + f * FH; // bawah lantai f
          if (f === KANTOR_DI) {
            // lantai kantor: hanya bagian di belakang dinding kantor (kantor sendiri sudah dibangun)
            pelat(y, false, X0, X1, Z0, -3.7);
            blok(y, X0, X1, Z0, -3.75, 0.6);
            bx(BW, 0.25, 0.25, '#ffd400', CX, -0.78, 3.55);
            continue;
          }
          pelat(y, f % 5 === 4);
          for (const [x, z] of [[X0, Z0], [X1, Z0], [X0, Z1], [X1, Z1]]) bx(0.7, FH, 0.7, '#f4f4f4', x!, y + FH / 2, z!);
          if (f === KANTOR_DI - 1 || f === KANTOR_DI - 2) {
            // lantai terbuka: dinding belakang kuning, meja siluet
            bx(BW, FH - 0.4, 0.2, '#ffd400', CX, y + FH / 2 + 0.2, Z0 + 3);
            bx(0.2, FH - 0.4, BD - 3, '#f4f4f4', X0 + 0.1, y + FH / 2 + 0.2, CZ + 1.5);
            blok(y, X0, X1, Z0, Z0 + 2.9, 0.5);
            for (const x of [-5, -1.5, 2, 5.5])
              for (const z of [-4.5, -0.5]) {
                pasang(K.kotak(1.6, 0.1, 0.8, 'meja'), meja, x, y + 1.1, z);
                pasang(K.kotak(0.7, 0.45, 0.06, 'layar'), layar, x, y + 1.55, z - 0.3);
                pasang(K.kotak(0.45, 0.8, 0.35, 'baju'), K.bahan(['#ff3b30', '#2e86ff', '#2ecc40', '#ffd400'][(x + 7) % 4 | 0]!, 'baju'), x, y + 1.0, z + 0.7);
              }
            continue;
          }
          if (f > KANTOR_DI) {
            // di atas kantor: depan dipotong supaya kantor terlihat (cutaway bertingkat)
            blok(y, X0, X1, Z0, -3.7, 0.25 + r() * 0.35);
            continue;
          }
          blok(y, X0, X1, Z0, Z1, f === 0 ? 0 : 0.25 + r() * 0.35);
        }
        const puncak = Y0 + 0.3 + LANTAI * FH;
        bx(BW + 0.6, 0.6, 6.6, '#555555', CX, puncak + 0.3, (Z0 - 3.7) / 2);
        const hp = kanvas(s, 64, 64, (g) => {
          g.fillStyle = '#2b2b30';
          g.fillRect(0, 0, 64, 64);
          g.fillStyle = '#ffd400';
          g.fillRect(4, 4, 56, 3);
          g.fillRect(4, 57, 56, 3);
          g.fillRect(4, 4, 3, 56);
          g.fillRect(57, 4, 3, 56);
          g.fillStyle = '#fff';
          g.fillRect(20, 16, 6, 32);
          g.fillRect(38, 16, 6, 32);
          g.fillRect(20, 29, 24, 6);
        }, { piksel: true, warna: true });
        pasang(s.simpan(new BoxGeometry(5, 0.3, 5)), s.simpan(new MeshLambertMaterial({ map: hp })), CX + 2, puncak + 0.75, (Z0 - 3.7) / 2);
        bx(0.4, 5, 0.4, '#888888', X0 + 1.5, puncak + 3, Z0 + 1.5);
        pasang(K.kotak(0.6, 0.6, 0.6, 'lampu'), s.simpan(new MeshBasicMaterial({ color: '#ff2a2a' })), X0 + 1.5, puncak + 5.7, Z0 + 1.5);
        // tanah, jalan, lobi, mobil, pohon
        pasang(K.kotak(80, 1, 80, 'tanah'), K.bahan('#5fbf4a', 'tanah'), 0, Y0 - 0.5, 0);
        pasang(K.kotak(80, 0.06, 5, 'jalan'), K.bahan('#4a4a52', 'jalan'), 0, Y0 + 0.03, Z1 + 6);
        pasang(K.kotak(80, 0.25, 2.6, 'jalan'), K.bahan('#cfcfcf', 'jalan'), 0, Y0 + 0.12, Z1 + 2.2);
        pasang(K.kotak(3, 2.6, 0.2, 'kaca'), K.bahan('#9fd8ff', 'kaca'), CX, Y0 + 1.6, Z1 + 0.05);
        pasang(s.simpan(new BoxGeometry(6, 1.2, 0.05)), s.simpan(new MeshBasicMaterial({ map: papanNama(s, 'AI TOWER', '#222222', '#ffd400', 'bold 64px "Courier New", monospace') })), CX, Y0 + 3.75, Z1 + 0.3);
        for (const [x, c] of [[-12, '#ff3b30'], [4, '#2e86ff'], [-20, '#ffd400'], [16, '#ffffff']] as const) {
          pasang(K.kotak(2.2, 0.7, 1.1, 'logam'), K.bahan(c, 'logam'), x, Y0 + 0.55, Z1 + 6);
          pasang(K.kotak(1.2, 0.55, 1, 'kaca'), K.bahan('#cfefff', 'kaca'), x - 0.1, Y0 + 1.15, Z1 + 6);
        }
        for (const [x, z] of [[-11, 1], [11, -2], [-12, -9], [12, -12], [-16, 6]]) {
          pasang(K.kotak(0.4, 1, 0.4, 'batang'), K.bahan('#7a4a22', 'batang'), x!, Y0 + 0.5, z!);
          pasang(K.kotak(1.4, 1.2, 1.4, 'daun'), K.bahan('#2ecc40', 'daun'), x!, Y0 + 1.6, z!);
        }
        return {
          gantiLuar: true,
          tinggi,
          lebar: 1.5,
          zoomJauh: 0.35,
          malam: (m) => jendela.forEach((j) => (j.emissiveIntensity = m ? 0.9 : 0.15)),
        };
      },
    });
  },
};
