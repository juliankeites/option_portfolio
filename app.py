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
st.markdown("**Pure bbl math** | +ve=INCOME | -ve=LOSS | Futures Δ=-1.0 when short")

# Sidebar
st.sidebar.header("Market")
S = st.sidebar.number_input("WTI Spot ($/bbl)", value=70.0, step=0.1)
IV = st.sidebar.number_input("Implied Vol (%)", value=35.0, min_value=1.0)/100
r = st.sidebar.number_input("Risk-Free Rate (%)", value=0.0)/100
T_days = st.sidebar.slider("Days to Expiry", 1, 90, 30)
T = T_days/365

# Portfolio with P&L convention
st.header("📊 Your Portfolio (bbl)")
positions = []
position_data = []

for i in range(5):
    with st.expander(f"Position {i+1}", expanded=(i==0)):
        col1, col2, col3, col4 = st.columns([2,1.5,2,1.5])
        bbls = col1.number_input("bbl (neg=short)", key=f"bbl{i}", value=0.0, step=10.0, format="%.0f", min_value=None)
        position_type = col2.selectbox("Type", ["call", "put", "futures"], key=f"type{i}")
        K = col3.number_input("Strike/Spot ($)", value=float(round(S)), key=f"K{i}", step=0.1, format="%.1f")
        
        if position_type == "futures":
            st.info("🛢️ Futures: Δ=±1.0")
        elif bbls != 0 and position_type != "futures":
            greeks = black_scholes_greeks(S, K, T, r, IV, position_type)
            st.info(f"Δ={greeks['delta']:.2f} | Γ={greeks['gamma']:.3f}")
        
        if bbls != 0:
            if position_type == "futures":
                # FIXED: Futures delta = DIRECTION of position
                delta = 1.0 if bbls > 0 else -1.0  # +bbl=long=+1, -bbl=short=-1
                greeks = {'delta': delta, 'gamma': 0.0, 'price': 0.0}
                mtm_value = bbls * S  # Futures MTM
            else:
                greeks = black_scholes_greeks(S, K, T, r, IV, position_type)
                # P&L Convention: BUY options=-ve (cost), SELL options=+ve (income)
                mtm_value = -bbls * greeks['price']  # Negative bbls = income
            
            position = {'bbls': bbls, 'type': position_type, 'K': K, 'greeks': greeks, 'mtm_value': mtm_value}
            positions.append(position)
            
            direction = "LONG" if bbls > 0 else "SHORT"
            position_data.append({
                'Pos': i+1,
                'bbl': f"{bbls:+,}",
                'Type': position_type.upper(),
                'Strike': f"${K:.1f}",
                'Δ/bbl': f"{greeks['delta']:.2f}",
                'Net Δ': f"{bbls * greeks['delta']:+,}",
                'MTM': f"${mtm_value:,.0f}"
            })

# Position Table
if position_data:
    st.subheader("📋 Positions")
    df = pd.DataFrame(position_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

# Net Greeks
if positions:
    net_delta_bbl = sum(p['bbls'] * p['greeks']['delta'] for p in positions)
    net_gamma_bbl = sum(p['bbls'] * p['greeks']['gamma'] for p in positions)
    net_mtm = sum(p['mtm_value'] for p in positions)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Net Δ", f"{net_delta_bbl:+,.0f} bbl")
    col2.metric("Net Γ", f"{net_gamma_bbl:.1f}")
    col3.metric("Net MTM", f"${net_mtm:,.0f}")

    # Delta Hedge
    st.subheader("🔧 Delta Hedge")
    hedge_bbl = -net_delta_bbl
    hedge_cl = hedge_bbl / 1000
    
    if abs(hedge_bbl) < 1:
        st.success("🎯 **DELTA NEUTRAL**")
    elif hedge_bbl > 0:
        st.success(f"✅ **BUY {hedge_bbl:,.0f} bbl** ({hedge_cl:.2f} CL)")
    else:
        st.error(f"❌ **SELL {-hedge_bbl:,.0f} bbl** ({-hedge_cl:.2f} CL)")

    # Live Shocks
    st.header("⚡ Market Shocks")
    col1, col2 = st.columns(2)
    spot_shock = col1.slider("Spot Shock ($)", -5.0, 5.0, 0.0, 0.1)
    iv_shock = col2.slider("IV Shock (%)", -10.0, 10.0, 0.0, 0.1)/100

    if st.button("🔄 Run Shock", use_container_width=True):
        new_S = S + spot_shock
        new_IV = IV + iv_shock
        
        # New portfolio MTM
        new_mtm = 0
        new_delta = 0
        
        for p in positions:
            if p['type'] == 'futures':
                new_mtm += p['bbls'] * new_S
                new_delta += p['bbls'] * p['greeks']['delta']
            else:
                new_greeks = black_scholes_greeks(new_S, p['K'], max(T-1/365, 1e-6), r, new_IV, p['type'])
                new_mtm += -p['bbls'] * new_greeks['price']  # P&L convention
                new_delta += p['bbls'] * new_greeks['delta']
        
        pnl = new_mtm - net_mtm
        
        col1, col2 = st.columns(2)
        col1.metric("Portfolio P&L", f"${pnl:,.0f}", delta_color="inverse")
        col2.metric("Delta Neutral P&L", f"${pnl - (net_delta_bbl * spot_shock):,.0f}")
        
        st.info(f"New Net Δ: {new_delta:,.0f} bbl")

# Charts
if positions:
    st.header("📈 Delta Profile")
    spot_range = np.linspace(S*0.85, S*1.15, 50)
    portfolio_deltas = []
    for s in spot_range:
        delta_sum = sum(p['bbls'] * black_scholes_greeks(s, p['K'], T, r, IV, p['type'])['delta'] 
                       for p in positions if p['type'] != 'futures')
        portfolio_deltas.append(delta_sum + sum(p['bbls'] * p['greeks']['delta'] for p in positions if p['type'] == 'futures'))
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=spot_range, y=portfolio_deltas, name='Net Delta', line=dict(color='blue', width=3)))
    fig.add_vline(x=S, line_dash="dash", line_color="black")
    fig.update_layout(title="Net Delta vs Spot", xaxis_title="Spot ($)", yaxis_title="Net Δ (bbl)")
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("**Fixed**: Short futures Δ=-1.0 | Buy options=-cost | Sell options=+income")
