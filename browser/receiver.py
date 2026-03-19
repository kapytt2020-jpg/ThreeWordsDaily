#!/usr/bin/env python3
"""Локальний сервер — приймає дані з браузера"""

import json
import http.server
import threading
from pathlib import Path

BASE_DIR = Path(__file__).parent
received_data = {}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        data = json.loads(body)

        name = self.path.strip('/')
        out_path = BASE_DIR / f"{name}.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Отримано '{name}' → збережено в {out_path}")

        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, *args):
        pass  # тихий режим

if __name__ == '__main__':
    server = http.server.HTTPServer(('localhost', 7777), Handler)
    print("🟢 Сервер запущено на http://localhost:7777")
    print("Чекаю на дані з браузера...\n")
    server.serve_forever()
