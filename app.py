import streamlit as st
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Option Portfolio Hedge Scanner", layout="wide")

st.title("🎯 Option Portfolio Hedge Scanner")
st.markdown("**Find optimal futures + option hedges for delta, gamma, vega, theta**")

# -------------------------------------------------------------
# Portfolio input
# -------------------------------------------------------------
st.sidebar.header("📊 Your Portfolio")
portfolio_data = st.sidebar.data_editor(
    {
        "Instrument": ["Call", "Put", "Call", "Future"],
        "Strike": [80, 75, 85, np.nan],
        "Expiry_Days": [30, 30, 30, np.nan],
        "Contracts": [10, 5, 8, 0],
        "Premium": [2.50, 1.80, 1.20, 0],
        "Delta": [0.45, -0.35, 0.25, 1.0],
        "Gamma": [0.03, 0.04, 0.02, 0],
        "Vega": [0.15, 0.12, 0.08, 0],
        "Theta": [-0.05, -0.04, -0.03, 0],
    },
    num_rows="dynamic",
    column_config={
        "Contracts": st.column_config.NumberColumn("Contracts", min_value=0, step=1),
        "Premium": st.column_config.NumberColumn("Premium ($)", format="%.2f"),
        "Delta": st.column_config.NumberColumn("Delta", format="%.3f"),
        "Gamma": st.column_config.NumberColumn("Gamma", format="%.3f"),
        "Vega": st.column_config.NumberColumn("Vega", format="%.3f"),
        "Theta": st.column_config.NumberColumn("Theta ($/day)", format="%.3f"),
    },
    use_container_width=True,
    hide_index=True,
)

if st.sidebar.button("🚀 Scan Hedges", type="primary"):
    # Calculate net Greeks
    df_port = pd.DataFrame(portfolio_data)
    df_port = df_port.dropna(subset=["Contracts"])
    
    net_delta = (df_port["Delta"] * df_port["Contracts"]).sum()
    net_gamma = (df_port["Gamma"] * df_port["Contracts"]).sum()
    net_vega = (df_port["Vega"] * df_port["Contracts"]).sum()
    net_theta = (df_port["Theta"] * df_port["Contracts"]).sum()
    
    # Available hedge instruments
    hedges = pd.DataFrame({
        "Instrument": ["WTI Future", "Call 82.5", "Put 77.5", "Call 85"],
        "Delta": [1.0, 0.55, -0.25, 0.15],
        "Gamma": [0.0, 0.025, 0.035, 0.01],
        "Vega": [0.0, 0.18, 0.14, 0.06],
        "Theta": [0.0, -0.06, -0.05, -0.02],
        "Cost": [0.0, 1.80, 1.45, 0.75],  # $/contract
    })
    
    st.session_state.net_greeks = {
        "delta": net_delta, "gamma": net_gamma, 
        "vega": net_vega, "theta": net_theta
    }
    st.session_state.hedges = hedges
    st.session_state.portfolio = df_port
    st.rerun()

# -------------------------------------------------------------
# Results
# -------------------------------------------------------------
if "net_greeks" in st.session_state:
    net_greeks = st.session_state.net_greeks
    hedges = st.session_state.hedges
    portfolio = st.session_state.portfolio
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Net Δ", f"{net_greeks['delta']:.1f}")
    with col2: st.metric("Net Γ", f"{net_greeks['gamma']:.3f}")
    with col3: st.metric("Net Vega", f"{net_greeks['vega']:.2f}")
    with col4: st.metric("Net Θ", f"{net_greeks['theta']:.3f}")
    
    st.markdown("---")
    
    # -------------------------------------------------------------
# Optimization: Minimize hedge cost subject to Greek targets
# -------------------------------------------------------------
def hedge_cost(x, target_delta=0, target_gamma=0, target_vega=0):
    """Cost of hedge position x (contracts per instrument)"""
    hedge_greeks = hedges[["Delta", "Gamma", "Vega"]].values @ x
    greek_error = (
        (hedge_greeks[0] - target_delta)**2 +
        10 * (hedge_greeks[1] - target_gamma)**2 +
        5 * (hedge_greeks[2] - target_vega)**2
    )
    cost = (hedges["Cost"] * np.abs(x)).sum()
    return cost + 100 * greek_error

# Scenario 1: Delta-neutral
res_delta = minimize(
    hedge_cost, 
    x0=np.zeros(len(hedges)), 
    args=(net_greeks['delta'], 0, 0),
    bounds=[(-50, 50)] * len(hedges),
    method="SLSQP",
    options={'disp': False}
)

# Scenario 2: Delta + Vega neutral
res_dv = minimize(
    hedge_cost, 
    x0=np.zeros(len(hedges)), 
    args=(net_greeks['delta'], 0, net_greeks['vega']),
    bounds=[(-50, 50)] * len(hedges),
    method="SLSQP",
    options={'disp': False}
)

# Scenario 3: Full Greek neutral (Δ, Γ, Vega)
res_full = minimize(
    hedge_cost, 
    x0=np.zeros(len(hedges)), 
    args=(net_greeks['delta'], net_greeks['gamma'], net_greeks['vega']),
    bounds=[(-50, 50)] * len(hedges),
    method="SLSQP",
    options={'disp': False}
)

    
    # Results table
    hedge_scenarios = pd.DataFrame({
        "Scenario": ["Delta-Neutral", "Delta+Vega Neutral", "Full Greek Neutral"],
        "Hedge Contracts": [
            f"{res_delta.x.round(1)}",
            f"{res_dv.x.round(1)}", 
            f"{res_full.x.round(1)}"
        ],
        "Cost ($)": [
            f"${(hedges['Cost'] * np.abs(res_delta.x)).sum():.0f}",
            f"${(hedges['Cost'] * np.abs(res_dv.x)).sum():.0f}",
            f"${(hedges['Cost'] * np.abs(res_full.x)).sum():.0f}"
        ],
        "Residual Δ": [
            f"{(hedges['Delta'] @ res_delta.x - net_greeks['delta']):.1f}",
            f"{(hedges['Delta'] @ res_dv.x - net_greeks['delta']):.1f}",
            f"{(hedges['Delta'] @ res_full.x - net_greeks['delta']):.1f}"
        ],
        "Residual Vega": [
            f"{(hedges['Vega'] @ res_delta.x):.2f}",
            f"{(hedges['Vega'] @ res_dv.x - net_greeks['vega']):.2f}",
            f"{(hedges['Vega'] @ res_full.x - net_greeks['vega']):.2f}"
        ]
    })
    
    st.subheader("🏆 Best Hedge Scenarios")
    st.dataframe(hedge_scenarios, use_container_width=True)
    
    # -------------------------------------------------------------
    # Hedge efficiency visualization
    # -------------------------------------------------------------
    st.subheader("📈 Hedge Efficiency")
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Delta", "Gamma", "Vega", "Theta Impact"),
        specs=[[{"type": "bar"}, {"type": "bar"}], 
               [{"type": "bar"}, {"type": "scatter"}]]
    )
    
    scenarios = ["Portfolio", "Δ-Neutral", "Δ+Vega", "Full Neutral"]
    delta_res = [net_greeks['delta'], 
                hedges['Delta'] @ res_delta.x - net_greeks['delta'],
                hedges['Delta'] @ res_dv.x - net_greeks['delta'],
                hedges['Delta'] @ res_full.x - net_greeks['delta']]
    
    fig.add_trace(
        go.Bar(x=scenarios, y=delta_res, name="Residual Δ", marker_color="red"),
        row=1, col=1
    )
    
    # Add other Greeks...
    fig.update_layout(height=600, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    
    # -------------------------------------------------------------
    # Trade recommendations
    # -------------------------------------------------------------
    st.subheader("💡 Recommended Trades")
    
    best_hedge = res_full.x.round(1)
    hedge_insts = hedges["Instrument"].values
    
    for i, (inst, qty) in enumerate(zip(hedge_insts, best_hedge)):
        if abs(qty) > 0.1:
            direction = "BUY" if qty > 0 else "SELL"
            st.write(f"**{direction} {abs(qty):.0f} {inst}** (${hedges['Cost'][i]*abs(qty):.0f})")

else:
    st.info("👆 Enter your portfolio above and click **Scan Hedges**")
