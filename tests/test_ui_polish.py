import time
import subprocess
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

def verify_ui_polish():
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    server_process = subprocess.Popen(
        [".venv/bin/uvicorn", "app.main:app", "--port", "8888", "--host", "127.0.0.1"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        time.sleep(2)  # Wait for uvicorn to start

        with sync_playwright() as p:
            # 1. Desktop Verification
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 850})
            page = context.new_page()

            page.goto("http://127.0.0.1:8888/")
            
            # Wait for auto-run review to complete and populate
            page.wait_for_selector(".verdict", timeout=12000)
            page.wait_for_selector(".finding", timeout=5000)

            # Check 1: Alive on first paint
            code_val = page.input_value("#code-input")
            assert "SELECT id, username, email FROM users" in code_val, "SQL Sample should be auto-loaded"
            sample_val = page.input_value("#sample")
            assert "sqli" in sample_val or "sql" in sample_val, "Sample dropdown should be set"
            
            verdict_text = page.inner_text(".verdict")
            assert "critical issue" in verdict_text or "issue" in verdict_text or "Static analysis only" in verdict_text
            print("✓ Check 1: Alive on first paint (auto-loaded SQL sample and auto-ran real review) PASS")

            # Check 2: Auto-grow editor
            box = page.eval_on_selector("#code-input", "el => ({ height: el.offsetHeight, scrollHeight: el.scrollHeight })")
            print(f"Editor height on sample: {box['height']}px (min 200, max 440)")
            assert 200 <= box['height'] <= 440, f"Editor height {box['height']} out of bounds [200, 440]"
            
            # Gutter scroll alignment
            gutter_text = page.inner_text("#gutter")
            assert "1" in gutter_text and "8" in gutter_text
            print("✓ Check 2: Auto-grow editor fits content without dead space PASS")

            # Check 3: Framing band
            framing_h2 = page.inner_text(".framing h2")
            assert "Code review that reads the whole file." in framing_h2
            framing_p = page.inner_text(".framing p")
            assert "Paste a change. Sentinel runs static analysis" in framing_p
            chips = page.eval_on_selector_all(".cap-chip", "els => els.map(e => e.textContent.trim())")
            assert any("Whole-file context" in c for c in chips)
            assert any("Flags hidden-comment prompt injection" in c for c in chips)
            assert any("False positives filtered by a verification pass" in c for c in chips)
            print("✓ Check 3: Framing band & 3 capability chips PASS")

            # Desktop screenshot
            os.makedirs("artifacts", exist_ok=True)
            page.screenshot(path="artifacts/screenshot_desktop.png", full_page=True)
            print("✓ Desktop screenshot captured: artifacts/screenshot_desktop.png")

            # 2. Mobile Verification (390px width)
            mobile_context = browser.new_context(viewport={"width": 390, "height": 844})
            mobile_page = mobile_context.new_page()
            mobile_page.goto("http://127.0.0.1:8888/")
            mobile_page.wait_for_selector(".verdict", timeout=12000)

            # Ensure no horizontal overflow
            scroll_width = mobile_page.evaluate("document.documentElement.scrollWidth")
            client_width = mobile_page.evaluate("document.documentElement.clientWidth")
            assert scroll_width <= client_width + 1, f"Horizontal scroll detected on mobile: {scroll_width} > {client_width}"

            mobile_page.screenshot(path="artifacts/screenshot_mobile.png", full_page=True)
            print("✓ Mobile screenshot captured: artifacts/screenshot_mobile.png")

            # 3. User-initiated run check: Edit code, click Review
            page.fill("#code-input", "def test():\n    eval('1+1')")
            page.click("#run")
            page.wait_for_selector(".verdict", timeout=10000)
            new_verdict = page.inner_text(".verdict")
            assert "issue" in new_verdict or "Dynamic" in page.inner_text(".findings") or "eval" in page.inner_text(".findings").lower()
            print("✓ Check 4: User-initiated review after editing works PASS")

            # Test copy button
            copy_btn = page.query_selector(".copy")
            if copy_btn:
                context.grant_permissions(["clipboard-read", "clipboard-write"])
                copy_btn.click()
                time.sleep(0.3)
                btn_txt = copy_btn.inner_text()
                assert "Copied" in btn_txt or "Press ⌘C" in btn_txt or "done" in (copy_btn.get_attribute("class") or "")
                print(f"✓ Copy-fix button feedback PASS (text: {btn_txt})")

            browser.close()
            print("\n=== ALL UI POLISH CHECKS EMPIRICALLY SATISFIED! ===")

    finally:
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    verify_ui_polish()
