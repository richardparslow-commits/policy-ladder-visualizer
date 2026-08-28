import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date

from pdf_report import build_client_pdf

# --- BRANDING & STYLES ---
PRIMARY_RED = "#CC0700"
ACCENT_BLUE = "#1E88E5"
ACCENT_GREEN = "#2E7D32"
LEGACY_GRAY = "#374151"
MODEL_YEARS = 40  # Model horizon in years

st.set_page_config(page_title="Life Policy Pilot | Gap Analysis Pro", layout="wide")

# Custom CSS
st.markdown(f"""
    <style>
    .stMetric {{ background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; border-top: 5px solid {PRIMARY_RED}; }}
    [data-testid="stSidebar"] {{ background-color: #f8f9fa; }}
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: FLIGHT PARAMETERS ---
with st.sidebar:
    st.header("📍 Flight Parameters")
    client_name = st.text_input("Client / Family Name (optional)", placeholder="e.g., The Smith Family", key="client_name")
    
    with st.expander("🏠 Debt & Mortgage (D&M)", expanded=True):
        mortgage = st.number_input("Remaining Mortgage ($)", value=400000, step=10000)
        mtg_rate = st.number_input("Mortgage Interest Rate (%)", value=6.0, min_value=0.0, max_value=25.0, step=0.125, format="%.3f")
        mtg_years = st.slider("Mortgage Years Left", 5, 30, 20)
        other_debt = st.number_input("Auto/Personal/Credit Debt ($)", value=25000)
        debt_years = st.slider("Debt Payoff Years", 1, 15, 5)

    with st.expander("💰 Income Replacement (I)", expanded=True):
        income_req = st.number_input("Annual Income to Replace ($)", value=75000)
        income_years = st.slider("Years of Replacement", 5, 30, 15)

    with st.expander("🎓 Milestones & Future (E)", expanded=False):
        college_total = st.number_input("Total College Fund ($)", value=100000)
        college_start = st.slider("College Starts In (Years)", 0, 25, 13)
        college_years = st.slider("Years of College to Fund", 0, 8, 4)
        childcare_annual = st.number_input("Annual Childcare Cost ($)", value=15000)
        childcare_years = st.slider("Years of Childcare", 0, 15, 5)
        final_expenses = st.number_input("Final Expenses (Funeral) ($)", value=20000)

    with st.expander("🏦 Financial Assets (Subtract)", expanded=True):
        liquid_assets = st.number_input("Cash/Savings/Investments ($)", value=50000)
        existing_life = st.number_input("Current Life Insurance ($)", value=100000)
        existing_life_type = st.selectbox("Existing Policy Type", ["Term (expires)", "Permanent (never expires)"])
        if existing_life_type.startswith("Term"):
            existing_life_years = st.slider("Existing Policy Years Remaining", 1, MODEL_YEARS, 10)
        else:
            existing_life_years = MODEL_YEARS + 1  # Permanent: outlives the model window

    st.header("🪜 Proposed Ladder")
    policies = []
    for i in range(1, 4):
        with st.expander(f"Proposed Policy #{i}", expanded=(i==1)):
            p_active = st.checkbox(f"Active {i}", value=(i==1), key=f"act{i}")
            p_amt = st.number_input(f"Benefit {i} ($)", value=250000 if i==1 else 0, key=f"amt{i}")
            p_type = st.selectbox(f"Type {i}", ["Term", "Permanent (IUL/WL)"], key=f"type{i}")
            p_prem = st.number_input(f"Annual Premium {i} ($)", value=350 if i==1 else 0, key=f"prem{i}")
            if "Term" in p_type:
                p_term = st.selectbox(f"Term {i}", [10, 15, 20, 25, 30], index=2, key=f"term{i}")
            else:
                p_term = MODEL_YEARS + 1  # Permanent: outlives the model window
            if p_active: policies.append({"amt": p_amt, "term": p_term, "prem": p_prem})

# --- LOGIC: CALCULATING THE GAP ---
def mortgage_balance(principal, annual_rate_pct, years_left, elapsed_years):
    """Standard amortized remaining balance: declines slowly early (interest-heavy payments), fast late."""
    n = years_left * 12
    if principal <= 0 or n <= 0:
        return 0.0
    r = annual_rate_pct / 100 / 12
    t = min(elapsed_years * 12, n)
    if r == 0:  # 0% rate: paydown is linear
        return max(0.0, principal * (1 - t / n))
    growth = (1 + r) ** n
    return max(0.0, principal * (growth - (1 + r) ** t) / (growth - 1))

years = list(range(0, MODEL_YEARS + 1))
data = []

for yr in years:
    # 1. Total Liabilities
    m = mortgage_balance(mortgage, mtg_rate, mtg_years, yr)
    i = income_req if yr < income_years else 0
    c = childcare_annual if yr < childcare_years else 0
    # College is a timed block: spread evenly over the funded years (not a day-one lump)
    college = (college_total / college_years) if (college_years > 0 and college_start <= yr < college_start + college_years) else 0
    d = max(0.0, other_debt * (1 - yr / debt_years)) if yr < debt_years else 0
    total_liabilities = m + i + c + college + d + final_expenses
    
    # 2. Net Insurance Gap (Liabilities - Assets)
    # Existing life coverage only offsets while it is in force — a lapsing term policy stops counting
    life_offset = existing_life if yr < existing_life_years else 0
    net_gap = max(0, total_liabilities - (liquid_assets + life_offset))
    
    # 3. Coverage Calculation (a "term-N" policy covers death in years 0..N-1)
    total_coverage = sum(p['amt'] for p in policies if yr < p['term'])
    annual_premium = sum(p['prem'] for p in policies if yr < p['term'])
    
    data.append({
        "Year": yr,
        "Mortgage": m, "Debt": d, "Income": i, "Childcare": c, "College": college,
        "Final Expenses": final_expenses,
        "Total Liabilities": total_liabilities,
        "Existing Resources": liquid_assets + life_offset,
        "Gap": net_gap, "Total Coverage": total_coverage,
        "Premium": annual_premium
    })

df = pd.DataFrame(data)

# --- DASHBOARD HEADER ---
st.markdown(
    f"""
    <div style="display:flex; align-items:center; flex-wrap:wrap; gap:16px; margin:0.2rem 0 0.4rem 0;">
        <img src="https://flagcdn.com/w80/us-tx.png" alt="Texas flag"
             style="height:42px; width:auto; border-radius:3px; box-shadow:0 1px 3px rgba(0,0,0,0.2);">
        <h1 style="margin:0; font-size:2.25rem; font-weight:700; line-height:1.4; letter-spacing:-0.02em; color:inherit; font-family:inherit;">
            🛡️ Life Insurance Gap Analysis
        </h1>
        <a href="https://lifeinsurancebrokeradvocate.com/contact" target="_blank" rel="noopener noreferrer"
           style="background:{PRIMARY_RED}; color:#ffffff; text-decoration:none; font-size:0.95rem; font-weight:600;
                  padding:0.5rem 1.1rem; border-radius:0.5rem; white-space:nowrap; box-shadow:0 1px 2px rgba(0,0,0,0.15);">
            Get a Quote ↗
        </a>
        <span style="flex:1;"></span>
        <img src="https://flagcdn.com/w80/us.png" alt="American flag"
             style="height:42px; width:auto; border-radius:3px; box-shadow:0 1px 3px rgba(0,0,0,0.2);">
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown("Precision underwriting means matching your coverage to your *actual* financial shortfall.")

annual_rolloff = df['Premium'].iloc[0] - df['Premium'].iloc[-1]

m1, m2, m3 = st.columns(3)
m1.metric("Current Insurance Gap", f"${df['Gap'][0]:,.0f}")
m2.metric("New Ladder Coverage", f"${df['Total Coverage'][0]:,.0f}")
m3.metric("Annual Premium Roll-Off", f"${annual_rolloff:,.0f}/yr", delta="As terms expire", delta_color="off")
st.caption("💡 Roll-off is the annual premium you stop paying once terms expire inside the model window — it is not a savings comparison against one large policy.")

# --- VISUALIZER ---
fig = go.Figure()

# The "Net Gap" Area (The Target)
fig.add_trace(go.Scatter(
    x=df['Year'], y=df['Gap'], 
    name='Required Insurance (Gap)', 
    fill='tozeroy', mode='none', fillcolor='#D1D5DB'
))

# The Proposed Ladder (The Solution)
fig.add_trace(go.Scatter(
    x=df['Year'], y=df['Total Coverage'], 
    name='Proposed Policy Ladder', 
    line=dict(color=PRIMARY_RED, width=5, shape='hv'),
    mode='lines'
))

fig.update_layout(
    hovermode="x unified", height=600,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(title="Dollar Amount ($)", gridcolor="#f0f0f0"),
    xaxis=dict(title="Years into Future", range=[0, MODEL_YEARS])
)

st.plotly_chart(fig, use_container_width=True)

# --- INSIGHTS ---
life_expiry_note = f" — but it **expires in year {existing_life_years}**" if existing_life_years <= MODEL_YEARS else ""
insight_md = f"💡 **Fiduciary Insight:** Your family has **${liquid_assets:,.0f}** in liquid resources plus **${existing_life:,.0f}** of existing life coverage{life_expiry_note}. We only need to bridge the remaining **${df['Gap'][0]:,.0f}** today. Using a laddered approach ensures you aren't over-insured as your mortgage, childcare, and college obligations disappear."
st.info(insight_md)

if df['Total Coverage'][0] < df['Gap'][0]:
    st.warning(f"⚠️ **Coverage Shortfall:** Your proposed ladder is currently **${df['Gap'][0] - df['Total Coverage'][0]:,.0f}** below your calculated need.")

# --- CLIENT EXPORTS ---
export = df.rename(columns={
    "Year": "Year",
    "Mortgage": "Mortgage Balance ($)",
    "Debt": "Other Debt ($)",
    "Income": "Income Replacement ($)",
    "Childcare": "Childcare ($)",
    "College": "College ($)",
    "Final Expenses": "Final Expenses ($)",
    "Total Liabilities": "Total Liabilities ($)",
    "Existing Resources": "Existing Resources ($)",
    "Gap": "Net Gap - Required Insurance ($)",
    "Total Coverage": "Proposed Ladder Coverage ($)",
    "Premium": "Annual Premium ($)",
}).astype(int)
insight_plain = insight_md.replace("💡 ", "").replace("**", "")

pdf_bytes = build_client_pdf(
    export,
    int(df["Gap"][0]), int(df["Total Coverage"][0]), annual_rolloff,
    insight_plain,
    client_name=client_name,
)

csv_col, pdf_col = st.columns(2)
with csv_col:
    st.download_button(
        "📄 Download year-by-year table (CSV)",
        data=export.to_csv(index=False).encode("utf-8"),
        file_name=f"gap_analysis_{date.today():%Y-%m-%d}.csv",
        mime="text/csv",
        key="csv_export",
        help="Full year-by-year breakdown of needs vs. coverage, ready for client meetings.",
    )
with pdf_col:
    st.download_button(
        "📕 Download one-page PDF report",
        data=pdf_bytes,
        file_name=f"gap_analysis_report_{date.today():%Y-%m-%d}.pdf",
        mime="application/pdf",
        key="pdf_export",
        help="Client handout: headline metrics, the gap-vs-ladder chart, and the full year-by-year table on one page.",
    )

# --- BOTTOM CTA ---
st.markdown(
    f"""
    <div style="text-align:center; margin:1.6rem 0 0.4rem 0;">
        <p style="margin:0 0 0.6rem 0; color:{LEGACY_GRAY}; font-size:1.05rem;">Ready to take the next step?</p>
        <a href="https://lifeinsurancebrokeradvocate.com/contact" target="_blank" rel="noopener noreferrer"
           style="background:{PRIMARY_RED}; color:#ffffff; text-decoration:none; font-size:1.05rem; font-weight:600;
                  padding:0.7rem 2rem; border-radius:0.5rem; white-space:nowrap; box-shadow:0 1px 3px rgba(0,0,0,0.2);">
            Get a Quote ↗
        </a>
    </div>
    """,
    unsafe_allow_html=True,
)
