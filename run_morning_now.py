import asyncio
import os
import sys

# Add current path to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

from jobs.scheduler import job_intraday_scan

if __name__ == "__main__":
    print("🌅 Running morning scan (00:01 WIB / 1d) and sending signals to Telegram...")
    asyncio.run(job_intraday_scan(interval_override="1d"))
    print("✅ Morning scan completed!")
