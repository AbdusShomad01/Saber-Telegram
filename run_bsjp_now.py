"""
run_bsjp_now.py
Entry script untuk menjalankan BSJP Screener secara manual.
Gunakan: python run_bsjp_now.py
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

from jobs.scheduler import job_bsjp_scan

if __name__ == "__main__":
    print("🌇 Running BSJP Screener (Beli Sore Jual Profit) ...")
    asyncio.run(job_bsjp_scan())
    print("✅ BSJP Scan completed!")

