#!/usr/bin/env python3
"""
Browser Agent — керує Chrome з persistent сесіями
Використання:
  python3 agent.py login n8n       # перший логін в n8n
  python3 agent.py login telegram  # перший логін в Telegram
  python3 agent.py run n8n         # читає workflow
  python3 agent.py run telegram    # читає повідомлення
"""

import sys
import json
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).parent
SESSIONS_DIR = BASE_DIR / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

SERVICES = {
    "n8n": "https://youtubeeee.app.n8n.cloud",
    "telegram": "https://web.telegram.org/k/",
}

async def login(service: str):
    """Відкриває браузер для ручного логіну, зберігає сесію"""
    url = SERVICES.get(service)
    if not url:
        print(f"Невідомий сервіс: {service}. Доступні: {list(SERVICES.keys())}")
        return

    session_path = SESSIONS_DIR / service
    print(f"Відкриваю {service} ({url})...")
    print("Залогінься вручну, потім закрий браузер — сесія збережеться автоматично")

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(session_path),
            headless=False,
            channel="chrome",
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
            ],
            ignore_default_args=["--enable-automation"],
            no_viewport=True,
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        # Приховуємо що це automation
        await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        await page.goto(url)
        print(f"Браузер відкрито. Залогінься і ЗАКРИЙ вікно — сесія збережеться.")
        await ctx.wait_for_event("close", timeout=0)
        print(f"✅ Сесія збережена в {session_path}")

async def run_n8n():
    """Читає всі workflows з n8n"""
    session_path = SESSIONS_DIR / "n8n"
    if not session_path.exists():
        print("Спочатку зроби: python3 agent.py login n8n")
        return

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(session_path),
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        print("Відкриваю n8n...")
        await page.goto("https://youtubeeee.app.n8n.cloud/home/workflows")
        await page.wait_for_load_state("networkidle", timeout=15000)

        # Беремо список workflows
        workflows = await page.evaluate("""() => {
            const items = document.querySelectorAll('[data-test-id="resources-list-item"]');
            return Array.from(items).map(el => ({
                name: el.querySelector('.el-tooltip span')?.innerText || el.innerText.trim().split('\\n')[0],
                id: el.getAttribute('data-test-id')
            }));
        }""")

        print(f"\nЗнайдено workflows: {len(workflows)}")
        for w in workflows:
            print(f"  - {w}")

        # Відкриваємо конкретний workflow
        target_url = "https://youtubeeee.app.n8n.cloud/workflow/5JJsg4DwRBcd7kTB"
        print(f"\nВідкриваю workflow {target_url}...")
        await page.goto(target_url)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(3000)

        # Скріншот
        screenshot_path = BASE_DIR / "n8n_workflow.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"Скріншот збережено: {screenshot_path}")

        # Експортуємо JSON через API n8n
        workflow_id = "5JJsg4DwRBcd7kTB"
        print("\nЕкспортую workflow JSON через API...")
        response = await page.evaluate(f"""async () => {{
            const r = await fetch('/api/v1/workflows/{workflow_id}', {{
                credentials: 'include',
                headers: {{'Accept': 'application/json'}}
            }});
            return r.ok ? await r.json() : {{'error': r.status}};
        }}""")

        json_path = BASE_DIR / f"workflow_{workflow_id}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(response, f, ensure_ascii=False, indent=2)
        print(f"JSON збережено: {json_path}")

        print("\nГотово! Закрий браузер коли захочеш.")
        await ctx.wait_for_event("close", timeout=0)

async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    service = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "login" and service:
        await login(service)
    elif cmd == "run":
        if service == "n8n":
            await run_n8n()
        else:
            print(f"run {service} — ще в розробці")
    else:
        print(__doc__)

if __name__ == "__main__":
    asyncio.run(main())
