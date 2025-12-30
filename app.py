import streamlit as st
import numpy as np
from scipy.stats import norm
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Black-Scholes Greeks (for oil calls/puts)
@st.cache_data
def black_scholes_greeks(S, K, T, r, sigma, option_type='call'):
    # Avoid division by zero for very small T
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

# Streamlit App
st.title("🛢️ Oil Options Delta-Gamma Hedging Trainer")
st.markdown("Practice market making & hedging with live simulations!")

# Sidebar: Market Parameters (Live-like)
st.sidebar.header("Market")
S = st.sidebar.number_input("WTI Spot ($/bbl)", value=70.0, step=0.1)
IV = st.sidebar.number_input("Implied Vol (%)", value=35.0, min_value=1.0)/100
r = st.sidebar.number_input("Risk-Free Rate (%)", value=5.0)/100
T_days = st.sidebar.slider("Days to Expiry", 1, 90, 30)
T = T_days/365

# Portfolio Input (Adaptable)
st.header("📊 Your Portfolio")
positions = []
for i in range(3):  # Add up to 3 legs
    with st.expander(f"Leg {i+1}", expanded=(i==0)):
        col1, col2 = st.columns(2)
        with col1:
            qty = st.number_input(f"Quantity (Contracts x100 bbl)", key=f"qty{i}", value=0, step=1, format="%d")
            opt_type = st.selectbox("Call/Put", ["call", "put"], key=f"type{i}")
        with col2:
            K = st.number_input("Strike ($)", value=float(round(S)), key=f"K{i}", step=0.1, format="%.1f")
        
        if qty != 0:
            greeks = black_scholes_greeks(S, K, T, r, IV, opt_type)
            positions.append({'qty': qty, 'type': opt_type, 'K': K, 'greeks': greeks})

# Calculate Net Greeks
if positions:
    net_delta = sum(p['qty'] * p['greeks']['delta'] for p in positions)
    net_gamma = sum(p['qty'] * p['greeks']['gamma'] for p in positions)
    net_premium = sum(p['qty'] * p['greeks']['price'] * 100 for p in positions)  # 100 barrels per contract
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Net Delta", f"{net_delta:.2f}")
    col2.metric("Net Gamma", f"{net_gamma:.4f}")
    col3.metric("Net Premium", f"${net_premium:.0f}")

    # Delta Hedge Suggestion
    st.subheader("🔧 Hedge Actions")
    hedge_futures = -net_delta * 100 / 1000  # Convert to futures contracts (1000 bbl each)
    st.info(f"**Trade {hedge_futures:.1f} CL futures** to delta-neutralize.")
    if abs(net_gamma) > 0.01:
        st.warning(f"High Gamma ({net_gamma:.4f}): Consider gamma hedging with ATM options.")

# Practice Rounds: Simulate Shocks
if positions:
    st.header("⚡ Live Hedging Practice")
    col1, col2 = st.columns(2)
    with col1:
        spot_shock = st.slider("Spot Shock ($)", -5.0, 5.0, 0.0, step=0.1)
    with col2:
        iv_shock = st.slider("IV Shock (%)", -10.0, 10.0, 0.0, step=0.1)/100

    if st.button("Run Hedge Round"):
        new_S = S + spot_shock
        new_IV = IV + iv_shock
        
        # Recalculate deltas with new parameters
        new_net_delta = 0
        for p in positions:
            new_greeks = black_scholes_greeks(new_S, p['K'], max(T-1/365, 1e-6), r, new_IV, p['type'])
            new_net_delta += p['qty'] * new_greeks['delta']
        
        # P&L calculations
        delta_change_pnl = (new_net_delta - net_delta) * spot_shock * 100  # Per contract
        gamma_pnl = 0.5 * net_gamma * (spot_shock**2) * 100  # Gamma effect
        theta_pnl = -0.01 * net_premium  # Simple theta decay approximation
        iv_pnl = 0.5 * iv_shock * net_premium  # Simple vega approximation
        
        pnl_unhedged = delta_change_pnl + gamma_pnl + theta_pnl + iv_pnl
        pnl_hedged = pnl_unhedged + hedge_futures * spot_shock * 1000  # Futures hedge effect
        
        col1, col2 = st.columns(2)
        col1.metric("Unhedged P&L", f"${pnl_unhedged:.0f}", delta_color="inverse")
        col2.metric("Hedged P&L (Delta-Neutral)", f"${pnl_hedged:.0f}", delta_color="normal")
        
        if abs(new_net_delta) < 0.1:
            st.balloons()
            st.success("🎉 Great hedge! Gamma scalping opportunity next.")

# Visualizations
st.header("📈 Risk Visualizations")

if positions:
    # Create Greeks surface plot
    st.subheader("Greeks Surface")
    
    # Generate range for spot prices
    spot_range = np.linspace(S*0.8, S*1.2, 50)
    
    # Calculate portfolio Greeks across spot range
    portfolio_deltas = []
    portfolio_gammas = []
    
    for s in spot_range:
        port_delta = 0
        port_gamma = 0
        for p in positions:
            greeks = black_scholes_greeks(s, p['K'], T, r, IV, p['type'])
            port_delta += p['qty'] * greeks['delta']
            port_gamma += p['qty'] * greeks['gamma']
        portfolio_deltas.append(port_delta)
        portfolio_gammas.append(port_gamma)
    
    # Create delta profile chart
    fig_delta = go.Figure()
    fig_delta.add_trace(go.Scatter(
        x=spot_range, 
        y=portfolio_deltas,
        mode='lines',
        name='Portfolio Delta',
        line=dict(color='blue', width=2)
    ))
    fig_delta.add_vline(x=S, line_dash="dash", line_color="gray")
    fig_delta.update_layout(
        title="Delta Profile vs Spot Price",
        xaxis_title="Spot Price ($)",
        yaxis_title="Portfolio Delta",
        height=400
    )
    st.plotly_chart(fig_delta, use_container_width=True)
    
    # Create gamma profile chart
    fig_gamma = go.Figure()
    fig_gamma.add_trace(go.Scatter(
        x=spot_range, 
        y=portfolio_gammas,
        mode='lines',
        name='Portfolio Gamma',
        line=dict(color='red', width=2)
    ))
    fig_gamma.add_vline(x=S, line_dash="dash", line_color="gray")
    fig_gamma.update_layout(
        title="Gamma Profile vs Spot Price",
        xaxis_title="Spot Price ($)",
        yaxis_title="Portfolio Gamma",
        height=400
    )
    st.plotly_chart(fig_gamma, use_container_width=True)

else:
    st.info("Add portfolio positions to see visualizations and run hedging simulations.")

st.info("💡 **Pro Tip**: In oil MM, rehedge on 1-2% moves. Gamma profits from volatility! Watch expiry weeks closely.")
