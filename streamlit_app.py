import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime

# Page Config
st.set_page_config(page_title="Mirae Asset ETF Chart", layout="wide")

# --- Helper Functions (Reusing logic) ---
@st.cache_data
def get_etf_list():
    try:
        df = fdr.StockListing('ETF/KR')
        # Filter for TIGER (Mirae Asset)
        etfs = df[df['Name'].str.contains('TIGER', na=False)]
        
        # Normalize columns
        code_col = 'Code' if 'Code' in df.columns else 'Symbol'
        if code_col != 'Code':
            etfs = etfs.rename(columns={code_col: 'Code'})
            
        return etfs[['Code', 'Name']].to_dict('records')
    except Exception as e:
        st.error(f"Error fetching ETF list: {e}")
        return []

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_rmi(series, period=5, momentum_period=10):
    delta = series.diff(momentum_period)
    up = delta.where(delta > 0, 0)
    down = -delta.where(delta < 0, 0)
    
    # EMA
    up_ema = up.ewm(span=period, adjust=False).mean()
    down_ema = down.ewm(span=period, adjust=False).mean()
    
    rmi = 100 * (up_ema / (up_ema + down_ema))
    return rmi

def get_data(ticker, period='D'):
    try:
        # Fetch generous amount of data
        start_date = (datetime.datetime.now() - datetime.timedelta(days=365*3)).strftime('%Y-%m-%d')
        df = fdr.DataReader(ticker, start_date)
        
        if period == 'W':
             df = df.resample('W').agg({
                'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
            })
            
        # Indicators
        df['RSI'] = calculate_rsi(df['Close'], 14)
        df['RMI'] = calculate_rmi(df['Close'], 5, 10)
        
        return df.dropna()
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

# --- Application Layout ---

st.title("🐯 TIGER ETF Chart App")

# 1. Sidebar / Search
etf_list = get_etf_list()

if not etf_list:
    st.stop()

# Search Format: "Name (Code)"
search_options = [f"{item['Name']} ({item['Code']})" for item in etf_list]
selected_option = st.selectbox("Search ETF", search_options)

# Parse selection
selected_name = selected_option.split(' (')[0]
selected_code = selected_option.split('(')[1].replace(')', '')

# Period Selection
col1, col2 = st.columns(2)
with col1:
    period = st.radio("Period", ['Daily', 'Weekly'], horizontal=True)
period_code = 'D' if period == 'Daily' else 'W'

# 2. Fetch Data
with st.spinner('Loading data...'):
    df = get_data(selected_code, period_code)

if df.empty:
    st.warning("No data found for this ETF.")
else:
    # 3. Plot Chart using Plotly
    fig = make_subplots(
        rows=3, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.05,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=(f"{selected_name} ({selected_code})", "RSI(14)", "RMI(5, 10)")
    )

    # Candle
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name='Price'
    ), row=1, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple', width=1), name='RSI'), row=2, col=1)
    fig.add_hrect(y0=30, y1=70, row=2, col=1, fillcolor="gray", opacity=0.1, line_width=0)
    fig.add_hline(y=30, row=2, col=1, line_dash="drive", line_color="gray")
    fig.add_hline(y=70, row=2, col=1, line_dash="drive", line_color="gray")

    # RMI
    fig.add_trace(go.Scatter(x=df.index, y=df['RMI'], line=dict(color='blue', width=1), name='RMI'), row=3, col=1)
    fig.add_hrect(y0=30, y1=70, row=3, col=1, fillcolor="gray", opacity=0.1, line_width=0)

    # Layout Updates
    fig.update_layout(
        height=800,
        xaxis_rangeslider_visible=False,
        margin=dict(l=20, r=20, t=40, b=20),
        spikedistance=1000, 
        hovermode="x unified"
    )
    
    # Hide weekends/gaps for daily
    if period == 'Daily':
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])]) 

    st.plotly_chart(fig, use_container_width=True)

    # Debug Data Preview
    with st.expander("View Raw Data"):
        st.dataframe(df.tail(10))
