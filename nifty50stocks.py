import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import pytz
import feedparser

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Mohapatra S. — Auto Market Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# AUTO-REFRESH (5 minutes)
# ============================================================
st.markdown("""
<script>
    setTimeout(function(){
        window.location.reload();
    }, 300000);
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
        margin-bottom: 4px;
    }
    .hero-sub { color: #94a3b8; font-size: 14px; }
    .soft-notice {
        background: #f8fafc11;
        border-left: 3px solid #38bdf8;
        padding: 8px 14px;
        border-radius: 6px;
        font-size: 12.5px;
        color: #cbd5e1;
        margin-top: 8px;
    }
    .news-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-left: 4px solid #38bdf8;
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 10px;
        transition: all 0.25s ease;
    }
    .news-card:hover {
        transform: translateX(6px);
        border-left-color: #f472b6;
    }
    .news-title { color: #f1f5f9; font-size: 15px; font-weight: 700; margin-bottom: 4px; }
    .news-meta { color: #64748b; font-size: 12px; }
    .section-title {
        font-size: 22px;
        font-weight: 700;
        color: #f1f5f9;
        margin: 18px 0 10px 0;
        padding-left: 10px;
        border-left: 4px solid #38bdf8;
    }
    hr { border-color: #1e293b; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER
# ============================================================
st.markdown('<div class="hero-title">📊 Mohapatra S. — Auto Market Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Live Gainers • Losers • News — Auto-Refresh Every 5 Minutes</div>', unsafe_allow_html=True)

ist = pytz.timezone('Asia/Kolkata')
st.markdown(
    f'<div class="soft-notice">🕐 Last updated: <b>{datetime.now(ist).strftime("%d %b %Y, %I:%M:%S %p IST")}</b></div>',
    unsafe_allow_html=True
)
st.divider()

# ============================================================
# LIVE TOP GAINERS / LOSERS
# ============================================================
st.markdown('<div class="section-title">📈📉 Live Top Movers</div>', unsafe_allow_html=True)

try:
    from nsetools import Nse
    
    @st.cache_data(ttl=300)
    def get_live_movers():
        nse = Nse()
        gainers = nse.get_top_gainers()[:5]
        losers = nse.get_top_losers()[:5]
        return gainers, losers
    
    gainers, losers = get_live_movers()
    
    col_g, col_l = st.columns(2)
    
    with col_g:
        st.markdown("#### 🟢 Top 5 Gainers")
        for g in gainers:
            try:
                st.metric(
                    label=g.get('symbol', 'N/A'),
                    value=f"₹{float(g.get('ltp', 0)):,.2f}",
                    delta=f"+{g.get('perChange', 0)}%"
                )
            except Exception:
                continue
    
    with col_l:
        st.markdown("#### 🔴 Top 5 Losers")
        for l in losers:
            try:
                st.metric(
                    label=l.get('symbol', 'N/A'),
                    value=f"₹{float(l.get('ltp', 0)):,.2f}",
                    delta=f"{l.get('perChange', 0)}%",
                    delta_color="inverse"
                )
            except Exception:
                continue

except Exception as e:
    st.warning(f"⚠️ Live movers temporarily unavailable. Retry in a few minutes.")
    st.info(f"Debug info: {e}")

st.divider()

# ============================================================
# MARKET NEWS FROM RSS
# ============================================================
st.markdown('<div class="section-title">📰 Latest Market News</div>', unsafe_allow_html=True)

NSE_FEEDS = [
    ("NSE Announcements", "https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml"),
    ("NSE Board Meetings", "https://nsearchives.nseindia.com/content/RSS/Board_Meetings.xml"),
    ("NSE Annual Reports", "https://nsearchives.nseindia.com/content/RSS/Annual_Reports.xml"),
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
All content, tools, charts, and data provided in this dashboard are for **educational and
informational purposes only** and should **NOT** be considered as investment advice or
trading recommendations.

Trading and investing in securities markets involves substantial risk of loss.
Please consult a **SEBI-registered Investment Advisor** before making any investment
or trading decision.

By using this dashboard, you acknowledge that you are solely responsible for your own
trading and investment decisions.
""")
