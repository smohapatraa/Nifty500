import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import numpy as np
from streamlit_autorefresh import st_autorefresh
import os
import base64
from PIL import Image

# ------------------------------------------------------------
# AUTO-REFRESH (every 5 minutes = 300,000 ms)
# ------------------------------------------------------------
st_autorefresh(interval=300000, key="nifty_gold_refresh")

# ------------------------------------------------------------
# Streamlit page config
# ------------------------------------------------------------
st.set_page_config(
    page_title="S. Mohapatra | Nifty + Gold Screener",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------------
# POP-UP BANNER HELPERS
# ------------------------------------------------------------
def dated_banner(date_obj, note="follows Analysis Date"):
    """Blue banner for date-driven blocks."""
    st.markdown(
        f'<div style="background: rgba(79, 172, 254, 0.15); '
        f'border-left: 4px solid #4facfe; padding: 8px 15px; '
        f'border-radius: 5px; margin-bottom: 10px; color: #e6f2ff;">'
        f'📅 <b>Data as of {date_obj.strftime("%d %b %Y")}</b> — {note}'
        f'</div>',
        unsafe_allow_html=True
    )


def live_banner(note="independent of Analysis Date"):
    """Green banner for live blocks."""
    st.markdown(
        f'<div style="background: rgba(0, 255, 136, 0.15); '
        f'border-left: 4px solid #00ff88; padding: 8px 15px; '
        f'border-radius: 5px; margin-bottom: 10px; color: #e6ffe6;">'
        f'🕐 <b>LIVE</b> — updated {datetime.now().strftime("%H:%M:%S")} IST · {note}'
        f'</div>',
        unsafe_allow_html=True
    )

# ------------------------------------------------------------
# SMART DEFAULT DATE HELPERS
# ------------------------------------------------------------
def get_default_candidate_date():
    """Return today if after 6 PM IST, else the previous weekday (skip weekends)."""
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    if now_ist.hour < 18:
        candidate = now_ist.date() - timedelta(days=1)
    else:
        candidate = now_ist.date()
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def has_market_data(base_data, check_date):
    """Return True if at least a few stocks have OHLC data on check_date."""
    if not base_data:
        return False
    target = pd.Timestamp(check_date)
    count = 0
    for ticker, hist in base_data.items():
        if hist is None or hist.empty:
            continue
        try:
            day_data = hist[hist.index.normalize() == target]
            if not day_data.empty:
                row = day_data.iloc[-1]
                close = _to_float(row['Close']) if 'Close' in row else None
                vol = _to_float(row['Volume']) if 'Volume' in row else None
                if close and vol and not pd.isna(close) and not pd.isna(vol):
                    count += 1
                    if count >= 5:
                        return True
        except Exception:
            continue
    return False


def find_last_trading_date(base_data, start_date, max_lookback=15):
    """Walk backwards until a date with real market data is found."""
    candidate = start_date
    for _ in range(max_lookback):
        while candidate.weekday() >= 5:
            candidate -= timedelta(days=1)
        if has_market_data(base_data, candidate):
            return candidate
        candidate -= timedelta(days=1)
    return start_date

# ------------------------------------------------------------
# HELPER: Ensure DataFrame columns are 1-D Series
# ------------------------------------------------------------
def _squeeze_close(df):
    """Return a clean 1-D Series of Close prices."""
    if df is None or df.empty:
        return None
    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = pd.to_numeric(close, errors='coerce').dropna()
    return close if len(close) > 0 else None


def _to_float(x):
    """Safely convert any scalar/Series/array to a Python float."""
    if x is None:
        return None
    try:
        if isinstance(x, pd.Series):
            x = x.iloc[0] if len(x) > 0 else None
        if isinstance(x, np.ndarray):
            x = x.flatten()[0] if x.size > 0 else None
        return float(x)
    except Exception:
        return None

# ------------------------------------------------------------
# PROFILE CARD (sidebar)
# ------------------------------------------------------------
def get_image_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

profile_path = "myimage.jpg"
if os.path.exists(profile_path):
    try:
        img_b64 = get_image_base64(profile_path)
        st.sidebar.markdown(f"""
        <div style="text-align: center; padding: 15px;">
            <img src="data:image/jpeg;base64,{img_b64}"
                 style="border-radius: 50%; width: 150px; height: 150px;
                        object-fit: cover; border: 4px solid #FFD700;
                        box-shadow: 0 0 20px rgba(255, 215, 0, 0.6);">
            <h3 style="margin: 15px 0 5px 0; color: #FFD700;">S. Mohapatra</h3>
            <p style="font-size: 13px; color: #00ff88; margin: 5px 0; font-weight: 600;">
                💼 Finance &amp; Accounts
            </p>
            <p style="font-size: 13px; color: #4facfe; margin: 5px 0; font-weight: 600;">
                📊 Data Analyst
            </p>
            <div style="margin-top: 12px; padding: 10px;
                        background: rgba(255, 255, 255, 0.05);
                        border-radius: 8px;">
                <p style="font-size: 11px; color: #ccc; margin: 0; line-height: 1.8;">
                    🐍 <b>Python</b> &nbsp;·&nbsp; 🐼 <b>Pandas</b> &nbsp;·&nbsp; 🚀 <b>Streamlit</b>
                </p>
            </div>
            <p style="font-size: 10px; color: #888; margin-top: 12px; font-style: italic;">
                "Turning spreadsheets into insights."
            </p>
        </div>
        """, unsafe_allow_html=True)
    except Exception:
        pass
else:
    st.sidebar.info("📷 Profile picture not found — add myimage.jpg to the repo")

# ------------------------------------------------------------
# 1. FETCH NIFTY CONSTITUENTS
# ------------------------------------------------------------
@st.cache_data(ttl=3600)
def get_nifty_tickers(index_type="Nifty 50"):
    url_map = {
        "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "Nifty 100": "https://archives.nseindia.com/content/indices/ind_nifty100list.csv",
        "Nifty 200": "https://archives.nseindia.com/content/indices/ind_nifty200list.csv",
    }
    try:
        url = url_map.get(index_type, url_map["Nifty 50"])
        df = pd.read_csv(url)
        df = df[df['Symbol'].notna()]
        df['YF_Ticker'] = df['Symbol'] + '.NS'
        return df[['Company Name', 'Symbol', 'YF_Ticker']]
    except Exception as e:
        st.error(f"Failed to fetch {index_type} list: {e}")
        return None

# ------------------------------------------------------------
# 2. DOWNLOAD EXTENDED DATA
# ------------------------------------------------------------
@st.cache_data(ttl=1800)
def load_all_recent_data(ticker_df):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=120)
    tickers = ticker_df['YF_Ticker'].tolist()
    all_data = {}
    total = len(tickers)
    progress_bar = st.progress(0, text="Downloading 120-day market data...")
    batch_size = 50
    for i in range(0, total, batch_size):
        batch = tickers[i:i+batch_size]
        try:
            data = yf.download(batch, start=start_date, end=end_date,
                               group_by="ticker", progress=False, auto_adjust=False)
            if len(batch) == 1:
                data = {batch[0]: data}
            for ticker in batch:
                if ticker in data and not data[ticker].empty:
                    all_data[ticker] = data[ticker].copy()
        except Exception:
            pass
        progress_bar.progress(min((i+batch_size)/total, 1.0),
                              text=f"Downloaded {min(i+batch_size,total)}/{total}")
    progress_bar.empty()
    return all_data

# ------------------------------------------------------------
# 3. TECHNICAL INDICATORS
# ------------------------------------------------------------
def calculate_ema(data, period):
    return data['Close'].ewm(span=period, adjust=False).mean()

def calculate_atr(data, period=14):
    high = data['High']
    low = data['Low']
    close = data['Close'].shift(1)
    tr1 = high - low
    tr2 = abs(high - close)
    tr3 = abs(low - close)
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ------------------------------------------------------------
# 4. FETCH MACRO INDICATORS
# ------------------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_macro_indicators_for_date(target_date):
    macro_data = {}
    today = datetime.today().date()
    if isinstance(target_date, datetime):
        target = target_date.date()
    else:
        target = target_date

    if target >= today - timedelta(days=2):
        start = target - timedelta(days=10)
        end = today + timedelta(days=1)
    else:
        start = target - timedelta(days=30)
        end = target + timedelta(days=5)

    try:
        nifty = yf.download("^NSEI", start=start, end=end, progress=False, auto_adjust=False)
        if not nifty.empty:
            nifty_before = nifty[nifty.index <= pd.Timestamp(target)]
            if not nifty_before.empty:
                nifty_target = nifty_before.iloc[-1]
                nifty_close = _to_float(nifty_target['Close'])
                if len(nifty_before) >= 2:
                    nifty_prev_close = _to_float(nifty_before.iloc[-2]['Close'])
                    nifty_change = ((nifty_close - nifty_prev_close) / nifty_prev_close) * 100 if nifty_prev_close else 0.0
                else:
                    nifty_change = 0.0
                nifty_high = _to_float(nifty_target['High'])
                nifty_low = _to_float(nifty_target['Low'])
                nifty_5d = _squeeze_close(nifty_before).tail(5)
                if nifty_close and not pd.isna(nifty_close) and 15000 < nifty_close < 30000:
                    macro_data['nifty'] = {
                        'close': round(nifty_close, 2),
                        'change': round(nifty_change, 2),
                        'high': round(nifty_high, 2),
                        'low': round(nifty_low, 2),
                        '5d_data': nifty_5d.values if nifty_5d is not None else np.array([]),
                        'data_date': nifty_before.index[-1].strftime('%Y-%m-%d')
                    }
    except Exception:
        pass

    try:
        brent = yf.download("BZ=F", start=start, end=end, progress=False, auto_adjust=False)
        if not brent.empty:
            brent_before = brent[brent.index <= pd.Timestamp(target)]
            if not brent_before.empty:
                brent_target = brent_before.iloc[-1]
                brent_close = _to_float(brent_target['Close'])
                if len(brent_before) >= 2:
                    brent_prev_close = _to_float(brent_before.iloc[-2]['Close'])
                    brent_change = ((brent_close - brent_prev_close) / brent_prev_close) * 100 if brent_prev_close else 0.0
                else:
                    brent_change = 0.0
                brent_5d = _squeeze_close(brent_before).tail(5)
                if brent_close and not pd.isna(brent_close) and 30 < brent_close < 200:
                    macro_data['crude'] = {
                        'close': round(brent_close, 2),
                        'change': round(brent_change, 2),
                        '5d_data': brent_5d.values if brent_5d is not None else np.array([]),
                        'data_date': brent_before.index[-1].strftime('%Y-%m-%d')
                    }
    except Exception:
        pass

    try:
        usdinr = yf.download("INR=X", start=start, end=end, progress=False, auto_adjust=False)
        if not usdinr.empty:
            inr_before = usdinr[usdinr.index <= pd.Timestamp(target)]
            if not inr_before.empty:
                inr_target = inr_before.iloc[-1]
                inr_close = _to_float(inr_target['Close'])
                if len(inr_before) >= 2:
                    inr_prev_close = _to_float(inr_before.iloc[-2]['Close'])
                    inr_change = ((inr_close - inr_prev_close) / inr_prev_close) * 100 if inr_prev_close else 0.0
                else:
                    inr_change = 0.0
                inr_5d = _squeeze_close(inr_before).tail(5)
                if inr_close and not pd.isna(inr_close) and 60 < inr_close < 100:
                    macro_data['usdinr'] = {
                        'close': round(inr_close, 4),
                        'change': round(inr_change, 2),
                        '5d_data': inr_5d.values if inr_5d is not None else np.array([]),
                        'data_date': inr_before.index[-1].strftime('%Y-%m-%d')
                    }
    except Exception:
        pass

    return macro_data


def get_fallback_macro_data():
    return {
        'nifty': {'close': 24500.00, 'change': 0.50, 'high': 24600.00, 'low': 24400.00,
                  '5d_data': np.array([24400, 24450, 24500, 24480, 24500]), 'data_date': 'fallback'},
        'crude': {'close': 75.00, 'change': -0.50,
                  '5d_data': np.array([76, 75.5, 75, 74.5, 75]), 'data_date': 'fallback'},
        'usdinr': {'close': 83.50, 'change': 0.10,
                   '5d_data': np.array([83.3, 83.4, 83.45, 83.5, 83.5]), 'data_date': 'fallback'}
    }


def calculate_macro_risk_score(macro_data):
    risk_score = 0
    risk_factors = []
    if macro_data.get('nifty'):
        nifty_change = macro_data['nifty']['change']
        if abs(nifty_change) > 2:
            risk_score += 3
            risk_factors.append(f"Nifty moved {nifty_change:+.2f}% — High volatility")
        elif abs(nifty_change) > 1:
            risk_score += 2
            risk_factors.append(f"Nifty moved {nifty_change:+.2f}% — Moderate volatility")
        elif abs(nifty_change) > 0.5:
            risk_score += 1
    if macro_data.get('crude'):
        crude_change = macro_data['crude']['change']
        if abs(crude_change) > 3:
            risk_score += 3
            risk_factors.append(f"Crude moved {crude_change:+.2f}% — Major energy shock")
        elif abs(crude_change) > 2:
            risk_score += 2
            risk_factors.append(f"Crude moved {crude_change:+.2f}% — Energy sector impact")
        elif abs(crude_change) > 1:
            risk_score += 1
    if macro_data.get('usdinr'):
        inr_change = macro_data['usdinr']['change']
        if abs(inr_change) > 0.5:
            risk_score += 3
            risk_factors.append(f"INR moved {inr_change:+.2f}% — FII flow concern")
        elif abs(inr_change) > 0.3:
            risk_score += 2
            risk_factors.append(f"INR moved {inr_change:+.2f}% — Currency pressure")
        elif abs(inr_change) > 0.1:
            risk_score += 1
    return risk_score, risk_factors


def get_macro_multiplier(score):
    if score <= 3:
        return 1.0
    elif score <= 6:
        return 0.5
    else:
        return 0.25


def get_breadth_multiplier(gainers, total):
    if total == 0:
        return 1.0
    breadth_ratio = gainers / total * 100
    if gainers < 5 or (total - gainers) < 5:
        return 0.25
    elif breadth_ratio > 60 or breadth_ratio < 40:
        return 1.0
    else:
        return 0.5

# ------------------------------------------------------------
# 4b. LIVE SECTORAL INDICES (NSEPython Server Edition)
# ------------------------------------------------------------
@st.cache_data(ttl=300)
def fetch_sector_data(sector_list):
    """Fetch live data for sectoral indices using nsepythonserver."""
    try:
        from nsepythonserver import index_info
    except ImportError:
        return pd.DataFrame()

    sector_data = []
    for sector in sector_list:
        try:
            data = index_info(sector)
            if data:
                sector_data.append({
                    "Sector": sector,
                    "Last Price": data.get('last', 0),
                    "Change (%)": data.get('percentChange', 0),
                    "Open": data.get('open', 0),
                    "High": data.get('high', 0),
                    "Low": data.get('low', 0)
                })
        except Exception:
            continue
    return pd.DataFrame(sector_data)

# ------------------------------------------------------------
# 5. COMPUTE ENHANCED METRICS
# ------------------------------------------------------------
def compute_enhanced_metrics(all_data, ticker_df, target_date, index_type):
    metrics_list = []
    failed_symbols = []

    min_volume = 50000 if "200" in index_type or "100" in index_type else 0
    min_turnover_cr = 5 if "200" in index_type else 0

    for _, row in ticker_df.iterrows():
        ticker = row['YF_Ticker']
        symbol = row['Symbol']
        company = row['Company Name']

        if ticker not in all_data:
            failed_symbols.append(symbol)
            continue

        hist = all_data[ticker].copy()
        hist = hist[hist.index <= pd.Timestamp(target_date)]

        if hist.empty or len(hist) < 20:
            failed_symbols.append(symbol)
            continue

        latest = hist.iloc[-1]
        close = _to_float(latest['Close'])
        volume = _to_float(latest['Volume'])
        if close is None or volume is None or pd.isna(close) or pd.isna(volume):
            failed_symbols.append(symbol)
            continue

        prev = hist.iloc[-2]
        prev_close = _to_float(prev['Close'])
        if prev_close is None or pd.isna(prev_close):
            failed_symbols.append(symbol)
            continue

        close = round(close, 2)
        prev_close = round(prev_close, 2)
        pct_change = round(((close - prev_close) / prev_close) * 100, 2)
        volume = int(volume)
        high = round(_to_float(latest['High']), 2)
        low = round(_to_float(latest['Low']), 2)
        open_price = round(_to_float(latest['Open']), 2)

        turnover_cr = (volume * close) / 1e7
        if min_turnover_cr > 0 and turnover_cr < min_turnover_cr:
            failed_symbols.append(symbol)
            continue
        if min_volume > 0 and volume < min_volume:
            failed_symbols.append(symbol)
            continue

        pdh = round(_to_float(prev['High']), 2)
        pdl = round(_to_float(prev['Low']), 2)
        gap_pct = round(((open_price - prev_close) / prev_close) * 100, 2)

        pre_target = hist.iloc[:-1]
        avg_volume_5 = int(pre_target['Volume'].iloc[-5:].mean()) if len(pre_target) >= 5 else volume
        avg_volume_10 = int(pre_target['Volume'].iloc[-10:].mean()) if len(pre_target) >= 10 else volume
        avg_volume_20 = int(pre_target['Volume'].iloc[-20:].mean()) if len(pre_target) >= 20 else volume

        volume_spike_5 = "Yes" if (avg_volume_5 > 0 and volume > avg_volume_5 * 1.5) else "No"
        volume_spike_10 = "Yes" if (avg_volume_10 > 0 and volume > avg_volume_10 * 1.5) else "No"
        volume_spike_20 = "Yes" if (avg_volume_20 > 0 and volume > avg_volume_20 * 1.5) else "No"

        ema_20_daily = round(calculate_ema(hist, 20).iloc[-1], 2)
        ema_50_daily = round(calculate_ema(hist, 50).iloc[-1], 2) if len(hist) >= 50 else None
        trend_20 = "Bullish" if close > ema_20_daily else "Bearish"

        atr_14 = round(calculate_atr(hist, 14).iloc[-1], 2)
        atr_pct = round((atr_14 / close) * 100, 2)

        if "200" in index_type and atr_pct > 5:
            failed_symbols.append(symbol)
            continue

        rsi_14 = round(calculate_rsi(hist, 14).iloc[-1], 1)

        breakout_5_long = "Yes" if len(pre_target) >= 5 and close > pre_target.iloc[-5:]['High'].max() else "No"
        breakout_5_short = "Yes" if len(pre_target) >= 5 and close < pre_target.iloc[-5:]['Low'].min() else "No"
        breakout_10_long = "Yes" if len(pre_target) >= 10 and close > pre_target.iloc[-10:]['High'].max() else "No"
        breakout_10_short = "Yes" if len(pre_target) >= 10 and close < pre_target.iloc[-10:]['Low'].min() else "No"
        breakout_20_long = "Yes" if len(pre_target) >= 20 and close > pre_target.iloc[-20:]['High'].max() else "No"
        breakout_20_short = "Yes" if len(pre_target) >= 20 and close < pre_target.iloc[-20:]['Low'].min() else "No"

        stop_loss_distance = round(atr_14 * 1.5, 2)
        position_size = int(1000 / stop_loss_distance) if stop_loss_distance > 0 else 0
        capital_required = position_size * close

        pre_market_score = 0
        if volume_spike_10 == "Yes":
            pre_market_score += 2
        if breakout_10_long == "Yes" or breakout_10_short == "Yes":
            pre_market_score += 2
        if abs(pct_change) > 0.5:
            pre_market_score += 1

        metrics_list.append({
            "Company Name": company,
            "Symbol": symbol,
            "Pre-Mkt Score": pre_market_score,
            "Close": close,
            "Open": open_price,
            "High": high,
            "Low": low,
            "PDH": pdh,
            "PDL": pdl,
            "Daily Change %": pct_change,
            "Gap %": gap_pct,
            "Volume": volume,
            "Avg Vol (5D)": avg_volume_5,
            "Avg Vol (10D)": avg_volume_10,
            "Avg Vol (20D)": avg_volume_20,
            "Vol Spike (5D)": volume_spike_5,
            "Vol Spike (10D)": volume_spike_10,
            "Vol Spike (20D)": volume_spike_20,
            "EMA 20": ema_20_daily,
            "EMA 50": ema_50_daily if ema_50_daily else "N/A",
            "Trend (20EMA)": trend_20,
            "ATR (14)": atr_14,
            "ATR %": atr_pct,
            "RSI (14)": rsi_14,
            "Breakout (5D)": breakout_5_long,
            "Breakdown (5D)": breakout_5_short,
            "Breakout (10D)": breakout_10_long,
            "Breakdown (10D)": breakout_10_short,
            "Breakout (20D)": breakout_20_long,
            "Breakdown (20D)": breakout_20_short,
            "Est. SL Distance": stop_loss_distance,
            "Est. Position Size": position_size,
            "Capital Required": round(capital_required, 2),
            "Turnover (Cr)": round(turnover_cr, 2),
        })

    if failed_symbols:
        st.warning(f"Filtered out {len(failed_symbols)} stocks (low liquidity/high volatility)")

    return pd.DataFrame(metrics_list)

# ------------------------------------------------------------
# 6. MAIN APP UI
# ------------------------------------------------------------
st.title("📊 Mohapatra S. — Indian Market Intraday & Gold Strategy Screener")
st.caption("Technical Market Analysis • Intraday Setups • Gold Trading Strategies")
st.caption("⚠️ Important: Please read the Disclaimer at the bottom of this page before using the screener.")
st.markdown("### Complete Pre-Market Analysis Dashboard | 1:2 Risk-Reward SOP + Gold Trading")

st.sidebar.header("⚙️ Configuration")

index_type = st.sidebar.selectbox(
    "Select Index Universe",
    ["Nifty 50", "Nifty 100", "Nifty 200"],
    index=2
)

trading_capital = st.sidebar.number_input(
    "Trading Capital (₹)",
    min_value=10000, value=1000000, step=10000
)

risk_per_trade = trading_capital * 0.01
st.sidebar.caption(f"Base Risk per trade (1%): ₹{risk_per_trade:,.0f}")

date_placeholder = st.sidebar.empty()

# ------------------------------------------------------------
# LOAD DATA
# ------------------------------------------------------------
with st.spinner(f"Fetching {index_type} constituents from NSE..."):
    ticker_list = get_nifty_tickers(index_type)

if ticker_list is None:
    st.error("Unable to load stock list. Please try again later.")
    st.stop()

st.sidebar.success(f"✅ Loaded {len(ticker_list)} stocks from {index_type}")

with st.spinner("Downloading 120-day market data (cached)..."):
    base_data = load_all_recent_data(ticker_list)

if not base_data:
    st.error("Failed to download market data. Check internet connection.")
    st.stop()

# ------------------------------------------------------------
# SMART DEFAULT DATE
# ------------------------------------------------------------
_candidate = get_default_candidate_date()
default_date = find_last_trading_date(base_data, _candidate)

with date_placeholder.container():
    selected_date = st.sidebar.date_input(
        "Select Analysis Date",
        value=default_date,
        max_value=datetime.today(),
        help="Defaults to last date with actual market data (6 PM IST cutoff)."
    )

day_name = selected_date.strftime('%A')
if day_name in ['Saturday', 'Sunday']:
    st.sidebar.warning(f"⚠️ {day_name} - Markets closed")

# ------------------------------------------------------------
# MACRO INDICATORS
# ------------------------------------------------------------
st.divider()
st.subheader("🌍 Macro Market Dashboard")
dated_banner(selected_date, note="follows Analysis Date")

if 'macro_indicators' not in st.session_state:
    st.session_state.macro_indicators = None
if 'macro_date' not in st.session_state:
    st.session_state.macro_date = None

if st.session_state.macro_indicators is None or st.session_state.macro_date != selected_date:
    with st.spinner(f"Fetching macro indicators for {selected_date}..."):
        st.session_state.macro_indicators = fetch_macro_indicators_for_date(selected_date)
        st.session_state.macro_date = selected_date

macro_indicators = st.session_state.macro_indicators

if macro_indicators is None or all(v is None for v in macro_indicators.values()):
    st.warning("⚠️ Live macro data unavailable. Using approximate values.")
    macro_indicators = get_fallback_macro_data()

col_nifty, col_crude, col_usdinr = st.columns(3)

with col_nifty:
    if macro_indicators.get('nifty'):
        n = macro_indicators['nifty']
        color = '#00ff88' if n['change'] > 0 else '#ff6b6b'
        st.markdown(
            f'<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); '
            f'padding: 20px; border-radius: 15px; color: white;">'
            f'<h4>🇮🇳 NIFTY 50</h4>'
            f'<h2>{n["close"]:,.2f}</h2>'
            f'<p style="color:{color};font-size:18px;">{n["change"]:+.2f}%</p>'
            f'</div>', unsafe_allow_html=True)

with col_crude:
    if macro_indicators.get('crude'):
        c = macro_indicators['crude']
        color = '#00ff88' if c['change'] < 0 else '#ff6b6b'
        st.markdown(
            f'<div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); '
            f'padding: 20px; border-radius: 15px; color: white;">'
            f'<h4>🛢️ BRENT CRUDE</h4>'
            f'<h2>${c["close"]:,.2f}</h2>'
            f'<p style="color:{color};font-size:18px;">{c["change"]:+.2f}%</p>'
            f'</div>', unsafe_allow_html=True)

with col_usdinr:
    if macro_indicators.get('usdinr'):
        u = macro_indicators['usdinr']
        color = '#ff6b6b' if u['change'] > 0 else '#00ff88'
        st.markdown(
            f'<div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); '
            f'padding: 20px; border-radius: 15px; color: white;">'
            f'<h4>💱 USD/INR</h4>'
            f'<h2>₹{u["close"]:,.4f}</h2>'
            f'<p style="color:{color};font-size:18px;">{u["change"]:+.2f}%</p>'
            f'</div>', unsafe_allow_html=True)

# ------------------------------------------------------------
# 4b. LIVE SECTORAL INDICES DASHBOARD
# ------------------------------------------------------------
st.divider()
st.subheader("📊 Live Sectoral Indices Dashboard")
live_banner(note="independent of Analysis Date")

SECTOR_INDICES = [
    "NIFTY BANK",
    "NIFTY IT",
    "NIFTY FINANCIAL SERVICES",
    "NIFTY AUTO",
    "NIFTY FMCG",
    "NIFTY METAL",
    "NIFTY PHARMA",
    "NIFTY REALTY",
    "NIFTY ENERGY",
    "NIFTY PSU BANK",
    "NIFTY PRIVATE BANK",
    "NIFTY MEDIA"
]

with st.spinner("Fetching live sector data from NSE..."):
    df_sectors = fetch_sector_data(SECTOR_INDICES)

if not df_sectors.empty:
    def color_change(val):
        if val > 0:
            return 'color: #00ff88'
        elif val < 0:
            return 'color: #ff6b6b'
        else:
            return 'color: #ffffff'

    styled_df = df_sectors.style.map(color_change, subset=['Change (%)'])

    st.dataframe(
        styled_df,
        column_config={
            "Last Price": st.column_config.NumberColumn(format="%.2f"),
            "Change (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "Open": st.column_config.NumberColumn(format="%.2f"),
            "High": st.column_config.NumberColumn(format="%.2f"),
            "Low": st.column_config.NumberColumn(format="%.2f"),
        },
        hide_index=True,
        use_container_width=True
    )

    st.subheader("Sector Performance Overview")
    fig_sectors = px.bar(
        df_sectors.sort_values('Change (%)', ascending=True),
        x='Change (%)',
        y='Sector',
        orientation='h',
        color='Change (%)',
        color_continuous_scale=['#ff6b6b', '#ffffff', '#00ff88'],
        title="Sectoral Performance (Change %)"
    )
    fig_sectors.update_layout(height=500, showlegend=False)
    st.plotly_chart(fig_sectors, use_container_width=True)
else:
    st.warning("⚠️ Unable to fetch live sector data. NSE API may be temporarily unavailable.")

# ------------------------------------------------------------
# MACRO RISK
# ------------------------------------------------------------
macro_risk_score, risk_factors = calculate_macro_risk_score(macro_indicators)
macro_multiplier = get_macro_multiplier(macro_risk_score)

st.divider()
st.subheader("⚠️ Macro Risk Assessment")
dated_banner(selected_date, note="calculated from macro data on this date")

col_risk1, col_risk2 = st.columns([1, 2])

with col_risk1:
    risk_level = "LOW" if macro_risk_score <= 3 else ("MODERATE" if macro_risk_score <= 6 else "HIGH")
    risk_color = "#00ff88" if macro_risk_score <= 3 else ("#ffa500" if macro_risk_score <= 6 else "#ff6b6b")
    st.markdown(
        f'<div style="background: linear-gradient(135deg, #232526 0%, #414345 100%); '
        f'padding: 25px; border-radius: 15px; color: white; text-align: center;">'
        f'<h3>Macro Risk Score</h3>'
        f'<h1 style="font-size: 60px; color: {risk_color};">{macro_risk_score}/10</h1>'
        f'<h3 style="color: {risk_color};">{risk_level} RISK</h3>'
        f'<p>Macro Multiplier: {macro_multiplier*100:.0f}%</p>'
        f'</div>', unsafe_allow_html=True)

with col_risk2:
    st.markdown("### 📋 Macro Risk Factors:")
    if risk_factors:
        for factor in risk_factors:
            st.warning(factor)
    else:
        st.success("✅ No significant macro risks detected")

# ------------------------------------------------------------
# COMPUTE STOCK METRICS
# ------------------------------------------------------------
with st.spinner(f"Computing enhanced metrics for {selected_date}..."):
    df_metrics = compute_enhanced_metrics(base_data, ticker_list, selected_date, index_type)

if df_metrics.empty:
    st.error(f"No market data available for {selected_date}. It may be a holiday or weekend.")
    st.stop()

# ------------------------------------------------------------
# MARKET OVERVIEW
# ------------------------------------------------------------
st.divider()
st.subheader(f"📈 {index_type} Market Overview")
dated_banner(selected_date, note="follows Analysis Date")

gainers = len(df_metrics[df_metrics["Daily Change %"] > 0])
losers = len(df_metrics[df_metrics["Daily Change %"] < 0])
unchanged = len(df_metrics[df_metrics["Daily Change %"] == 0])
bullish_trend = len(df_metrics[df_metrics["Trend (20EMA)"] == "Bullish"])
high_score_stocks = len(df_metrics[df_metrics["Pre-Mkt Score"] >= 3])

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("📈 Advancing", gainers)
with col2:
    st.metric("📉 Declining", losers)
with col3:
    st.metric("📊 Unchanged", unchanged)
with col4:
    st.metric("🐂 Bullish Trend", bullish_trend)
with col5:
    st.metric("🎯 High Score (≥3)", high_score_stocks)

total_stocks = len(df_metrics)
breadth_ratio = gainers / total_stocks * 100 if total_stocks > 0 else 0
breadth_multiplier = get_breadth_multiplier(gainers, total_stocks)

final_multiplier = min(macro_multiplier, breadth_multiplier)
final_risk_per_trade = risk_per_trade * final_multiplier
final_max_trades = 3 if final_multiplier >= 1.0 else (2 if final_multiplier >= 0.5 else 1)
final_daily_loss_limit = final_risk_per_trade * 3

st.divider()
st.subheader("🎯 FINAL TRADING PARAMETERS (Unified Risk)")
dated_banner(selected_date, note="calculated for this date")

col_final1, col_final2, col_final3, col_final4 = st.columns(4)
with col_final1:
    st.metric("Macro Multiplier", f"{macro_multiplier*100:.0f}%")
with col_final2:
    st.metric("Breadth Multiplier", f"{breadth_multiplier*100:.0f}%")
with col_final3:
    st.metric("FINAL Multiplier", f"{final_multiplier*100:.0f}%")
with col_final4:
    st.metric("Risk Per Trade", f"₹{final_risk_per_trade:,.0f}")

st.markdown(f"""
### 📐 Final Trading Rules:
| Parameter | Value |
|-----------|-------|
| 💰 Risk per trade | ₹{final_risk_per_trade:,.0f} |
| 🔢 Max trades | {final_max_trades} |
| ⛔ Daily loss limit | ₹{final_daily_loss_limit:,.0f} |
| 🎯 Risk:Reward | 1:2 |
| 📊 Index | {index_type} |
| 📅 Date | {selected_date} |
""")

# ------------------------------------------------------------
# SCREENER FILTERS
# ------------------------------------------------------------
st.sidebar.header("🎯 Screener Filters")
search = st.sidebar.text_input("🔎 Search Symbol/Company", "").strip().upper()
min_score = st.sidebar.slider("Minimum Pre-Market Score", 0, 5, 3)
trend_filter = st.sidebar.selectbox("Daily Trend (20 EMA)", ["All", "Bullish Only", "Bearish Only"])
breakout_period = st.sidebar.selectbox("Breakout Period", ["5-Day", "10-Day", "20-Day"])
breakout_type = st.sidebar.selectbox("Breakout Type", ["All", "Breakout (Long)", "Breakdown (Short)"])
volume_filter = st.sidebar.selectbox("Volume Spike", ["None", "5-Day Spike", "10-Day Spike", "20-Day Spike"])

filtered_df = df_metrics.copy()
if search:
    filtered_df = filtered_df[
        filtered_df['Symbol'].str.contains(search, case=False) |
        filtered_df['Company Name'].str.upper().str.contains(search)
    ]
filtered_df = filtered_df[filtered_df['Pre-Mkt Score'] >= min_score]

if trend_filter == "Bullish Only":
    filtered_df = filtered_df[filtered_df['Trend (20EMA)'] == "Bullish"]
elif trend_filter == "Bearish Only":
    filtered_df = filtered_df[filtered_df['Trend (20EMA)'] == "Bearish"]

period_map = {"5-Day": "5D", "10-Day": "10D", "20-Day": "20D"}
if breakout_type == "Breakout (Long)":
    col_name = f"Breakout ({period_map[breakout_period]})"
    filtered_df = filtered_df[filtered_df[col_name] == "Yes"]
elif breakout_type == "Breakdown (Short)":
    col_name = f"Breakdown ({period_map[breakout_period]})"
    filtered_df = filtered_df[filtered_df[col_name] == "Yes"]

if volume_filter == "5-Day Spike":
    filtered_df = filtered_df[filtered_df["Vol Spike (5D)"] == "Yes"]
elif volume_filter == "10-Day Spike":
    filtered_df = filtered_df[filtered_df["Vol Spike (10D)"] == "Yes"]
elif volume_filter == "20-Day Spike":
    filtered_df = filtered_df[filtered_df["Vol Spike (20D)"] == "Yes"]

filtered_df = filtered_df.sort_values(['Pre-Mkt Score', 'Turnover (Cr)'], ascending=[False, False])

st.divider()
st.subheader("🔍 Advanced Strategy Screener Results")
dated_banner(selected_date, note="follows Analysis Date")
st.markdown(f"**📋 Showing {len(filtered_df)} stocks matching criteria**")

if len(filtered_df) >= 3:
    top3_symbols = filtered_df.head(3)['Symbol'].tolist()
    st.success(f"🎯 **Top 3 SOP Candidates:** {', '.join(top3_symbols)}")

st.dataframe(filtered_df, hide_index=True, use_container_width=True, height=600)

# ------------------------------------------------------------
# 7. GOLD TRACKER + PREDICTION
# ------------------------------------------------------------
st.divider()
st.subheader("🥇 Gold Price Tracker & Next-Day Opening Prediction")
live_banner(note="independent of Analysis Date")

@st.cache_data(ttl=1800)
def fetch_gold_related_data():
    result = {}
    try:
        gold = yf.download("GC=F", period="90d", progress=False, auto_adjust=False)
        if not gold.empty:
            result['gold'] = gold
    except Exception:
        pass
    try:
        usdinr = yf.download("INR=X", period="90d", progress=False, auto_adjust=False)
        if not usdinr.empty:
            result['usdinr'] = usdinr
    except Exception:
        pass
    try:
        setfgold = yf.download("SETFGOLD.NS", period="90d", progress=False, auto_adjust=False)
        if not setfgold.empty:
            result['setfgold'] = setfgold
    except Exception:
        pass
    return result


def predict_next_day_open(gold_df, inr_df, etf_df):
    predictions = {}

    gold_close = _squeeze_close(gold_df)
    if gold_close is not None and len(gold_close) >= 10:
        last = float(gold_close.iloc[-1])
        recent_5 = gold_close.tail(5).values.astype(float)
        slope = float(np.polyfit(np.arange(len(recent_5)), recent_5, 1)[0])
        trend_pred = last + slope
        returns_3 = float(gold_close.pct_change().tail(3).mean())
        momentum_pred = last * (1 + returns_3)
        gold_pred = float(trend_pred * 0.6 + momentum_pred * 0.4)
        predictions['gold'] = {
            'last_close': round(last, 2),
            'predicted_open': round(gold_pred, 2),
            'change_pct': round(((gold_pred - last) / last) * 100, 2),
        }

    inr_close = _squeeze_close(inr_df)
    if inr_close is not None and len(inr_close) >= 10:
        last = float(inr_close.iloc[-1])
        recent_5 = inr_close.tail(5).values.astype(float)
        slope = float(np.polyfit(np.arange(len(recent_5)), recent_5, 1)[0])
        trend_pred = last + slope
        returns_3 = float(inr_close.pct_change().tail(3).mean())
        momentum_pred = last * (1 + returns_3)
        inr_pred = float(trend_pred * 0.6 + momentum_pred * 0.4)
        predictions['usdinr'] = {
            'last_close': round(last, 4),
            'predicted_open': round(inr_pred, 4),
            'change_pct': round(((inr_pred - last) / last) * 100, 3),
        }

    etf_close = _squeeze_close(etf_df)
    if etf_close is not None and len(etf_close) >= 10:
        last = float(etf_close.iloc[-1])
        recent_5 = etf_close.tail(5).values.astype(float)
        slope = float(np.polyfit(np.arange(len(recent_5)), recent_5, 1)[0])
        trend_pred = last + slope
        returns_3 = float(etf_close.pct_change().tail(3).mean())
        momentum_pred = last * (1 + returns_3)
        etf_pred_technical = float(trend_pred * 0.6 + momentum_pred * 0.4)

        etf_pred_correlated = None
        if 'gold' in predictions and 'usdinr' in predictions:
            combined_change = (
                predictions['gold']['change_pct'] / 100 +
                predictions['usdinr']['change_pct'] / 100
            )
            etf_pred_correlated = float(last * (1 + combined_change))

        if etf_pred_correlated is not None:
            etf_pred_final = float(etf_pred_technical * 0.5 + etf_pred_correlated * 0.5)
        else:
            etf_pred_final = etf_pred_technical

        predictions['setfgold'] = {
            'last_close': round(last, 2),
            'predicted_open_technical': round(etf_pred_technical, 2),
            'predicted_open_correlated': round(etf_pred_correlated, 2) if etf_pred_correlated is not None else None,
            'predicted_open': round(etf_pred_final, 2),
            'change_pct': round(((etf_pred_final - last) / last) * 100, 2),
        }

    return predictions


with st.spinner("Fetching gold, USD/INR, and SETFGOLD data..."):
    gold_bundle = fetch_gold_related_data()

gold_df = gold_bundle.get('gold') if gold_bundle else None
inr_df = gold_bundle.get('usdinr') if gold_bundle else None
etf_df = gold_bundle.get('setfgold') if gold_bundle else None

if gold_df is None:
    st.error("⚠️ Unable to fetch gold-related data.")
else:
    predictions = predict_next_day_open(gold_df, inr_df, etf_df)

    st.markdown("### 📊 Current Market Snapshot")
    col_g1, col_g2, col_g3 = st.columns(3)

    with col_g1:
        if gold_df is not None and len(gold_df) >= 2:
            gc = float(_squeeze_close(gold_df).iloc[-1])
            gp = float(_squeeze_close(gold_df).iloc[-2])
            gc_chg = ((gc - gp) / gp) * 100
            color = '#006400' if gc_chg > 0 else '#8B0000'
            st.markdown(
                f'<div style="background: linear-gradient(135deg, #FFD700 0%, #DAA520 100%); '
                f'padding: 18px; border-radius: 12px; color: #000;">'
                f'<h4>🌍 Gold Futures (COMEX)</h4>'
                f'<h2>${gc:,.2f}</h2>'
                f'<p style="color:{color};font-size:16px;">{gc_chg:+.2f}%</p>'
                f'<small>per troy ounce</small></div>', unsafe_allow_html=True)

    with col_g2:
        if inr_df is not None and len(inr_df) >= 2:
            ic = float(_squeeze_close(inr_df).iloc[-1])
            ip = float(_squeeze_close(inr_df).iloc[-2])
            ic_chg = ((ic - ip) / ip) * 100
            color = '#ffcccc' if ic_chg > 0 else '#ccffcc'
            st.markdown(
                f'<div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); '
                f'padding: 18px; border-radius: 12px; color: #fff;">'
                f'<h4>💱 USD/INR</h4>'
                f'<h2>₹{ic:,.4f}</h2>'
                f'<p style="color:{color};font-size:16px;">{ic_chg:+.3f}%</p>'
                f'<small>1 USD = ₹{ic:,.2f}</small></div>', unsafe_allow_html=True)

    with col_g3:
        if etf_df is not None and len(etf_df) >= 2:
            ec = float(_squeeze_close(etf_df).iloc[-1])
            ep = float(_squeeze_close(etf_df).iloc[-2])
            ec_chg = ((ec - ep) / ep) * 100
            color = '#006400' if ec_chg > 0 else '#8B0000'
            st.markdown(
                f'<div style="background: linear-gradient(135deg, #f6d365 0%, #fda085 100%); '
                f'padding: 18px; border-radius: 12px; color: #000;">'
                f'<h4>🇮🇳 SETFGOLD (NSE)</h4>'
                f'<h2>₹{ec:,.2f}</h2>'
                f'<p style="color:{color};font-size:16px;">{ec_chg:+.2f}%</p>'
                f'<small>SBI Gold ETF</small></div>', unsafe_allow_html=True)

    st.divider()
    st.markdown("### 🔮 Next-Day Opening Price Prediction")

    col_p1, col_p2, col_p3 = st.columns(3)

    with col_p1:
        if 'gold' in predictions:
            p = predictions['gold']
            arrow = "🔼" if p['change_pct'] > 0 else ("🔽" if p['change_pct'] < 0 else "➡️")
            st.metric("🌍 Gold Open", f"${p['predicted_open']:,.2f}",
                      delta=f"{p['change_pct']:+.2f}% {arrow}")
            st.caption(f"Last: ${p['last_close']:,.2f}")

    with col_p2:
        if 'usdinr' in predictions:
            p = predictions['usdinr']
            arrow = "🔼" if p['change_pct'] > 0 else ("🔽" if p['change_pct'] < 0 else "➡️")
            st.metric("💱 USD/INR Open", f"₹{p['predicted_open']:,.4f}",
                      delta=f"{p['change_pct']:+.3f}% {arrow}")
            st.caption(f"Last: ₹{p['last_close']:,.4f}")

    with col_p3:
        if 'setfgold' in predictions:
            p = predictions['setfgold']
            arrow = "🔼" if p['change_pct'] > 0 else ("🔽" if p['change_pct'] < 0 else "➡️")
            st.metric("🇮🇳 SETFGOLD Open", f"₹{p['predicted_open']:,.2f}",
                      delta=f"{p['change_pct']:+.2f}% {arrow}")
            st.caption(f"Last: ₹{p['last_close']:,.2f}")

    st.divider()
    st.markdown("### 📋 Trading Suggestion for SETFGOLD")

    if 'setfgold' in predictions and 'gold' in predictions and 'usdinr' in predictions:
        etf_pred_chg = predictions['setfgold']['change_pct']
        gold_pred_chg = predictions['gold']['change_pct']
        inr_pred_chg = predictions['usdinr']['change_pct']

        if gold_pred_chg > 0.3 and inr_pred_chg > 0:
            suggestion = "🟢 STRONG BUY"
            rationale = f"Gold up {gold_pred_chg:+.2f}% + INR weak {inr_pred_chg:+.3f}% → double tailwind."
            color_type = "success"
        elif gold_pred_chg > 0.3 and inr_pred_chg <= 0:
            suggestion = "🟢 BUY (Mild)"
            rationale = f"Gold up {gold_pred_chg:+.2f}%, INR strong may offset. Net: {etf_pred_chg:+.2f}%."
            color_type = "success"
        elif gold_pred_chg < -0.3 and inr_pred_chg > 0:
            suggestion = "🟡 HOLD / WAIT"
            rationale = f"Gold down {gold_pred_chg:+.2f}%, INR weak cushions. Net: {etf_pred_chg:+.2f}%."
            color_type = "info"
        elif gold_pred_chg < -0.3 and inr_pred_chg <= 0:
            suggestion = "🔴 SELL / AVOID"
            rationale = f"Gold down {gold_pred_chg:+.2f}% + INR strong {inr_pred_chg:+.3f}% → double headwind."
            color_type = "error"
        else:
            suggestion = "⚪ NEUTRAL"
            rationale = f"Gold {gold_pred_chg:+.2f}% and INR {inr_pred_chg:+.3f}% — no clear direction."
            color_type = "warning"

        msg = f"**{suggestion}** — {rationale}"
        if color_type == "success":
            st.success(msg)
        elif color_type == "error":
            st.error(msg)
        elif color_type == "info":
            st.info(msg)
        else:
            st.warning(msg)

        st.markdown(f"""
| Metric | Value |
|--------|-------|
| 🌍 Gold Open | ${predictions['gold']['predicted_open']:,.2f} |
| 💱 USD/INR Open | ₹{predictions['usdinr']['predicted_open']:,.4f} |
| 🇮🇳 SETFGOLD Open | ₹{predictions['setfgold']['predicted_open']:,.2f} |
| 📊 Expected SETFGOLD Change | {etf_pred_chg:+.2f}% |
| 🎯 Action | {suggestion} |
""")

        st.caption("⚠️ *Technical prediction only. Not financial advice.*")

# ------------------------------------------------------------
# 8. BUY/SELL ZONE
# ------------------------------------------------------------
st.divider()
st.subheader("🚦 Gold Buy Zone / Sell Zone Indicator")
live_banner(note="independent of Analysis Date")

st.sidebar.header("🥇 Gold Strategy Settings")
core_holding_pct = st.sidebar.slider("Core Holding (% never sold)", 0, 100, 60, 5)
max_gold_allocation_pct = st.sidebar.slider("Max Gold Allocation (%)", 5, 50, 20, 5)

buy_trigger_1 = st.sidebar.number_input("Buy small (25%) if falls %", value=2.0, step=0.5)
buy_trigger_2 = st.sidebar.number_input("Buy medium (50%) if falls %", value=4.0, step=0.5)
buy_trigger_3 = st.sidebar.number_input("Buy aggressive (100%) if falls %", value=7.0, step=0.5)
sell_trigger_1 = st.sidebar.number_input("Sell 25% if rises %", value=3.0, step=0.5)
sell_trigger_2 = st.sidebar.number_input("Sell 50% if rises %", value=5.0, step=0.5)
sell_trigger_3 = st.sidebar.number_input("Sell 100% if rises %", value=10.0, step=0.5)


def calculate_buy_sell_zones(etf_df, gold_df, inr_df,
                             buy_t1, buy_t2, buy_t3,
                             sell_t1, sell_t2, sell_t3):
    etf_close = _squeeze_close(etf_df)
    if etf_close is None or len(etf_close) < 20:
        return None

    def _squeeze_col(df, col):
        if df is None or df.empty or col not in df.columns:
            return None
        s = df[col]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        s = pd.to_numeric(s, errors='coerce').dropna()
        return s if len(s) > 0 else None

    etf_high_series = _squeeze_col(etf_df, 'High')
    etf_low_series = _squeeze_col(etf_df, 'Low')

    if etf_high_series is None or etf_low_series is None:
        return None

    lookback = min(30, len(etf_close))
    recent_high_series = etf_high_series.tail(lookback)
    recent_low_series = etf_low_series.tail(lookback)

    last_close = float(etf_close.iloc[-1])
    recent_high = float(recent_high_series.max())
    recent_low = float(recent_low_series.min())
    recent_avg = float(etf_close.tail(lookback).mean())

    pct_from_high = ((last_close - recent_high) / recent_high) * 100
    pct_from_low = ((last_close - recent_low) / recent_low) * 100

    if len(etf_close) >= 7:
        week_ago = float(etf_close.iloc[-7])
        week_change_pct = ((last_close - week_ago) / week_ago) * 100
    else:
        week_change_pct = 0.0

    if len(etf_close) >= 2:
        yesterday = float(etf_close.iloc[-2])
        day_change_pct = ((last_close - yesterday) / yesterday) * 100
    else:
        day_change_pct = 0.0

    zone = "HOLD"
    zone_color = "#FFA500"
    action = "Do nothing — wait for clearer signal"
    sell_pct = 0
    buy_pct = 0

    if week_change_pct >= sell_t3:
        zone, zone_color = "STRONG SELL", "#8B0000"
        action = f"🔥 SELL 100% of trading portion — up {week_change_pct:+.2f}% this week"
        sell_pct = 100
    elif week_change_pct >= sell_t2:
        zone, zone_color = "SELL", "#DC143C"
        action = f"💰 SELL 50% — up {week_change_pct:+.2f}% this week"
        sell_pct = 50
    elif week_change_pct >= sell_t1:
        zone, zone_color = "SELL (Partial)", "#FF6347"
        action = f"💵 SELL 25% — up {week_change_pct:+.2f}% this week"
        sell_pct = 25
    elif week_change_pct <= -buy_t3:
        zone, zone_color = "STRONG BUY", "#006400"
        action = f"🎯 AGGRESSIVE BUY — down {week_change_pct:+.2f}% this week"
        buy_pct = 100
    elif week_change_pct <= -buy_t2:
        zone, zone_color = "BUY", "#228B22"
        action = f"🛒 BUY MEDIUM — down {week_change_pct:+.2f}% this week"
        buy_pct = 50
    elif week_change_pct <= -buy_t1:
        zone, zone_color = "BUY (Partial)", "#32CD32"
        action = f"🛍️ BUY SMALL — down {week_change_pct:+.2f}% this week"
        buy_pct = 25

    inr_trend = "Unknown"
    inr_close = _squeeze_close(inr_df)
    if inr_close is not None and len(inr_close) >= 5:
        inr_5d_ago = float(inr_close.iloc[-5])
        inr_now = float(inr_close.iloc[-1])
        inr_chg = ((inr_now - inr_5d_ago) / inr_5d_ago) * 100
        if inr_chg > 0.3:
            inr_trend = "INR Weakening (bullish for gold)"
        elif inr_chg < -0.3:
            inr_trend = "INR Strengthening (bearish for gold)"
        else:
            inr_trend = "INR Stable"

    return {
        'last_close': last_close,
        'recent_high': recent_high,
        'recent_low': recent_low,
        'recent_avg': recent_avg,
        'pct_from_high': pct_from_high,
        'pct_from_low': pct_from_low,
        'week_change_pct': week_change_pct,
        'day_change_pct': day_change_pct,
        'zone': zone,
        'zone_color': zone_color,
        'action': action,
        'buy_pct': buy_pct,
        'sell_pct': sell_pct,
        'inr_trend': inr_trend,
    }

if etf_df is not None and len(etf_df) >= 20:
    zones = calculate_buy_sell_zones(
        etf_df, gold_df, inr_df,
        buy_trigger_1, buy_trigger_2, buy_trigger_3,
        sell_trigger_1, sell_trigger_2, sell_trigger_3
    )

    if zones:
        st.markdown(
            f'<div style="background: {zones["zone_color"]}; '
            f'padding: 25px; border-radius: 15px; color: white; text-align: center;">'
            f'<h2 style="margin:0; font-size: 42px;">{zones["zone"]}</h2>'
            f'<h3>{zones["action"]}</h3>'
            f'<p style="font-size: 20px;">SETFGOLD: <b>₹{zones["last_close"]:,.2f}</b></p>'
            f'</div>', unsafe_allow_html=True)

        st.markdown("")
        col_z1, col_z2, col_z3, col_z4 = st.columns(4)

        with col_z1:
            st.metric("1-Day Change", f"{zones['day_change_pct']:+.2f}%")
        with col_z2:
            delta_label = "Buy zone" if zones['week_change_pct'] < -buy_trigger_1 else (
                "Sell zone" if zones['week_change_pct'] > sell_trigger_1 else "Neutral"
            )
            st.metric("7-Day Change", f"{zones['week_change_pct']:+.2f}%", delta=delta_label)
        with col_z3:
            st.metric("% from 30D High", f"{zones['pct_from_high']:+.2f}%",
                      help=f"High: ₹{zones['recent_high']:,.2f}")
        with col_z4:
            st.metric("% from 30D Low", f"{zones['pct_from_low']:+.2f}%",
                      help=f"Low: ₹{zones['recent_low']:,.2f}")

        st.info(f"💱 **USD/INR Trend**: {zones['inr_trend']}")

        st.markdown("### 📋 Recommended Action")
        col_act1, col_act2 = st.columns([2, 1])

        with col_act1:
            if zones['buy_pct'] > 0:
                st.success(f"**BUY SIGNAL** 🟢 — Deploy **{zones['buy_pct']}%** of remaining capital.")
            elif zones['sell_pct'] > 0:
                st.error(f"**SELL SIGNAL** 🔴 — Book **{zones['sell_pct']}%** of trading portion. Keep core {core_holding_pct}%.")
            else:
                st.warning(f"**NO ACTION — HOLD** 🟡 — Wait for clearer signal.")

        with col_act2:
            st.markdown(f"""
**Setup**
- Core: {core_holding_pct}%
- Trading: {100-core_holding_pct}%
- Max Alloc: {max_gold_allocation_pct}%
""")

        st.markdown("### 📈 SETFGOLD Price with Buy/Sell Zones")
        chart_data = etf_df.tail(60).copy()
        chart_close = _squeeze_close(chart_data)

        fig_zones = go.Figure()
        fig_zones.add_trace(go.Scatter(
            x=chart_close.index, y=chart_close.values,
            mode='lines', name='SETFGOLD',
            line=dict(color='#FFA500', width=2)
        ))

        buy_level_1 = zones['recent_high'] * (1 - buy_trigger_1/100)
        buy_level_2 = zones['recent_high'] * (1 - buy_trigger_2/100)
        buy_level_3 = zones['recent_high'] * (1 - buy_trigger_3/100)
        sell_level_1 = zones['recent_avg'] * (1 + sell_trigger_1/100)
        sell_level_2 = zones['recent_avg'] * (1 + sell_trigger_2/100)
        sell_level_3 = zones['recent_avg'] * (1 + sell_trigger_3/100)

        fig_zones.add_hline(y=buy_level_3, line_dash="dot", line_color="darkgreen",
                            annotation_text=f"Strong Buy (-{buy_trigger_3}%)")
        fig_zones.add_hline(y=buy_level_2, line_dash="dot", line_color="green",
                            annotation_text=f"Buy (-{buy_trigger_2}%)")
        fig_zones.add_hline(y=buy_level_1, line_dash="dot", line_color="lightgreen",
                            annotation_text=f"Small Buy (-{buy_trigger_1}%)")
        fig_zones.add_hline(y=sell_level_1, line_dash="dot", line_color="lightsalmon",
                            annotation_text=f"Sell 25% (+{sell_trigger_1}%)")
        fig_zones.add_hline(y=sell_level_2, line_dash="dot", line_color="crimson",
                            annotation_text=f"Sell 50% (+{sell_trigger_2}%)")
        fig_zones.add_hline(y=sell_level_3, line_dash="dot", line_color="darkred",
                            annotation_text=f"Sell All (+{sell_trigger_3}%)")

        fig_zones.update_layout(
            title="SETFGOLD — 60-Day Chart with Trigger Levels",
            xaxis_title="Date", yaxis_title="Price (₹)",
            height=500, hovermode='x unified'
        )
        st.plotly_chart(fig_zones, use_container_width=True)

        st.caption("⚠️ *Technical guide only. Not financial advice.*")

# ------------------------------------------------------------
# DOWNLOAD
# ------------------------------------------------------------
st.divider()
col_dl1, col_dl2 = st.columns(2)
with col_dl1:
    st.download_button(
        label=f"📥 Full {index_type} Data",
        data=df_metrics.to_csv(index=False).encode('utf-8'),
        file_name=f"{index_type.replace(' ', '_').lower()}_{selected_date}.csv",
        mime='text/csv'
    )
with col_dl2:
    st.download_button(
        label="📥 Screened Results",
        data=filtered_df.to_csv(index=False).encode('utf-8'),
        file_name=f"screened_{selected_date}.csv",
        mime='text/csv'
    )

st.divider()
st.caption("⚠️ Not financial advice. Always verify at market open (9:15 AM IST).")

# ------------------------------------------------------------
# SEBI DISCLAIMER
# ------------------------------------------------------------
st.divider()
st.caption("""
⚠️ **DISCLAIMER:** I am **NOT** a SEBI-registered Research Analyst or Investment Advisor. 
All content, tools, charts, screeners, and signals provided in this dashboard are for 
**educational and informational purposes only** and should **NOT** be considered as 
investment advice or trading recommendations. 

Trading and investing in securities markets involves substantial risk of loss. 
Past performance is not indicative of future results. 

Please consult a **SEBI-registered Investment Advisor** before making any investment 
or trading decision. The creator of this dashboard shall not be held liable for any 
direct or indirect losses arising from the use of this content.

By using this dashboard, you acknowledge that you are solely responsible for your 
own trading and investment decisions.
""")
