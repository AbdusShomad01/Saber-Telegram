import type { Kit } from './alat';

/** Data satu gaya 3D (pemilih, README). */
export interface InfoGaya {
  id: string;
  nama: string;
  jenis: 'asli' | 'menyeluruh' | 'paduan';
  /** Satu baris penjelasan. */
  ket: string;
  /** Latar CSS di belakang kanvas (siang, malam). Kosong = latar bawaan. */
  latar?: { siang: string; malam: string };
  /** Kabur tilt-shift atas-bawah (miniatur). */
  tiltShift?: boolean;
  /** UI/HUD selalu mode malam. */
  malam?: boolean;
}

/** Pembangun kit gaya (dipanggil tiap scene dibangun; textures & geometri dibuang lagi lewat kit.dispose()). */
export interface PembangunGaya {
  buat(): Kit;
}
