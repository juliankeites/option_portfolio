import streamlit as st
import numpy as np
from scipy.stats import norm
import plotly.graph_objects as go
import pandas as pd

@st.cache_data
def black_scholes_greeks(S, K, T, r, sigma, option_type='call'):
    if T <= 0: T = 1e-6
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
        delta = norm.cdf(d1)
    else:  # put
        price = K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = -norm.cdf(-d1)
    
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    return {'price': price, 'delta': delta, 'gamma': gamma}

st.title("🛢️ Oil Options Delta-Gamma Hedging Trainer")
st.markdown("**Pure bbl math** - Long/Short Options + Futures | Real oil MM simulator")

# Sidebar: Market Parameters
st.sidebar.header("Market")
S = st.sidebar.number_input("WTI Spot ($/bbl)", value=70.0, step=0.1)
IV = st.sidebar.number_input("Implied Vol (%)", value=35.0, min_value=1.0)/100
r = st.sidebar.number_input("Risk-Free Rate (%)", value=5.0)/100
T_days = st.sidebar.slider("Days to Expiry", 1, 90, 30)
T = T_days/365

# Portfolio: OPTIONS + FUTURES with POSITION TABLE
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
            K = col3.number_input("Strike/Spot ($)", value=float(round(S)), key=f"K{i}", step=0.1, format="%.1f")
        with col4:
            if position_type == "futures":
                st.info("🛢️ Futures: Δ=±1.0")
            elif bbls != 0 and position_type != "futures":
                greeks = black_scholes_greeks(S, K, T, r, IV, position_type)
                st.info(f"Δ={greeks['delta']:.2f} | Γ={greeks['gamma']:.3f}")
        
        if bbls != 0:
            if position_type == "futures":
                # FIXED: Delta = SIGN(bbls) * 1.0
                delta = 1.0 if bbls > 0 else -1.0
                greeks = {'delta': delta, 'gamma': 0.0, 'price': 0.0}
                value = bbls * S  # Futures marked to spot
            else:
                greeks = black_scholes_greeks(S, K, T, r, IV, position_type)
                value = bbls * greeks['price']
            
            position = {'bbls': bbls, 'type': position_type, 'K': K, 'greeks': greeks, 'value': value}
            positions.append(position)
            
            # Position table data
            direction = "LONG" if bbls > 0 else "SHORT"
            position_data.append({
                'Position': i+1,
                'bbl': f"{bbls:+,} bbl",
                'Type': position_type.upper(),
                'Strike': f"${K:.1f}",
                'Δ/bbl': f"{greeks['delta']:.2f}",
                'Net Δ': f"{bbls * greeks['delta']:+,.0f}",
                'Value': f"${value:,.0f}"
            })

# Position Table
if position_data:
    st.subheader("📋 Position Summary")
    df_positions = pd.DataFrame(position_data)
    st.dataframe(df_positions, use_container_width=True)

# Net Greeks & Portfolio Totals
if positions:
    net_delta_bbl = sum(p['bbls'] * p['greeks']['delta'] for p in positions)
    net_gamma_bbl = sum(p['bbls'] * p['greeks']['gamma'] for p in positions)
    net_value = sum(p['value'] for p in positions)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Net Δ (bbl)", f"{net_delta_bbl:+,.0f}")
    col2.metric("Net Γ (bbl)", f"{net_gamma_bbl:.1f}")
    col3.metric("Total Value", f"${net_value:,.0f}")

    # Delta Hedge - PERFECT MATH
    st.subheader("🔧 Delta Hedge")
    hedge_bbl = -net_delta_bbl
    hedge_cl = hedge_bbl / 1000
    
    if abs(hedge_bbl) < 1:
        st.success("🎯 **DELTA NEUTRAL** - No futures needed!")
    elif hedge_bbl > 0:
        st.success(f"✅ **BUY {hedge_bbl:,.0f} bbl** futures ({hedge_cl:.2f} CL)")
    else:
        st.error(f"❌ **SELL {-hedge_bbl:,.0f} bbl** futures ({-hedge_cl:.2f} CL)")
    
    if abs(net_gamma_bbl) > 10:
        st.warning(f"⚠️ Gamma {net_gamma_bbl:.1f} bbl - Add ATM options")

    # Live Shocks
    st.header("⚡ Live Market Shocks")
    col1, col2 = st.columns(2)
    spot_shock = col1.slider("Spot Shock ($)", -5.0, 5.0, 0.0, 0.1)
    iv_shock = col2.slider("IV Shock (%)", -10.0, 10.0, 0.0, 0.1)/100

    if st.button("🔄 Run Shock Simulation", use_container_width=True):
        new_S = S + spot_shock
        new_IV = IV + iv_shock
        
        # New portfolio value
        new_value = 0
        new_delta_bbl = 0
        
        for p in positions:
            if p['type'] == 'futures':
                new_value += p['bbls'] * new_S
                new_delta_bbl += p['bbls'] * p['greeks']['delta']
            else:
                new_greeks = black_scholes_greeks(new_S, p['K'], max(T-1/365, 1e-6), r, new_IV, p['type'])
                new_value += p['bbls'] * new_greeks['price']
                new_delta_bbl += p['bbls'] * new_greeks['delta']
        
        # TRUE P&L
        total_pnl = new_value - net_value
        
        col1, col2 = st.columns(2)
        col1.metric("Portfolio P&L", f"${total_pnl:,.0f}", delta_color="inverse")
        col2.metric("Delta Neutral P&L", f"${total_pnl - (net_delta_bbl * spot_shock):,.0f}", delta_color="normal")
        
        st.info(f"**New Net Δ: {new_delta_bbl:,.0f} bbl**")
        
        if abs(total_pnl - (net_delta_bbl * spot_shock)) > 50:
            st.balloons()
            st.success("🎉 **Pure gamma/vega profit!**")

# Charts
if positions:
    st.header("📈 Risk Profiles")
    spot_range = np.linspace(S*0.85, S*1.15, 50)
    deltas = [sum(p['bbls'] * black_scholes_greeks(s, p['K'], T, r, IV, p['type'])['delta'] 
                 for p in positions if p['type'] != 'futures') for s in spot_range]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=spot_range, y=deltas, name='Net Delta', line=dict(color='blue', width=3)))
    fig.add_vline(x=S, line_dash="dash", line_color="black")
    fig.update_layout(title="Delta Profile", xaxis_title="Spot ($)", yaxis_title="Net Δ (bbl)", height=400)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("**Oil trader ready** | bbl positions | Futures Δ=sign(bbl)*1.0 | True marked-to-market P&L [memory:72]")
