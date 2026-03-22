"""
data/share_sheet.py — Share Google Sheet with service account via OAuth2.
Uses gcloud's built-in client ID to get Drive-scoped user credentials.
Run: python3 data/share_sheet.py
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import webbrowser

SHEET_ID = "1RqUFRnwiP0puYUk9f0VV_IRA4cHGebkgHKENOPMWlzc"
SERVICE_ACCOUNT_EMAIL = "voodoo-sheets@voodoobot-platform.iam.gserviceaccount.com"
TOKEN_FILE = Path(__file__).parent / "user_drive_token.json"
ENV_FILE = Path(__file__).parent.parent / ".env"

CLIENT_CONFIG = {
    "installed": {
        "client_id": "32555940559.apps.googleusercontent.com",
        "client_secret": "ZmssLNjJy2998hD4CTg2ejr2",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
    }
}

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

PORT = 8090
auth_code_received = None
server_done = threading.Event()


class CallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress logs

    def do_GET(self):
        global auth_code_received
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            auth_code_received = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
<html><body style='font-family:sans-serif;text-align:center;padding:40px'>
<h2>&#x2705; Authorized!</h2>
<p>VoodooBot now has access to Google Drive.</p>
<p>You can close this tab.</p>
</body></html>
""")
            server_done.set()
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Error: no auth code")


def open_in_chrome(url: str):
    """Open URL in Chrome via AppleScript."""
    script = f'''tell application "Google Chrome"
    activate
    open location "{url}"
end tell'''
    subprocess.run(["osascript", "-e", script], capture_output=True)


def get_credentials():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import Flow

    # Try cached token first
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds and creds.valid:
            print("✅ Using cached token")
            return creds
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing token...")
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
            return creds

    # Start local server to capture OAuth callback
    server = HTTPServer(("localhost", PORT), CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    # Build auth URL
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=f"http://localhost:{PORT}",
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        login_hint="kapytt2020@gmail.com",
    )

    print(f"🌐 Opening Google auth in Chrome...")
    print(f"   URL: {auth_url[:80]}...")
    open_in_chrome(auth_url)

    print("⏳ Waiting for you to click Allow in Chrome (60s timeout)...")
    server_done.wait(timeout=60)

    if not auth_code_received:
        raise TimeoutError("OAuth timeout — no response in 60s")

    # Exchange code for token
    flow.fetch_token(code=auth_code_received)
    creds = flow.credentials
    TOKEN_FILE.write_text(creds.to_json())
    print(f"✅ Token saved → {TOKEN_FILE.name}")
    return creds


def share_sheet(creds, sheet_id: str, email: str) -> bool:
    from googleapiclient.discovery import build

    service = build("drive", "v3", credentials=creds)
    permission = {
        "type": "user",
        "role": "writer",
        "emailAddress": email,
    }
    result = service.permissions().create(
        fileId=sheet_id,
        body=permission,
        sendNotificationEmail=False,
        fields="id,emailAddress,role",
    ).execute()
    print(f"✅ Shared: {result.get('emailAddress')} → {result.get('role')}")
    return True


def update_env(key: str, value: str):
    content = ENV_FILE.read_text()
    if re.search(rf"^{key}=", content, re.MULTILINE):
        content = re.sub(rf"^{key}=.*$", f"{key}={value}", content, flags=re.MULTILINE)
    else:
        content += f"\n{key}={value}\n"
    ENV_FILE.write_text(content)


if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  VoodooBot → Share Sheet with SA")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Sheet: {SHEET_ID}")
    print(f"SA:    {SERVICE_ACCOUNT_EMAIL}")
    print()

    try:
        creds = get_credentials()

        share_sheet(creds, SHEET_ID, SERVICE_ACCOUNT_EMAIL)
        update_env("USERS_SHEET_ID", SHEET_ID)
        print(f"✅ USERS_SHEET_ID updated in .env")

        print("\n📊 Running initial Google Sheets sync...")
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "google_sheets.py"), "--sync"],
            capture_output=True, text=True, cwd=str(Path(__file__).parent.parent)
        )
        print(result.stdout)
        if result.returncode == 0:
            print("✅ Google Sheets sync complete!")
        else:
            print("⚠️  Sync note:", result.stderr[:200])

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
