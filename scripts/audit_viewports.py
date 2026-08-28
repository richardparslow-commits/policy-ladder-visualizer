"""Responsive viewport audit for the live deployment.

Loads the app at desktop, iPad, and iPhone sizes and fails the build if the
layout regresses: horizontal overflow, elements escaping the content area,
header elements colliding, or the flags/title/CTA misplacing on smaller
screens. Runs in CI as the second job of .github/workflows/smoke-live.yml;
also runnable locally:

    SETTLE_SECONDS=0 python scripts/audit_viewports.py

The deployed app renders inside Streamlit Cloud's wrapper iframe (URL ends
with /~/+), so all measurements run against that frame, not the top page.
Screenshots of each viewport are written under audit_shots/ for debugging.
"""
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

APP_URL = os.environ.get("APP_URL", "https://policy-ladder-visualizer.streamlit.app/")
SETTLE_SECONDS = int(os.environ.get("SETTLE_SECONDS", "120"))
POLL_TIMEOUT_SECONDS = int(os.environ.get("POLL_TIMEOUT_SECONDS", "480"))
TRIGGERED_BY = os.environ.get("TRIGGERED_BY", "")
SHOTS = Path(os.environ.get("SCREENSHOT_DIR", "audit_shots"))
VIEWPORTS = [("desktop", 1440, 900), ("ipad", 768, 1024), ("iphone", 390, 844)]
CTA_URL = "https://lifeinsurancebrokeradvocate.com/contact"

MEASURE_JS = """
() => {
  const box = el => { const r = el.getBoundingClientRect();
    return {left: Math.round(r.left), right: Math.round(r.right),
            top: Math.round(r.top), bottom: Math.round(r.bottom),
            width: Math.round(r.width), height: Math.round(r.height)}; };
  const tx = document.querySelector('img[alt="Texas flag"]');
  const us = document.querySelector('img[alt="American flag"]');
  const h1 = document.querySelector('h1');
  const cta = document.querySelector('a[href="%CTA_URL%"]');
  const main = document.querySelector('[data-testid="stMainBlockContainer"]');
  const mb = main ? main.getBoundingClientRect() : {left: 0, right: window.innerWidth};
  return {
    innerW: window.innerWidth,
    docScrollW: document.documentElement.scrollWidth,
    tx: tx ? box(tx) : null, us: us ? box(us) : null,
    h1: h1 ? box(h1) : null, cta: cta ? box(cta) : null,
    metrics: document.querySelectorAll('[data-testid="stMetricValue"]').length,
    flagsLoaded: tx && us ? [tx.complete && tx.naturalWidth > 0, us.complete && us.naturalWidth > 0] : [false, false],
    contentLeft: Math.round(mb.left), contentRight: Math.round(mb.right)
  };
}
""".replace("%CTA_URL%", CTA_URL)


def log(msg):
    print(f"[audit] {msg}", flush=True)


def look_like_login(page):
    if "/-/login" in page.url:
        return True
    try:
        return "sign in" in page.locator("body").inner_text(timeout=3000).lower()
    except Exception:
        return False


def find_app_frame(page):
    for f in page.frames:
        if f.url.rstrip("/").endswith("/~/+"):
            try:
                if f.locator('[data-testid="stSidebar"]').count() > 0:
                    return f
            except Exception:
                pass
    return None


def overlap(a, b):
    return (min(a["right"], b["right"]) - max(a["left"], b["left"]) > 2 and
            min(a["bottom"], b["bottom"]) - max(a["top"], b["top"]) > 2)


def audit_viewport(page, app, name, width, height):
    issues = []
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_timeout(2500)  # let the app re-layout to the new size
    m = app.evaluate(MEASURE_JS)
    if m["metrics"] < 3:
        issues.append(f"expected >=3 headline metrics, found {m['metrics']}")
    if m["docScrollW"] > m["innerW"] + 1:
        issues.append(f"horizontal overflow: document {m['docScrollW']}px > viewport {m['innerW']}px")
    if not all(m["flagsLoaded"]):
        issues.append("flag image(s) did not load")
    for tag in ("tx", "h1", "cta", "us"):
        e = m[tag]
        if e is None:
            issues.append(f"missing header element: {tag}")
            continue
        if e["right"] > m["innerW"] + 1 or e["left"] < -1:
            issues.append(f"{tag} escapes viewport [{e['left']},{e['right']}] vs {m['innerW']}px")
        if e["right"] > m["contentRight"] + 2 or e["left"] < m["contentLeft"] - 2:
            issues.append(f"{tag} escapes content area [{e['left']},{e['right']}] vs "
                          f"[{m['contentLeft']},{m['contentRight']}]")
    if m["tx"] and m["h1"] and overlap(m["tx"], m["h1"]):
        issues.append("Texas flag overlaps title")
    if m["h1"] and m["cta"] and overlap(m["h1"], m["cta"]):
        issues.append("title overlaps CTA")
    if m["cta"] and m["us"] and overlap(m["cta"], m["us"]):
        issues.append("CTA overlaps American flag")
    if m["tx"] and m["us"] and overlap(m["tx"], m["us"]):
        issues.append("flags overlap each other")

    if name == "iphone":
        tx, us, h1, cta = m["tx"], m["us"], m["h1"], m["cta"]
        if not (tx and us and us["left"] > tx["right"] and abs(us["top"] - tx["top"]) < us["height"]):
            issues.append("flags not on one row at opposite corners on phone")
        content_center = (m["contentLeft"] + m["contentRight"]) / 2
        for tag, e in (("h1", h1), ("cta", cta)):
            if e and abs(e["left"] + e["width"] / 2 - content_center) > 40:
                issues.append(f"{tag} not centered on phone (center {e['left'] + e['width'] / 2:.0f} "
                              f"vs content center {content_center:.0f})")
    else:
        if abs(m["us"]["top"] - m["tx"]["top"]) > m["us"]["height"]:
            issues.append("American flag wrapped off the header row (should stay top-right)")
        if not (m["us"]["left"] > m["cta"]["right"]):
            issues.append("American flag not right of the CTA")

    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)
    return issues


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            if SETTLE_SECONDS:
                if TRIGGERED_BY == "schedule":
                    log("scheduled run: skipping settle")
                else:
                    log(f"sleeping {SETTLE_SECONDS}s so Streamlit Cloud can redeploy")
                    time.sleep(SETTLE_SECONDS)
            log(f"loading {APP_URL}")
            page.goto(APP_URL, timeout=60000, wait_until="domcontentloaded")

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
                    log(f"poll {poll}: app not rendering yet; waiting 20s")
                    time.sleep(20)
                    if poll % 4 == 0:
                        try:
                            page.reload(wait_until="domcontentloaded")
                        except Exception:
                            pass
            if app is None:
                log("FAIL: app never rendered (no app iframe with a sidebar)")
                sys.exit(1)
            try:
                app.wait_for_selector('[data-testid="stMetricValue"]', timeout=90000)
            except Exception:
                log("FAIL: app frame appeared but never rendered metrics")
                sys.exit(1)

            SHOTS.mkdir(parents=True, exist_ok=True)
            all_issues = {}
            for name, w, h in VIEWPORTS:
                issues = audit_viewport(page, app, name, w, h)
                all_issues[name] = issues
                status = "OK" if not issues else "ISSUES"
                log(f"{name:8s} {w}x{h}: {status}")
                for i in issues:
                    log(f"         - {i}")

            if any(all_issues.values()):
                log("FAIL: viewport audit found layout issues (screenshots in audit_shots/)")
                sys.exit(1)
            log("PASS: layout clean at desktop, iPad, and iPhone sizes")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
