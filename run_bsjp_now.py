"""
run_bsjp_now.py
Entry script untuk menjalankan BSJP Screener secara manual.
Gunakan: python run_bsjp_now.py
"""
import asyncio
import os
import sys
import socket

# Force IPv4 untuk bypass issue blackhole IPv6 di VPS Biznet / ISP Indonesia
try:
    _orig_getaddrinfo = socket.getaddrinfo
    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
    socket.getaddrinfo = _ipv4_getaddrinfo
except Exception:
    pass

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

