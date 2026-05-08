import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- CONFIGURATION & BRANDING ---
PRIMARY_RED = "#CC0700"
SILVER_BG = "#E2E8F0"

st.set_page_config(page_title="Policy Laddering Visualizer", layout="wide")

# --- SIDEBAR INPUTS ---
st.sidebar.header("Flight Parameters")
mortgage = st.sidebar.number_input("Current Mortgage Balance ($)", value=400000, step=10000)
mtg_years = st.sidebar.slider("Years Remaining on Mortgage", 5, 30, 20)
income_req = st.sidebar.number_input("Annual Income to Replace ($)", value=75000, step=5000)
income_years = st.sidebar.slider("Years of Income Replacement Needed", 5, 30, 15)
youngest_child_age = st.sidebar.slider("Age of Youngest Child", 0, 21, 5)

# --- LOGIC: GENERATING THE DATA ---
years = list(range(0, 31))
data = []

for yr in years:
    current_mtg = max(0, mortgage * (1 - (yr / mtg_years))) if yr <= mtg_years else 0
    current_income = income_req if yr <= income_years else 0
    current_child = 25000 if (yr + youngest_child_age) <= 22 else 0
    total_need = current_mtg + current_income + current_child
    data.append({"Year": yr, "Mortgage": current_mtg, "Income": current_income, "Children": current_child, "Total": total_need})

df = pd.DataFrame(data)

# --- VISUALIZATION ---
st.title("Custom Policy Laddering Visualizer")
st.markdown("Assess your projected financial liability milestones and see how a laddered strategy eliminates unnecessary premium costs.")

fig = go.Figure()

fig.add_trace(go.Scatter(x=df['Year'], y=df['Mortgage'], name='Mortgage', fill='tonexty', mode='none', stackgroup='one', fillcolor='#D1D5DB'))
fig.add_trace(go.Scatter(x=df['Year'], y=df['Income'], name='Income Replacement', fill='tonexty', mode='none', stackgroup='one', fillcolor='#9CA3AF'))
fig.add_trace(go.Scatter(x=df['Year'], y=df['Children'], name='Children/Education', fill='tonexty', mode='none', stackgroup='one', fillcolor='#4B5563'))

fig.update_layout(
    plot_bgcolor='white',
    paper_bgcolor='white',
    hovermode="x unified",
    yaxis_title="Coverage Amount ($)",
    xaxis_title="Years into Future",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

st.plotly_chart(fig, use_container_width=True)
st.info("Results are projected estimates for educational purposes and do not represent a final underwriting offer.")
