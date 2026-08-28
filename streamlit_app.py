import json
import urllib.parse
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, datetime

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
    /* App header: flags at the corners, title + CTA beside each other */
    .app-header {{ display:flex; align-items:center; flex-wrap:wrap; gap:16px; margin:0.2rem 0 0.4rem 0; }}
    .app-header h1 {{ margin:0; font-size:clamp(1.3rem, 3.6vw, 2.25rem); font-weight:700; line-height:1.4; letter-spacing:-0.02em; color:inherit; font-family:inherit; }}
    .app-header .flag {{ height:42px; width:auto; border-radius:3px; box-shadow:0 1px 3px rgba(0,0,0,0.2); }}
    .app-header .spacer {{ flex:1; }}
    .app-cta {{ background:{PRIMARY_RED}; color:#ffffff; text-decoration:none; font-size:0.95rem; font-weight:600; padding:0.5rem 1.1rem; border-radius:0.5rem; white-space:nowrap; box-shadow:0 1px 2px rgba(0,0,0,0.15); }}
    /* Phones: flags stay at the corners, title and CTA stack centered below */
    @media (max-width: 700px) {{
        .app-header {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
        .app-header .flag {{ height:34px; }}
        .app-header .flag:first-child {{ grid-column:1; grid-row:1; justify-self:start; }}
        .app-header .flag:last-child {{ grid-column:2; grid-row:1; justify-self:end; }}
        .app-header .spacer {{ display:none; }}
        .app-header > div:has(> h1) {{ grid-column:1 / -1; grid-row:2; width:100%; text-align:center; }}
        .app-header > div:has(> h1) h1 {{ font-size:1.55rem; }}
        .app-header .app-cta {{ grid-column:1 / -1; grid-row:3; justify-self:center; font-size:1rem; padding:0.65rem 1.4rem; }}
    }}
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: GUIDED INPUTS ---
# Preset scenarios let new users see a sensible starting point in one click.
PRESETS = {
    "Custom (default)": {},
    "Young family with mortgage": {
        "mortgage": 350000, "mtg_rate": 6.25, "mtg_years": 30, "other_debt": 15000, "debt_years": 4,
        "income_req": 90000, "income_years": 20,
        "childcare_annual": 18000, "childcare_years": 6,
        "college_total": 120000, "college_start": 14, "college_years": 4,
        "final_expenses": 25000, "liquid_assets": 40000, "existing_life": 100000,
        "existing_life_type": "Term (expires)", "existing_life_years": 20,
        "act1": True, "amt1": 300000, "type1": "Term", "prem1": 420, "term1": 20,
        "act2": True, "amt2": 200000, "type2": "Term", "prem2": 180, "term2": 30,
        "act3": False, "amt3": 0, "type3": "Term", "prem3": 0, "term3": 20,
    },
    "Empty nester": {
        "mortgage": 80000, "mtg_rate": 4.5, "mtg_years": 10, "other_debt": 5000, "debt_years": 2,
        "income_req": 40000, "income_years": 5,
        "childcare_annual": 0, "childcare_years": 0,
        "college_total": 0, "college_start": 0, "college_years": 0,
        "final_expenses": 25000, "liquid_assets": 200000, "existing_life": 75000,
        "existing_life_type": "Permanent (never expires)", "existing_life_years": 41,
        "act1": True, "amt1": 150000, "type1": "Term", "prem1": 220, "term1": 10,
        "act2": False, "amt2": 0, "type2": "Term", "prem2": 0, "term2": 20,
        "act3": False, "amt3": 0, "type3": "Term", "prem3": 0, "term3": 20,
    },
    "Sole breadwinner": {
        "mortgage": 300000, "mtg_rate": 5.75, "mtg_years": 25, "other_debt": 20000, "debt_years": 5,
        "income_req": 120000, "income_years": 25,
        "childcare_annual": 20000, "childcare_years": 8,
        "college_total": 150000, "college_start": 12, "college_years": 4,
        "final_expenses": 20000, "liquid_assets": 25000, "existing_life": 50000,
        "existing_life_type": "Term (expires)", "existing_life_years": 10,
        "act1": True, "amt1": 500000, "type1": "Term", "prem1": 550, "term1": 25,
        "act2": True, "amt2": 250000, "type2": "Term", "prem2": 220, "term2": 30,
        "act3": False, "amt3": 0, "type3": "Term", "prem3": 0, "term3": 20,
    },
}

with st.sidebar:
    st.header("📝 Your situation")
    st.caption("Answer the questions in order — or start from a preset.")

    # Restore a shared scenario from the URL, if one was opened.
    raw_scenario = st.query_params.get("scenario", "")
    if raw_scenario:
        restored = None
        try:
            restored = json.loads(raw_scenario)
        except Exception:
            try:
                restored = json.loads(urllib.parse.unquote(raw_scenario))
            except Exception:
                restored = None
        if restored:
            st.session_state["preset"] = "Custom (default)"
            for k, v in restored.items():
                if k == "policies" and isinstance(v, list):
                    for idx, pol in enumerate(v, start=1):
                        if isinstance(pol, dict):
                            st.session_state[f"act{idx}"] = bool(pol.get("active", True))
                            st.session_state[f"amt{idx}"] = pol.get("amt", 0)
                            st.session_state[f"type{idx}"] = pol.get("type", "Term")
                            st.session_state[f"prem{idx}"] = pol.get("prem", 0)
                            st.session_state[f"term{idx}"] = pol.get("term", 20)
                else:
                    st.session_state[k] = v

    preset = st.selectbox(
        "Start from a preset (optional)",
        list(PRESETS),
        key="preset",
        help="Pick a realistic starting point, then adjust any numbers below.",
    )
    if preset != "Custom (default)":
        for k, v in PRESETS[preset].items():
            st.session_state[k] = v

    client_name = st.text_input(
        "Client / Family Name (optional)",
        placeholder="e.g., The Smith Family",
        key="client_name",
        help="Shown on the PDF report header.",
    )

    tab_family, tab_money, tab_coverage, tab_advanced = st.tabs(
        ["1 · Family", "2 · Money & debts", "3 · Coverage", "4 · Advanced"]
    )

    with tab_family:
        income_req = st.number_input(
            "Yearly income your family would need", value=75000, step=5000, key="income_req",
            help="What your family would need each year if you were gone — usually the income you earn.",
        )
        income_years = st.slider(
            "How many years it must last", 5, 30, 15, key="income_years",
            help="Often until the kids are independent or your spouse retires.",
        )
        childcare_annual = st.number_input(
            "Childcare cost per year", value=15000, step=1000, key="childcare_annual",
            help="What childcare costs today, per year.",
        )
        childcare_years = st.slider(
            "Years of childcare needed", 0, 15, 5, key="childcare_years",
            help="How many more years you expect to pay for childcare.",
        )
        college_total = st.number_input(
            "Total college fund for the kids", value=100000, step=5000, key="college_total",
            help="The total you want set aside for college across all kids.",
        )
        college_start = st.slider(
            "Years until college starts", 0, 25, 13, key="college_start",
            help="Years from now until the first tuition payment is due.",
        )
        college_years = st.slider(
            "Years of college to cover", 0, 8, 4, key="college_years",
            help="How many years of tuition this fund covers.",
        )
        final_expenses = st.number_input(
            "Funeral / final expenses", value=20000, step=1000, key="final_expenses",
            help="One-time costs like funeral, probate, and final medical bills.",
        )

    with tab_money:
        mortgage = st.number_input(
            "Money still owed on your mortgage", value=400000, step=10000, key="mortgage",
            help="What you still owe on your home today.",
        )
        mtg_years = st.slider(
            "Years left on your mortgage", 5, 30, 20, key="mtg_years",
            help="How many years remain on your mortgage.",
        )
        other_debt = st.number_input(
            "Other debts (car, cards, loans)", value=25000, step=5000, key="other_debt",
            help="Car loans, credit cards, personal loans — anything you owe besides the mortgage.",
        )
        liquid_assets = st.number_input(
            "Cash, savings & investments", value=50000, step=5000, key="liquid_assets",
            help="Money that could be used right away to cover expenses.",
        )

    with tab_coverage:
        existing_life = st.number_input(
            "Life insurance you already own", value=100000, step=10000, key="existing_life",
            help="The death benefit of life insurance you already have.",
        )
        st.markdown("**🪜 Your proposed policies**")
        policies = []
        policy_widgets = []
        for i in range(1, 4):
            with st.expander(f"Policy #{i}", expanded=(i == 1)):
                p_active = st.checkbox("Include this policy?", value=(i == 1), key=f"act{i}",
                                       help="Untick to leave this slot empty.")
                p_amt = st.number_input("Amount it pays out ($)", value=250000 if i == 1 else 0,
                                        step=10000, key=f"amt{i}",
                                        help="The death benefit this policy pays out.")
                p_type = st.selectbox("Kind of policy", ["Term", "Permanent (whole life)"],
                                      key=f"type{i}",
                                      help="Term lasts a set number of years; permanent lasts your whole life.")
                p_prem = st.number_input("Cost per year ($)", value=350 if i == 1 else 0,
                                         step=50, key=f"prem{i}",
                                         help="What you pay each year for this policy.")
                if "Term" in p_type:
                    p_term = st.selectbox("How long it lasts (years)", [10, 15, 20, 25, 30],
                                          index=2, key=f"term{i}",
                                          help="How many years the term policy stays in force.")
                else:
                    p_term = MODEL_YEARS + 1  # Permanent: outlives the model window
                policy_widgets.append({"active": p_active, "amt": p_amt, "type": p_type,
                                       "prem": p_prem, "term": p_term})
                if p_active:
                    policies.append({"amt": p_amt, "term": p_term, "prem": p_prem})

    with tab_advanced:
        mtg_rate = st.number_input(
            "Your mortgage interest rate (%)", value=6.0, min_value=0.0, max_value=25.0,
            step=0.125, format="%.3f", key="mtg_rate",
            help="Used to calculate the real remaining mortgage balance over time. Check your statement.",
        )
        debt_years = st.slider(
            "Years until those debts are paid off", 1, 15, 5, key="debt_years",
            help="How many years until your other debts are fully paid off.",
        )
        existing_life_type = st.selectbox(
            "What kind of policy is it?", ["Term (expires)", "Permanent (never expires)"],
            key="existing_life_type",
            help="Term policies expire; permanent (whole life) policies stay in force.",
        )
        if existing_life_type.startswith("Term"):
            existing_life_years = st.slider(
                "Years left on that policy", 1, MODEL_YEARS, 10, key="existing_life_years",
                help="Years before this term policy lapses. Choose Permanent above if it never expires.",
            )
        else:
            existing_life_years = MODEL_YEARS + 1  # Permanent: outlives the model window

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


def build_df(mortgage, mtg_rate, mtg_years, other_debt, debt_years, income_req, income_years,
             college_total, college_start, college_years, childcare_annual, childcare_years,
             final_expenses, liquid_assets, existing_life, existing_life_years, policies):
    """Year-by-year model: liabilities, net gap, ladder coverage, and premiums."""
    data = []
    for yr in range(0, MODEL_YEARS + 1):
        m = mortgage_balance(mortgage, mtg_rate, mtg_years, yr)
        i = income_req if yr < income_years else 0
        c = childcare_annual if yr < childcare_years else 0
        # College is a timed block: spread evenly over the funded years (not a day-one lump)
        college = (college_total / college_years) if (college_years > 0 and college_start <= yr < college_start + college_years) else 0
        d = max(0.0, other_debt * (1 - yr / debt_years)) if yr < debt_years else 0
        total_liabilities = m + i + c + college + d + final_expenses

        # Existing life coverage only offsets while it is in force — a lapsing term policy stops counting
        life_offset = existing_life if yr < existing_life_years else 0
        net_gap = max(0, total_liabilities - (liquid_assets + life_offset))

        # A "term-N" policy covers death in years 0..N-1
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
    return pd.DataFrame(data)


df = build_df(mortgage, mtg_rate, mtg_years, other_debt, debt_years, income_req, income_years,
              college_total, college_start, college_years, childcare_annual, childcare_years,
              final_expenses, liquid_assets, existing_life, existing_life_years, policies)


def snapshot_inputs():
    return {
        "mortgage": mortgage, "mtg_rate": mtg_rate, "mtg_years": mtg_years,
        "other_debt": other_debt, "debt_years": debt_years,
        "income_req": income_req, "income_years": income_years,
        "college_total": college_total, "college_start": college_start, "college_years": college_years,
        "childcare_annual": childcare_annual, "childcare_years": childcare_years,
        "final_expenses": final_expenses,
        "liquid_assets": liquid_assets, "existing_life": existing_life,
        "existing_life_type": existing_life_type, "existing_life_years": existing_life_years,
        "policies": policy_widgets,
    }


def df_from_snapshot(snap):
    kw = {k: v for k, v in snap.items() if k in (
        "mortgage", "mtg_rate", "mtg_years", "other_debt", "debt_years", "income_req",
        "income_years", "college_total", "college_start", "college_years",
        "childcare_annual", "childcare_years", "final_expenses", "liquid_assets",
        "existing_life", "existing_life_years")}
    saved_policies = [{"amt": p["amt"], "term": p["term"], "prem": p["prem"]}
                      for p in snap.get("policies", []) if p.get("active")]
    return build_df(policies=saved_policies, **kw)


# --- DASHBOARD HEADER ---
st.markdown(
    f"""
    <div class="app-header">
        <img src="https://flagcdn.com/w80/us-tx.png" alt="Texas flag" class="flag">
        <h1>🛡️ Life Insurance Gap Analysis</h1>
        <a class="app-cta" href="https://lifeinsurancebrokeradvocate.com/contact" target="_blank" rel="noopener noreferrer">Get a Quote ↗</a>
        <span class="spacer"></span>
        <img src="https://flagcdn.com/w80/us.png" alt="American flag" class="flag">
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

# --- SCENARIO TOOLS: save, compare, share ---
tool1, tool2, tool3 = st.columns(3)
with tool1:
    if st.button("📌 Save this scenario", key="save_scenario", use_container_width=True,
                 help="Remember these numbers so you can compare them against another option."):
        st.session_state["saved_scenario"] = snapshot_inputs()
        st.session_state["saved_at"] = datetime.now().strftime("%H:%M")
        st.toast(f"Scenario saved at {st.session_state['saved_at']}")
with tool2:
    if st.button("🔗 Shareable link", key="share_link", use_container_width=True,
                 help="Encodes this scenario in the address bar — send it or bookmark it."):
        st.query_params["scenario"] = urllib.parse.quote(json.dumps(snapshot_inputs(), default=str))
        st.toast("Scenario link ready — copy it from the browser address bar.")
# Read the saved snapshot after the handlers above so the toggle appears on the same run as the save.
saved = st.session_state.get("saved_scenario")
with tool3:
    if saved is not None:
        compare_on = st.toggle("Compare with saved", key="compare_toggle",
                               help="Overlay the saved scenario on the chart and compare the numbers.")
    else:
        compare_on = False
        st.caption("Save a scenario to compare two options.")

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

saved_df = None
if compare_on and saved is not None:
    saved_df = df_from_snapshot(saved)
    fig.add_trace(go.Scatter(
        x=saved_df['Year'], y=saved_df['Gap'],
        name='Saved: Required (Gap)',
        line=dict(color=ACCENT_BLUE, width=2, dash='dot'),
    ))
    fig.add_trace(go.Scatter(
        x=saved_df['Year'], y=saved_df['Total Coverage'],
        name='Saved: Ladder',
        line=dict(color=ACCENT_GREEN, width=2, dash='dot'),
    ))

fig.update_layout(
    hovermode="x unified", height=600,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(title="Dollar Amount ($)", gridcolor="#f0f0f0"),
    xaxis=dict(title="Years into Future", range=[0, MODEL_YEARS])
)

st.plotly_chart(fig, use_container_width=True)

if saved_df is not None:
    diff0 = int(df['Gap'][0] - saved_df['Gap'][0])
    st.caption(f"🔁 vs. saved scenario — today's gap differs by **${diff0:+,.0f}** "
               f"(saved: ${saved_df['Gap'][0]:,.0f}, current: ${df['Gap'][0]:,.0f}).")

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
gap_today = int(df["Gap"][0])
if gap_today > 0:
    cta_prompt = f"Your family's coverage gap is real — <b>${gap_today:,.0f}</b> today. See how affordable closing it can be."
else:
    cta_prompt = "Your coverage needs are covered today — but life changes. Get a fresh second opinion."
st.markdown(
    f"""
    <div style="text-align:center; margin:1.6rem 0 0.4rem 0;">
        <p style="margin:0 0 0.6rem 0; color:{LEGACY_GRAY}; font-size:1.05rem;">{cta_prompt}</p>
        <a href="https://lifeinsurancebrokeradvocate.com/contact" target="_blank" rel="noopener noreferrer"
           style="background:{PRIMARY_RED}; color:#ffffff; text-decoration:none; font-size:1.05rem; font-weight:600;
                  padding:0.7rem 2rem; border-radius:0.5rem; white-space:nowrap; box-shadow:0 1px 3px rgba(0,0,0,0.2);">
            Get a Quote ↗
        </a>
    </div>
    """,
    unsafe_allow_html=True,
)
