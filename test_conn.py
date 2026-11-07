"""
Diagnosa koneksi Telegram dari server VPS Biznet
Jalankan: python test_conn.py
"""
import socket
import ssl
import sys
import os

print("=" * 60)
print("🔍 DIAGNOSA KONEKSI TELEGRAM DARI VPS BIZNET")
print("=" * 60)

host = "api.telegram.org"
port = 443

# 1. Cek DNS
print("\n[1] Memeriksa DNS...")
try:
    ips = socket.gethostbyname_ex(host)[2]
    print(f"  ✅ DNS Berhasil. IP terdeteksi: {ips}")
except Exception as e:
    print(f"  ❌ DNS Gagal: {e}")
    sys.exit(1)

# 2. Cek TCP Socket Connect (Port 443)
print("\n[2] Memeriksa Koneksi TCP ke Port 443 (timeout 5s)...")
for ip in ips:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5.0)
    try:
        s.connect((ip, port))
        print(f"  ✅ Berhasil koneksi TCP ke {ip}:{port}")
        s.close()
    except Exception as e:
        print(f"  ❌ Gagal koneksi TCP ke {ip}:{port} -> {e}")

# 3. Cek SSL / HTTPS Handshake
print("\n[3] Memeriksa SSL / HTTPS Handshake...")
ctx = ssl.create_default_context()
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10.0)
try:
    s.connect((host, port))
    with ctx.wrap_socket(s, server_hostname=host) as ss:
        print(f"  ✅ SSL Handshake Berhasil! Cipher: {ss.cipher()[0]}")
except Exception as e:
    print(f"  ❌ SSL Handshake Gagal: {e}")

# 4. Tes HTTP Request langsung
print("\n[4] Memeriksa HTTP Request ke api.telegram.org...")
import urllib.request
try:
    req = urllib.request.Request(
        "https://api.telegram.org",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        print(f"  ✅ HTTP Response OK! Status code: {resp.status}")
except Exception as e:
    print(f"  ❌ HTTP Request Gagal: {e}")

print("\n" + "=" * 60)
