import time
import subprocess
import os
import signal
from playwright.sync_api import sync_playwright

def run_smoke_test():
    # Start uvicorn server in background
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    server_process = subprocess.Popen(
        [".venv/bin/uvicorn", "app.main:app", "--port", "8888", "--host", "127.0.0.1"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        # Give server 2 seconds to bind
        time.sleep(2)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 1. Visit root route
            page.goto("http://127.0.0.1:8888/")
            page.wait_for_selector("#sample-select", timeout=5000)
            assert "SentinelReview" in page.title()

            # 2. Select Sample A (SQL injection)
            page.select_option("#sample-select", "sample-python-sqli")
            time.sleep(0.5)

            # Check that code input got populated
            code_content = page.input_value("#code-input")
            assert "SELECT id, username, email FROM users" in code_content

            # 3. Click Review Code
            page.click("#btn-review")

            # 4. Wait for results to render
            page.wait_for_selector(".summary-card", timeout=10000)
            page.wait_for_selector(".finding-card", timeout=5000)

            # Check findings
            summary_text = page.inner_text(".summary-card")
            assert "Automated review completed" in summary_text
            assert "High" in summary_text

            finding_titles = page.inner_text(".finding-title")
            assert "Sql Injection" in finding_titles

            print("PLAYWRIGHT SMOKE TEST PASSED: Successfully rendered UI, executed review on Sample A, and verified findings cards!")

            # 5. Now select Sample C (Hidden Prompt Injection)
            page.select_option("#sample-select", "sample-hidden-prompt-injection")
            time.sleep(0.5)
            page.click("#btn-review")
            time.sleep(2)
            page.wait_for_selector(".finding-card", timeout=5000)
            content_all = page.inner_text("#inspector-pane")
            assert "Prompt Injection" in content_all or "Adversarial" in content_all
            assert "Eval" in content_all or "Dynamic" in content_all or "CWE-95" in content_all

            print("PLAYWRIGHT SMOKE TEST PASSED: Sample C prompt injection & eval findings rendered accurately!")

            browser.close()

    finally:
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    run_smoke_test()
