/** Paduan: clay + pulau melayang (kantor di atas pulau rumput bertebing tanah, laut pastel jauh di bawah, awan). */
import { ConeGeometry, CylinderGeometry, MeshStandardMaterial, PlaneGeometry, SphereGeometry } from 'three';
import { acak, buatKit, pelacak } from './alat';
import { bagianClay } from './clay';
import type { PembangunGaya } from './tipe';

export const pulau: PembangunGaya = {
  buat: () => {
    const s = pelacak();
    return buatKit(s, {
      ...bagianClay(s),
      kabut: null,
      dunia: ({ K, pasang }) => {
        const r = acak(11);
        const Y = -0.65;
        const rumput = K.bahan('#8fd06a', 'tanah');
        const tepi = K.bahan('#7cc35a', 'tanah');
        const tanah = K.bahan('#b0703f', 'tanah');
        const batu = K.bahan('#c9884f', 'batu');
        pasang(s.simpan(new CylinderGeometry(10.5, 10.5, 0.8, 40)), rumput, 0, Y - 0.4, 0);
        pasang(s.simpan(new CylinderGeometry(10.6, 10.3, 0.3, 40)), tepi, 0, Y - 0.9, 0);
        pasang(s.simpan(new ConeGeometry(10.3, 9, 12, 4)), tanah, 0, Y - 5.55, 0).rotation.x = Math.PI;
        for (let k = 0; k < 10; k++) {
          const a = k * 0.63, rr = 6 + r() * 2.5;
          pasang(s.simpan(new SphereGeometry(0.8 + r() * 0.6, 16, 12)), batu, Math.cos(a) * rr, Y - 2.2 - r() * 2, Math.sin(a) * rr);
        }
        const laut = pasang(s.simpan(new PlaneGeometry(240, 240)), s.simpan(new MeshStandardMaterial({ color: '#9fdcf0', roughness: 0.6 })), 0, -18, 0);
        laut.rotation.x = -Math.PI / 2;
        const batang = K.bahan('#b9764a', 'batang');
        const daun = [K.bahan('#5fbf6a', 'daun'), K.bahan('#8fd06a', 'daun'), K.bahan('#f6a5c0', 'daun')];
        const pohon = (x: number, z: number, sk: number, c: number, y = Y) => {
          pasang(K.tabung(0.14 * sk, 0.2 * sk, 1.1 * sk, 'batang'), batang, x, y + 0.55 * sk, z);
          pasang(K.bola(0.8 * sk, 'daun'), daun[c]!, x, y + 1.5 * sk, z);
          pasang(K.bola(0.55 * sk, 'daun'), daun[c]!, x + 0.45 * sk, y + 1.25 * sk, z + 0.3 * sk);
        };
        for (const [x, z, sk, c] of [[-8.6, -3, 1.3, 0], [-6, -6.8, 1.1, 2], [2.5, -8, 1.4, 1], [7.5, -5.5, 1.2, 0], [-9.2, 2.6, 1, 1]] as const) pohon(x, z, sk, c);
        for (const [x, z, c] of [[-4, 4.6, '#ff8fb1'], [-2.6, 4.9, '#fde74c'], [8.4, 1.6, '#b28dff']] as const) pasang(K.bola(0.26, 'daun'), K.bahan(c, 'daun'), x, Y + 0.25, z);
        const awan = s.simpan(new MeshStandardMaterial({ color: '#ffffff', roughness: 1, emissive: '#ffe6f0', emissiveIntensity: 0.3 }));
        for (const [x, y, z] of [[-16, 3, -10], [9, 5, -17], [-4, 7, -22], [17, -4, -4], [-18, -6, 6]]) for (let j = 0; j < 5; j++) pasang(s.simpan(new SphereGeometry(1 + r() * 0.9, 18, 12)), awan, x! + j * 1.2, y! + r() * 0.8, z! + r());
        for (const [x, y, z, sk] of [[-16, -4, -8, 2], [14, -7, -11, 1.5]]) {
          pasang(s.simpan(new CylinderGeometry(sk! * 1.5, sk! * 1.5, 0.4, 20)), rumput, x!, y!, z!);
          pasang(s.simpan(new ConeGeometry(sk! * 1.45, sk! * 2, 10)), tanah, x!, y! - sk! - 0.2, z!).rotation.x = Math.PI;
          pohon(x!, z!, sk! * 0.6, 0, y! + 0.2);
        }
        return { gantiLuar: true, lebar: 1.3, zoomJauh: 0.8 };
      },
    });
  },
};
