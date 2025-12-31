import streamlit as st
import numpy as np
from scipy.stats import norm
import pandas as pd
import plotly.graph_objects as go

@st.cache_data
def black_scholes_greeks(S, K, T, r, sigma, option_type='call'):
    if T <= 0: T = 1e-6
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
        delta = norm.cdf(d1)
        vega = S * norm.pdf(d1) * np.sqrt(T)
        theta = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) - r * K * np.exp(-r*T) * norm.cdf(d2)
    else:  # put
        price = K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = -norm.cdf(-d1)
        vega = S * norm.pdf(d1) * np.sqrt(T)  # Same vega
        theta = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) + r * K * np.exp(-r*T) * norm.cdf(-d2)
    
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    return {'price': price, 'delta': delta, 'gamma': gamma, 'vega': vega/100, 'theta': theta/365}  # Per day

st.title("🛢️ Oil Options FULL Greeks Hedging Trainer")
st.markdown("**Delta + Gamma + Vega + Theta** | Complete oil MM simulator")

# Sidebar
st.sidebar.header("Market")
S = st.sidebar.number_input("WTI Spot ($/bbl)", value=70.0, step=0.1)
IV = st.sidebar.number_input("Implied Vol (%)", value=35.0, min_value=1.0)/100
r = st.sidebar.number_input("Risk-Free Rate (%)", value=5.0)/100
T_days = st.sidebar.slider("Days to Expiry", 1, 90, 30)
T = T_days/365

# Portfolio - FULL GREEKS
st.header("📊 Your Portfolio (bbl)")
positions = []
position_data = []

for i in range(6):
    with st.expander(f"Position {i+1}", expanded=(i==0)):
        col1, col2, col3, col4 = st.columns([2,1.5,2,2])
        with col1:
            bbls = col1.number_input("bbl (neg=short)", key=f"bbl{i}", value=0.0, step=10.0, format="%.0f", min_value=None)
        with col2:
            position_type = col2.selectbox("Type", ["call", "put", "futures"], key=f"type{i}")
        with col3:
            K = col3.number_input("Strike/Entry ($)", value=float(S), key=f"K{i}", step=0.1, format="%.1f")
        with col4:
            if position_type == "futures":
                st.info("Futures: Δ=1.0 | V=0 | Θ=0")
            elif bbls != 0:
                greeks = black_scholes_greeks(S, K, T, r, IV, position_type)
                st.info(f"Δ={greeks['delta']:.2f} | Γ={greeks['gamma']:.3f} | V={greeks['vega']:.2f}")
        
        if bbls != 0:
            if position_type == "futures":
                greeks = {'delta': 1.0, 'gamma': 0.0, 'vega': 0.0, 'theta': 0.0, 'price': 0.0}
                mtm_pnl = bbls * (S - K)
                value = mtm_pnl
            else:
                greeks = black_scholes_greeks(S, K, T, r, IV, position_type)
                value = bbls * greeks['price']
            
            positions.append({'bbls': bbls, 'type': position_type, 'K': K, 'greeks': greeks, 'value': value})
            position_data.append({
                'Pos': i+1, 'bbl': f"{bbls:+,}", 'Type': position_type.upper(), 
                'Δ': f"{bbls*greeks['delta']:+,}", 'Γ': f"{bbls*greeks['gamma']:.1f}",
                'V': f"{bbls*greeks['vega']:.0f}", 'Θ': f"{bbls*greeks['theta']:.0f}", 'P&L': f"${value:,.0f}"
            })

# Position Table
if position_data:
    st.subheader("📋 Portfolio Greeks")
    st.dataframe(pd.DataFrame(position_data), use_container_width=True, hide_index=True)

# Net Greeks
if positions:
    net_delta = sum(p['bbls'] * p['greeks']['delta'] for p in positions)
    net_gamma = sum(p['bbls'] * p['greeks']['gamma'] for p in positions)
    net_vega = sum(p['bbls'] * p['greeks']['vega'] for p in positions)
    net_theta = sum(p['bbls'] * p['greeks']['theta'] for p in positions)
    net_value = sum(p['value'] for p in positions)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Net Δ", f"{net_delta:,.0f} bbl")
    col2.metric("Net Γ", f"{net_gamma:.1f}")
    col3.metric("Net Vega", f"{net_vega:.0f}")
    col4.metric("Net Theta", f"${net_theta:.0f}/day")

    # FULL Hedge Recommendations
    st.subheader("🎯 Hedge Actions")
    hedge_delta = -net_delta
    hedge_gamma = -net_gamma if abs(net_gamma) > 10 else 0
    hedge_vega = -net_vega if abs(net_vega) > 100 else 0
    
    col1, col2, col3 = st.columns(3)
    if abs(hedge_delta) > 1:
        direction = "BUY" if hedge_delta > 0 else "SELL"
        col1.error(f"**{direction} {abs(hedge_delta):,.0f} bbl** futures")
    else:
        col1.success("✅ **Delta Neutral**")
    
    if abs(hedge_gamma) > 0.1:
        col2.warning(f"**Gamma hedge**: {abs(hedge_gamma):.1f} ATM options")
    else:
        col2.success("✅ **Gamma OK**")
    
    if abs(hedge_vega) > 50:
        col3.warning(f"**Vega hedge**: {abs(hedge_vega):.0f} vol product")
    else:
        col3.success("✅ **Vega OK**")

# Live Shocks - FULL GREEKS
st.header("⚡ Live Market Shocks")
col1, col2, col3 = st.columns(3)
spot_shock = col1.slider("Spot Δ ($)", -5.0, 5.0, 0.0, 0.1)
iv_shock = col2.slider("IV Δ (%)", -10.0, 10.0, 0.0, 0.1)/100
days_passed = col3.slider("Days Passed", 0, 7, 0)

if st.button("💥 Run FULL Shock", use_container_width=True) and positions:
    new_S = S + spot_shock
    new_IV = IV + iv_shock
    new_T = max(T - days_passed/365, 1e-6)
    
    # Full portfolio revaluation
    new_value = 0
    new_delta, new_gamma, new_vega, new_theta = 0, 0, 0, 0
    
    for p in positions:
        if p['type'] == 'futures':
            new_value += p['bbls'] * (new_S - p['K'])
            new_delta += p['bbls'] * p['greeks']['delta']
        else:
            new_greeks = black_scholes_greeks(new_S, p['K'], new_T, r, new_IV, p['type'])
            new_value += p['bbls'] * new_greeks['price']
            new_delta += p['bbls'] * new_greeks['delta']
            new_gamma += p['bbls'] * new_greeks['gamma']
            new_vega += p['bbls'] * new_greeks['vega']
            new_theta += p['bbls'] * new_greeks['theta']
    
    total_pnl = new_value - net_value
    
    # Breakdown
    delta_pnl = net_delta * spot_shock
    gamma_pnl = 0.5 * net_gamma * (spot_shock**2)
    vega_pnl = net_vega * (iv_shock * 100)
    theta_pnl = net_theta * days_passed
    
    col1, col2 = st.columns(2)
    col1.metric("Total P&L", f"${total_pnl:,.0f}", delta_color="inverse")
    col2.metric("Delta Neutral P&L", f"${total_pnl - delta_pnl:,.0f}", delta_color="normal")
    
    # P&L Table
    st.subheader("📊 FULL Greeks P&L")
    pnl_data = {
        "Greek": ["Delta", "Gamma", "Vega", "Theta", "Total"],
        "P&L ($)": [f"{delta_pnl:,.0f}", f"{gamma_pnl:,.0f}", f"{vega_pnl:,.0f}", f"{theta_pnl:,.0f}", f"{total_pnl:,.0f}"]
    }
    st.table(pnl_data)
    
    st.info(f"**New Greeks**: Δ={new_delta:,.0f} | Γ={new_gamma:.1f} | V={new_vega:.0f} | Θ=${new_theta:.0f}")
    
    if abs(total_pnl - delta_pnl) > 100:
        st.balloons()
        st.success("🎉 **Greek-neutral scalping profit!**")

# Charts
if positions:
    st.header("📈 Risk Surfaces")
    fig = go.Figure()
    # Delta profile
    spot_range = np.linspace(S*0.9, S*1.1, 30)
    deltas = []
    for s in spot_range:
        pd = sum(p['bbls'] * black_scholes_greeks(s, p['K'], T, r, IV, p['type'])['delta'] 
                for p in positions if p['type'] != 'futures')
        deltas.append(pd)
    fig.add_trace(go.Scatter(x=spot_range, y=deltas, name='Net Delta', line=dict(color='blue', width=3)))
    fig.add_vline(x=S, line_dash="dash", line_color="black")
    fig.update_layout(title="Delta Profile vs Spot", height=400)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("**FULL Greeks**: ΔΓVΘ + Futures MTM | Real oil desk hedging [memory:72][memory:73]")
