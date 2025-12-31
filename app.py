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

st.title("🛢️ Oil Options Hedging - PERFECT")
st.markdown("**Trade→MTM→P&L** | Futures MTM=0 | Long call+short future=Δ0")

# Sidebar
st.sidebar.header("Market")
S = st.sidebar.number_input("WTI Spot ($/bbl)", value=70.0, step=0.1)
IV = st.sidebar.number_input("Implied Vol (%)", value=35.0, min_value=1.0)/100
r = st.sidebar.number_input("Risk-Free (%)", value=0.0)/100
T_days = st.sidebar.slider("Days to Expiry", 1, 90, 30)
T = T_days/365

# Portfolio - BULLETPROOF DELTA + FUTURES FIX
st.header("📊 Portfolio")
positions = []
position_data = []

for i in range(5):
    with st.expander(f"Position {i+1}", expanded=(i==0)):
        col1, col2, col3, col4, col5 = st.columns(5)
        
        bbls = col1.number_input("bbl", key=f"bbl{i}", value=0.0, step=10.0, format="%.0f", min_value=None)
        position_type = col2.selectbox("Type", ["call", "put", "futures"], key=f"type{i}")
        
        # DISABLE STRIKE FOR FUTURES
        if position_type == "futures":
            col3.info("🛢️ Futures: Strike N/A")
            K = S  # Use spot
        else:
            K = col3.number_input("Strike ($)", value=float(round(S)), key=f"K{i}", step=0.1, format="%.1f")
        
        trade_price = col4.number_input("Trade Price ($)", value=0.0, key=f"trade{i}", step=0.1, format="%.2f")
        
        if bbls != 0:
            if position_type == "futures":
                # FIXED FUTURES DELTA: bbls * -1.0 for short, +1.0 for long
                futures_delta = np.sign(bbls) * 1.0
                greeks = {'delta': futures_delta, 'gamma': 0.
