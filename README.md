# 🛡️ Life Policy Pilot | Gap Analysis Pro

[![Source checks](https://github.com/richardparslow-commits/policy-ladder-visualizer/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/richardparslow-commits/policy-ladder-visualizer/actions/workflows/ci.yml)
[![Live deployment](https://github.com/richardparslow-commits/policy-ladder-visualizer/actions/workflows/smoke-live.yml/badge.svg?branch=main)](https://github.com/richardparslow-commits/policy-ladder-visualizer/actions/workflows/smoke-live.yml)

[Live app](https://policy-ladder-visualizer.streamlit.app/)

The app models the capital needed at the beginning of each year to fund remaining
income, childcare and tuition, pay remaining mortgage/debt and final expenses,
then offsets constant liquid assets and existing insurance while it is in force.
The annual income need is the living budget after debt payoff: exclude separately
entered childcare, tuition and final expenses, and deduct surviving-family income.
Amounts use today's dollars with zero assumed return, inflation and taxes. Other
debt is paid down linearly; the mortgage uses monthly amortization. College funds
are reserved before college begins and decline as tuition is paid. These explicit
simplifications are planning assumptions, not a personalized recommendation.

Up to three proposed policies start today. A term N covers years 0 through N−1;
permanent coverage is modeled through year 40. Same-year expiries aggregate.
Premiums are entered annual quotes, summed only while policies remain in force.
No health-class rating or blended premium estimate is supplied. Roll-off measures
premiums that stop at expiry; it does not measure savings versus another policy.

Save and compare scenarios within a session. Clear this session discards saved
inputs and prepared reports. URL scenario sharing and client-name collection have
been removed. Reports are prepared on demand as a three-page PDF with a readable
full table; CSV export retains rounded dollar values. See [data handling and
hosting limits](PRIVACY.md) before using real client information.

## Run locally

Use Python 3.12 or 3.13.

```sh
python -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python -m streamlit run streamlit_app.py
```

The devcontainer pins a Python 3.12 image digest, uses the non-root vscode user,
installs into a virtual environment, and stops setup if installation fails. Start
the app manually using the same command. Keep forwarded ports private. When using
a remote forwarded hostname, set `--browser.serverAddress` to that hostname so
CORS validation matches the deployment; retain CORS and XSRF protection.

## Verify and update dependencies

```sh
.venv/bin/python -m pip install --require-hashes -r requirements-dev.txt
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
.venv/bin/python -m pip_audit --no-deps --disable-pip -r requirements.txt
```

Locks include direct and transitive dependencies, hashes and cross-platform
markers. To intentionally refresh them, install uv 0.12.23 and run:

```sh
uv pip compile --universal --python-version 3.12 --generate-hashes requirements.in -o requirements.txt
uv pip compile --universal --python-version 3.12 --generate-hashes requirements-dev.in -o requirements-dev.txt
```

Re-run tests and the vulnerability scan after updating. No automatic upgrade or
unhashed extra install runs during container startup.

Source checks run mathematical, Streamlit session, PDF lifecycle and deadline
tests, followed by Chromium and WebKit responsive checks against a local server.
Desktop, tablet, small phone, phone, landscape and widths 699/700/701 are covered;
controls, saved comparisons and PDF preparation are exercised with synthetic data.
The live canary runs for this repository's main branch after pushes, nightly at
09:00 UTC, or on manual dispatch. It waits for a fingerprint of the checked-out
application source, preventing an older healthy deploy from passing the new run.
Failed runs retain synthetic screenshots for three days. Both workflows have
read-only tokens and immutable action references. Community Cloud deployment and
repository branch rules are configured separately from these workflows.
