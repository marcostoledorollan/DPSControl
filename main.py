from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from playwright.sync_api import sync_playwright
from urllib.parse import parse_qs, urlparse
import base64
import json
import os
import time

DEFAULT_URL = os.environ.get(
    "CONFLUENCE_PAGE_URL",
    "https://confluence.prosegur.net/pages/viewpage.action?spaceKey=DTDA&title=PRO+GEDGE+2026",
)
USERNAME = os.environ.get("CONFLUENCE_USERNAME")
PASSWORD = os.environ.get("CONFLUENCE_PASSWORD")
HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "false").lower() in {"1", "true", "yes"}
PROJECT_NAME = os.environ.get("CONFLUENCE_PROJECT_NAME")
TARGET_ENVIRONMENT = os.environ.get("CONFLUENCE_ENVIRONMENT", "PRO")


def _get_url_for_environment(uat_variable: str, pro_variable: str, environment: str) -> str:
    match environment.upper():
        case "UAT":
            url = os.environ.get(uat_variable)
        case "PRO":
            url = os.environ.get(pro_variable)
        case _:
            raise ValueError("CONFLUENCE_ENVIRONMENT must be UAT or PRO")

    if not url:
        raise ValueError(f"Missing URL for environment {environment}")

    return url


def get_confluence_url(project_name: str, environment: str) -> str:
    match project_name:
        case "dSOC":
            return _get_url_for_environment("DSOC_UAT_URL", "DSOC_PRO_URL", environment)
        case "Firesoc":
            return _get_url_for_environment(
                "FIRESOC_UAT_URL",
                "FIRESOC_PRO_URL",
                environment,
            )
        case "AlarmControl":
            return _get_url_for_environment(
                "ALARMCONTROL_UAT_URL",
                "ALARMCONTROL_PRO_URL",
                environment,
            )
        case "Video":
            return _get_url_for_environment("VIDEO_UAT_URL", "VIDEO_PRO_URL", environment)
        case _:
            raise ValueError(
                "CONFLUENCE_PROJECT_NAME must be dSOC, Firesoc, AlarmControl, or Video"
            )


def run() -> str:
    if not USERNAME or not PASSWORD:
        raise ValueError("CONFLUENCE_USERNAME and CONFLUENCE_PASSWORD must be set")

    url = DEFAULT_URL
    if PROJECT_NAME:
        url = get_confluence_url(PROJECT_NAME, TARGET_ENVIRONMENT)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()

        page.goto(url, wait_until="domcontentloaded")

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


def _unauthorized_response(handler: BaseHTTPRequestHandler) -> None:
    handler.send_response(HTTPStatus.UNAUTHORIZED)
    handler.send_header("WWW-Authenticate", 'Basic realm="Confluence API"')
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()
    handler.wfile.write(json.dumps({"error": "Unauthorized"}).encode("utf-8"))


def _is_authorized(handler: BaseHTTPRequestHandler) -> bool:
    if not API_USERNAME or not API_PASSWORD:
        raise ValueError("API_USERNAME and API_PASSWORD must be set")

    auth_header = handler.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Basic "):
        return False

    encoded_credentials = auth_header.split(" ", 1)[1].strip()
    try:
        decoded = base64.b64decode(encoded_credentials).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False

    username, _, password = decoded.partition(":")
    return username == API_USERNAME and password == API_PASSWORD


class ConfluenceHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if not _is_authorized(self):
            _unauthorized_response(self)
            return

        parsed_url = urlparse(self.path)
        if parsed_url.path != "/run":
            self.send_response(HTTPStatus.NOT_FOUND)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not Found"}).encode("utf-8"))
            return

        query_params = parse_qs(parsed_url.query)
        project_name = query_params.get("project_name", [None])[0]
        target_environment = query_params.get("target_environment", [None])[0]

        try:
            new_url_published = run(project_name, target_environment)
        except ValueError as exc:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps({"newUrlPublished": new_url_published}).encode("utf-8")
        )

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    server = HTTPServer((SERVER_HOST, SERVER_PORT), ConfluenceHandler)
    server.serve_forever()
