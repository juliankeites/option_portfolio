import streamlit as st
import numpy as np
from scipy.stats import norm
import plotly.graph_objects as go

@st.cache_data
def black_scholes_greeks(S, K, T, r, sigma, option_type='call'):
    if T <= 0: 
        T = 1e-6
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
st.markdown("**Pure bbl math** - Long/Short Options + Futures | Real oil desk simulator")

# Sidebar: Market Parameters
st.sidebar.header("Market")
S = st.sidebar.number_input("WTI Spot ($/bbl)", value=70.0, step=0.1)
IV = st.sidebar.number_input("Implied Vol (%)", value=35.0, min_value=1.0)/100
r = st.sidebar.number_input("Risk-Free Rate (%)", value=0.0)/100
T_days = st.sidebar.slider("Days to Expiry", 1, 90, 30)
T = T_days/365

# Portfolio: OPTIONS + FUTURES (bbl) - FIXED DELTA
st.header("📊 Portfolio (bbl)")
positions = []
for i in range(5):
    with st.expander(f"Position {i+1}", expanded=(i==0)):
        col1, col2, col3, col4 = st.columns([2,1.5,2,1.5])
        with col1:
            bbls = col1.number_input(
                "bbl (negative=short)", 
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
                st.info("Futures: Δ=±1.0, Γ=0")
        
        if bbls != 0:
            if position_type == "futures":
                # FIXED: Delta matches position direction
                delta_sign = 1.0 if bbls > 0 else -1.0
                positions.append({
                    'bbls': bbls, 'type': 'futures', 'K': S,
                    'greeks': {'delta': delta_sign, 'gamma': 0.0, 'price': 0.0}
                })
            else:
                greeks = black_scholes_greeks(S, K, T, r, IV, position_type)
                positions.append({'bbls': bbls, 'type': position_type, 'K': K, 'greeks': greeks})

# Calculate Net Greeks & Portfolio Value
if positions:
    net_delta_bbl = sum(p['bbls'] * p['greeks']['delta'] for p in positions)
    net_gamma_bbl = sum(p['bbls'] * p['greeks']['gamma'] for p in positions)
    net_premium = sum(p['bbls'] * p['greeks']['price'] for p in positions)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Net Δ (bbl)", f"{net_delta_bbl:.0f}")
    col2.metric("Net Γ (bbl)", f"{net_gamma_bbl:.1f}")
    col3.metric("Portfolio Value", f"${net_premium:.0f}")

    # Delta Hedge Actions
    st.subheader("🔧 Delta Hedge")
    hedge_bbl = -net_delta_bbl
    hedge_futures = hedge_bbl / 1000  # CL contracts (1,000 bbl)
    
    if abs(hedge_bbl) < 1:
        st.success("🎯 **DELTA NEUTRAL** - No futures hedge needed!")
    elif hedge_bbl > 0:
        st.success(f"✅ **BUY {hedge_bbl:.0f} bbl** futures ({hedge_futures:.2f} CL)")
    else:
        st.error(f"❌ **SELL {-hedge_bbl:.0f} bbl** futures ({-hedge_futures:.2f} CL)")
    
    if abs(net_gamma_bbl) > 10:
        st.warning(f"⚠️ Gamma {net_gamma_bbl:.1f} bbl - Consider gamma hedge")

    # Live Practice Rounds
    st.header("⚡ Live Hedging Practice")
    col1, col2 = st.columns(2)
    spot_shock = col1.slider("Spot Shock ($)", -5.0, 5.0, 0.0, 0.1)
    iv_shock = col2.slider("IV Shock (%)", -10.0, 10.0, 0.0, 0.1)/100

    if st.button("🔄 Run Market Shock", use_container_width=True):
        new_S = S + spot_shock
        new_IV = IV + iv_shock
        
        # Calculate NEW portfolio value
        initial_value = net_premium
        new_value = 0
        new_delta_bbl = 0
        
        for p in positions:
            if p['type'] == 'futures':
                # Futures value = bbls * spot price
                new_value += p['bbls'] * new_S
                new_delta_bbl += p['bbls'] * p['greeks']['delta']
            else:
                # Options: recalculate premium
                new_greeks = black_scholes_greeks(new_S, p['K'], max(T-1/365, 1e-6), r, new_IV, p['type'])
                new_value += p['bbls'] * new_greeks['price']
                new_delta_bbl += p['bbls'] * new_greeks['delta']
        
        # TRUE P&L = Change in portfolio value
        total_pnl = new_value - initial_value
        
        col1, col2 = st.columns(2)
        col1.metric("Unhedged P&L", f"${total_pnl:.0f}", delta_color="inverse")
        col2.metric("Delta-Hedged P&L*", f"{0.5 * net_gamma_bbl * (spot_shock**2):.0f}", delta_color="normal")
        
        st.caption("*Delta-hedged assumes perfect futures hedge + gamma scalping")
        
        # P&L Breakdown
        st.subheader("📊 Value Breakdown")
        delta_approx = net_delta_bbl * spot_shock
        gamma_approx = 0.5 * net_gamma_bbl * (spot_shock**2)
        st.table({
            "Component": ["Actual P&L", "Δ Approx", "Γ Approx", "Difference"],
            "Value ($)": [f"{total_pnl:.0f}", f"{delta_approx:.0f}", f"{gamma_approx:.0f}", f"{total_pnl - delta_approx:.0f}"]
        })
        
        st.info(f"**New Net Δ: {new_delta_bbl:.0f} bbl** → Rehedge required")
        
        if abs(total_pnl) > 100:
            st.balloons()
            st.success("🎉 **Significant P&L move!**")

# Risk Profiles
if positions:
    st.header("📈 Risk Profiles")
    spot_range = np.linspace(S*0.85, S*1.15, 50)
    
    portfolio_values = []
    for s in spot_range:
        port_value = 0
        for p in positions:
            if p['type'] == 'futures':
                port_value += p['bbls'] * s
            else:
                greeks = black_scholes_greeks(s, p['K'], T, r, IV, p['type'])
                port_value += p['bbls'] * greeks['price']
        portfolio_values.append(port_value)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=spot_range, y=portfolio_values, 
                            name='Portfolio Value', line=dict(color='green', width=3)))
    fig.add_hline(y=net_premium, line_dash="dash", line_color="black", 
                  annotation_text=f"Current: ${net_premium:.0f}")
    fig.add_vline(x=S, line_dash="dash", line_color="gray")
    fig.update_layout(
        title="Portfolio Value vs Spot Price",
        xaxis_title="WTI Spot ($/bbl)", 
        yaxis_title="Portfolio Value ($)",
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("➕ Add positions above to see analytics")

st.markdown("---")
st.caption("**Oil Trader Tools** | 100 bbl options | 1,000 bbl CL futures | Pure barrel math")
