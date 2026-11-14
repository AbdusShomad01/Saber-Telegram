/**
 * ✏️ Saber Trader HQ — IDX AI Trading Operations
 * Visualisasi 3D Agen AI Saber Trader untuk memantau aktivitas bursa saham IDX.
 */

import laporanAgen from './laporan.json';
import type { GayaId } from './gaya/daftar';

export const KANTOR = {
  nama: 'Saber Trader HQ',
  /** Baris kecil di bawah nama (nama sistem). */
  subjudul: 'IDX AI Signal & Trading Operations',
};

/**
 * Gaya 3D kantor: 'asli' | 'clay' | 'felt' | 'voxel' | 'vinyl' | 'diorama' | 'kayu' |
 * 'stickman' | 'pulau' | 'toko' | 'menara' | 'taman' | 'gedung30' | 'hologram' | 'angkringan' | 'pecellele' | 'bakso'.
 */
export const GAYA: GayaId = 'hologram';
/** Tombol pemilih gaya di pojok kanan bawah. */
export const TAMPIL_PEMILIH_GAYA = true;

/** Tiga ruangan dari kiri ke kanan. */
export const RUANGAN = [
  { key: 'bizdev', label: 'Riset & Scanner', x0: -7, x1: -1.8, warna: '#1e293b', karpet: '#e4572e' },
  { key: 'keuangan', label: 'Trading Floor', x0: -1.8, x1: 2, warna: '#0f172a', karpet: '#10b981' },
  { key: 'studio', label: 'BSJP & Strategi', x0: 2, x1: 7, warna: '#1e1b4b', karpet: '#3a86ff' },
] as const;
export type RoomKey = (typeof RUANGAN)[number]['key'];

export interface Agen {
  key: string;
  nama: string;
  /** Tugasnya, satu baris. */
  tugas: string;
  ruang: RoomKey;
  /** Warna baju. */
  warna: string;
  /** Posisi meja (x kiri–kanan −7…7, z belakang–depan −3…3). */
  x: number;
  z: number;
}

/** Enam agen AI Saber Trader. */
export const AGEN: Agen[] = [
  { key: 'screener', nama: 'Rani', tugas: 'Scan 900+ Saham IHSG', ruang: 'bizdev', warna: '#e4572e', x: -5.2, z: -1.4 },
  { key: 'bandar', nama: 'Bagus', tugas: 'Smart Money & Broksun', ruang: 'bizdev', warna: '#8e6bd8', x: -3.2, z: -1.4 },
  { key: 'monitor', nama: 'Dimas', tugas: 'Pantau TP1, TP2 & Cutloss', ruang: 'keuangan', warna: '#10b981', x: 0.6, z: -0.2 },
  { key: 'trader', nama: 'Rian', tugas: 'Eksekusi & Risk Guard', ruang: 'keuangan', warna: '#f2b134', x: -0.8, z: 1.2 },
  { key: 'bsjp', nama: 'Laras', tugas: 'BSJP & Rekap Winrate', ruang: 'studio', warna: '#3a86ff', x: 3.6, z: -1.2 },
  { key: 'optimizer', nama: 'Bayu', tugas: 'Optimasi Bobot AI (ML)', ruang: 'studio', warna: '#ff5d8f', x: 5.4, z: 0.8 },
];

export type Aktivitas = 'kerja' | 'laporan' | 'belajar';

/** Jadwal kerja (WIB) selaras jam bursa IDX. */
export const JADWAL: { agen: string[] | '*'; mulai: string; menit: number; hari: number[]; aktivitas: Aktivitas; label: string }[] = [
  { agen: ['screener'], mulai: '06:00', menit: 45, hari: [1, 2, 3, 4, 5], aktivitas: 'kerja', label: 'scanning 900+ saham IHSG pagi…' },
  { agen: ['bandar'], mulai: '07:30', menit: 30, hari: [1, 2, 3, 4, 5], aktivitas: 'kerja', label: 'analisa broker summary & foreign flow…' },
  { agen: ['trader'], mulai: '08:45', menit: 15, hari: [1, 2, 3, 4, 5], aktivitas: 'kerja', label: 'menyiapkan trading plan & watchlist…' },
  { agen: ['monitor'], mulai: '09:00', menit: 180, hari: [1, 2, 3, 4, 5], aktivitas: 'kerja', label: 'memantau TP1/TP2 & SL sesi 1 bursa…' },
  { agen: ['screener'], mulai: '12:30', menit: 30, hari: [1, 2, 3, 4, 5], aktivitas: 'kerja', label: 'noon breakout technical scan…' },
  { agen: ['monitor'], mulai: '13:30', menit: 155, hari: [1, 2, 3, 4, 5], aktivitas: 'kerja', label: 'memantau TP1/TP2 & SL sesi 2 bursa…' },
  { agen: ['bsjp'], mulai: '15:45', menit: 25, hari: [1, 2, 3, 4, 5], aktivitas: 'kerja', label: 'skrining saham BSJP (Beli Sore Jual Pagi)…' },
  { agen: '*', mulai: '16:30', menit: 30, hari: [1, 2, 3, 4, 5], aktivitas: 'laporan', label: 'menulis laporan rekap harian…' },
  { agen: ['optimizer'], mulai: '20:00', menit: 120, hari: [1, 2, 3, 4, 5, 6, 7], aktivitas: 'belajar', label: 'optimasi bobot indikator teknikal…' },
];

/** Jam operasional bursa & AI bot: 06:00 - 21:00 WIB. */
export const JAM_KANTOR = { buka: '06:00', tutup: '21:00' };

export interface Laporan {
  /** Ringkasan hari ini (gelembung di atas kepala). */
  ringkasan?: string;
  /** Butir yang menunggu keputusanmu (tanda "!" dan Mission Board). */
  menunggu?: string[];
  /** Butir mendesak (mejanya berkedip). */
  mendesak?: string[];
  /** Angka hari ini (Mission Board). */
  angka?: { label: string; nilai: string }[];
}

/** Laporan hari ini per agen. */
export const LAPORAN: Record<string, Laporan> = laporanAgen;

/** Timelapse: satu hari dalam tiga babak (detik = lama tiap babak di video). */
export const BABAK = [
  { dari: '06:00', sampai: '09:15', detik: 10, judul: 'Pagi · Scan IHSG & Buka Sesi 1' },
  { dari: '12:30', sampai: '16:05', detik: 12, judul: 'Siang · Breakout & Monitor Sesi 2' },
  { dari: '16:15', sampai: '20:30', detik: 8, judul: 'Sore-Malam · Rekap & Optimasi AI' },
];
