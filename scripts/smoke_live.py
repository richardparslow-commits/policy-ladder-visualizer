"""Post-deploy smoke test: load the live Streamlit app in a headless browser and fail if it doesn't render.

Runs in CI after every push to main (see .github/workflows/smoke-live.yml) so a broken
deploy turns the commit red. Also runnable locally:

    SETTLE_SECONDS=0 python scripts/smoke_live.py

Notes:
- Streamlit Cloud redeploys asynchronously after a push, so we settle briefly and then
  poll for the app to render. The marker set below pins the *current* expected UI;
  update EXPECTED_MARKERS/FORBIDDEN_MARKERS when the UI legitimately changes.
- The app renders inside Streamlit Cloud's wrapper iframe (URL ends with /~/+), so all
  checks run against that frame, not the top-level document.
"""
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

APP_URL = os.environ.get("APP_URL", "https://policy-ladder-visualizer.streamlit.app/")
SETTLE_SECONDS = int(os.environ.get("SETTLE_SECONDS", "120"))
POLL_TIMEOUT_SECONDS = int(os.environ.get("POLL_TIMEOUT_SECONDS", "480"))
MARKERS = [
    m.strip() for m in os.environ.get(
        "EXPECTED_MARKERS",
        "Mortgage Interest Rate,Debt Payoff Years,College Starts In,Years of College to Fund,"
        "Existing Policy Type,Existing Policy Years Remaining,Annual Premium Roll-Off",
    ).split(",") if m.strip()
]
FORBIDDEN = [m.strip() for m in os.environ.get("FORBIDDEN_MARKERS", "Projected Savings").split(",") if m.strip()]
AXIS_MAX = os.environ.get("AXIS_MAX", "40")
SHOTS = Path(os.environ.get("SCREENSHOT_DIR", "smoke_shots"))


def log(msg):
    print(f"[smoke] {msg}", flush=True)


def look_like_login(page):
    """Cloud bounces some requests (bots, rate-limits) to an email login page."""
    if "/-/login" in page.url:
        return True
    try:
        return "sign in" in page.locator("body").inner_text(timeout=3000).lower()
    except Exception:
        return False


def find_app_frame(page):
    """Return the Frame hosting the app (sidebar present), or None."""
    for f in page.frames:
        if f.url.rstrip("/").endswith("/~/+"):
            try:
                if f.locator('[data-testid="stSidebar"]').count() > 0:
                    return f
            except Exception:
                pass
    return None


def run_checks(app):
    failures = []
    for marker in MARKERS:
        if app.get_by_text(marker, exact=False).count() == 0:
            failures.append(f"missing expected UI element: {marker!r}")
    for marker in FORBIDDEN:
        if app.get_by_text(marker, exact=False).count() > 0:
            failures.append(f"stale UI still present: {marker!r}")
    try:
        ticks = app.evaluate(
            "Array.from(document.querySelectorAll('.js-plotly-plot .xaxislayer-above text')).map(t => t.textContent)"
        )
        if AXIS_MAX not in ticks:
            failures.append(f"chart x-axis missing tick {AXIS_MAX!r} (ticks: {ticks})")
    except Exception as e:
        failures.append(f"could not read chart x-axis: {e}")
    n_metrics = app.locator('[data-testid="stMetricValue"]').count()
    if n_metrics < 3:
        failures.append(f"expected 3 headline metrics, found {n_metrics}")
    return failures


def save_shots(page, app, tag):
    try:
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"{tag}_full.png"), full_page=True)
        if app is not None:
            app.locator('[data-testid="stSidebar"]').screenshot(path=str(SHOTS / f"{tag}_sidebar.png"))
    except Exception as e:
        log(f"could not save screenshots: {e}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        try:
            if SETTLE_SECONDS:
                log(f"sleeping {SETTLE_SECONDS}s so Streamlit Cloud can redeploy the fresh push")
                time.sleep(SETTLE_SECONDS)

            log(f"loading {APP_URL}")
            page.goto(APP_URL, timeout=60000, wait_until="domcontentloaded")

            # Poll until the app frame renders (handles cold boots, slow redeploys,
            # and Cloud's intermittent login bounce for automated visitors).
            deadline = time.time() + POLL_TIMEOUT_SECONDS
            app, poll = None, 0
            while time.time() < deadline:
                app = find_app_frame(page)
                if app:
                    break
                poll += 1
                if look_like_login(page):
                    log(f"poll {poll}: Cloud served the login bounce; clearing cookies and re-navigating")
                    try:
                        page.context.clear_cookies()
                    except Exception:
                        pass
                    try:
                        page.goto(APP_URL, timeout=60000, wait_until="domcontentloaded")
                    except Exception as e:
                        log(f"re-navigate failed: {e}")
                else:
                    log(f"poll {poll}: app not rendering yet (url={page.url[:80]}); waiting 20s")
                    time.sleep(20)
                    if poll % 4 == 0:
                        log("reloading to nudge a sleeping app")
                        try:
                            page.reload(wait_until="domcontentloaded")
                        except Exception:
                            pass

            if app is None:
                save_shots(page, None, "failure")
                log(f"FAIL: the Streamlit app never rendered; last url: {page.url}")
                sys.exit(1)

            try:
                app.wait_for_selector('[data-testid="stMetricValue"]', timeout=90000)
            except Exception:
                save_shots(page, app, "failure")
                log("FAIL: app frame appeared but never finished rendering metrics")
                sys.exit(1)
            time.sleep(4)  # let the chart finish drawing

            failures = run_checks(app)
            if failures:
                # Might have caught the previous deploy mid-swap; retry once.
                log("checks failed; retrying once after 60s")
                time.sleep(60)
                try:
                    page.reload(wait_until="domcontentloaded")
                except Exception:
                    pass
                retry_deadline = time.time() + 180
                while time.time() < retry_deadline:
                    app = find_app_frame(page)
                    if app:
                        try:
                            app.wait_for_selector('[data-testid="stMetricValue"]', timeout=90000)
                            time.sleep(4)
                        except Exception:
                            pass
                        break
                    time.sleep(15)
                if app is not None:
                    failures = run_checks(app)

            save_shots(page, app, "success" if not failures else "failure")
            if failures:
                for f in failures:
                    log(f"FAIL: {f}")
                sys.exit(1)
            log(f"PASS: live app at {APP_URL} renders all expected UI "
                f"({len(MARKERS)} markers, no stale UI, x-axis reaches {AXIS_MAX})")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
