/** Data gaya untuk pemilih & README (tanpa three.js, jadi ringan dimuat di App). Pembangunnya ada di src/gaya/<id>.ts. */
import type { InfoGaya } from './tipe';

export const DAFTAR_GAYA = [
  {
    id: 'asli',
    nama: 'Asli',
    jenis: 'asli',
    ket: 'Gaya bawaan: bentuk sederhana, warna hangat, paling ringan.',
  },
  {
    id: 'clay',
    nama: 'Clay',
    jenis: 'menyeluruh',
    ket: 'Plastisin: sudut membulat tebal, bekas jari, warna pastel.',
    latar: { siang: 'radial-gradient(130% 90% at 50% 15%, #fff6ea 0%, #efe3cf 60%, #e2cdb2 100%)', malam: '' },
  },
  {
    id: 'felt',
    nama: 'Felt',
    jenis: 'menyeluruh',
    ket: 'Kain flanel/wol: serat halus, warna lembut, jahitan di tepi.',
    latar: { siang: 'radial-gradient(130% 90% at 50% 15%, #f5ecdc 0%, #e7ddcc 60%, #d6c7ae 100%)', malam: '' },
  },
  {
    id: 'voxel',
    nama: 'Voxel',
    jenis: 'menyeluruh',
    ket: 'Semua objek jadi balok piksel ala gim kotak-kotak.',
    latar: { siang: 'linear-gradient(#7fc6ff 0 40%, #a9dbff 40% 70%, #cfeeff 70%)', malam: 'linear-gradient(#060b24, #142250)' },
  },
  {
    id: 'vinyl',
    nama: 'Vinyl (chibi)',
    jenis: 'menyeluruh',
    ket: 'Mainan vinyl mengilap: kepala besar, sudut bulat, warna permen.',
    latar: { siang: 'linear-gradient(160deg, #ffd6e8, #d8e6ff 55%, #d6fff1)', malam: 'linear-gradient(160deg, #3a1a40, #141a3a 55%, #0e2a2a)' },
  },
  {
    id: 'diorama',
    nama: 'Diorama',
    jenis: 'menyeluruh',
    ket: 'Miniatur meja: kayu, kain, rumput asli, alas kayu, kabur tilt-shift.',
    latar: { siang: 'radial-gradient(circle at 50% 40%, #5a4330, #1e140c 75%)', malam: 'radial-gradient(circle at 50% 40%, #2a2030, #0a0608 75%)' },
    tiltShift: true,
  },
  {
    id: 'kayu',
    nama: 'Balok kayu',
    jenis: 'menyeluruh',
    ket: 'Mainan balok kayu: serat kayu, cat pudar, agen boneka pasak.',
    latar: { siang: 'radial-gradient(130% 90% at 50% 15%, #f6ecdc 0%, #ede2cf 60%, #dccaa8 100%)', malam: '' },
  },
  {
    id: 'stickman',
    nama: 'Stickman',
    jenis: 'menyeluruh',
    ket: 'Gambar garis 3D: dunia putih bergaris tinta, agen batang tipis.',
    latar: { siang: '#f6f6f4', malam: 'radial-gradient(130% 90% at 50% 15%, #2a2a30 0%, #121216 100%)' },
  },
  {
    id: 'pulau',
    nama: 'Pulau melayang',
    jenis: 'paduan',
    ket: 'Clay + kantor di atas pulau melayang, laut pastel, awan.',
    latar: { siang: 'linear-gradient(#bfe6ff, #ffe1ee)', malam: 'linear-gradient(#141a40, #3a2050)' },
  },
  {
    id: 'toko',
    nama: 'Toko di trotoar',
    jenis: 'paduan',
    ket: 'Lukisan tangan + kantor jadi toko di pinggir jalan, papan nama, lampu jalan.',
    latar: { siang: 'linear-gradient(#f6c58a, #f3e2c0)', malam: 'linear-gradient(#1a1430, #3a2440)' },
  },
  {
    id: 'menara',
    nama: 'Menara neon',
    jenis: 'paduan',
    ket: 'Neon malam + kantor di puncak bangunan bertumpuk, tangga zigzag, papan AGEN.',
    latar: { siang: 'radial-gradient(130% 90% at 50% 20%, #1a0b33 0%, #05030f 70%)', malam: 'radial-gradient(130% 90% at 50% 20%, #1a0b33 0%, #05030f 70%)' },
    malam: true,
  },
  {
    id: 'taman',
    nama: 'Paviliun taman',
    jenis: 'paduan',
    ket: 'Low-poly + kantor jadi paviliun di taman: kolam, jembatan, pergola, cemara.',
    latar: { siang: 'linear-gradient(#cfe8e4, #eef6e8)', malam: 'linear-gradient(#0e1a2a, #1a2a30)' },
  },
  {
    id: 'gedung30',
    nama: 'Gedung 30 lantai',
    jenis: 'paduan',
    ket: 'Voxel + kantor di lantai 13 gedung 30 lantai, beberapa lantai dibuka (cutaway).',
    latar: { siang: 'linear-gradient(#5b6fc8, #ffb47a)', malam: 'linear-gradient(#0a0f2a, #2a1a40)' },
  },
  {
    id: 'hologram',
    nama: 'Hologram malam',
    jenis: 'paduan',
    ket: 'Blueprint malam: lantai grid cyan, dinding kaca, tepi garis cahaya, Mission Board hologram, partikel data.',
    latar: { siang: 'radial-gradient(130% 90% at 50% 20%, #0a1a33 0%, #03060d 70%)', malam: 'radial-gradient(130% 90% at 50% 20%, #0a1a33 0%, #03060d 70%)' },
    malam: true,
  },
  {
    id: 'angkringan',
    nama: 'Angkringan Malam',
    jenis: 'paduan',
    ket: 'Kaki lima malam: tikar lesehan, gerobak beratap terpal, tungku arang & ceret, untaian bohlam kuning, motor parkir.',
    latar: { siang: 'linear-gradient(#141a33, #2a2030)', malam: 'linear-gradient(#141a33, #2a2030)' },
    malam: true,
  },
  {
    id: 'pecellele',
    nama: 'Warung Tenda Pecel Lele',
    jenis: 'paduan',
    ket: 'Tenda terpal dengan spanduk lukis, meja panjang & bangku plastik, gerobak penggorengan, lampu neon, kabel semrawut.',
    latar: { siang: 'linear-gradient(#1d2440, #3a2a40)', malam: 'linear-gradient(#1d2440, #3a2a40)' },
    malam: true,
  },
  {
    id: 'bakso',
    nama: 'Gerobak Bakso & Es',
    jenis: 'paduan',
    ket: 'Siang di depan sekolah: gerobak bakso berkaca, gerobak es, payung pelangi, pohon peneduh, pagar sekolah, sepeda.',
    latar: { siang: 'linear-gradient(#9fdcff, #fff1d0)', malam: 'linear-gradient(#0e1a2a, #2a2a40)' },
  },
] as const satisfies readonly InfoGaya[];

export type GayaId = (typeof DAFTAR_GAYA)[number]['id'];

export const cariGaya = (id: string | null | undefined): InfoGaya => DAFTAR_GAYA.find((g) => g.id === id) ?? DAFTAR_GAYA[0];
export const adaGaya = (id: string | null | undefined): id is GayaId => !!id && DAFTAR_GAYA.some((g) => g.id === id);

/** Urutan: ?gaya=<id> di URL, lalu pilihan terakhir (localStorage), lalu `GAYA` di config. */
export function gayaAwal(url: string | null, simpanan: string | null, bawaan: string): GayaId {
  if (adaGaya(url)) return url;
  if (adaGaya(simpanan)) return simpanan;
  return adaGaya(bawaan) ? bawaan : 'asli';
}

export const KUNCI_SIMPAN = 'kantor-ai-gaya';
