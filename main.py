from playwright.sync_api import sync_playwright
import os
import time

URL = os.environ.get(
    "CONFLUENCE_PAGE_URL",
    "https://confluence.prosegur.net/pages/viewpage.action?spaceKey=DTDA&title=PRO+GEDGE+2026",
)
USERNAME = os.environ.get("CONFLUENCE_USERNAME")
PASSWORD = os.environ.get("CONFLUENCE_PASSWORD")
HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "false").lower() in {"1", "true", "yes"}


def run() -> str:
    if not USERNAME or not PASSWORD:
        raise ValueError("CONFLUENCE_USERNAME and CONFLUENCE_PASSWORD must be set")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()

        page.goto(URL, wait_until="domcontentloaded")

        time.sleep(1)

        page.fill("#i0116", USERNAME)
        time.sleep(0.5)

        page.click("#idSIButton9")

        page.wait_for_selector("#i0118", timeout=15000)
        page.fill("#i0118", PASSWORD)
        time.sleep(0.5)

        page.click("#idSIButton9")
        page.wait_for_load_state("networkidle")

        time.sleep(3)

        page.wait_for_selector("#action-menu-link", timeout=10000)
        page.wait_for_selector("#action-copy-page-link", state="visible", timeout=10000)
        page.click("#action-copy-page-link")

        page.wait_for_selector("#copy-dialog-next", state="visible")
        page.click("#copy-dialog-next")

        page.wait_for_load_state("networkidle")

        page.wait_for_selector("#rte-button-publish", state="visible", timeout=20000)
        page.click("#rte-button-publish")

        page.wait_for_url("**/pages/viewpage.action**", timeout=30000)
        new_url_published = page.url

        browser.close()
        return new_url_published


if __name__ == "__main__":
    print(run())
