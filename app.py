import streamlit as st
import numpy as np
import pandas as pd
from scipy.optimize import minimize

st.set_page_config(page_title="Option Portfolio Hedge Scanner", layout="wide")

st.title("🎯 Option Portfolio Hedge Scanner")
st.markdown("**Find optimal futures + option hedges for delta, gamma, vega, theta**")
st.caption("📏 **Position size in bbl** (1 = 1 bbl, 1000 = 1000 bbl) | 🔒 **Greeks auto-signed**")

# -------------------------------------------------------------
# Portfolio input with Greek sign enforcement
# -------------------------------------------------------------
st.sidebar.header("📊 Your Portfolio (per bbl)")

# Define standard Long Greeks (will be flipped for Short)
default_greeks_long = {
    "Delta_per_bbl": 0.45,
    "Gamma_per_bbl": 0.03,
    "Vega_per_bbl": 0.15,
    "Theta_per_bbl": -0.05
}

portfolio_data = st.sidebar.data_editor(
    {
        "Instrument": ["Call 80", "Put 75", "Call 85", "WTI Future"],
        "Long/Short": ["Long", "Long", "Short", "Short"],
        "Strike": [80, 75, 85, np.nan],
        "Expiry_Days": [30, 30, 30, np.nan],
        "Position_bbl": [10000, 5000, 8000, 0],
        "Delta_per_bbl": [0.45, 0.35, 0.25, 1.0],
        "Gamma_per_bbl": [0.03, 0.04, 0.02, 0.0],
        "Vega_per_bbl": [0.15, 0.12, 0.08, 0.0],
        "Theta_per_bbl": [-0.05, -0.04, -0.03, 0.0],
    },
    num_rows="dynamic",
    column_config={
        "Long/Short": st.column_config.SelectboxColumn(
            "Long/Short", options=["Long", "Short"], default="Long"
        ),
        "Position_bbl": st.column_config.NumberColumn(
            "Position (bbl)", min_value=0, step=1000, format="%.0f"
        ),
        "Delta_per_bbl": st.column_config.NumberColumn(
            "Delta (long basis)", format="%.3f", help="Enter as if LONG position"
        ),
        "Gamma_per_bbl": st.column_config.NumberColumn(
            "Gamma (long basis)", format="%.3f", help="Enter as if LONG position"
        ),
        "Vega_per_bbl": st.column_config.NumberColumn(
            "Vega (long basis)", format="%.3f", help="Enter as if LONG position"
        ),
        "Theta_per_bbl": st.column_config.NumberColumn(
            "Theta (long basis)", format="%.3f", help="Enter as if LONG position (negative)"
        ),
    },
    use_container_width=True,
    hide_index=True,
)

if st.sidebar.button("🚀 Scan Hedges", type="primary"):
    df_port = pd.DataFrame(portfolio_data)
    df_port = df_port.dropna(subset=["Position_bbl"])
    
    # ✅ AUTO-ENFORCE GREEK SIGNS based on Long/Short
    df_port['effective_delta'] = np.where(
        df_port['Long/Short'] == 'Short', 
        -df_port['Delta_per_bbl'], 
        df_port['Delta_per_bbl']
    )
    df_port['effective_gamma'] = np.where(
        df_port['Long/Short'] == 'Short', 
        -df_port['Gamma_per_bbl'], 
        df_port['Gamma_per_bbl']
    )
    df_port['effective_vega'] = np.where(
        df_port['Long/Short'] == 'Short', 
        -df_port['Vega_per_bbl'], 
        df_port['Vega_per_bbl']
    )
    df_port['effective_theta'] = np.where(
        df_port['Long/Short'] == 'Short', 
        -df_port['Theta_per_bbl'], 
        df_port['Theta_per_bbl']
    )
    
    # Net Greeks (position size * effective Greeks)
    net_delta = (df_port['effective_delta'] * df_port['Position_bbl']).sum()
    net_gamma = (df_port['effective_gamma'] * df_port['Position_bbl']).sum()
    net_vega = (df_port['effective_vega'] * df_port['Position_bbl']).sum()
    net_theta = (df_port['effective_theta'] * df_port['Position_bbl']).sum()
    
    # Available hedge instruments (per bbl, entered as LONG basis)
    hedges = pd.DataFrame({
        "Instrument": ["WTI Future", "Call 82.5", "Put 77.5", "Call 85"],
        "Delta_per_bbl": [1.0, 0.55, 0.25, 0.15],  # Absolute values (long basis)
        "Gamma_per_bbl": [0.0, 0.025, 0.035, 0.01],
        "Vega_per_bbl": [0.0, 0.18, 0.14, 0.06],
        "Theta_per_bbl": [0.0, -0.06, -0.05, -0.02],
        "Cost_per_bbl": [0.0, 1.80, 1.45, 0.75],
    })
    
    st.session_state.net_greeks = {
        "delta": net_delta, "gamma": net_gamma, 
        "vega": net_vega, "theta": net_theta
    }
    st.session_state.hedge_greeks = hedges[["Delta_per_bbl", "Gamma_per_bbl", "Vega_per_bbl"]].values
    st.session_state.hedge_costs = hedges["Cost_per_bbl"].values
    st.session_state.hedge_names = hedges["Instrument"].values
    st.session_state.portfolio = df_port
    st.rerun()

# -------------------------------------------------------------
# Results
# -------------------------------------------------------------
if "net_greeks" in st.session_state:
    net_greeks = st.session_state.net_greeks
    hedge_greeks = np.array(st.session_state.hedge_greeks)
    hedge_costs = np.array(st.session_state.hedge_costs)
    hedge_names = st.session_state.hedge_names
    df_port = st.session_state.portfolio
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Net Δ", f"{net_greeks['delta']:,.0f} bbl")
    with col2: st.metric("Net Γ", f"{net_greeks['gamma']:,.1f}")
    with col3: st.metric("Net Vega", f"{net_greeks['vega']:,.0f}")
    with col4: st.metric("Net Θ", f"${net_greeks['theta']:,.0f}/day")
    
    st.markdown("---")
    
    # -------------------------------------------------------------
    # Optimization
    # -------------------------------------------------------------
    def hedge_cost(x, target_delta, target_gamma, target_vega):
        hedge_delta = hedge_greeks[:, 0] @ x
        hedge_gamma = hedge_greeks[:, 1] @ x  
        hedge_vega = hedge_greeks[:, 2] @ x
        
        greek_error = (
            (hedge_delta - target_delta)**2 +
            10 * (hedge_gamma - target_gamma)**2 +
            5 * (hedge_vega - target_vega)**2
        )
        cost = np.abs(hedge_costs @ x)
        return cost + 100 * greek_error
    
    n_hedges = hedge_greeks.shape[0]
    
    # Scenarios
    res_delta = minimize(hedge_cost, x0=np.zeros(n_hedges), 
                        args=(net_greeks['delta'], 0, 0),
                        bounds=[(-50000, 50000)] * n_hedges, method="SLSQP", 
                        options={'disp': False, 'maxiter': 100})
    
    res_dv = minimize(hedge_cost, x0=np.zeros(n_hedges), 
                     args=(net_greeks['delta'], 0, net_greeks['vega']),
                     bounds=[(-50000, 50000)] * n_hedges, method="SLSQP", 
                     options={'disp': False, 'maxiter': 100})
    
    res_full = minimize(hedge_cost, x0=np.zeros(n_hedges), 
                       args=(net_greeks['delta'], net_greeks['gamma'], net_greeks['vega']),
                       bounds=[(-50000, 50000)] * n_hedges, method="SLSQP", 
                       options={'disp': False, 'maxiter': 100})
    
    # Results table
    hedge_scenarios = pd.DataFrame({
        "Scenario": ["Delta-Neutral", "Delta+Vega Neutral", "Full Greek Neutral"],
        "Hedge Position (bbl)": [
            " | ".join([f"{h}: {res_delta.x[i]:,.0f}" for i, h in enumerate(hedge_names)]),
            " | ".join([f"{h}: {res_dv.x[i]:,.0f}" for i, h in enumerate(hedge_names)]),
            " | ".join([f"{h}: {res_full.x[i]:,.0f}" for i, h in enumerate(hedge_names)])
        ],
        "Cost ($)": [
            f"${np.abs(hedge_costs @ res_delta.x):,.0f}",
            f"${np.abs(hedge_costs @ res_dv.x):,.0f}",
            f"${np.abs(hedge_costs @ res_full.x):,.0f}"
        ],
        "Residual Δ (bbl)": [
            f"{(hedge_greeks[:,0] @ res_delta.x - net_greeks['delta']):,.0f}",
            f"{(hedge_greeks[:,0] @ res_dv.x - net_greeks['delta']):,.0f}",
            f"{(hedge_greeks[:,0] @ res_full.x - net_greeks['delta']):,.0f}"
        ],
        "Residual Vega": [
            f"{(hedge_greeks[:,2] @ res_delta.x):,.0f}",
            f"{(hedge_greeks[:,2] @ res_dv.x - net_greeks['vega']):,.0f}",
            f"{(hedge_greeks[:,2] @ res_full.x - net_greeks['vega']):,.0f}"
        ]
    })
    
    st.subheader("🏆 Best Hedge Scenarios")
    st.dataframe(hedge_scenarios, use_container_width=True)
    
    st.subheader("💡 Recommended Trades (Full Greek Neutral)")
    best_hedge = res_full.x.round(0).astype(int)
    for i, (name, qty) in enumerate(zip(hedge_names, best_hedge)):
        if abs(qty) > 10:
            direction = "BUY" if qty > 0 else "SELL"
            cost = hedge_costs[i] * abs(qty)
            st.success(f"**{direction} {abs(qty):,} bbl {name}** (${cost:,.0f})")

    # Portfolio summary table - SHOWS EFFECTIVE GREEKS
    st.subheader("📋 Portfolio (Effective Greeks)")
    portfolio_summary = df_port[[
        'Instrument', 'Long/Short', 'Position_bbl', 'Delta_per_bbl', 'effective_delta',
        'Vega_per_bbl', 'effective_vega', 'Theta_per_bbl', 'effective_theta'
    ]].rename(columns={
        'effective_delta': 'Net Δ/ bbl', 'effective_vega': 'Net Vega/ bbl', 
        'effective_theta': 'Net Θ/ bbl'
    })
    st.dataframe(portfolio_summary, use_container_width=True)

else:
    st.info("👆 Enter your portfolio **Greeks on LONG basis** above and click **Scan Hedges**")
