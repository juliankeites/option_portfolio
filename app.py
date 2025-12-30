import streamlit as st
import numpy as np
from scipy.stats import norm
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Black-Scholes Greeks (for oil calls/puts)
@st.cache_data
def black_scholes_greeks(S, K, T, r, sigma, option_type='call'):
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

# Streamlit App
st.title("🛢️ Oil Options Delta-Gamma Hedging Trainer")
st.markdown("Practice market making & hedging with live simulations!")

# Sidebar: Market Parameters (Live-like)
st.sidebar.header("Market")
S = st.sidebar.number_input("WTI Spot ($/bbl)", value=70.0, step=0.1)
IV = st.sidebar.number_input("Implied Vol (%)", value=35.0, min_value=1.0)/100
r = st.sidebar.number_input("Risk-Free Rate (%)", value=5.0)/100
T = st.sidebar.slider("Days to Expiry", 1, 90, 30)/365

# Portfolio Input (Adaptable)
st.header("📊 Your Portfolio")
positions = []
for i in range(3):  # Add up to 3 legs
    with st.expander(f"Leg {i+1}"):
        qty = st.number_input(f"Quantity (Contracts x100 bbl)", key=f"qty{i}", value=0)
        opt_type = st.selectbox("Call/Put", ["call", "put"], key=f"type{i}")
        K = st.number_input("Strike ($)", value=round(S), key=f"K{i}")
        if qty > 0:
            greeks = black_scholes_greeks(S, K, T, r, IV, opt_type)
            positions.append({'qty': qty, 'type': opt_type, 'K': K, 'greeks': greeks})

# Calculate Net Greeks
if positions:
    net_delta = sum(p['qty'] * p['greeks']['delta'] for p in positions)
    net_gamma = sum(p['qty'] * p['greeks']['gamma'] for p in positions)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Net Delta", f"{net_delta:.2f}", delta=f"{net_delta:.2f}")
    col2.metric("Net Gamma", f"{net_gamma:.4f}")
    col3.metric("Net Premium", f"${sum(p['qty']*p['greeks']['price']*100):.0f}")

    # Delta Hedge Suggestion
    st.subheader("🔧 Hedge Actions")
    hedge_futures = -net_delta  # Contracts to trade
    st.success(f"**Trade {hedge_futures:.1f} CL futures** to delta-neutralize.")
    if net_gamma > 0.01:
        st.warning(f"High Gamma ({net_gamma:.4f}): Add short ATM options to gamma hedge.")

# Practice Rounds: Simulate Shocks
st.header("⚡ Live Hedging Practice")
spot_shock = st.slider("Spot Shock ($)", -5.0, 5.0, 0.0)
iv_shock = st.slider("IV Shock (%)", -10.0, 10.0, 0.0)/100

if st.button("Run Hedge Round") and positions:
    new_S = S + spot_shock
    new_IV = IV + iv_shock
    new_net_delta = sum(p['qty'] * black_scholes_greeks(new_S, p['K'], T*0.99, r, new_IV, p['type'])['delta'] 
                        for p in positions)  # Theta decay sim
    
    pnl_unhedged = (new_net_delta - net_delta) * spot_shock * 100  # Per contract
    pnl_hedged = pnl_unhedged + hedge_futures * spot_shock * 1000  # Futures $10/tick
    
    st.metric("Unhedged P&L", f"${pnl_unhedged:.0f}", delta_color="inverse")
    st.metric("Hedged P&L (Delta-Neutral)", f"${pnl_hedged:.0f}", delta_color="normal")
    
    if abs(new_net_delta) < 0.1:
        st.balloons()
        st.success("🎉 Perfect hedge! Gamma scalping opportunity next.")

# Visuals: Greeks Surface & P&L Paths
fig = make_subplots(rows=2, cols=1, subplot_titles=["Greeks Heatmap", "Hedging P&L Paths"])
# ... (plotly code for surfaces/paths)
st.plotly_chart(fig)

st.info("💡 **Pro Tip**: In oil MM, rehedge on 1-2% moves. Gamma profits from vol! Adapt portfolio above.[web:22]")
