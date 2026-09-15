import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import pytz
import feedparser
import time

# Try to import nsetools or dalal for live data
try:
    from nsetools import Nse
    NSE_AVAILABLE = True
except ImportError:
    NSE_AVAILABLE = False

try:
    import dalal
    DALAL_AVAILABLE = True
except ImportError:
    DALAL_AVAILABLE = False

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Mohapatra S. — Auto Market Dashboard",
    page_icon="📊",
    layout="wide"
)

# ============================================================
# AUTO-REFRESH (5 minutes)
# ============================================================
# Simple JavaScript-based auto-refresh
st.markdown("""
<script>
    setTimeout(function(){
        window.location.reload();
    }, 300000);  // 5 minutes = 300,000 ms
</script>
""", unsafe_allow_html=True)

# ============================================================
# CUSTOM CSS
# ============================================================
st.markdown("""
<style>
    .hero-title {
        font-size: 36px;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8, #818cf8, #f472b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-sub { color: #94a3b8; font-size: 14px; }
    .soft-notice {
        background: #f8fafc11;
        border-left: 3px solid #38bdf8;
        padding: 8px 14px;
        border-radius: 6px;
        font-size: 12.5px;
        color: #cbd5e1;
    }
    .news-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-left: 4px solid #38bdf8;
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 10px;
    }
    .news-title { color: #f1f5f9; font-size: 15px; font-weight: 700; }
    .news-meta { color: #64748b; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER
# ============================================================
st.markdown('<div class="hero-title">📊 Mohapatra S. — Auto Market Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Live Gainers • Losers • News — Auto-Refresh Every 5 Minutes</div>', unsafe_allow_html=True)

ist = pytz.timezone('Asia/Kolkata')
st.markdown(f'<div class="soft-notice">🕐 Last updated: <b>{datetime.now(ist).strftime("%d %b %Y, %I:%M:%S %p IST")}</b></div>', unsafe_allow_html=True)
st.divider()

# ============================================================
# LIVE TOP GAINERS / LOSERS
# ============================================================
st.markdown("### 📈📉 Live Top Movers")

if NSE_AVAILABLE:
    @st.cache_data(ttl=300)
    def get_live_movers():
        nse = Nse()
        gainers = nse.get_top_gainers()[:5]
        losers = nse.get_top_losers()[:5]
        return gainers, losers
    
    try:
        gainers, losers = get_live_movers()
        
        col_g, col_l = st.columns(2)
        
        with col_g:
            st.markdown("#### 🟢 Top 5 Gainers")
            for g in gainers:
                st.metric(
                    label=g.get('symbol', 'N/A'),
                    value=f"₹{g.get('ltp', 0):,.2f}",
                    delta=f"+{g.get('perChange', 0)}%"
                )
        
        with col_l:
            st.markdown("#### 🔴 Top 5 Losers")
            for l in losers:
                st.metric(
                    label=l.get('symbol', 'N/A'),
                    value=f"₹{l.get('ltp', 0):,.2f}",
                    delta=f"{l.get('perChange', 0)}%",
                    delta_color="inverse"
                )
    except Exception as e:
        st.warning(f"⚠️ Live data unavailable: {e}")
        st.info("💡 Install: `pip install nsetools`")
else:
    st.info("📦 Install `nsetools` for live movers: `pip install nsetools`")

st.divider()

# ============================================================
# MARKET NEWS FROM RSS
# ============================================================
st.markdown("### 📰 Latest Market News")

# NSE RSS feeds
NSE_FEEDS = [
    ("NSE Announcements", "https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml"),
    ("NSE Annual Reports", "https://nsearchives.nseindia.com/content/RSS/Annual_Reports.xml"),
    ("NSE Board Meetings", "https://nsearchives.nseindia.com/content/RSS/Board_Meetings.xml"),
]

@st.cache_data(ttl=600)
def fetch_rss(url):
    try:
        feed = feedparser.parse(url)
        return feed.entries[:5]
    except Exception:
        return []

all_news = []
for source_name, url in NSE_FEEDS:
    entries = fetch_rss(url)
    for entry in entries:
        all_news.append({
            "source": source_name,
            "title": entry.get('title', 'No title'),
            "link": entry.get('link', '#'),
            "published": entry.get('published', '')
        })

# Display news
if all_news:
    for news in all_news[:15]:
        st.markdown(f"""
        <div class="news-card">
            <div class="news-title">🔹 {news['title']}</div>
            <div class="news-meta">📌 {news['source']} • {news['published']}</div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("📰 News will appear here when RSS feeds are available.")

st.divider()

# ============================================================
# DISCLAIMER
# ============================================================
st.caption("""
⚠️ **DISCLAIMER:** I am **NOT** a SEBI-registered Research Analyst or Investment Advisor.
All content is for **educational purposes only**. Trading involves substantial risk.
Please consult a SEBI-registered advisor before making decisions.
""")
