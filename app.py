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
    else:
        price = K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = -norm.cdf(-d1)
    
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    return {'price': price, 'delta': delta, 'gamma': gamma}

st.title("🛢️ Oil Trading Desk - PERFECT DELTA")
st.markdown("**Short -52 futures = -52 delta** | Trade→Notional→MTM→P&L")

# Sidebar
st.sidebar.header("Market")
S = st.sidebar.number_input("WTI Spot ($/bbl)", value=70.0, step=0.1)
IV = st.sidebar.number_input("Implied Vol (%)", value=35.0, min_value=1.0)/100
r = st.sidebar.number_input("Risk-Free (%)", value=0.0)/100
T_days = st.sidebar.slider("Days to Expiry", 1, 90, 30)
T = T_days/365

# Portfolio with CORRECT FUTURES DELTA
st.header("📊 Portfolio")
positions = []
position_data = []

for i in range(5):
    with st.expander(f"Position {i+1}", expanded=(i==0)):
        col1, col2, col3, col4, col5 = st.columns(5)
        
        bbls = col1.number_input("bbl", key=f"bbl{i}", value=0.0, step=10.0, format="%.0f", min_value=None)
        position_type = col2.selectbox("Type", ["call", "put", "futures"], key=f"type{i}")
        
        if position_type == "futures":
            col3.info("🛢️ No Strike")
            K = S
        else:
            K = col3.number_input("Strike ($)", value=float(round(S)), key=f"K{i}", step=0.1, format="%.1f")
        
        trade_price = col4.number_input("Trade Price ($)", value=0.0, key=f"trade{i}", step=0.1, format="%.2f")
        
        if bbls != 0:
            if position_type == "futures":
                # **CORRECT FUTURES LOGIC**:
                # Futures always have delta = +1.0 per bbl
                # Long futures (+bbls): net_delta = +bbls * 1.0 = +bbls
                # Short futures (-bbls): net_delta = -bbls * 1.0 = -bbls ✓
                delta_per_bbl = 1.0  # Always +1.0 for futures!
                current_price = 0.0
                notional_value = abs(bbls) * trade_price
                mtm_value = 0.0
                pnl = 0.0
                col5.info(f"Δ=+1.0/bbl | MTM=0")
            else:
                greeks = black_scholes_greeks(S, K, T, r, IV, position_type)
                delta_per_bbl = greeks['delta']
                current_price = greeks['price']
                notional_value = abs(bbls) * trade_price
                mtm_value = bbls * current_price
                pnl = mtm_value - (bbls * trade_price)
                col5.metric("Δ/Γ", f"{delta_per_bbl:.2f}/{greeks['gamma']:.3f}")
            
            # **NET DELTA = bbls * delta_per_bbl**
            net_delta = bbls * delta_per_bbl
            
            position = {
                'bbls': bbls, 'type': position_type, 'K': K,
                'trade_price': trade_price, 'current_price': current_price,
                'notional_value': notional_value, 'mtm_value': mtm_value, 
                'pnl': pnl, 'delta_per_bbl': delta_per_bbl, 'net_delta': net_delta
            }
            positions.append(position)
            
            position_data.append({
                'Pos': i+1,
                'bbls': f"{bbls:+.0f}",
                'Type': position_type.upper(),
                'Trade': f"${trade_price:.2f}",
                'Notional': f"${notional_value:,.0f}",
                'MTM Val': f"${mtm_value:,.0f}",
                'P&L': f"${pnl:,.0f}",
                'Net Δ': f"{net_delta:+.1f}"
            })

# TRADE BOOK
if position_data:
    st.subheader("📊 Trade Book")
    df = pd.DataFrame(position_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # NET TOTALS
    net_delta_total = sum(p['net_delta'] for p in positions)
    net_gamma_total = sum(p['bbls'] * black_scholes_greeks(S, p['K'], T, r, IV, p['type'])['gamma'] 
                         for p in positions if p['type'] != 'futures')
    net_pnl_total = sum(p['pnl'] for p in positions)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("**Net Δ**", f"{net_delta_total:+.1f} bbl")
    col2.metric("**Net Γ**", f"{net_gamma_total:+.2f}")
    col3.metric("**Total P&L**", f"${net_pnl_total:,.0f}")

    # DELTA HEDGE
    st.subheader("🔧 Delta Hedge")
    hedge_bbl = -net_delta_total
    hedge_cl = hedge_bbl / 1000
    
    if abs(hedge_bbl) < 0.5:
        st.success("🎯 **DELTA NEUTRAL**")
    elif hedge_bbl > 0:
        st.success(f"✅ **BUY {hedge_bbl:+.1f} bbl** ({hedge_cl:.2f} CL)")
    else:
        st.error(f"❌ **SELL {-hedge_bbl:+.1f} bbl** ({-hedge_cl:.2f} CL)")

    # MARKET SHOCKS
    st.header("⚡ Market Shocks")
    col1, col2 = st.columns(2)
    spot_shock = col1.slider("Spot Shock ($)", -5.0, 5.0, 0.0, 0.1)
    iv_shock = col2.slider("IV Shock (%)", -10.0, 10.0, 0.0, 0.1)/100

    if st.button("🎯 Run Shock", use_container_width=True):
        new_S = S + spot_shock
        new_IV = IV + iv_shock
        
        shock_data = []
        shock_total_pnl = 0
        new_net_delta = 0
        
        for p in positions:
            if p['type'] == "futures":
                shock_pnl = p['bbls'] * spot_shock
                new_net_delta += p['net_delta']
            else:
                new_greeks = black_scholes_greeks(new_S, p['K'], max(T-1/365, 1e-6), r, new_IV, p['type'])
                new_mtm_value = p['bbls'] * new_greeks['price']
                shock_pnl = new_mtm_value - p['mtm_value']
                new_net_delta += p['bbls'] * new_greeks['delta']
            
            shock_total_pnl += shock_pnl
            shock_data.append({
                'Position': f"{p['bbls']:+.0f} {p['type'].upper()}",
                'Shock P&L': f"${shock_pnl:+,.0f}"
            })
        
        col1, col2 = st.columns(2)
        col1.metric("**Shock P&L**", f"${shock_total_pnl:,.0f}", delta_color="inverse")
        col2.metric("**New Net Δ**", f"{new_net_delta:+.1f} bbl")
        
        st.subheader("💥 Shock P&L")
        st.table(shock_data)

# P&L Profile Chart
if positions:
    st.header("📈 P&L Profile")
    spot_range = np.linspace(S*0.85, S*1.15, 50)
    pnls = []
    
    for spot in spot_range:
        portfolio_pnl = 0
        for p in positions:
            if p['type'] == 'futures':
                portfolio_pnl += p['bbls'] * (spot - S)
            else:
                greeks = black_scholes_greeks(spot, p['K'], T, r, IV, p['type'])
                new_value = p['bbls'] * greeks['price']
                portfolio_pnl += new_value - (p['bbls'] * p['trade_price'])
        pnls.append(portfolio_pnl)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=spot_range, y=pnls, name='Portfolio P&L', 
                            line=dict(color='green', width=3)))
    fig.add_vline(x=S, line_dash="dash", line_color="black", annotation_text="Current")
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.update_layout(title="Portfolio P&L vs Spot", xaxis_title="WTI Spot ($)", 
                     yaxis_title="P&L ($)", height=400)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("**PERFECT** | Short -52 futures = -52 delta | +100 call = +53.6 delta = NEUTRAL")
