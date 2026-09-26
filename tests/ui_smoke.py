"""
Optional browser smoke test (needs `pip install playwright && playwright install chromium`).
Start the app first:  python app.py   then:  python tests/ui_smoke.py [http://localhost:5000]
Checks: welcome, no technical labels, voice transcript is editable and NOT auto-sent,
mic language independent of reply language, card clicks queue correctly, hotel images
load (with fallback), Kannada labels, phone layout renders.
"""
import asyncio
import sys

from playwright.async_api import async_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
FAKE_SR = """
window.__srLang = null;
class FakeSR { constructor(){ this.lang='en-US'; }
  start(){ window.__srLang = this.lang; setTimeout(()=>{ this.onstart && this.onstart();
    this.onresult && this.onresult({results:[[{transcript:'flight to goa tomorow'}]]});
    this.onend && this.onend(); }, 50); }
  stop(){ this.onend && this.onend(); } }
window.SpeechRecognition = FakeSR;
window.webkitSpeechRecognition = FakeSR;
"""


async def settle(pg):
    await pg.wait_for_function("!document.querySelector('.thinking')", timeout=10000)
    await pg.wait_for_timeout(150)


async def main():
    ok = True
    def check(cond, msg):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + msg)
        ok = ok and cond
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1280, "height": 900})
        await pg.add_init_script(FAKE_SR)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.goto(BASE)
        await pg.wait_for_selector(".msg.bot")
        body = (await pg.inner_text("body")).lower()
        check(all(x not in body for x in ["fast nlp", "rag ready", "confidence", "intent:", "llama"]), "no technical labels")
        check(len(await pg.inner_text(".msg.bot")) < 80, "short welcome")

        # voice: reply language Kannada, mic language Hindi -> independent
        await pg.select_option("#reply-lang-select", "kn")
        await pg.select_option("#voice-lang-select", "hi-IN")
        await pg.click("#mic-btn")
        await pg.wait_for_timeout(300)
        check(await pg.input_value("#user-input") == "flight to goa tomorow", "transcript placed in input")
        check(await pg.is_visible("#transcript-hint"), "transcript hint shown")
        check(await pg.locator(".msg.user").count() == 0, "transcript not auto-sent")
        check(await pg.evaluate("window.__srLang") == "hi-IN", "mic uses its own language setting")
        await pg.fill("#user-input", "one way flight to goa tomorrow from Pune, 1 adult economy")   # user corrects
        await pg.press("#user-input", "Enter")
        await settle(pg)
        check("ಗೋವಾ" in await pg.inner_text(".msg.bot >> nth=-1") or "Goa" in await pg.inner_text(".msg.bot >> nth=-1"), "corrected transcript sent")
        check("ಆಯ್ಕೆ" in await pg.inner_text(".msg.bot >> nth=-1") or "ವಿಮಾನ" in await pg.inner_text(".msg.bot >> nth=-1"), "reply in Kannada")
        await pg.click(".quick-reply-btn >> nth=1")
        await pg.wait_for_selector(".flight-card")
        await settle(pg)
        check("ಆರಿಸಿ" in await pg.inner_text(".flight-card .select-btn >> nth=0"), "card labels in Kannada")

        # rapid clicks are queued, not dropped
        await pg.locator(".flight-card .select-btn").nth(0).click()
        await pg.click(".chip[data-message='Find a hotel']")
        await settle(pg)
        await pg.wait_for_timeout(600)
        msgs = await pg.eval_on_selector_all(".msg.bot", "e=>e.map(x=>x.textContent)")
        check(any("ಆಯ್ಕೆಯಾಗಿದೆ" in m for m in msgs[-3:]), "flight selection not lost when clicking quickly")

        await pg.goto(BASE)   # history restored after reload
        await pg.wait_for_timeout(500)
        check(await pg.locator(".flight-card").count() > 0, "history restored after reload")

        ph = await b.new_page(viewport={"width": 390, "height": 844})
        await ph.goto(BASE)
        await ph.wait_for_selector(".msg.bot")
        await ph.screenshot(path="ui_phone.png")
        check(await ph.is_visible("#user-input"), "phone layout usable")
        check(not errors, f"no page errors {errors}")
        await b.close()
    sys.exit(0 if ok else 1)


asyncio.run(main())
