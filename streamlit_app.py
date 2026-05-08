import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- BRANDING & STYLES ---
PRIMARY_RED = "#CC0700"
ACCENT_BLUE = "#1E88E5"
ACCENT_GREEN = "#2E7D32"
SILVER_TEXT = "#E2E8F0"

st.set_page_config(page_title="Life Policy Pilot | Laddering Visualizer", layout="wide")

# Custom CSS for better styling
st.markdown(f"""
    <style>
    .main {{ background-color: #ffffff; }}
    .stMetric {{ background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid {PRIMARY_RED}; }}
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: FLIGHT PARAMETERS ---
with st.sidebar:
    st.image("https://lifepolicypilot.blog/wp-content/uploads/2024/03/cropped-Life-Policy-Pilot-Logo.png", width=200) # Optional: Add your logo URL
    st.header("📍 Flight Parameters")
    
    with st.expander("🏠 Housing & Debt", expanded=True):
        mortgage = st.number_input("Mortgage Balance ($)", value=450000, step=10000)
        mtg_years = st.slider("Mortgage Years Left", 5, 30, 25)
        other_debt = st.number_input("Other Debts (Car/Student) ($)", value=15000)

    with st.expander("💰 Family Income", expanded=True):
        income_req = st.number_input("Annual Income to Replace ($)", value=80000)
        income_years = st.slider("Years Needed", 5, 30, 20)
        inflation = st.slider("Inflation Adjustment (%)", 0.0, 5.0, 3.0) / 100

    with st.expander("🎓 Future & Legacy", expanded=True):
        children_count = st.number_input("Number of Children", 0, 5, 2)
        college_fund = st.number_input("Target College Fund per Child ($)", value=100000)
        final_expenses = st.number_input("Final Expenses/Legacy ($)", value=50000)

# --- LOGIC: CALCULATING THE MILESTONES ---
years = list(range(0, 31))
data = []

for yr in years:
    # 1. Mortgage (Linear decrease)
    m = max(0, mortgage * (1 - (yr / mtg_years))) if yr <= mtg_years else 0
    # 2. Income Replacement (With Inflation)
    i = (income_req * ((1 + inflation) ** yr)) if yr <= income_years else 0
    # 3. Children (Stepped decrease as they age out)
    c = (children_count * college_fund) if yr <= 15 else 0 # Simplified college horizon
    # 4. Final Expenses (Fixed floor)
    f = final_expenses
    
    total = m + i + c + f + other_debt
    data.append({"Year": yr, "Mortgage": m, "Income": i, "Education": c, "Legacy": f, "Total": total})

df = pd.DataFrame(data)

# --- HEADER METRICS ---
st.title("🛡️ Policy Laddering Visualizer")
st.markdown("Compare your total financial liabilities against a smart, staggered insurance strategy.")

m1, m2, m3 = st.columns(3)
m1.metric("Peak Coverage Needed", f"${df['Total'].max():,.0f}")
m2.metric("Legacy Floor", f"${final_expenses:,.0f}")
m3.metric("Optimization Potential", "High", delta="30-40% Savings")

# --- THE VISUALIZER ---
fig = go.Figure()

# Stacked Area Chart with Vibrant Colors
fig.add_trace(go.Scatter(x=df['Year'], y=df['Legacy'], name='Legacy/Final Expenses', fill='toself', mode='none', stackgroup='one', fillcolor='#374151'))
fig.add_trace(go.Scatter(x=df['Year'], y=df['Mortgage'], name='Mortgage & Debt', fill='tonexty', mode='none', stackgroup='one', fillcolor='#94a3b8'))
fig.add_trace(go.Scatter(x=df['Year'], y=df['Education'], name='Education Fund', fill='tonexty', mode='none', stackgroup='one', fillcolor=ACCENT_GREEN))
fig.add_trace(go.Scatter(x=df['Year'], y=df['Income'], name='Income Replacement (Adjusted)', fill='tonexty', mode='none', stackgroup='one', fillcolor=ACCENT_BLUE))

# Overlay the "Ladders"
fig.add_trace(go.Scatter(x=[0, 10, 10, 0], y=[df['Total'].max(), df['Total'].max(), 0, 0], fill="toself", name="10-Year Rung", line=dict(color=PRIMARY_RED, width=2), opacity=0.1, showlegend=True))

fig.update_layout(
    hovermode="x unified",
    plot_bgcolor='white',
    height=600,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(gridcolor='#f0f0f0', title="Coverage Amount ($)"),
    xaxis=dict(gridcolor='#f0f0f0', title="Years into Future")
)

st.plotly_chart(fig, use_container_width=True)

st.success("💡 **Fiduciary Insight:** Notice how your needs drop significantly at Year 15 and 25. A single 30-year policy would force you to pay for 'empty' coverage in those later years.")
