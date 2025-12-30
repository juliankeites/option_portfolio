import streamlit as st
import numpy as np
from scipy.stats import norm
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

st.title("🛢️ Oil Options Delta-Gamma Hedging Trainer")
st.markdown("**Pure bbl math** - Practice market making & hedging!")

# Sidebar: Market Parameters
st.sidebar.header("Market")
S = st.sidebar.number_input("Crude Price ($/bbl)", value=70.0, step=0.1)
IV = st.sidebar.number_input("Implied Vol (%)", value=35.0, min_value=1.0)/100
r = st.sidebar.number_input("Risk-Free Rate (%)", value=0.0)/100
T_days = st.sidebar.slider("Days to Expiry", 1, 90, 30)
T = T_days/365

# Portfolio: PURE BBL INPUT
st.header("📊 Your Portfolio (bbl)")
positions = []
for i in range(4):
    with st.expander(f"Position {i+1}", expanded=(i==0)):
        col1, col2, col3 = st.columns(3)
        with col1:
            bbls = col1.number_input(f"bbl", key=f"bbl{i}", value=0.0, step=10.0, format="%.0f")
        with col2:
            opt_type = col2.selectbox("Call/Put", ["call", "put"], key=f"type{i}")
        with col3:
            K = col3.number_input("Strike ($)", value=float(round(S)), key=f"K{i}", step=0.1, format="%.1f")
        
        if bbls > 0:
            greeks = black_scholes_greeks(S, K, T, r, IV, opt_type)
            positions.append({'bbls': bbls, 'type': opt_type, 'K': K, 'greeks': greeks})

# Calculate Net Greeks (ALL in bbl)
if positions:
    net_delta_bbl = sum(p['bbl'] * p['greeks']['delta'] for p in positions)
    net_gamma_bbl = sum(p['bbl'] * p['greeks']['gamma'] for p in positions)
    net_premium = sum(p['bbl'] * p['greeks']['price'] for p in positions)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Net Δ (bbl)", f"{net_delta_bbl:.0f}")
    col2.metric("Net Γ (bbl)", f"{net_gamma_bbl:.1f}")
    col3.metric("Net Premium", f"${net_premium:.0f}")

    # Delta Hedge: Pure bbl → bbl
    st.subheader("🔧 Hedge Actions")
    hedge_bbl = -net_delta_bbl
    hedge_futures = hedge_bbl / 1000  # Show CL equivalent
    st.success(f"**Short {hedge_bbl:.0f} bbl** futures ({hedge_futures:.2f} CL contracts)")
    
    if abs(net_gamma_bbl) > 10:
        st.warning(f"⚠️ Gamma {net_gamma_bbl:.0f} bbl - Consider ATM options hedge")

    # Live Practice Rounds
    st.header("⚡ Live Hedging Practice")
    col1, col2 = st.columns(2)
    spot_shock = col1.slider("Spot Shock ($)", -5.0, 5.0, 0.0, 0.1)
    iv_shock = col2.slider("IV Shock (%)", -10.0, 10.0, 0.0, 0.1)/100

    if st.button("🔄 Run Shock & Rehedge", use_container_width=True):
        new_S = S + spot_shock
        new_IV = IV + iv_shock
        
        # Recalculate post-shock
        new_delta_bbl = 0
        for p in positions:
            new_greeks = black_scholes_greeks(new_S, p['K'], max(T-1/365, 1e-6), r, new_IV, p['type'])
            new_delta_bbl += p['bbls'] * new_greeks['delta']
        
        # P&L Breakdown
        delta_pnl = net_delta_bbl * spot_shock
        gamma_pnl = 0.5 * net_gamma_bbl * (spot_shock**2)
        hedge_pnl = hedge_bbl * spot_shock
        total_hedged_pnl = gamma_pnl  # Pure gamma scalping profit
        
        col1, col2 = st.columns(2)
        col1.metric("Unhedged P&L", f"${delta_pnl+gamma_pnl:.0f}", delta_color="inverse")
        col2.metric("Hedged P&L", f"${total_hedged_pnl:.0f}", delta_color="normal")
        
        st.info(f"**New Delta: {new_delta_bbl:.0f} bbl** → Rehedge: Short {new_delta_bbl:.0f} bbl")
        
        if abs(total_hedged_pnl) > 50:
            st.balloons()
            st.success("🎉 **Gamma scalping profit!**")

# Visuals
if positions:
    st.header("📈 Risk Profiles")
    spot_range = np.linspace(S*0.85, S*1.15, 50)
    
    deltas, gammas = [], []
    for s in spot_range:
        pd = sum(p['bbls'] * black_scholes_greeks(s, p['K'], T, r, IV, p['type'])['delta'] for p in positions)
        pg = sum(p['bbls'] * black_scholes_greeks(s, p['K'], T, r, IV, p['type'])['gamma'] for p in positions)
        deltas.append(pd)
        gammas.append(pg)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=spot_range, y=deltas, name='Delta (bbl)', line=dict(color='blue', width=3)))
    fig.add_trace(go.Scatter(x=spot_range, y=gammas, name='Gamma (bbl)', line=dict(color='red', width=3)))
    fig.add_vline(x=S, line_dash="dash", line_color="black", annotation_text="Current Spot")
    fig.update_layout(title="Portfolio Greeks vs Spot Price", xaxis_title="Spot ($/bbl)", yaxis_title="Exposure (bbl)", height=500)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("➕ Enter bbl positions above")

st.markdown("---")
st.caption("**Pure bbl math** | Options & Futures both in barrels | Perfect for oil MM training")
