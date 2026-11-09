"""
test_conn.py
Tes koneksi & kirim pesan bot BSJP ke Telegram menggunakan library requests.
Jalankan: python test_conn.py
"""
import sys
import socket

# Force IPv4 untuk bypass blackhole IPv6 pada VPS Biznet
try:
    _orig = socket.getaddrinfo
    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return _orig(host, port, socket.AF_INET, type, proto, flags)
    socket.getaddrinfo = _ipv4_getaddrinfo
except Exception:
    pass

def main():
    import requests

    print("=" * 60)
    print("🚀 TEST KONEKSI & KIRIM PESAN BOT BSJP KE TELEGRAM (REQUESTS)")
    print("=" * 60)

    token = "9261989934:AAFO3q5Bs32pp4ElVyxYf-VufWaYj66rwPo"
    chat_id = "-1004302595573"
    thread_id = 107

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 1. Cek GetMe
    print("\n[1] Memeriksa info bot BSJP di Telegram...")
    url_getme = f"https://api.telegram.org/bot{token}/getMe"
    try:
        r = requests.get(url_getme, headers=headers, timeout=15)
        if r.status_code == 200:
            res = r.json()
            bot_user = res.get("result", {}).get("username")
            bot_name = res.get("result", {}).get("first_name")
            print(f"  ✅ Bot Aktif! Nama: {bot_name} (@{bot_user})")
        else:
            print(f"  ❌ Telegram API Error ({r.status_code}): {r.text}")
            sys.exit(1)
    except Exception as e:
        print(f"  ❌ Gagal cek bot: {e}")
        sys.exit(1)

    # 2. Kirim pesan tes
    print(f"\n[2] Mengirim pesan tes ke Chat {chat_id} (Thread {thread_id})...")
    url_send = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "message_thread_id": thread_id,
        "text": "🤖 <b>Tes Koneksi Bot Saber Trader — BSJP</b>\nKoneksi berhasil dan bot aktif!",
        "parse_mode": "HTML",
    }
    try:
        r = requests.post(url_send, json=payload, headers=headers, timeout=20)
        if r.status_code == 200:
            res = r.json()
            msg_id = res.get("result", {}).get("message_id")
            print(f"  ✅ BERHASIL TERKIRIM! Message ID: {msg_id}")
            print("  🎉 Silakan cek grup Telegram Anda pada room 107 (BSJP)!")
        else:
            print(f"  ❌ Gagal kirim ({r.status_code}): {r.text}")
    except Exception as e:
        print(f"  ❌ Gagal kirim: {e}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
