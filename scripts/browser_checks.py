"""Browser checks use synthetic defaults only; never accept scenario URLs."""
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import TimeoutError as BrowserTimeout
from build_info import app_revision


class CheckError(RuntimeError):
    pass


def config():
    url = os.environ.get("APP_URL", "https://policy-ladder-visualizer.streamlit.app/")
    parsed = urlsplit(url)
    local = parsed.hostname in {"localhost", "127.0.0.1"}
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path != "/":
        raise CheckError("APP_URL must be an app root with no credentials or query")
    if not (local and parsed.scheme == "http") and not (parsed.scheme == "https" and parsed.hostname == "policy-ladder-visualizer.streamlit.app"):
        raise CheckError("Unsupported test target")
    timeout = int(os.environ.get("POLL_TIMEOUT_SECONDS", "480"))
    if not 10 <= timeout <= 600:
        raise CheckError("Invalid test timeout")
    return url, timeout


def find_app_frame(page):
    # Also supports the directly hosted app used by pre-deployment CI.
    for frame in page.frames:
        if frame.locator('[data-testid="stSidebar"]').count():
            return frame
    return None


def load_app(page):
    url, timeout = config()
    deadline = time.monotonic() + timeout
    expected = os.environ.get("APP_REVISION", app_revision())
    if len(expected) != 16 or any(c not in "0123456789abcdef" for c in expected):
        raise CheckError("Invalid expected revision")
    page.set_default_timeout(5000)
    last_navigation = 0
    last_wake_attempt = float("-inf")
    while time.monotonic() < deadline:
        remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
        if time.monotonic() - last_navigation > 15:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=min(30000, remaining_ms))
            except BrowserTimeout:
                pass
            last_navigation = time.monotonic()
        # Community Cloud presents an explicit wake button after inactivity;
        # reloading alone leaves the app asleep. Use the observed public control
        # and limit retries within the same overall readiness deadline.
        wake = page.get_by_role("button", name="Yes, get this app back up!", exact=True)
        if time.monotonic() - last_wake_attempt > 30 and wake.count() and wake.is_visible():
            last_wake_attempt = time.monotonic()
            try:
                wake.click(timeout=min(3000, max(1, int((deadline - time.monotonic()) * 1000))))
            except BrowserTimeout:
                pass
        frame = find_app_frame(page)
        if frame:
            build = frame.locator('#app-build')
            if build.count() and build.get_attribute('data-revision') == expected:
                try:
                    frame.wait_for_function("document.querySelector('.js-plotly-plot')?._fullLayout?.xaxis?.range?.[1] === 40",
                                            timeout=min(5000, max(1, int((deadline-time.monotonic())*1000))))
                    if frame.locator('[data-testid="stMetricValue"]').count() == 4:
                        return frame
                except BrowserTimeout:
                    pass
        page.wait_for_timeout(min(1000, max(1, int((deadline - time.monotonic()) * 1000))))
    raise CheckError("Expected deployment did not become ready within the deadline")


def run_checks(app):
    failures = []
    for selector in ('[data-testid="stException"]', '[data-testid="stAlert"] [data-testid="stException"]'):
        if app.locator(selector).count():
            failures.append("application exception is visible")
    if app.locator('[data-testid="stMetricValue"]').count() != 4:
        failures.append("expected four metrics")
    chart = app.locator('.js-plotly-plot')
    if chart.count() != 1 or chart.evaluate("e => e._fullLayout.xaxis.range[1]") != 40:
        failures.append("chart horizon is incorrect")
    for text in ("Worst-Year Shortfall", "Current Insurance Gap", "Annual Premium Roll-Off", "In plain English:"):
        if not app.get_by_text(text, exact=False).count():
            failures.append("required summary is missing")
    if not app.get_by_role('button', name='Prepare PDF report', exact=True).is_visible():
        failures.append("PDF preparation control is missing")
    if app.get_by_role('button', name='🔗 Shareable link', exact=True).count():
        failures.append("financial URL sharing is still exposed")
    return failures


def screenshot(page, name, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    # Browser contexts are created afresh and hold synthetic defaults only.
    page.screenshot(path=str(directory / f"{name}.png"), full_page=True, timeout=5000)
