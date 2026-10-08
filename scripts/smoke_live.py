"""Verify the exact checked-out source is deployed; exit nonzero on failure."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from browser_checks import CheckError, load_app, run_checks, screenshot


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        passed = False
        try:
            app = load_app(page)
            failures = run_checks(app)
            if failures:
                raise CheckError("; ".join(failures))
            passed = True
            print("PASS: expected deployment, four metrics, chart and export controls verified")
            return 0
        except Exception as exc:
            # Don't log exception messages or URLs that could contain client data.
            print(f"FAIL: live smoke check ({type(exc).__name__})")
            return 1
        finally:
            try:
                screenshot(page, "success" if passed else "failure", os.environ.get("SCREENSHOT_DIR", "smoke_shots"))
            except Exception:
                print("Screenshot unavailable")
            context.close(); browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
