import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- BRANDING & STYLES ---
PRIMARY_RED = "#CC0700"
ACCENT_BLUE = "#1E88E5"
ACCENT_GREEN = "#2E7D32"
LEGACY_GRAY = "#374151"

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
    
    with st.expander("🏠 Debt & Mortgage (D&M)", expanded=True):
        mortgage = st.number_input("Remaining Mortgage ($)", value=400000, step=10000)
        mtg_years = st.slider("Mortgage Years Left", 5, 30, 20)
        other_debt = st.number_input("Auto/Personal/Credit Debt ($)", value=25000)

    with st.expander("💰 Income Replacement (I)", expanded=True):
        income_req = st.number_input("Annual Income to Replace ($)", value=75000)
        income_years = st.slider("Years of Replacement", 5, 30, 15)

    with st.expander("🎓 Milestones & Future (E)", expanded=False):
        college_total = st.number_input("Total College Fund ($)", value=100000)
        childcare_annual = st.number_input("Annual Childcare Cost ($)", value=15000)
        childcare_years = st.slider("Years of Childcare", 0, 15, 5)
        final_expenses = st.number_input("Final Expenses (Funeral) ($)", value=20000)

    with st.expander("🏦 Financial Assets (Subtract)", expanded=True):
        liquid_assets = st.number_input("Cash/Savings/Investments ($)", value=50000)
        existing_life = st.number_input("Current Life Insurance ($)", value=100000)

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
                p_term = 40 # Permanent horizon
            if p_active: policies.append({"amt": p_amt, "term": p_term, "prem": p_prem})

# --- LOGIC: CALCULATING THE GAP ---
years = list(range(0, 41))
data = []

for yr in years:
    # 1. Total Liabilities
    m = max(0, mortgage * (1 - (yr / mtg_years))) if yr <= mtg_years else 0
    i = income_req if yr <= income_years else 0
    c = childcare_annual if yr <= childcare_years else 0
    total_liabilities = m + i + c + college_total + final_expenses + other_debt
    
    # 2. Net Insurance Gap (Liabilities - Assets)
    net_gap = max(0, total_liabilities - (liquid_assets + existing_life))
    
    # 3. Coverage Calculation
    total_coverage = sum(p['amt'] for p in policies if yr <= p['term'])
    annual_premium = sum(p['prem'] for p in policies if yr <= p['term'])
    savings = sum(p['prem'] for p in policies if yr > p['term'])
    
    data.append({
        "Year": yr, 
        "Mortgage": m, "Income": i, "Childcare": c,
        "Gap": net_gap, "Total Coverage": total_coverage,
        "Premium": annual_premium, "Savings": savings
    })

df = pd.DataFrame(data)

# --- DASHBOARD HEADER ---
st.title("🛡️ Life Insurance Gap Analysis")
st.markdown("Precision underwriting means matching your coverage to your *actual* financial shortfall.")

m1, m2, m3 = st.columns(3)
m1.metric("Current Insurance Gap", f"${df['Gap'][0]:,.0f}")
m2.metric("New Ladder Coverage", f"${df['Total Coverage'][0]:,.0f}")
m3.metric("Projected Savings", f"${df['Savings'].sum():,.0f}", delta="From Dropped Premiums")

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
    xaxis=dict(title="Years into Future", range=[0, 30])
)

st.plotly_chart(fig, use_container_width=True)

# --- INSIGHTS ---
st.info(f"💡 **Fiduciary Insight:** Your family has **${liquid_assets + existing_life:,.0f}** in existing resources. We only need to bridge the remaining **${df['Gap'][0]:,.0f}**. Using a laddered approach ensures you aren't over-insured as your mortgage and childcare costs disappear.")

if df['Total Coverage'][0] < df['Gap'][0]:
    st.warning(f"⚠️ **Coverage Shortfall:** Your proposed ladder is currently **${df['Gap'][0] - df['Total Coverage'][0]:,.0f}** below your calculated need.")
