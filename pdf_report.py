"""Bounded, de-identified reports rendered in a disposable worker process.

No report input or output is written to disk. Only public Matplotlib font cache
metadata uses a private temporary directory. A worker is killed on timeout.
"""
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import BoundedSemaphore
from datetime import date
import textwrap

PRIMARY_RED = "#CC0700"
GAP_FILL = "#D1D5DB"
INK = "#374151"
MAX_INPUT_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
REPORT_TIMEOUT_SECONDS = 20
_RENDER_SLOT = BoundedSemaphore(1)
SHORT = {
    "Year": "Yr", "Mortgage Balance ($)": "Mtg", "Other Debt ($)": "Debt",
    "Income Replacement ($)": "Income", "Childcare ($)": "Child",
    "College ($)": "College", "Final Expenses ($)": "Final",
    "Total Liabilities ($)": "Total Liab", "Existing Resources ($)": "Resources",
    "Net Gap - Required Insurance ($)": "Net Gap",
    "Proposed Ladder Coverage ($)": "Coverage", "Annual Premium ($)": "Premium",
}
LEGEND = ("Mtg = mortgage balance; Debt = other debt; Income = remaining income funding; "
          "Child = remaining childcare; College = remaining tuition; Final = final expenses; "
          "Total Liab = total liabilities; Resources = existing resources; Net Gap = required insurance; "
          "Coverage = proposed ladder; Premium = annual premium. All amounts in US dollars.")


class ReportError(RuntimeError):
    """Safe error with no client inputs or renderer traceback."""


class _BoundedBuffer(io.BytesIO):
    def write(self, value):
        if self.tell() + len(value) > MAX_OUTPUT_BYTES:
            raise ReportError("Report exceeds output limit")
        return super().write(value)


def _validate_payload(payload):
    if not isinstance(payload, dict) or set(payload) != {"rows", "gap0", "coverage0", "rolloff", "insight", "as_pdf"}:
        raise ReportError("Invalid report fields")
    rows = payload["rows"]
    if not isinstance(rows, list) or len(rows) != 41:
        raise ReportError("Report must contain years 0 through 40")
    for year, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != set(SHORT):
            raise ReportError("Invalid report columns")
        for value in row.values():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1_000_000_000:
                raise ReportError("Invalid report value")
        if row["Year"] != year:
            raise ReportError("Report years must be ordered")
    for key in ("gap0", "coverage0", "rolloff"):
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1_000_000_000:
            raise ReportError("Invalid report metric")
    if type(payload["as_pdf"]) is not bool or not isinstance(payload["insight"], str) or len(payload["insight"]) > 800:
        raise ReportError("Invalid report text")
    if any(ord(c) < 32 and c not in "\n\t" for c in payload["insight"]):
        raise ReportError("Invalid report text")


def _draw_chart(ax, frame):
    years = frame["Year"]
    gap = frame["Net Gap - Required Insurance ($)"]
    cov = frame["Proposed Ladder Coverage ($)"]
    ax.fill_between(years, gap, color=GAP_FILL, label="Required Insurance (Gap)")
    ax.step(years, cov, where="post", color=PRIMARY_RED, linewidth=2.5, label="Proposed Policy Ladder")
    ax.set(xlim=(0, 40), xlabel="Years into Future", ylabel="Dollar Amount ($)")
    ax.tick_params(labelsize=9, colors=INK)
    ax.yaxis.set_major_formatter(lambda x, pos: f"${x / 1000:,.0f}k")
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.5)
    ax.legend(loc="upper right", fontsize=9, frameon=False)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def _summary_figure(frame, payload, Figure, patches):
    fig = Figure(figsize=(11, 8.5))
    fig.text(.06, .94, "Life Insurance Gap Analysis", fontsize=18, color=PRIMARY_RED, weight="bold")
    fig.text(.06, .90, f"Prepared {date.today():%B %d, %Y} · De-identified planning report", fontsize=10, color=INK)
    shortfall = (frame["Net Gap - Required Insurance ($)"] - frame["Proposed Ladder Coverage ($)"]).clip(lower=0)
    worst_year = int(shortfall.idxmax())
    cards = [("Worst-Year Shortfall", f"${shortfall.max():,.0f} (year {worst_year})"),
             ("Current Insurance Gap", f"${payload['gap0']:,.0f}"),
             ("New Ladder Coverage", f"${payload['coverage0']:,.0f}"),
             ("Annual Premium Roll-Off", f"${payload['rolloff']:,.0f}/yr")]
    for i, (label, value) in enumerate(cards):
        x = .06 + i * .225
        fig.patches.append(patches.FancyBboxPatch((x, .77), .21, .09, boxstyle="round,pad=.004",
                           transform=fig.transFigure, facecolor="#f4f6f8", edgecolor="#e2e8f0"))
        fig.text(x + .01, .825, label, fontsize=8, color=INK)
        fig.text(x + .01, .79, value, fontsize=10, weight="bold", color=INK)
    _draw_chart(fig.add_axes([.10, .31, .84, .38]), frame)
    assumptions = ("Remaining obligations are funded in today's dollars, with zero assumed investment return, "
                   "inflation or taxes. Assets remain constant. All policies start today and are assumed in force "
                   "until expiry. Premiums are entered quotes, not underwriting estimates. Roll-off is not a "
                   "comparison with the cost of a single policy. Detailed figures follow on pages 2 and 3.")
    fig.text(.06, .20, textwrap.fill(assumptions, 125), fontsize=9, color=INK, va="top")
    fig.text(.06, .105, textwrap.fill(payload["insight"], 125), fontsize=8, color=INK, va="top")
    return fig


def _table_figure(block, Figure):
    fig = Figure(figsize=(11, 8.5))
    first, last = int(block["Year"].iloc[0]), int(block["Year"].iloc[-1])
    fig.text(.04, .94, f"Year-by-year detail — years {first}–{last}", fontsize=16, color=PRIMARY_RED)
    ax = fig.add_axes([.04, .20, .92, .67]); ax.axis("off")
    cells = [[f"{int(round(v)):,}" for v in row] for row in block.itertuples(index=False, name=None)]
    table = ax.table(cellText=cells, colLabels=list(SHORT.values()), cellLoc="right", bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False); table.set_fontsize(7)
    for (r, _), cell in table.get_celld().items():
        cell.set_edgecolor("#e5e7eb"); cell.set_linewidth(.3)
        cell.set_facecolor("#EEF2F7" if r == 0 else ("#F8FAFC" if r % 2 == 0 else "white"))
    fig.text(.04, .14, textwrap.fill(LEGEND, 150), fontsize=8, color=INK, va="top")
    return fig


def _render(payload):
    # Imports are confined to a short-lived process. There is no pyplot registry
    # or shared renderer state between sessions.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.patches as patches
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_pdf import PdfPages
    import pandas as pd
    _validate_payload(payload)
    frame = pd.DataFrame(payload["rows"], columns=list(SHORT))
    with matplotlib.rc_context({"text.usetex": False, "text.parse_math": False}), _BoundedBuffer() as buffer:
        fig = None
        try:
            fig = _summary_figure(frame, payload, Figure, patches)
            if payload["as_pdf"]:
                with PdfPages(buffer, metadata={"Title": "De-identified insurance planning report"}) as pdf:
                    pdf.savefig(fig); fig.clear()
                    for block in (frame.iloc[:21], frame.iloc[21:]):
                        fig = _table_figure(block, Figure)
                        pdf.savefig(fig); fig.clear()
            else:
                fig.savefig(buffer, format="png", dpi=150)
            return buffer.getvalue()
        finally:
            if fig is not None:
                fig.clear()


def build_client_pdf(export_df, gap0, coverage0, rolloff, insight_plain, client_name="", as_pdf=True):
    """Return a 3-page PDF (or summary PNG). One worker per server process.

    No global data cache. At capacity, fail promptly instead of queuing clients.
    The Linux worker has a 1 GiB virtual-memory cap and a 15-second CPU cap;
    the parent enforces a 20-second wall-clock deadline on every platform.
    """
    if client_name:
        raise ReportError("Client identifiers are not supported")
    if export_df.shape != (41, len(SHORT)):
        raise ReportError("Report dimensions exceed supported bounds")
    payload = {"rows": export_df.to_dict(orient="records"), "gap0": float(gap0),
               "coverage0": float(coverage0), "rolloff": float(rolloff),
               "insight": insight_plain, "as_pdf": as_pdf}
    _validate_payload(payload)
    raw = json.dumps(payload, allow_nan=False).encode("utf-8")
    if len(raw) > MAX_INPUT_BYTES:
        raise ReportError("Report input is too large")
    if not _RENDER_SLOT.acquire(blocking=False):
        raise ReportError("Report renderer is busy")
    try:
        with tempfile.TemporaryDirectory(prefix="policy-fonts-") as cache:
            env = os.environ.copy()
            env.update(MPLCONFIGDIR=cache, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MPLBACKEND="Agg")
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker"],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
            try:
                output, _ = process.communicate(raw, timeout=REPORT_TIMEOUT_SECONDS)
            except BaseException:
                process.kill(); process.communicate()
                raise
            if process.returncode or not output or len(output) > MAX_OUTPUT_BYTES:
                raise ReportError("Report generation failed")
            return output
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReportError("Report generation unavailable") from None
    finally:
        _RENDER_SLOT.release()


def _worker():
    if sys.platform.startswith("linux"):
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (1024 ** 3, 1024 ** 3))
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        return 1
    try:
        payload = json.loads(raw)
        _validate_payload(payload)
        sys.stdout.buffer.write(_render(payload))
        return 0
    except Exception:
        return 1  # Never emit input values, exception text, or a traceback.


if __name__ == "__main__":
    raise SystemExit(_worker() if sys.argv[1:] == ["--worker"] else 1)
