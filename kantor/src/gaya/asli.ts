/** Gaya bawaan template: bentuk sederhana, warna hangat, bahan Lambert. */
import { buatKit, pelacak } from './alat';
import type { PembangunGaya } from './tipe';

export const asli: PembangunGaya = {
  buat: () => buatKit(pelacak()),
};
