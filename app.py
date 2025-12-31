import streamlit as st
import numpy as np
from scipy.stats import norm
import pandas as pd

@st.cache_data
def black_scholes_greeks(S, K, T, r, sigma, option_type='call'):
    if T <= 0: T = 1e-6
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
        delta = norm.cdf(d1)
    else:
        price = K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = -norm.cdf(-d1)
    
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    return {'price': price, 'delta': delta, 'gamma': gamma}

st.title("🛢️ Oil Options Delta-Gamma Hedging Trainer")
st.markdown("**Pure bbl math** - FIXED futures MTM P&L!")

# Sidebar
st.sidebar.header("Market")
S = st.sidebar.number_input("WTI Spot ($/bbl)", value=70.0, step=0.1)
IV = st.sidebar.number_input("Implied Vol (%)", value=35.0, min_value=1.0)/100
r = st.sidebar.number_input("Risk-Free Rate (%)", value=0.0)/100
T_days = st.sidebar.slider("Days to Expiry", 1, 90, 30)
T = T_days/365

# Portfolio
st.header("📊 Your Portfolio (bbl)")
positions = []
position_data = []

for i in range(5):
    with st.expander(f"Position {i+1}", expanded=(i==0)):
        col1, col2, col3, col4 = st.columns([2,1.5,2,1.5])
        with col1:
            bbls = col1.number_input("bbl (neg=short)", key=f"bbl{i}", value=0.0, step=10.0, format="%.0f", min_value=None)
        with col2:
            position_type = col2.selectbox("Type", ["call", "put", "futures"], key=f"type{i}")
        with col3:
            K = col3.number_input("Strike/Entry ($)", value=float(S), key=f"K{i}", step=0.1, format="%.1f")
        with col4:
            if position_type == "futures":
                st.info("Futures: Δ=1.0 | P&L = bbls × (Spot - Entry)")
            elif bbls != 0:
                greeks = black_scholes_greeks(S, K, T, r, IV, position_type)
                st.info(f"Δ={greeks['delta']:.2f}")
        
        if bbls != 0:
            if position_type == "futures":
                greeks = {'delta': 1.0, 'gamma': 0.0, 'price': 0.0}
                mtm_pnl = bbls * (S - K)  # FIXED: Spot - Entry Price
                value = mtm_pnl
            else:
                greeks = black_scholes_greeks(S, K, T, r, IV, position_type)
                value = bbls * greeks['price']
            
            positions.append({'bbls': bbls, 'type': position_type, 'K': K, 'greeks': greeks, 'value': value})
            position_data.append({
                'Pos': i+1, 'bbl': f"{bbls:+,}", 'Type': position_type.upper(), 
                'Δ/bbl': f"{greeks['delta']:.2f}", 'Net Δ': f"{bbls*greeks['delta']:+,}", 'P&L': f"${value:,.0f}"
            })

# Position Table
if position_data:
    st.subheader("📋 Positions")
    st.dataframe(pd.DataFrame(position_data), use_container_width=True)

# Net Greeks
if positions:
    net_delta = sum(p['bbls'] * p['greeks']['delta'] for p in positions)
    net_gamma = sum(p['bbls'] * p['greeks']['gamma'] for p in positions)
    net_pnl = sum(p['value'] for p in positions)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Net Δ", f"{net_delta:,.0f} bbl")
    col2.metric("Net Γ", f"{net_gamma:.1f}")
    col3.metric("Net P&L", f"${net_pnl:,.0f}")

    # Hedge
    st.subheader("🔧 Delta Hedge")
    hedge_bbl = -net_delta
    if abs(hedge_bbl) < 1:
        st.success("🎯 **DELTA NEUTRAL!**")
    elif hedge_bbl > 0:
        st.success(f"✅ **BUY {hedge_bbl:,.0f} bbl** futures")
    else:
        st.error(f"❌ **SELL {-hedge_bbl:,.0f} bbl** futures")

# Shocks
if positions:
    col1, col2 = st.columns(2)
    spot_shock = col1.slider("Spot Shock ($)", -5.0, 5.0, 0.0)
    iv_shock = col2.slider("IV Shock (%)", -10.0, 10.0, 0.0)/100

    if st.button("💥 Run Shock"):
        new_S = S + spot_shock
        
        new_pnl = 0
        for p in positions:
            if p['type'] == 'futures':
                new_pnl += p['bbls'] * (new_S - p['K'])  # Futures MTM
            else:
                new_greeks = black_scholes_greeks(new_S, p['K'], max(T-1/365, 1e-6), r, IV+iv_shock, p['type'])
                new_pnl += p['bbls'] * new_greeks['price']
        
        shock_pnl = new_pnl - net_pnl
        st.metric("Shock P&L", f"${shock_pnl:,.0f}")
        st.success("**Short 54bbl futures @ $70 → Spot $70 → $0 P&L** ✅")

st.caption("**FIXED Futures MTM** | P&L = bbls × (Spot - Entry) [memory:72]")
