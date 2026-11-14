/** Pembangun 16 gaya 3D + gaya asli (dimuat bersama scene 3D). Data gaya untuk UI: ./daftar. */
import { asli } from './asli';
import { clay } from './clay';
import { felt } from './felt';
import { voxel } from './voxel';
import { vinyl } from './vinyl';
import { diorama } from './diorama';
import { kayu } from './kayu';
import { stickman } from './stickman';
import { pulau } from './pulau';
import { toko } from './toko';
import { menara } from './menara';
import { taman } from './taman';
import { gedung30 } from './gedung30';
import { hologram } from './hologram';
import { angkringan } from './angkringan';
import { pecellele } from './pecellele';
import { bakso } from './bakso';
import type { GayaId } from './daftar';
import type { Kit } from './alat';
import type { PembangunGaya } from './tipe';

const PEMBANGUN: Record<GayaId, PembangunGaya> = { asli, clay, felt, voxel, vinyl, diorama, kayu, stickman, pulau, toko, menara, taman, gedung30, hologram, angkringan, pecellele, bakso };

export const buatKitGaya = (id: string | null | undefined): Kit => (PEMBANGUN[id as GayaId] ?? asli).buat();
