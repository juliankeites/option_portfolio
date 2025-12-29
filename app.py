import streamlit as st
import numpy as np
import pandas as pd
from scipy.optimize import minimize

st.set_page_config(page_title="Option Portfolio Hedge Scanner", layout="wide")

st.title("🎯 Option Portfolio Hedge Scanner")
st.markdown("**Find optimal futures + option hedges for delta, gamma, vega, theta**")
st.caption("📏 **Position size in bbl** | 🔒 **Greeks auto-signed** | ⚡ **Synthetic future detection**")

# -------------------------------------------------------------
# Portfolio input with Greek sign enforcement
# -------------------------------------------------------------
st.sidebar.header("📊 Your Portfolio (per bbl)")

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
    
    # Auto-enforce Greek signs
    df_port['effective_delta'] = np.where(
        df_port['Long/Short'] == 'Short', 
        -df_port['Delta_per_bbl'], df_port['Delta_per_bbl']
    )
    df_port['effective_gamma'] = np.where(
        df_port['Long/Short'] == 'Short', 
        -df_port['Gamma_per_bbl'], df_port['Gamma_per_bbl']
    )
    df_port['effective_vega'] = np.where(
        df_port['Long/Short'] == 'Short', 
        -df_port['Vega_per_bbl'], df_port['Vega_per_bbl']
    )
    df_port['effective_theta'] = np.where(
        df_port['Long/Short'] == 'Short', 
        -df_port['Theta_per_bbl'], df_port['Theta_per_bbl']
    )
    
    net_delta = (df_port['effective_delta'] * df_port['Position_bbl']).sum()
    net_gamma = (df_port['effective_gamma'] * df_port['Position_bbl']).sum()
    net_vega = (df_port['effective_vega'] * df_port['Position_bbl']).sum()
    net_theta = (df_port['effective_theta'] * df_port['Position_bbl']).sum()
    
    # ✅ FIXED: Enhanced hedge instruments with FUTURES PRIORITY
    hedges = pd.DataFrame({
        "Instrument": ["WTI Future", "WTI Future (x2)", "Call 82.5", "Put 77.5", "Call 85"],
        "Delta_per_bbl": [1.0, 2.0, 0.55, 0.25, 0.15],
        "Gamma_per_bbl": [0.0, 0.0, 0.025, 0.035, 0.01],
        "Vega_per_bbl": [0.0, 0.0, 0.18, 0.14, 0.06],
        "Theta_per_bbl": [0.0, 0.0, -0.06, -0.05, -0.02],
        "Cost_per_bbl": [0.0, 0.0, 1.80, 1.45, 0.75],
        "Future_priority": [1, 1, 0, 0, 0]  # Futures first
    })
    
    st.session_state.net_greeks = {
        "delta": net_delta, "gamma": net_gamma, 
        "vega": net_vega, "theta": net_theta
    }
    st.session_state.hedge_greeks = hedges[["Delta_per_bbl", "Gamma_per_bbl", "Vega_per_bbl"]].values
    st.session_state.hedge_costs = hedges["Cost_per_bbl"].values
    st.session_state.hedge_names = hedges["Instrument"].values
    st.session_state.hedge_priority = hedges["Future_priority"].values
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
    hedge_priority = np.array(st.session_state.hedge_priority)
    df_port = st.session_state.portfolio
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Net Δ", f"{net_greeks['delta']:,.0f} bbl")
    with col2: st.metric("Net Γ", f"{net_greeks['gamma']:,.1f}")
    with col3: st.metric("Net Vega", f"{net_greeks['vega']:,.0f}")
    with col4: st.metric("Net Θ", f"${net_greeks['theta']:,.0f}/day")
    
    st.markdown("---")
    
    # -------------------------------------------------------------
    # FIXED OPTIMIZATION - Futures prioritized
    # -------------------------------------------------------------
    def hedge_cost(x, target_delta, target_gamma, target_vega):
        hedge_delta = hedge_greeks[:, 0] @ x
        hedge_gamma = hedge_greeks[:, 1] @ x  
        hedge_vega = hedge_greeks[:, 2] @ x
        
        # ✅ PRIORITIZE FUTURES (lower cost for futures)
        future_cost = np.sum(np.abs(x[hedge_priority == 1]) * 0.1)  # Minimal future cost
        option_cost = np.sum(np.abs(x[hedge_priority == 0]) * hedge_costs[hedge_priority == 0])
        total_cost = future_cost + option_cost
        
        greek_error = (
            (hedge_delta - target_delta)**2 +
            10 * (hedge_gamma - target_gamma)**2 +
            5 * (hedge_vega - target_vega)**2
        )
        return total_cost + 50 * greek_error  # Reduced penalty
    
    n_hedges = hedge_greeks.shape[0]
    
    # Test case: Long 80C + Short 80P = Synthetic Future
    synthetic_delta = 10000 * 0.45 - 10000 * 0.35  # Should be ~1000 delta
    
    # Scenarios - FUTURES FIRST
    res_delta = minimize(hedge_cost, x0=np.zeros(n_hedges), 
                        args=(net_greeks['delta'], 0, 0),
                        bounds=[(-100000, 100000)] * n_hedges, method="SLSQP", 
                        options={'disp': False, 'maxiter': 200})
    
    res_dv = minimize(hedge_cost, x0=np.zeros(n_hedges), 
                     args=(net_greeks['delta'], 0, net_greeks['vega']),
                     bounds=[(-100000, 100000)] * n_hedges, method="SLSQP", 
                     options={'disp': False, 'maxiter': 200})
    
    res_full = minimize(hedge_cost, x0=np.zeros(n_hedges), 
                       args=(net_greeks['delta'], net_greeks['gamma'], net_greeks['vega']),
                       bounds=[(-100000, 100000)] * n_hedges, method="SLSQP", 
                       options={'disp': False, 'maxiter': 200})
    
    # Results table
    hedge_scenarios = pd.DataFrame({
        "Scenario": ["Delta-Neutral", "Delta+Vega", "Full Neutral"],
        "Hedge (bbl)": [
            " | ".join([f"{h}: {res_delta.x[i]:,.0f}" for i, h in enumerate(hedge_names)]),
            " | ".join([f"{h}: {res_dv.x[i]:,.0f}" for i, h in enumerate(hedge_names)]),
            " | ".join([f"{h}: {res_full.x[i]:,.0f}" for i, h in enumerate(hedge_names)])
        ],
        "Cost ($)": [
            f"${np.abs(hedge_costs @ res_delta.x):,.0f}",
            f"${np.abs(hedge_costs @ res_dv.x):,.0f}",
            f"${np.abs(hedge_costs @ res_full.x):,.0f}"
        ],
        "Res Δ": [
            f"{(hedge_greeks[:,0] @ res_delta.x - net_greeks['delta']):,.0f}",
            f"{(hedge_greeks[:,0] @ res_dv.x - net_greeks['delta']):,.0f}",
            f"{(hedge_greeks[:,0] @ res_full.x - net_greeks['delta']):,.0f}"
        ]
    })
    
    st.subheader("🏆 Best Hedge Scenarios")
    st.dataframe(hedge_scenarios, use_container_width=True)
    
    # ✅ SYNTHETIC FUTURE DETECTION
    st.markdown("---")
    st.subheader("🔍 Synthetic Future Analysis")
    
    # Check for Long Call + Short Put same strike
    calls = df_port[df_port['Instrument'].str.contains('Call', na=False)]
    puts = df_port[df_port['Instrument'].str.contains('Put', na=False)]
    
    if len(calls) > 0 and len(puts) > 0:
        call_strike = calls['Strike'].iloc[0]
        put_strike = puts['Strike'].iloc[0]
        if abs(call_strike - put_strike) < 0.1:  # Same strike
            synthetic_delta = (calls['effective_delta'].iloc[0] * calls['Position_bbl'].iloc[0] + 
                             puts['effective_delta'].iloc[0] * puts['Position_bbl'].iloc[0])
            st.success(f"✅ **Detected Synthetic
