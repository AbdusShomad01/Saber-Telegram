"""
Tes kirim pesan langsung dari bot BSJP ke Telegram
Jalankan: python test_conn.py
"""
import urllib.request
import json
import ssl
import sys

print("=" * 60)
print("🚀 TEST KIRIM PESAN BOT BSJP KE TELEGRAM")
print("=" * 60)

token = "9261989934:AAFO3q5Bs32pp4ElVyxYf-VufWaYj66rwPo"
chat_id = "-1004302595573"
thread_id = 107

# 1. Cek GetMe (info bot)
print("\n[1] Memeriksa info bot BSJP di Telegram...")
url_getme = f"https://api.telegram.org/bot{token}/getMe"
try:
    with urllib.request.urlopen(url_getme, timeout=10.0) as resp:
        res = json.loads(resp.read().decode())
        bot_user = res.get("result", {}).get("username")
        bot_name = res.get("result", {}).get("first_name")
        print(f"  ✅ Bot Aktif! Nama: {bot_name} (@{bot_user})")
except Exception as e:
    print(f"  ❌ Gagal cek bot: {e}")
    sys.exit(1)

# 2. Kirim pesan tes ke Group thread 107
print(f"\n[2] Mengirim pesan tes ke Chat {chat_id} (Thread {thread_id})...")
url_send = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {
    "chat_id": chat_id,
    "message_thread_id": thread_id,
    "text": "🤖 <b>Tes Koneksi Bot Saber Trader — BSJP</b>\nKoneksi berhasil dan bot aktif!",
    "parse_mode": "HTML",
}
data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(url_send, data=data, headers={"Content-Type": "application/json"})

try:
    with urllib.request.urlopen(req, timeout=15.0) as resp:
        res = json.loads(resp.read().decode())
        if res.get("ok"):
            msg_id = res.get("result", {}).get("message_id")
            print(f"  ✅ BERHASIL TERKIRIM! Message ID: {msg_id}")
            print("  🎉 Silakan cek grup Telegram Anda pada room 107!")
        else:
            print(f"  ⚠️ Response bukan OK: {res}")
except urllib.error.HTTPError as e:
    err_body = e.read().decode()
    print(f"  ❌ Telegram HTTP Error {e.code}: {err_body}")
except Exception as e:
    print(f"  ❌ Gagal kirim: {e}")

print("\n" + "=" * 60)
