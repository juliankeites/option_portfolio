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

# Portfolio: OPTIONS + FUTURES (bbl)
st.header("📊 Your Portfolio (bbl)")
positions = []
for i in range(4):
    with st.expander(f"Position {i+1}", expanded=(i==0)):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            bbls = col1.number_input(
                "bbl (neg=short)", 
                key=f"bbl{i}", 
                value=0.0, 
                step=10.0, 
                format="%.0f",
                min_value=None
            )
        with col2:
            position_type = col2.selectbox("Type", ["call", "put", "futures"], key=f"type{i}")
        with col3:
            K = col3.number_input("Strike/Spot ($)", value=float(round(S)), key=f"K{i}", step=0.1, format="%.1f")
        with col4:
            if position_type == "futures":
                st.info("Futures: Δ=1.0, Γ=0")
        
        if bbls != 0:
            if position_type == "futures":
                positions.append({'bbls': bbls, 'type': 'futures', 'K': K, 
                                'greeks': {'delta': 1.0 if bbls > 0 else -1.0, 'gamma': 0.0, 'price': 0.0}})
            else:
                greeks = black_scholes_greeks(S, K, T, r, IV, position_type)
                positions.append({'bbls': bbls, 'type': position_type, 'K': K, 'greeks': greeks})

# Calculate Net Greeks (ALL in bbl)
if positions:
    net_delta_bbl = sum(p['bbls'] * p['greeks']['delta'] for p in positions)
    net_gamma_bbl = sum(p['bbls'] * p['greeks']['gamma'] for p in positions)
    net_premium = sum(p['bbls'] * p['greeks']['price'] for p in positions)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Portfolio Net Δ (bbl)", f"{net_delta_bbl:.0f}")
    col2.metric("Portfolio Net Γ (bbl)", f"{net_gamma_bbl:.1f}")
    col3.metric("Net Premium: +ve=Paid/-ve=Received", f"${net_premium:.0f}")

    # Delta Hedge: DIRECTIONAL (sign matters!)
    st.subheader("🔧 Hedge Actions")
    hedge_bbl = -net_delta_bbl
    hedge_futures = hedge_bbl / 1000

    if hedge_bbl > 0:
        st.success(f"✅ **BUY {hedge_bbl:.0f} bbl** futures ({hedge_futures:.2f} CL contracts)")
    else:
        st.error(f"❌ **SELL {-hedge_bbl:.0f} bbl** futures ({-hedge_futures:.2f} CL contracts)")
    
    if abs(net_gamma_bbl) > 10:
        st.warning(f"⚠️ Gamma {net_gamma_bbl:.1f} bbl - Consider ATM options hedge")

    # Live Practice Rounds
    st.header("⚡ Live Hedging Practice")
    col1, col2 = st.columns(2)
    spot_shock = col1.slider("Spot Shock ($)", -5.0, 5.0, 0.0, 0.1)
    iv_shock = col2.slider("IV Shock (%)", -10.0, 10.0, 0.0, 0.1)/100

    if st.button("🔄 Run Shock & Rehedge", use_container_width=True):
        new_S = S + spot_shock
        new_IV = IV + iv_shock
        
        # Recalculate post-shock portfolio value
        new_delta_bbl = 0
        new_gamma_bbl = 0
        new_premium = 0
        futures_pnl = 0
        
        for p in positions:
            if p['type'] == 'futures':
                futures_pnl += p['bbls'] * spot_shock
                new_delta_bbl += p['bbls'] * p['greeks']['delta']
            else:
                new_greeks = black_scholes_greeks(new_S, p['K'], max(T-1/365, 1e-6), r, new_IV, p['type'])
                new_delta_bbl += p['bbls'] * new_greeks['delta']
                new_gamma_bbl += p['bbls'] * new_greeks['gamma']
                new_premium += p['bbls'] * new_greeks['price']
        
        # TRUE P&L: Portfolio value change
        delta_pnl = net_delta_bbl * spot_shock
        gamma_pnl = 0.5 * net_gamma_bbl * (spot_shock**2)
        vega_pnl = (new_premium - net_premium) * 100
        theta_pnl = -net_premium * (1/365)
        total_futures_pnl = futures_pnl
        
        # RESULTS
        unhedged_total = delta_pnl + gamma_pnl + vega_pnl + theta_pnl + total_futures_pnl
        hedged_total = gamma_pnl + vega_pnl + theta_pnl + total_futures_pnl
        
        col1, col2 = st.columns(2)
        col1.metric("Unhedged P&L", f"${unhedged_total:.0f}", delta_color="inverse")
        col2.metric("Hedged P&L", f"${hedged_total:.0f}", delta_color="normal")
        
        # FULL Breakdown
        st.subheader("📊 P&L Breakdown")
        pnl_data = {
            "Component": ["Options Δ", "Options Γ", "Vega", "Theta", "Futures Spot", "Hedged Total"],
            "P&L ($)": [f"{delta_pnl:.0f}", f"{gamma_pnl:.0f}", f"{vega_pnl:.0f}", f"{theta_pnl:.0f}", f"{total_futures_pnl:.0f}", f"{hedged_total:.0f}"]
        }
        st.table(pnl_data)
        
        st.info(f"**New Δ: {new_delta_bbl:.0f} bbl** → Rehedge needed")
        
        if abs(hedged_total) > 50:
            st.balloons()
            st.success("🎉 **Greek-neutral profit!**")

# Visuals
if positions:
    st.header("📈 Risk Profiles")
    spot_range = np.linspace(S*0.85, S*1.15, 50)
    
    deltas, gammas = [], []
    for s in spot_range:
        pd = sum(p['bbls'] * black_scholes_greeks(s, p['K'], T, r, IV, p['type'])['delta'] for p in positions if p['type'] != 'futures')
        pg = sum(p['bbls'] * black_scholes_greeks(s, p['K'], T, r, IV, p['type'])['gamma'] for p in positions if p['type'] != 'futures')
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
