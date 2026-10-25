"""
Script untuk mengosongkan (reset) riwayat sinyal di database SQLite
idx_signal_bot.db agar bersih dari nol.
"""

import sqlite3
import os
import sys

# Add current path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.config import get_settings

def reset_signals():
    settings = get_settings()
    db_path = settings.DATABASE_URL_SYNC.replace("sqlite:///", "") if settings.DATABASE_URL_SYNC.startswith("sqlite:///") else "./idx_signal_bot.db"
    
    if not os.path.exists(db_path):
        print(f"File database {db_path} tidak ditemukan.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Hitung jumlah sinyal sebelum dihapus
    cursor.execute("SELECT COUNT(*) FROM signals")
    count_before = cursor.fetchone()[0]
    
    # Hapus seluruh sinyal
    cursor.execute("DELETE FROM signals")
    conn.commit()
    conn.close()
    
    print(f"Berhasil mengosongkan tabel signals! ({count_before} data sinyal lama telah dihapus).")
    print("Database sekarang bersih dan siap mencatat sinyal baru.")

if __name__ == "__main__":
    reset_signals()
