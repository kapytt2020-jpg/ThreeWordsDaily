"""
data/connect_sheets.py — One-time Google Sheets connection setup.
Run: python3 data/connect_sheets.py
"""
import re
import subprocess
import sys
from pathlib import Path

ENV_FILE = Path(__file__).parent.parent / ".env"

def update_env(key: str, value: str):
    content = ENV_FILE.read_text()
    if re.search(rf"^{key}=", content, re.MULTILINE):
        content = re.sub(rf"^{key}=.*$", f"{key}={value}", content, flags=re.MULTILINE)
    else:
        content += f"\n{key}={value}\n"
    ENV_FILE.write_text(content)

print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  VoodooBot → Google Sheets Connection
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Service account: voodoo-sheets@voodoobot-platform.iam.gserviceaccount.com

Зроби в браузері (вже залогінений):
  1. Відкрий: https://sheets.new
  2. Назви: "VoodooBot Analytics"
  3. Клікни Share (кнопка вгорі праворуч)
  4. Додай: voodoo-sheets@voodoobot-platform.iam.gserviceaccount.com
  5. Роль: Editor → Share
  6. Скопіюй URL таблиці

Встав URL або ID нижче:
""")

url_or_id = input("URL або Sheet ID: ").strip()

# Extract ID from URL
match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url_or_id)
sheet_id = match.group(1) if match else url_or_id

if not sheet_id:
    print("❌ Не вдалося отримати Sheet ID")
    sys.exit(1)

print(f"\nSheet ID: {sheet_id}")
update_env("USERS_SHEET_ID", sheet_id)
print("✅ .env оновлено")

# Test connection
print("\nТестую підключення...")
try:
    import gspread
    from google.oauth2.service_account import Credentials

    creds_file = Path(__file__).parent / "google_credentials.json"
    creds = Credentials.from_service_account_file(str(creds_file), scopes=[
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ])
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    print(f"✅ З'єднання успішне! Таблиця: {sh.title}")
    print("\nЗапускаю синхронізацію...")
    subprocess.run([sys.executable, "data/google_sheets.py", "--sync"])
except Exception as e:
    print(f"❌ Помилка: {e}")
    print("\nПереконайся що поділився таблицею з:")
    print("  voodoo-sheets@voodoobot-platform.iam.gserviceaccount.com")
