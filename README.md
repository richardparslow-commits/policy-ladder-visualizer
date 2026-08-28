# 🛡️ Life Policy Pilot | Gap Analysis Pro

[![Live deploy smoke test](https://github.com/richardparslow-commits/policy-ladder-visualizer/actions/workflows/smoke-live.yml/badge.svg?branch=main)](https://github.com/richardparslow-commits/policy-ladder-visualizer/actions/workflows/smoke-live.yml)

**Live app:** https://policy-ladder-visualizer.streamlit.app/

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://policy-ladder-visualizer.streamlit.app/)

A life-insurance planning tool that:

1. **Gap Analysis** — calculates, year by year, the difference between a family's
   projected financial needs (income replacement, mortgage payoff, other debts,
   future college tuition, childcare, final expenses) and the financial resources
   or existing insurance coverage available — with real mortgage amortization and
   expiring term policies modeled honestly.
2. **Policy Laddering Visualization** — models a "ladder" of smaller term policies
   (e.g., 10/20/30-year terms) instead of one large 30-year policy, and maps how
   total coverage steps down over time as major obligations are paid off, so
   premium cost matches the duration of each liability.

## Deployment health

Pushes to `main` auto-deploy to Streamlit Cloud. After every push — and on a
**nightly schedule** (09:00 UTC) — the **Live deploy smoke test** workflow loads
the live app in a headless browser and verifies the real UI renders (controls,
metrics, and the 0–40 chart). The badge at the top shows whether the deployed
app is healthy right now, including between pushes; run screenshots are attached
as artifacts on each run.

## How to run it on your own machine

1. Install the requirements:

   ```
   $ pip install -r requirements.txt
   ```

2. Run the app:

   ```
   $ streamlit run streamlit_app.py
   ```
