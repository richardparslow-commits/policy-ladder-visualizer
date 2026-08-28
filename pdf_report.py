"""One-page client PDF report for the Life Policy Pilot gap analysis.

Landscape letter page: headline metric cards, the gap-vs-ladder chart, and the
full year-by-year table split into two side-by-side blocks (today → year 20,
year 21 → 40) with abbreviated column headers.

Streamlit-free on purpose: takes plain pandas/numpy values so it can be unit
tested or rendered headlessly. Set as_pdf=False to get an identical PNG
(handy for previews and tests).
"""
import io
import textwrap
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

PRIMARY_RED = "#CC0700"
GAP_FILL = "#D1D5DB"
INK = "#374151"

# Full column name (as produced by streamlit_app.py's export frame) → short header
SHORT = {
    "Year": "Yr",
    "Mortgage Balance ($)": "Mtg",
    "Other Debt ($)": "Debt",
    "Income Replacement ($)": "Income",
    "Childcare ($)": "Child",
    "College ($)": "College",
    "Final Expenses ($)": "Final",
    "Total Liabilities ($)": "Total Liab",
    "Existing Resources ($)": "Resources",
    "Net Gap - Required Insurance ($)": "Net Gap",
    "Proposed Ladder Coverage ($)": "Coverage",
    "Annual Premium ($)": "Premium",
}

LEGEND = (
    "Mtg = mortgage balance · Debt = other debt · Income = income replacement · Child = childcare · "
    "Final = final expenses · Total Liab = total liabilities · Resources = existing resources · "
    "Net Gap = required insurance · Coverage = proposed ladder · Premium = annual premium. All figures in US$."
)


def _fmt(v, commas=True):
    return f"{int(v):,}" if commas else str(int(v))


def _draw_chart(ax, export):
    years = export["Year"]
    gap = export["Net Gap - Required Insurance ($)"]
    cov = export["Proposed Ladder Coverage ($)"]
    ax.fill_between(years, gap, color=GAP_FILL, label="Required Insurance (Gap)")
    ax.step(years, cov, where="post", color=PRIMARY_RED, linewidth=2.5, label="Proposed Policy Ladder")
    ax.set_xlim(0, int(years.max()))
    ax.set_title("Required insurance vs. proposed ladder, years 0–40", fontsize=8, loc="left", color=INK, pad=4)
    ax.set_xlabel("Years into Future", fontsize=7, color=INK)
    ax.set_ylabel("Dollar Amount ($)", fontsize=7, color=INK)
    ax.tick_params(labelsize=6.5, colors=INK)
    ax.yaxis.set_major_formatter(lambda x, pos: f"${x / 1000:,.0f}k")
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", fontsize=6.5, frameon=False)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def _add_table(fig, rect, block, caption):
    fig.text(rect[0], rect[1] + rect[3] + 0.008, caption, fontsize=7.5, fontweight="bold", color=INK)
    ax = fig.add_axes(rect)
    ax.axis("off")
    data = block.rename(columns=SHORT)
    cols = list(data.columns)
    cells = [[_fmt(data[c].iloc[i], commas=(c != "Yr")) for c in cols] for i in range(len(data))]
    tbl = ax.table(cellText=cells, colLabels=cols, cellLoc="right", loc="upper center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(4.8)
    tbl.auto_set_column_width(range(len(cols)))
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#e5e7eb")
        cell.set_linewidth(0.3)
        if r == 0:
            cell.set_facecolor("#EEF2F7")
            cell.set_text_props(fontweight="bold", fontsize=4.6, color=INK)
        elif r % 2 == 0:
            cell.set_facecolor("#F8FAFC")
    return ax


def build_client_pdf(export_df, gap0, coverage0, rolloff, insight_plain, as_pdf=True):
    """Render the one-page report. export_df is the app's labeled/rounded export frame."""
    fig = plt.figure(figsize=(11, 8.5))

    # Header
    fig.text(0.06, 0.955, "Life Insurance Gap Analysis", fontsize=17, fontweight="bold",
             color=PRIMARY_RED, ha="left", va="center")
    fig.text(0.06, 0.925, f"Prepared {date.today():%B %d, %Y}  ·  Needs vs. coverage, year by year",
             fontsize=8, color=INK, ha="left")

    # Metric cards
    cards = [
        ("Current Insurance Gap", f"${gap0:,.0f}", "#FDECEA"),
        ("Proposed Ladder Coverage", f"${coverage0:,.0f}", "#EAF2FB"),
        ("Annual Premium Roll-Off", f"${rolloff:,.0f} / yr", "#EAF7EC"),
    ]
    card_w, gap_w = 0.28, 0.025
    for i, (label, value, color) in enumerate(cards):
        x = 0.06 + i * (card_w + gap_w)
        fig.patches.append(mpatches.FancyBboxPatch(
            (x, 0.835), card_w, 0.068, boxstyle="round,pad=0.004",
            facecolor=color, edgecolor="#e2e8f0", linewidth=0.8, transform=fig.transFigure))
        fig.text(x + 0.008, 0.878, label, fontsize=7, color=INK, ha="left")
        fig.text(x + 0.008, 0.847, value, fontsize=13, fontweight="bold", color="#111827", ha="left")

    # Chart
    _draw_chart(fig.add_axes([0.07, 0.505, 0.87, 0.265]), export_df)

    # Table split into two side-by-side blocks
    half = (len(export_df) + 1) // 2
    _add_table(fig, [0.06, 0.145, 0.43, 0.275], export_df.iloc[:half], "Year-by-year detail — today to year 20")
    _add_table(fig, [0.535, 0.145, 0.43, 0.275], export_df.iloc[half:],
               f"Year-by-year detail — year {int(export_df['Year'].iloc[half])} to 40")

    # Legend, insight, footer
    fig.text(0.06, 0.125, LEGEND, fontsize=5, color="#6b7280", ha="left")
    fig.text(0.06, 0.09, textwrap.fill(insight_plain, 150), fontsize=6.5, color=INK, ha="left", va="top")
    fig.text(0.06, 0.035, "Generated by Life Policy Pilot · policy-ladder-visualizer.streamlit.app",
             fontsize=5.5, color="#9ca3af", ha="left")

    buf = io.BytesIO()
    fig.savefig(buf, format="pdf" if as_pdf else "png", dpi=200)
    plt.close(fig)
    return buf.getvalue()
