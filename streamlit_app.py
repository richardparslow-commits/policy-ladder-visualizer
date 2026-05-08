import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- BRANDING & STYLES ---
PRIMARY_RED = "#CC0700"
ACCENT_BLUE = "#1E88E5"
ACCENT_GREEN = "#2E7D32"
LEGACY_GRAY = "#374151"

st.set_page_config(page_title="Life Policy Pilot | Policy Ladder Pro", layout="wide")

# Custom CSS for UI
st.markdown(f"""
    <style>
    .stMetric {{ background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; border-top: 5px solid {PRIMARY_RED}; }}
    [data-testid="stSidebar"] {{ background-color: #f8f9fa; }}
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: PARAMETERS ---
with st.sidebar:
    st.header("📍 Flight Parameters")
    
    with st.expander("🏠 Debts & Milestones", expanded=False):
        mortgage = st.number_input("Mortgage Balance ($)", value=450000, step=10000)
        mtg_years = st.slider("Mortgage Years Left", 5, 30, 25)
        income_req = st.number_input("Annual Income to Replace ($)", value=80000)
        income_years = st.slider("Years Needed", 5, 30, 20)
        final_expenses = st.number_input("Final Expenses/Legacy ($)", value=50000)

    st.header("🪜 Policy Ladder Config")
    policies = []
    for i in range(1, 4):
        with st.expander(f"Policy #{i}", expanded=(i==1)):
            p_active = st.checkbox(f"Enable Policy {i}", value=(i==1))
            p_type = st.selectbox(f"Type {i}", ["Term", "IUL", "Whole Life"], key=f"type{i}")
            p_amt = st.number_input(f"Death Benefit {i} ($)", value=250000 if i==1 else 0, step=50000, key=f"amt{i}")
            p_prem = st.number_input(f"Annual Premium {i} ($)", value=400 if i==1 else 0, key=f"prem{i}")
            
            if p_type == "Term":
                p_term = st.selectbox(f"Term Length {i}", [10, 15, 20, 25, 30], index=2, key=f"term{i}")
            else:
                p_term = 50 # Permanent
                
            if p_active:
                policies.append({"amt": p_amt, "term": p_term, "prem": p_prem, "type": p_type})

# --- LOGIC: CALCULATING NEEDS VS COVERAGE ---
years = list(range(0, 36))
data = []
total_lifetime_savings = 0

for yr in years:
    # 1. Needs Calculation
    m = max(0, mortgage * (1 - (yr / mtg_years))) if yr <= mtg_years else 0
    i = income_req if yr <= income_years else 0
    f = final_expenses
    total_need = m + i + f
    
    # 2. Coverage Calculation
    total_coverage = 0
    annual_premium_outlay = 0
    saved_this_year = 0
    
    for p in policies:
        if yr <= p['term']:
            total_coverage += p['amt']
            annual_premium_outlay += p['prem']
        else:
            saved_this_year += p['prem']
            
    data.append({
        "Year": yr, 
        "Mortgage": m, "Income": i, "Legacy": f, "Total Need": total_need,
        "Total Coverage": total_coverage,
        "Premium Outlay": annual_premium_outlay,
        "Savings": saved_this_year
    })

df = pd.DataFrame(data)

# --- DASHBOARD HEADER ---
st.title("🛡️ The Policy Ladder Visualizer")
st.markdown("Dynamic analysis of your staggered coverage versus declining financial liabilities.")

m1, m2, m3 = st.columns(3)
m1.metric("Initial Total Coverage", f"${df['Total Coverage'][0]:,.0f}")
m2.metric("Current Annual Premium", f"${df['Premium Outlay'][0]:,.0f}")
m3.metric("Projected Total Savings", f"${df['Savings'].sum():,.0f}", delta="From Expired Policies")

# --- THE VISUALIZER ---
fig = go.Figure()

# Needs (Stacked Areas)
fig.add_trace(go.Scatter(x=df['Year'], y=df['Legacy'], name='Legacy Floor', fill='toself', mode='none', stackgroup='one', fillcolor=LEGACY_GRAY))
fig.add_trace(go.Scatter(x=df['Year'], y=df['Mortgage'], name='Mortgage Debt', fill='tonexty', mode='none', stackgroup='one', fillcolor='#94a3b8'))
fig.add_trace(go.Scatter(x=df['Year'], y=df['Income'], name='Income Replacement', fill='tonexty', mode='none', stackgroup='one', fillcolor=ACCENT_BLUE))

# Coverage (The Ladder) - Step chart to show hard drops
fig.add_trace(go.Scatter(
    x=df['Year'], y=df['Total Coverage'], 
    name='Your Policy Ladder', 
    line=dict(color=PRIMARY_RED, width=4, shape='hv'),
    mode='lines'
))

fig.update_layout(
    hovermode="x unified",
    height=600,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(title="Dollar Amount ($)", gridcolor="#f0f0f0"),
    xaxis=dict(title="Years into Future", gridcolor="#f0f0f0", range=[0, 30])
)

st.plotly_chart(fig, use_container_width=True)

# --- INSIGHTS ENGINE ---
st.header("✈️ Flight Path Insights")
col1, col2 = st.columns(2)

with col1:
    st.subheader("Why coverage drops:")
    for yr in [10, 15, 20, 25, 30]:
        m_val = max(0, mortgage * (1 - (yr / mtg_years))) if yr <= mtg_years else 0
        if yr == mtg_years:
            st.write(f"✅ **Year {yr}:** Mortgage is paid off. High-limit coverage no longer required.")
        if yr == income_years:
            st.write(f"✅ **Year {yr}:** Income replacement goal met. Children are likely self-sufficient.")

with col2:
    st.subheader("Cash Flow Recovery:")
    active_savings = df[df['Savings'] > 0].groupby('Year')['Savings'].first()
    if not active_savings.empty:
        for yr, amt in active_savings.items():
            if yr in [11, 16, 21, 26, 31]:
                st.write(f"💰 **Year {yr-1}:** Policy expired. **${amt:,.0f}/year** returned to your household budget.")
    else:
        st.write("Adjust your policy terms in the sidebar to see projected premium savings.")
