"""
Manual trigger script to immediately run the SPS Signal Recap
(Sync to Google Sheets and Send Telegram Message).
"""

import asyncio
import os
import sys

# Add current path to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

from jobs.scheduler import job_sps_recap

if __name__ == "__main__":
    print("🚀 Menjalankan rekapitulasi sinyal SPS (Google Sheets & Telegram)...")
    asyncio.run(job_sps_recap())
    print("✅ Selesai!")
