"""
tg_auto_add_bot.py — Auto-add VoodooOpsBot to My team group via Telegram Web.
Uses existing Chrome profile (already logged in to Telegram Web).
"""
import asyncio, re, os, time
from pathlib import Path
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

GROUP_LINK = "https://t.me/+h25oRixdZco3ZWQy"
BOT_USERNAME = "VoodooOpsBot"
ENV_FILE = Path(__file__).parent / ".env"
CHROME_PROFILE = os.path.expanduser("~/Library/Application Support/Google/Chrome")


def save_group_id(gid: str):
    text = ENV_FILE.read_text()
    text = re.sub(r"^INTERNAL_GROUP_ID=.*$", f"INTERNAL_GROUP_ID={gid}", text, flags=re.MULTILINE)
    ENV_FILE.write_text(text)
    print(f"✅ INTERNAL_GROUP_ID={gid} збережено в .env")


async def main():
    async with async_playwright() as pw:
        print("🌐 Відкриваю Chrome з твоїм профілем...")
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE,
            channel="chrome",
            headless=False,
            args=["--no-sandbox"],
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # Open Telegram Web
        print("📱 Відкриваю Telegram Web...")
        await page.goto("https://web.telegram.org/k/", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        # Check if logged in
        if "login" in page.url or await page.locator("text=Log in").count() > 0:
            print("❌ Telegram Web не авторизований. Відкрий https://web.telegram.org і увійди.")
            await ctx.close()
            return

        print("✅ Telegram Web відкритий")

        # Navigate to the group via invite link
        print(f"📥 Відкриваю групу My team...")
        await page.goto(f"https://web.telegram.org/k/#?tgaddr=tg%3A%2F%2Fjoin%3Finvite%3Dh25oRixdZco3ZWQy", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Try searching for the group
        try:
            search = page.locator('input[placeholder*="Search"]').first
            await search.click()
            await search.fill("My team")
            await page.wait_for_timeout(2000)
            group_result = page.locator('text=My team').first
            await group_result.click()
            await page.wait_for_timeout(2000)
            print("✅ Зайшов в групу My team")
        except Exception as e:
            print(f"⚠️ Пошук: {e}")

        # Get group ID from URL
        current_url = page.url
        print(f"URL: {current_url}")
        gid_match = re.search(r'-(\d+)', current_url)
        if gid_match:
            gid = f"-100{gid_match.group(1)}"
            print(f"Group ID: {gid}")
            save_group_id(gid)

        # Open group info / members
        print("👥 Відкриваю учасників групи...")
        try:
            # Click on group name/title to open info
            await page.locator('.chat-info').first.click()
            await page.wait_for_timeout(1500)

            # Click Add members
            add_btn = page.locator('text=Add member').first
            await add_btn.click()
            await page.wait_for_timeout(1000)

            # Search for the bot
            search_input = page.locator('input[type="text"]').last
            await search_input.fill(BOT_USERNAME)
            await page.wait_for_timeout(2000)

            # Select the bot
            bot_result = page.locator(f'text={BOT_USERNAME}').first
            await bot_result.click()
            await page.wait_for_timeout(500)

            # Confirm
            ok_btn = page.locator('text=Add').last
            await ok_btn.click()
            await page.wait_for_timeout(2000)
            print(f"✅ @{BOT_USERNAME} доданий в групу!")

        except Exception as e:
            print(f"⚠️ Add member: {e}")
            print("Відкрий групу вручну і додай @VoodooOpsBot як адміна")

        print("\n✅ Готово! Тепер запускаю group_manager.py...")
        await page.wait_for_timeout(3000)
        await ctx.close()

        os.execv("/opt/homebrew/opt/python@3.14/Frameworks/Python.framework/Versions/3.14/bin/python3",
                 ["python3", "group_manager.py"])


asyncio.run(main())
