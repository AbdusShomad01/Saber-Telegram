import asyncio
import os
import sys

# Add current path to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from jobs.scheduler import job_signal_followup, job_fetch_daily_data

async def main():
    print("=== TUGAS 1: Evaluasi Sinyal (Follow-Up) ===")
    await job_signal_followup()
    
    print("\n=== TUGAS 2: Mengunduh Data OHLCV Harian ===")
    await job_fetch_daily_data()
    
    print("\n✅ Semua tugas akhir hari telah selesai!")

if __name__ == "__main__":
    asyncio.run(main())
