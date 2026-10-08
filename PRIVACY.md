# Data handling and deployment limits

This public planning app is designed for hypothetical or de-identified inputs. It
has no health-class, medical-history, SSN, email, or client-name input. It is not an
underwriting system. Per-policy annual premiums must come from actual quotes.

Financial inputs and comparison snapshots remain in the current Streamlit
session. They are not put in query strings, a global Streamlit cache, analytics,
application log statements, or application-created database/files. Clear this
session removes the active inputs, comparison, and prepared report. Streamlit
may retain disconnected sessions until cleanup; the configured TTL is 60 seconds.
This is a cleanup threshold, not a guarantee of secure memory erasure.

Reports are created on explicit request. One PDF per session is kept in memory,
invalidated on input changes and date rollover. The renderer sends bounded JSON
through anonymous OS pipes to a disposable child process; PDF bytes return through
a pipe. A private temporary directory contains only Matplotlib font metadata.
Worker failures emit no client data or traceback. No PDF or CSV is written to the
server filesystem. UI assets are embedded to avoid third-party image requests.
CI creates fresh browsers with synthetic values and short-lived screenshots.

The UI and authorized downloads necessarily reveal entered financial values to
the person using the session. Downloaded PDFs and CSVs are unencrypted; users must
protect their devices and store exports securely. Browser memory, download
history, OS swap, crash dumps, reverse-proxy logs, and hosting retention are not
controlled by the application source. Previously shared scenario URLs may remain
in old history/logs; clearing a query parameter cannot erase those copies.

No HIPAA/PHI compliance certification is claimed. Applicability depends on the
operator and data use. If a regulated operator intends to use real client data,
first verify hosting contracts/BAAs where applicable, risk assessment, TLS,
authentication and access controls, encrypted storage/swap, log redaction,
retention/deletion, and incident response. Do not enter PHI into this public app.
See [HHS cloud guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/health-information-technology/cloud-computing/index.html).

Community Cloud obtains repository access through its authorized GitHub App;
`@streamlit/community-cloud` in CODEOWNERS neither configures that integration nor
grants access. Confirm the integration in hosting settings. Configure a GitHub
ruleset requiring the Source checks before merging to main. If code-owner approval
is required, designate an additional eligible reviewer: an author cannot approve
their own pull request. No repository ruleset or hosting contract is supplied by
these source files.

For deployments with multiple Streamlit server processes, each process admits one
PDF worker. Capacity must be limited at the deployment level as well. The Linux
worker has a 1 GiB virtual-memory cap, a 15-second CPU cap, and a cross-platform
20-second wall-clock timeout. A virtual-memory cap is not a process RSS guarantee;
provision and load-test the server/container for its allowed session count.
