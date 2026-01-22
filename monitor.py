import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, time, timezone, timedelta
import os
import sys
import re

# mengatasi warning certificate verification sementara
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from dotenv import load_dotenv
load_dotenv()

WIB = timezone(timedelta(hours=7))
START_TIME = time(6, 0)   # 06:00
END_TIME   = time(9, 0)   # 09:00


print("EMAIL_SENDER:", os.getenv("EMAIL_SENDER"))
print("TELEGRAM_BOT_TOKEN:", "OK" if os.getenv("TELEGRAM_BOT_TOKEN") else "NOT SET")

# ================= CONFIG =================
API_URL = "https://api.kbbank.co.id/backend/api/v1/reports"
PARAMS = {
    "cat": "laporan_bulanan",
    "from": "2025-01-01",
    "to": "2025-12-31",
    "orderBy": "asc",
    "perPage": 100
}

TARGET_MONTH = "2025-12"

EMAIL_SENDER = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_RECEIVER = os.environ["EMAIL_RECEIVER"]

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# GitHub config
IS_GITHUB = os.getenv("GITHUB_ACTIONS") == "true"
GITHUB_TOKEN = os.environ["GH_TOKEN"]
REPO = os.getenv("GITHUB_REPOSITORY")
WORKFLOW_FILE = "monitor.yml"

# =========================================

def test_telegram_bot():
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    r = requests.get(url)
    data = r.json()
    print(data)


def send_email(item):
    file_name = item.get("file", " ").split("/")[-1]
    file_url = item.get('file', '--url--')
    message = f"""
<html>
  <body>
    <h3>📢 LAPORAN BBKP TERSEDIA</h3>
    <p>📄 Judul&emsp;: <b>{item.get('title', 'BBKP Laporan Bulanan')}</b></p>
    <p>🕒 Waktu&emsp;: <b>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</b></p>
    <p>🔗 Filename&emsp;: <b>{file_name}</b></p>
    <div>
        Laporan resmi sudah tersedia.<br>
        <a href="{file_url}">
            👉 Download Laporan (PDF)
        </a>
    </div>
  </body>
</html>
"""
    msg = MIMEText(message, "html", "utf-8")
    msg["Subject"] = f"🚨 BBKP {item.get('title', 'BBKP Laporan Bulanan')}"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)


def send_telegram(item):
    file_url = item.get('file', '--url--')

    message = f"""
📢 LAPORAN BBKP TERSEDIA

📄 Judul\t\t\t\t: {item.get('title', 'Laporan Bulanan')}
🕒 Waktu \t\t: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
🔗 File\t\t\t\t\t\t\t\t: {item.get('file', '--url--')}

✅ Monitoring dihentikan otomatis
"""
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": int(TELEGRAM_CHAT_ID),
        "text": message,
        "reply_markup": {
            "inline_keyboard": [
                [
                    {
                        "text": "⬇️ Download File",
                        "url": file_url
                    }
                ]
            ]
        }
    }
    r = requests.post(url, json=payload)
    print("TELEGRAM STATUS:", r.status_code)
    print("TELEGRAM RESPONSE:", r.text)


def disable_workflow(reason=""):
    if not IS_GITHUB:
        print("ℹ️ Local mode: skip disable workflow")
        return
    
    print(f"🛑 Disabling workflow: {reason}")

    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/disable"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    r = requests.put(url, headers=headers)
    if r.status_code == 204:
        print("🛑 Workflow berhasil di-disable.")
    else:
        print("⚠️ Gagal disable workflow:", r.status_code, r.text)


def handle_time_window():
    now = datetime.now(WIB).time()

    if now > END_TIME:
        disable_workflow("Monitoring window closed (after 09:00 WIB)")
        exit()

    if now < START_TIME:
        print("⏸ Before monitoring window")
        exit()


def notify_and_shutdown(item):
    # test_telegram_bot()
    send_telegram(item)
    send_email(item)
    disable_workflow()
    sys.exit(0)


def main():
    handle_time_window()
    
    r = requests.get(
        API_URL, 
        params=PARAMS, 
        timeout=15, 
        verify=False  # ⬅️ bypass SSL
    )
    if r.status_code != 200:
        print("API error:", r.status_code)
        return

    data = r.json().get("data", {}).get("result", [])
    if (data):
        for item in data:
            created_date = item.get("created_date", "")
            if re.search(r"-(12)-2025", created_date):
                notify_and_shutdown(item)
                return

    print("⏳ Belum ada laporan Desember 2025.")


if __name__ == "__main__":
    main()
