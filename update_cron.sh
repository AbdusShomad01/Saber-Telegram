#!/usr/bin/env bash
# Script update jadwal otomatis crontab VPS Biznet

cat << 'EOF' | crontab -
# Set Timezone WIB
CRON_TZ=Asia/Jakarta

# 1. Scan Pagi (06:00 WIB, Senin - Jumat)
0 6 * * 1-5 cd /home/sabertrader/Saber-Telegram && .venv/bin/python run_morning_now.py >> morning.log 2>&1

# 2. Rekap BSJP Pagi (09:30 WIB, Senin - Jumat)
30 9 * * 1-5 cd /home/sabertrader/Saber-Telegram && .venv/bin/python run_bsjp_rekap_now.py >> bsjp_rekap.log 2>&1

# 3. Scan Siang 15M (12:30 WIB, Senin - Jumat)
30 12 * * 1-5 cd /home/sabertrader/Saber-Telegram && .venv/bin/python run_intraday_now.py >> noon.log 2>&1

# 4. BSJP Screener Sore (15:45 WIB, Senin - Jumat)
45 15 * * 1-5 cd /home/sabertrader/Saber-Telegram && .venv/bin/python run_bsjp_now.py >> bsjp.log 2>&1

# 5. Real-Time Monitor TP/SL (Tiap 10 menit jam bursa)
*/10 9-15 * * 1-5 cd /home/sabertrader/Saber-Telegram && .venv/bin/python run_monitor_tp_sl.py >> monitor.log 2>&1
0 16 * * 1-5 cd /home/sabertrader/Saber-Telegram && .venv/bin/python run_monitor_tp_sl.py >> monitor.log 2>&1
EOF

echo "✅ Crontab berhasil diupdate!"
crontab -l
