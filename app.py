"""ZimiFare — professional Streamlit interface for the integrated fare prototype."""

from __future__ import annotations

import hmac
import html
import os
import base64
from datetime import date, datetime, timedelta, timezone
from io import StringIO
import csv

import altair as alt
import pandas as pd
from pathlib import Path

import streamlit as st

from zimifare.core import (
    AccessDenied,
    FRAUD_THRESHOLD_CENTS,
    MAX_RIDES,
    MAX_TRANSACTIONS,
    MAX_USERS,
    ZimiFareError,
    ZimiFareStore,
    cents_from_input,
    money,
)
from zimifare.identifiers import user_ref, ride_ref, transaction_ref, parse_transaction_ref
from zimifare.analytics import filter_transactions, summarise_transactions
from zimifare.postgres_store import get_zimifare_store

ROOT = Path(__file__).resolve().parent
ICON_B64 = base64.b64encode((ROOT / "assets" / "icon.png").read_bytes()).decode("ascii")

st.set_page_config(
    page_title="ZimiFare | Move smart. Pay easy.",
    page_icon=str(ROOT / "assets" / "icon.png"),
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap');
:root { --ink:#102e46; --navy:#0d293d; --teal:#00ae96; --mint:#e7f7f3; --gold:#f6bd47; --bg:#f5f8fb; --slate:#627487; }
html,body,[class*="css"],.stApp { font-family:'DM Sans','Manrope',sans-serif; }
[data-testid="stAppViewContainer"] { background: #f5f8fb; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="block-container"] { max-width:1280px; padding-top: 2.4rem; padding-bottom:3.5rem; }
h1,h2,h3 { font-family:'Manrope','DM Sans',sans-serif !important; color:var(--ink); letter-spacing:-.025em; }
h1 { font-weight:800 !important; } h2,h3{font-weight:750 !important;}
.stCaption,.stMarkdown small { color: var(--slate); }
section[data-testid="stSidebar"] { background: #0d293d; border-right:0; }
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] { background:linear-gradient(180deg,#0d293d 0%,#112f43 72%,#063d45 100%); padding-top:1.3rem; }
section[data-testid="stSidebar"] .stMarkdown, section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] span { color: #edf7fb !important; }
section[data-testid="stSidebar"] [role="radiogroup"] label { border-radius:12px !important; padding:8px 10px !important; margin:2px 0; }
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) { background:rgba(2,195,158,.22) !important; }
section[data-testid="stSidebar"] [role="radiogroup"] label:hover { background:rgba(255,255,255,.075); }
section[data-testid="stSidebar"] hr { border-color:rgba(255,255,255,.18); }
[data-testid="stForm"], [data-testid="stVerticalBlockBorderWrapper"]:has(>div>div>div[data-testid="stMetric"]) {border-radius:18px !important;}
[data-testid="stMetric"] { background:white; padding:19px 20px; border-radius:17px; border:1px solid #e8eef2; box-shadow:0 6px 30px rgba(10,43,62,.035); }
[data-testid="stMetricLabel"] { color:#697c8a; font-size:.85rem; font-weight:600; }
[data-testid="stMetricValue"] { color:#102e46; font-size:1.85rem; font-weight:800; letter-spacing:-.05em; }
.stButton > button, [data-testid="stFormSubmitButton"] button, [data-testid="stBaseButton-primary"] { border-radius:11px !important; font-weight:700 !important; min-height:2.75rem !important; }
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"], [data-testid="stBaseButton-primary"] { background:#00ae96 !important; border:1px solid #00ae96 !important; color:white !important; box-shadow:0 5px 14px rgba(0,174,150,.17); }
.stButton > button[kind="primary"]:hover,[data-testid="stFormSubmitButton"] button[kind="primary"]:hover { background:#008f7b !important; border-color:#008f7b !important; }
[data-baseweb="input"] > div, [data-baseweb="select"]>div, textarea { border-radius:10px !important; }
[data-testid="stDataFrame"] { border:1px solid #e8eff3; border-radius:12px; overflow:hidden; }
[data-testid="stAlert"] { border-radius:12px; }
[data-testid="stTabs"] button { font-weight:650 !important; }
[data-testid="stTabs"] [aria-selected="true"] { color:#00a48e !important; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background:#00ae96 !important; }
.eyebrow { font-size:.75rem;font-weight:800;color:#1a9889;text-transform:uppercase;letter-spacing:.13em; }
.hero { position:relative; overflow:hidden; border-radius:22px; background:linear-gradient(113deg,#0d293d 0%,#0e4b55 70%,#0b6661 100%); padding:33px 37px 34px; color:white; margin-bottom:24px; box-shadow:0 11px 30px rgba(15,47,67,.12); }
.hero:before { content:'';position:absolute;right:-45px;top:-165px;width:440px;height:440px;border:58px solid rgba(22,211,169,.11);border-radius:50%;pointer-events:none; }
.hero:after { content:'';position:absolute;right:90px;bottom:-135px;width:280px;height:280px;border:3px dashed rgba(253,192,68,.30);border-radius:50%;pointer-events:none; }
.hero h1 { color:#fff !important; margin:3px 0 9px; font-size:2.05rem;letter-spacing:-.045em; }
.hero p { color:#cfebe9;max-width:700px;font-size:.98rem;margin:0; }
.hero .eyebrow { color:#ffd476; }
.paper { background:white;border-radius:18px;border:1px solid #e5eef2;padding:22px 25px;box-shadow:0 6px 25px rgba(8,41,62,.035); }
.paper h3 {margin-top:0;}
.pill { padding:5px 9px; border-radius:100px; display:inline-block; font-size:.73rem;font-weight:800;letter-spacing:.03em; }
.pill-paid { background:#dbf8ed;color:#087f63; } .pill-unpaid{background:#fff0d1;color:#966000;}
.brand-lockup { display:flex; align-items:center; gap:11px; color:white; margin:4px 0 23px; }
.brand-symbol {width:47px;height:47px;background:#063844;border-radius:13px;display:flex;align-items:center;justify-content:center;color:#27d4b4;font-size:1.7rem;font-weight:900;border:1px solid rgba(255,255,255,.12);}
.brand-name {font-family:'Manrope',sans-serif;font-size:1.7rem;font-weight:800;letter-spacing:-.075em;}
.brand-name span {color:#42ddbc;}
.smallmuted {font-size:.78rem;color:#90b4c0;}
.public-kicker { display:inline-block;background:#e4f9f1;color:#007c70;border-radius:20px;padding:8px 13px;font-size:.78rem;font-weight:800;letter-spacing:.045em; }
.public-h1 {color:#102e46;font-size:3.2rem;font-weight:800;line-height:1.13;letter-spacing:-.07em;margin-top:16px;margin-bottom:17px;}
.public-h1 span{color:#00aa92;}
.public-description{font-size:1.05rem;color:#6a7f8e;line-height:1.8;max-width:540px;}
.public-feature{display:flex;align-items:center;gap:12px;margin-top:15px;font-weight:700;color:#19394f;}
.public-feature .bullet{width:32px;height:32px;background:#ddf7ef;color:#087f6d;border-radius:10px;display:flex;align-items:center;justify-content:center;}
.divider-line{height:1px;background:#dbe6eb;margin:25px 0;}
.note{font-size:.81rem;color:#708393;}

/* ZimiFare Pro · subtle transitions & accessible motion */
:root { color-scheme:light; }
[data-testid="block-container"] { animation: pageReveal .32s ease-out both; }
@keyframes pageReveal { from {opacity:.6; transform:translateY(7px)} to {opacity:1; transform:translateY(0)} }
[data-testid="stMetric"] {transition:transform .2s ease, box-shadow .2s ease, border-color .2s ease; position:relative; overflow:hidden;}
[data-testid="stMetric"]:hover {transform:translateY(-3px); border-color:#bfe4da; box-shadow:0 12px 28px rgba(11,53,74,.1);}
[data-testid="stMetric"]::before {content:"";position:absolute; top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#00ad92,#e8bd4f);}
[data-testid="stForm"], [data-testid="stVerticalBlockBorderWrapper"] {transition:box-shadow .18s ease;}
.stButton > button { transition:transform .18s ease, box-shadow .18s ease !important; }
.stButton > button:hover {transform:translateY(-1px)}
.stButton > button:active {transform:translateY(0)}
.ride-visual {position:absolute;z-index:1;right:26px;top:20px;width:290px;height:126px;opacity:.94;pointer-events:none;}
.ride-visual .car-body {animation:carFloat 3.3s ease-in-out infinite; transform-origin:center;}
.ride-visual .wheel { transform-origin:center;animation:wheelTurn 3s linear infinite; }
.ride-visual .dash-1 {animation:driveDash 1.9s linear infinite;}
.ride-visual .dash-2 {animation:driveDash 1.9s linear infinite -.75s;}
@keyframes carFloat {0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}
@keyframes wheelTurn {to{transform:rotate(360deg)}}
@keyframes driveDash {0%{transform:translateX(100px);opacity:0}15%{opacity:1}85%{opacity:1}100%{transform:translateX(-120px);opacity:0}}
.hero .hero-copy {position:relative;z-index:2;max-width:calc(100% - 258px)}
.animated-road {display:block; margin-top:30px; border-radius:20px;background:linear-gradient(115deg,#0c2d43,#13726a);padding:24px 24px 16px; color:#fff;position:relative;overflow:hidden;min-height:165px;box-shadow:0 12px 28px rgba(4,53,67,.15);}
.animated-road h3{color:#fff;font-size:1.2rem;margin:0;position:relative;z-index:2;}
.animated-road p {color:#d8f5ef;font-size:.87rem;margin:5px 0 0;position:relative;z-index:2;max-width:65%;}
.animated-road .ride-visual {top:42px;right:13px;width:245px;}
.report-tag{display:inline-block;padding:6px 10px;border:1px solid #d7e9e6;border-radius:18px;background:#edfaf7;color:#137968;font-size:.77rem;font-weight:800;}
.insight {border:1px solid #e2eef1;border-left:4px solid #04aa92;border-radius:13px;background:#fff;padding:15px 17px;line-height:1.65;color:#435a69;margin:8px 0 16px;}
@media(max-width:760px){.hero .hero-copy{max-width:100%}.hero .ride-visual{opacity:.14;right:-28px;top:15px}.animated-road .ride-visual{opacity:.25;right:-70px}.animated-road p{max-width:100%}.public-h1{font-size:2.35rem}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none !important;transition:none !important;transform:none !important;scroll-behavior:auto !important;}}

/* -------------------------------------------------------------
   ZimiFare Pro · accessibility and visibility patch · Nov 2026
   Contrast: primary button #006e62 / white = 6.16:1.
   Headings are deliberately explicit because modern Streamlit's
   own Markdown selectors can override plain h2/h3 selectors.
   This patch is visual only; it changes no application logic.
   ------------------------------------------------------------- */
html, body, .stApp { color-scheme: light !important; }
[data-testid="stAppViewContainer"] {
  background: #f5f8fb !important;
  color: #15364b !important;
}
[data-testid="stHeader"] { background: #f5f8fb !important; }
/* All standard page headings must be readable on the light canvas. */
[data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] :is(h1, h2, h3, h4, h5, h6),
[data-testid="stAppViewContainer"] [data-testid="stHeadingWithActionElements"] :is(h1, h2, h3, h4, h5, h6) {
  color: #102e46 !important;
  opacity: 1 !important;
  text-shadow: none !important;
  font-weight: 750 !important;
}
/* Retain intentionally white text on the dark graphical banners. */
[data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] .hero h1,
[data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] .animated-road h3 {
  color: #ffffff !important;
}
[data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] .hero p {
  color: #dcefed !important;
}
[data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] .animated-road p {
  color: #def4f0 !important;
}
/* Standard descriptions and captions, on white and light grey. */
[data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"],
[data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"] p,
[data-testid="stAppViewContainer"] [data-testid="stWidgetLabel"] p,
[data-testid="stAppViewContainer"] [data-testid="stWidgetLabel"] label {
  color: #496276 !important;
  opacity: 1 !important;
}
/* Clickable items: readable text, clear borders and visible focus. */
[data-testid="stAppViewContainer"] .stButton > button[kind="primary"],
[data-testid="stAppViewContainer"] [data-testid="stFormSubmitButton"] button[kind="primary"],
[data-testid="stAppViewContainer"] button[data-testid="stBaseButton-primary"] {
  background: #006e62 !important;
  color: #ffffff !important;
  border: 1px solid #006e62 !important;
  box-shadow: 0 4px 12px rgba(0, 92, 80, .14) !important;
}
[data-testid="stAppViewContainer"] .stButton > button[kind="primary"]:hover,
[data-testid="stAppViewContainer"] [data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
[data-testid="stAppViewContainer"] button[data-testid="stBaseButton-primary"]:hover {
  background: #00564c !important;
  border-color: #00564c !important;
}
[data-testid="stAppViewContainer"] .stButton > button[kind="secondary"],
[data-testid="stAppViewContainer"] [data-testid="stFormSubmitButton"] button[kind="secondary"],
[data-testid="stAppViewContainer"] button[data-testid="stBaseButton-secondary"] {
  background: #ffffff !important;
  color: #163c50 !important;
  border: 1px solid #b3c9d2 !important;
  box-shadow: 0 2px 8px rgba(12, 46, 63, .04) !important;
}
[data-testid="stAppViewContainer"] .stButton > button[kind="secondary"]:hover,
[data-testid="stAppViewContainer"] [data-testid="stFormSubmitButton"] button[kind="secondary"]:hover,
[data-testid="stAppViewContainer"] button[data-testid="stBaseButton-secondary"]:hover {
  background: #e8f6f2 !important;
  border-color: #08796f !important;
  color: #00574f !important;
}
[data-testid="stAppViewContainer"] button:focus-visible,
[data-testid="stSidebar"] button:focus-visible,
[data-testid="stAppViewContainer"] input:focus-visible,
[data-testid="stAppViewContainer"] a:focus-visible {
  outline: 3px solid #e6a934 !important;
  outline-offset: 2px !important;
}
[data-testid="stAppViewContainer"] button:disabled {
  opacity: .66 !important;
  cursor: not-allowed !important;
}
/* Data entry controls & tabs must not inherit white-on-white text. */
[data-testid="stAppViewContainer"] [data-testid="stTextInput"] input,
[data-testid="stAppViewContainer"] [data-testid="stNumberInput"] input,
[data-testid="stAppViewContainer"] [data-testid="stDateInput"] input,
[data-testid="stAppViewContainer"] textarea,
[data-testid="stAppViewContainer"] [data-baseweb="select"] [role="combobox"] {
  color: #16384a !important;
  background-color: #ffffff !important;
}
[data-testid="stAppViewContainer"] [data-baseweb="tab"] {
  color: #3c576a !important;
}
[data-testid="stAppViewContainer"] [data-baseweb="tab"][aria-selected="true"] {
  color: #006e62 !important;
  font-weight: 800 !important;
}
/* Sidebar keeps the navy palette; increase selection & icon contrast. */
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: #126968 !important;
  box-shadow: inset 3px 0 0 #6af0d3 !important;
}
section[data-testid="stSidebar"] [role="radiogroup"] label:not(:has(input:checked)):hover {
  background: rgba(255,255,255,.13) !important;
}
section[data-testid="stSidebar"] [role="radiogroup"] input[type="radio"] {
  accent-color: #58e6c5 !important;
}
section[data-testid="stSidebar"] [data-testid="stButton"] button {
  background: rgba(255,255,255,.09) !important;
  color: #ffffff !important;
  border: 1px solid rgba(255,255,255,.32) !important;
}
section[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
  background: rgba(255,255,255,.17) !important;
}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
  color: #bed9e2 !important;
}
[data-testid="stAppViewContainer"] [data-testid="stMetricLabel"] {
  color: #4f6677 !important;
}
[data-testid="stAppViewContainer"] [data-testid="stMetricValue"] {
  color: #102e46 !important;
}
@media (prefers-reduced-motion: reduce) {
  [data-testid="stAppViewContainer"] *,
  [data-testid="stSidebar"] * { animation:none !important; transition:none !important; }
}

</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def get_store() -> ZimiFareStore:
    # Root-level Streamlit Cloud secrets normally become environment variables.
    # Reading st.secrets as a fallback also supports local secrets.toml files.
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        try:
            url = str(st.secrets.get("DATABASE_URL", ""))
        except Exception:
            url = ""
    return get_zimifare_store(url)


def setup_secret() -> str:
    v = os.environ.get("ZIMIFARE_ADMIN_SETUP_KEY", "")
    if v:
        return v
    try:
        return str(st.secrets.get("ZIMIFARE_ADMIN_SETUP_KEY", ""))
    except Exception:
        return ""


def friendly_error(exc: Exception) -> None:
    if isinstance(exc, (ZimiFareError, AccessDenied)):
        st.error(str(exc))
    else:
        st.error("Something unexpected happened. Please try again or contact your project administrator.")


def flash(message: str) -> None:
    st.session_state["flash"] = message


def show_flash() -> None:
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)


def nav_to(page: str) -> None:
    # Navigation radio has already been instantiated this run, so queue change.
    st.session_state["_next_nav"] = page
    st.rerun()


def sign_out() -> None:
    # Button callbacks run before widgets are created on the next Streamlit rerun.
    st.session_state.pop("user_id", None)
    st.session_state.pop("nav", None)
    st.session_state.pop("_next_nav", None)
    flash("You have signed out successfully.")


def moving_car() -> str:
    """Inline SVG is decorative only; animation is pure CSS and respects reduced-motion."""
    return """<svg class="ride-visual" viewBox="0 0 300 140" aria-hidden="true" focusable="false">
      <g opacity=".8"><path d="M5 121 H295" stroke="#87c7c4" stroke-opacity=".4" stroke-width="2"/>
      <path class="dash-1" d="M105 119 h35" stroke="#e5ce80" stroke-width="3" stroke-linecap="round"/>
      <path class="dash-2" d="M225 119 h35" stroke="#e5ce80" stroke-width="3" stroke-linecap="round"/></g>
      <g class="car-body">
        <path d="M46 78 C54 73 63 72 77 71 L112 43 Q119 36 132 36 H193 Q202 36 211 47 L232 70 L247 74 Q257 76 258 86 V104 H44 V89 Q44 82 46 78Z" fill="#e5fcf7"/>
        <path d="M98 69 L123 45 H190 Q195 45 201 52 L215 69Z" fill="#2d8d94"/>
        <path d="M151 46 L149 69" stroke="#d8f7f4" stroke-width="3"/>
        <path d="M53 79 H72" stroke="#ffcf57" stroke-width="7" stroke-linecap="round"/>
        <path d="M245 79 H255" stroke="#ffcf57" stroke-width="7" stroke-linecap="round"/>
        <path d="M77 77 H227" stroke="#06aa94" stroke-width="3" stroke-linecap="round"/>
        <circle class="wheel" cx="91" cy="104" r="17" fill="#102839" stroke="#a9dde3" stroke-width="4"/>
        <circle cx="91" cy="104" r="6" fill="#e5fcf7"/>
        <circle class="wheel" cx="219" cy="104" r="17" fill="#102839" stroke="#a9dde3" stroke-width="4"/>
        <circle cx="219" cy="104" r="6" fill="#e5fcf7"/>
      </g>
      </svg>"""


def travel_illustration() -> None:
    st.markdown('<div class="animated-road"><h3>Every journey, connected.</h3>'
                '<p>Ride requests, simple payments and clear records — all in one place.</p>'
                + moving_car() + '</div>', unsafe_allow_html=True)


def main_header(user: dict, heading: str, description: str) -> None:
    first = html.escape(user["full_name"].split()[0])
    st.markdown(
        f'<div class="hero"><div class="hero-copy"><div class="eyebrow">ZIMIFARE · {html.escape(user["role"])} PORTAL</div>'
        f'<h1>{html.escape(heading)}{", " + first if heading == "Welcome back" else ""}</h1>'
        f'<p>{html.escape(description)}</p></div>' + moving_car() + '</div>',
        unsafe_allow_html=True,
    )

def section(title: str, description: str = "") -> None:
    st.markdown(f"### {title}")
    if description:
        st.caption(description)


def empty(message: str) -> None:
    st.info(message)


def ride_table(rows: list[dict], *, driver_view: bool = False) -> None:
    if not rows:
        empty("No rides match this view yet.")
        return
    items = []
    for r in rows:
        items.append({
            "Ride": ride_ref(r["ride_id"]),
            "Date": r["ride_date"],
            "Passenger" if driver_view else "Driver": r["passenger_name"] if driver_view else r["driver_name"],
            "Journey": f"{r['pickup']} → {r['destination']}",
            "Fare": money(r["fare_cents"]),
            "Status": r["payment_status"].title(),
            "Method": r["payment_method"].replace("_", " ").title() if r["payment_status"] == "PAID" else "Awaiting payment",
        })
    st.dataframe(items, hide_index=True, use_container_width=True)


def transactions_table(rows: list[dict], *, admin: bool) -> None:
    if not rows:
        empty("There are no transactions in this view yet.")
        return
    table = []
    for t in rows:
        rec = {
            "Transaction": transaction_ref(t["transaction_id"]),
            "Type": "Card top-up" if t["tx_type"] == "TOP_UP" else "Ride payment",
            "Ride": ride_ref(t["ride_id"]) if t["ride_id"] else "—",
            "Amount": money(t["amount_cents"]),
            "Method": t["method"].replace("_", " ").title(),
            "Recorded (UTC)": t["recorded_at"].replace("T", " ")[:16],
        }
        if admin:
            rec["Passenger"] = t["passenger_name"]
            rec["Driver"] = t["driver_name"]
            rec["Review"] = "Flagged" if t["flagged"] else "Clear"
        table.append(rec)
    st.dataframe(table, hide_index=True, use_container_width=True)


def sidebar(user: dict) -> str:
    role = user["role"]
    st.sidebar.markdown(
        f'<div class="brand-lockup"><img alt="ZimiFare icon" '
        f'src="data:image/png;base64,{ICON_B64}" width="48" height="48" '
        f'style="border-radius:13px"/>'
        '<div class="brand-name">Zimi<span>Fare</span></div></div>', unsafe_allow_html=True
    )
    st.sidebar.markdown(f"**{html.escape(user['full_name'])}**")
    st.sidebar.caption(f"{role.title()} account · {user_ref(user['user_id'], role)}")
    st.sidebar.divider()
    options = {
        "PASSENGER": ["Overview", "Top up fare card", "Pay a fare", "Ride history", "My profile"],
        "DRIVER": ["Overview", "Receive a fare", "My earnings", "Ride history", "My profile"],
        "ADMIN": ["Overview", "Analytics & reports", "Manage users", "Transactions", "Fraud review", "My profile"],
    }[role]
    icons = {
        "Overview":"◈", "Top up fare card":"▣", "Pay a fare":"↗", "Ride history":"▤",
        "My profile":"◉", "Receive a fare":"▰", "My earnings":"▥", "Manage users":"◎",
        "Transactions":"▦", "Fraud review":"⚑", "Analytics & reports":"▧",
    }
    if "_next_nav" in st.session_state:
        st.session_state.nav = st.session_state.pop("_next_nav")
    if st.session_state.get("nav") not in options:
        st.session_state.nav = "Overview"
    value = st.sidebar.radio(
        "WORKSPACE", options, format_func=lambda x: f"{icons[x]}    {x}", key="nav"
    )
    st.sidebar.divider()
    st.sidebar.button("↪  Sign out", use_container_width=True, on_click=sign_out)
    st.sidebar.markdown(
        '<p style="font-size:.73rem;color:#9cb9c5;margin-top:48px;line-height:1.7">'
        'ZIMIFARE · ACADEMIC PROTOTYPE<br/>'
        'Top-ups are simulations. No actual payments are processed.</p>',
        unsafe_allow_html=True
    )
    return value


def admin_setup(store: ZimiFareStore) -> None:
    st.image(str(ROOT / "assets" / "logo.png"), width=285)
    st.markdown("## Set up your ZimiFare administrator")
    st.info("The first administrator must be created by a trusted operator before public registration opens.")
    secret = setup_secret()
    if not secret:
        st.warning("Secure browser setup is disabled because no setup key has been configured.")
        st.markdown("**On your own Windows computer**, close Streamlit, then run this in your ZimiFare project folder:")
        st.code("python create_admin.py", language="bat")
        st.caption("Follow the prompts, then run `python -m streamlit run app.py` again. For hosted setup, configure ZIMIFARE_ADMIN_SETUP_KEY in Streamlit secrets.")
        return
    with st.form("admin_setup_form"):
        full_name = st.text_input("Administrator full name")
        email = st.text_input("Administrator email")
        phone = st.text_input("Phone number")
        pw = st.text_input("New password (8+ characters)", type="password")
        check = st.text_input("Confirm password", type="password")
        entered_key = st.text_input("One-time setup key", type="password")
        submitted = st.form_submit_button("Create administrator", type="primary", use_container_width=True)
    if submitted:
        if not hmac.compare_digest(entered_key, secret):
            st.error("The setup key is incorrect.")
        elif pw != check:
            st.error("Passwords do not match.")
        else:
            try:
                account = store.bootstrap_admin(full_name, email, phone, pw, trusted_setup=True)
                st.success(f"Administrator {user_ref(account, 'ADMIN')} created. You can now sign in.")
                st.rerun()
            except Exception as exc:
                friendly_error(exc)


def public_page(store: ZimiFareStore) -> None:
    st.image(str(ROOT / "assets" / "logo.png"), width=280)
    st.markdown("<div style='height:17px'></div>", unsafe_allow_html=True)
    left, right = st.columns([1.13, 1], gap="large", vertical_alignment="top")
    with left:
        st.markdown(
            '<span class="public-kicker">YOUR JOURNEY. MADE EASIER.</span>'
            '<div class="public-h1">One smart way to <span>move and pay.</span></div>'
            '<div class="public-description">ZimiFare connects passengers, drivers and administrators '
            'through a simple, secure fare-management experience. Create fare requests, manage your '
            'card balance and track payments in one place.</div>'
            '<div class="divider-line"></div>'
            '<div class="public-feature"><div class="bullet">✓</div> Seamless fare-card payments</div>'
            '<div class="public-feature"><div class="bullet">✓</div> Transparent trip and earnings history</div>'
            '<div class="public-feature"><div class="bullet">✓</div> Built-in transaction monitoring</div>',
            unsafe_allow_html=True
        )
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        travel_illustration()
        st.caption("Academic prototype • Currency: Jamaican dollars (JMD) • No real funds collected")
    with right:
        with st.container(border=True):
            st.markdown("### Your ZimiFare account")
            st.caption("Sign in or create a passenger / driver account to begin.")
            login_tab, register_tab = st.tabs(["Sign in", "Create account"])
            with login_tab:
                with st.form("login_form"):
                    email = st.text_input("Email address", placeholder="you@example.com")
                    password = st.text_input("Password", type="password")
                    submit = st.form_submit_button("Sign in securely", type="primary", use_container_width=True)
                if submit:
                    try:
                        user = store.login(email, password)
                        st.session_state.user_id = user["user_id"]
                        st.session_state.pop("nav", None)
                        st.rerun()
                    except Exception as exc:
                        friendly_error(exc)
            with register_tab:
                with st.form("register_form"):
                    name = st.text_input("Full name", placeholder="Your full name")
                    em = st.text_input("Email address", placeholder="you@example.com")
                    phone = st.text_input("Phone number")
                    role = st.selectbox("Register as", ["PASSENGER", "DRIVER"], format_func=str.title)
                    password = st.text_input("Create password (8+ characters)", type="password")
                    password_2 = st.text_input("Confirm password", type="password")
                    submit_registration = st.form_submit_button("Create my account", type="primary", use_container_width=True)
                if submit_registration:
                    if password != password_2:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            uid = store.register(name, em, phone, password, role)
                            st.success(f"Account created! Your user ID is {user_ref(uid, role)}. Switch to Sign in to continue.")
                        except Exception as exc:
                            friendly_error(exc)
    show_flash()


def profile_page(store: ZimiFareStore, user: dict) -> None:
    main_header(user, "Your profile", "Manage your account details and sign-in password.")
    a, b = st.columns([1.55, 1], gap="large")
    with a:
        section("Profile details")
        with st.form("my_profile"):
            st.caption("Leave a field blank to keep the existing information.")
            st.text_input("Email address (cannot be changed)", value=user["email"], disabled=True)
            name = st.text_input("New full name", placeholder=user["full_name"])
            phone = st.text_input("New phone number", placeholder=user["phone_num"])
            current_pw = st.text_input("Current password (only for password changes)", type="password")
            new_pw = st.text_input("New password (optional)", type="password")
            submit = st.form_submit_button("Save profile changes", type="primary")
        if submit:
            try:
                store.update_profile(user["user_id"], name, phone, new_pw, current_pw)
                flash("Your profile has been updated successfully.")
                st.rerun()
            except Exception as exc:
                friendly_error(exc)
    with b:
        st.markdown("### Account information")
        with st.container(border=True):
            st.write(f"**Account ID:** {user_ref(user['user_id'], user['role'])}")
            st.write(f"**Role:** {user['role'].title()}")
            st.write(f"**Status:** {user['status'].title()}")
            st.caption("Email addresses and assigned roles cannot be changed from the profile screen.")


def passenger_overview(store: ZimiFareStore, user: dict) -> None:
    main_header(user, "Welcome back", "Your fare card, upcoming payments and travel history, in one place.")
    rides = store.list_rides(user["user_id"])
    unpaid = [r for r in rides if r["payment_status"] == "UNPAID"]
    paid = [r for r in rides if r["payment_status"] == "PAID"]
    a,b,c = st.columns(3)
    a.metric("Fare-card balance", money(user["balance_cents"]))
    b.metric("Unpaid fares", len(unpaid))
    c.metric("Completed rides", len(paid))
    st.markdown("### Quick actions")
    a,b,c = st.columns(3)
    with a:
        if st.button("＋  Top up fare card", type="primary", use_container_width=True): nav_to("Top up fare card")
    with b:
        if st.button("↗  Pay a fare", use_container_width=True): nav_to("Pay a fare")
    with c:
        if st.button("▤  View ride history", use_container_width=True): nav_to("Ride history")
    st.markdown("### Recent rides")
    ride_table(rides[:5])
    if unpaid:
        st.warning(f"You have {len(unpaid)} outstanding fare request(s). Open **Pay a fare** to settle one.")


def passenger_topup(store: ZimiFareStore, user: dict) -> None:
    main_header(user, "Top up your fare card", "Add simulated funds to your ZimiFare balance and receive a transaction reference.")
    a,b = st.columns([1.4,1], gap="large")
    with a:
        with st.form("topup_form"):
            st.markdown("### Add funds")
            amount = st.text_input("Amount (JMD)", value="1000.00", help="Positive amount, with up to two decimal places.")
            agreed = st.checkbox("I understand this is a simulated top-up, not a real bank payment.")
            submit = st.form_submit_button("Confirm simulated top-up", type="primary", use_container_width=True)
        if submit:
            if not agreed:
                st.error("Please confirm that you understand the top-up is simulated.")
            else:
                try:
                    tx, balance = store.top_up(user["user_id"], cents_from_input(amount))
                    flash(f"Top-up recorded! Transaction {transaction_ref(tx)}. New balance: {money(balance)}.")
                    st.rerun()
                except Exception as exc:
                    friendly_error(exc)
    with b:
        st.metric("Available balance", money(user["balance_cents"]))
        st.info("For this academic demonstration, top-ups are treated as confirmed **without a bank connection or actual transfer**.")
    section("Your recent transactions")
    transactions_table(store.passenger_transactions(user["user_id"])[:8], admin=False)


def passenger_pay(store: ZimiFareStore, user: dict) -> None:
    main_header(user, "Pay a taxi fare", "Settle an outstanding ride created by your assigned driver.")
    rides = [r for r in store.list_rides(user["user_id"]) if r["payment_status"] == "UNPAID"]
    st.metric("Available fare-card balance", money(user["balance_cents"]))
    if not rides:
        empty("You have no unpaid rides. Ask your driver to create a fare request first.")
        return
    with st.form("pay_fare"):
        selected = st.selectbox(
            "Unpaid ride", rides,
            format_func=lambda r: f"{ride_ref(r['ride_id'])}  •  {r['pickup']} → {r['destination']}  •  {money(r['fare_cents'])}"
        )
        st.markdown(f"**Driver:** {selected['driver_name']}  ")
        st.markdown(f"**Ride date:** {selected['ride_date']}  ")
        st.markdown(f"**Agreed fare:** {money(selected['fare_cents'])}  ")
        confirm = st.checkbox("I authorise this fare-card payment to be deducted from my balance.")
        submit = st.form_submit_button("Pay selected fare", type="primary", use_container_width=True)
    if submit:
        if not confirm:
            st.error("Please authorise the payment before continuing.")
        else:
            try:
                tx, remaining = store.settle_ride(user["user_id"], selected["ride_id"], "FARE_CARD")
                flash(f"Payment successful! Ride {ride_ref(selected['ride_id'])}, {transaction_ref(tx)}. Remaining balance: {money(remaining or 0)}.")
                st.rerun()
            except Exception as exc:
                friendly_error(exc)
    st.caption("Payment can only be made once. Your driver receives earnings credit from the paid ride; no additional amount is entered here.")


def passenger_history(store: ZimiFareStore, user: dict) -> None:
    main_header(user, "Your ride history", "Every ride linked to your ZimiFare passenger account.")
    rows = store.list_rides(user["user_id"])
    f = st.selectbox("Payment status", ["All rides", "Paid", "Unpaid"])
    if f != "All rides":
        rows = [r for r in rows if r["payment_status"] == f.upper()]
    ride_table(rows)


def driver_overview(store: ZimiFareStore, user: dict) -> None:
    main_header(user, "Welcome back", "Manage your fare requests and track successful passenger payments.")
    rides = store.list_rides(user["user_id"])
    paid = store.driver_earnings(user["user_id"])
    a,b,c = st.columns(3)
    a.metric("Total fares earned", money(paid["total_cents"]))
    b.metric("Paid rides", paid["paid_count"])
    c.metric("Awaiting payment", len([r for r in rides if r["payment_status"]=="UNPAID"]))
    st.markdown("### Quick actions")
    a,b,c = st.columns(3)
    with a:
        if st.button("＋  Create fare request", type="primary", use_container_width=True): nav_to("Receive a fare")
    with b:
        if st.button("▥  View earnings", use_container_width=True): nav_to("My earnings")
    with c:
        if st.button("▤  All rides", use_container_width=True): nav_to("Ride history")
    section("Recent rides")
    ride_table(rides[:5], driver_view=True)


def driver_receive(store: ZimiFareStore, user: dict) -> None:
    main_header(user, "Receive a fare", "Create a fare request or confirm cash received for an existing ride.")
    create_tab, cash_tab = st.tabs(["Create fare request", "Receive cash"])
    with create_tab:
        passengers = store.passengers(user["user_id"])
        if not passengers:
            empty("No active passenger accounts are available yet. Ask a passenger to register first.")
        else:
            with st.form("create_ride"):
                st.markdown("### Journey and passenger details")
                p = st.selectbox(
                    "Passenger", passengers,
                    format_func=lambda item: f"{item['full_name']}  ·  {user_ref(item['user_id'], 'PASSENGER')} ({item['email']})"
                )
                a,b = st.columns(2)
                with a:
                    ride_date = st.date_input("Ride date", value=date.today())
                    pickup = st.text_input("Pickup location", placeholder="e.g. Half Way Tree")
                with b:
                    fare = st.text_input("Agreed fare (JMD)", value="250.00")
                    destination = st.text_input("Destination", placeholder="e.g. New Kingston")
                confirmation = st.checkbox("The passenger and I have agreed on the fare and journey details.")
                create = st.form_submit_button("Create unpaid ride", type="primary", use_container_width=True)
            if create:
                if not confirmation:
                    st.error("Please confirm the agreed fare and journey details.")
                else:
                    try:
                        ride_id = store.create_ride(
                            user["user_id"], p["user_id"], ride_date.isoformat(),
                            pickup, destination, cents_from_input(fare)
                        )
                        st.success(f"Fare request {ride_ref(ride_id)} created. The passenger can now pay with their fare card, or you can confirm cash using the Receive cash tab.")
                    except Exception as exc:
                        friendly_error(exc)
        st.caption(f"This prototype allows up to {MAX_RIDES} ride records, as specified in the pseudocode.")
    with cash_tab:
        unpaid = [r for r in store.list_rides(user["user_id"]) if r["payment_status"] == "UNPAID"]
        if not unpaid:
            empty("No unpaid rides are assigned to your driver account.")
        else:
            with st.form("cash_received"):
                selected = st.selectbox(
                    "Select an unpaid ride", unpaid,
                    format_func=lambda r: f"{ride_ref(r['ride_id'])}  •  {r['passenger_name']}  •  {money(r['fare_cents'])}"
                )
                st.write(f"**Route:** {selected['pickup']} → {selected['destination']}")
                st.write(f"**Agreed fare:** {money(selected['fare_cents'])}")
                confirm_cash = st.checkbox("I confirm that I have physically received the full cash fare.")
                settle = st.form_submit_button("Record cash payment", type="primary", use_container_width=True)
            if settle:
                if not confirm_cash:
                    st.error("Confirm that the cash was received before recording payment.")
                else:
                    try:
                        tx, _ = store.settle_ride(user["user_id"], selected["ride_id"], "CASH")
                        flash(f"Cash received! Ride {ride_ref(selected['ride_id'])} settled as {transaction_ref(tx)}. The passenger's fare-card balance is unchanged.")
                        st.rerun()
                    except Exception as exc:
                        friendly_error(exc)
        st.caption("Cash is recorded by the assigned driver only. Fare-card payment is completed by the passenger.")


def driver_earnings(store: ZimiFareStore, user: dict) -> None:
    main_header(user, "My earnings", "Earnings come from successfully paid rides only, including card and cash payments.")
    report = store.driver_earnings(user["user_id"])
    a,b = st.columns(2)
    a.metric("Total earnings", money(report["total_cents"]))
    b.metric("Paid ride count", report["paid_count"])
    section("Completed fare payments")
    ride_table(report["rides"], driver_view=True)
    st.caption("Unpaid fares are not included in earnings. These are gross recorded fares, not net profit after expenses.")


def driver_history(store: ZimiFareStore, user: dict) -> None:
    main_header(user, "Driver ride history", "Track every paid and unpaid fare request associated with your account.")
    rows = store.list_rides(user["user_id"])
    status = st.selectbox("Payment status", ["All rides", "Paid", "Unpaid"])
    if status != "All rides":
        rows = [r for r in rows if r["payment_status"] == status.upper()]
    ride_table(rows, driver_view=True)


def analytics_charts(rows: list[dict], *, compact: bool = False) -> None:
    """Chart only genuine recorded transactions; never make up sample values."""
    summary = summarise_transactions(rows)
    if not rows:
        st.info("No transactions match the current filters. Charts will appear after genuine top-ups or payments are recorded.")
        return

    brand = alt.Scale(domain=["FARE_PAYMENT", "TOP_UP"], range=["#00ae96", "#f0b644"])
    daily = pd.DataFrame(summary["daily"])
    # Groups are aggregated once in Python, so bars and lines display actual sums.
    val_chart = (alt.Chart(daily).mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
        .encode(x=alt.X("day:T", title="Transaction date (UTC)", axis=alt.Axis(format="%d %b", labelAngle=0)),
                y=alt.Y("sum(amount):Q", title="Amount (JMD)", axis=alt.Axis(format=",.0f")),
                color=alt.Color("type:N", scale=brand, title="Transaction type",
                                legend=alt.Legend(orient="bottom")),
                tooltip=[alt.Tooltip("day:T", title="Date", format="%d %b %Y"),
                         alt.Tooltip("type:N", title="Type"),
                         alt.Tooltip("sum(amount):Q", title="Total JMD", format=",.2f")])
        .properties(height=265 if compact else 315))

    fare_rows = [r for r in rows if r["tx_type"] == "FARE_PAYMENT"]
    method_data = []
    for method, label in (("FARE_CARD", "Fare card"), ("CASH", "Cash")):
        these = [r for r in fare_rows if r["method"] == method]
        if these:
            method_data.append({"method": label, "rides": len(these),
                                "amount": sum(int(r["amount_cents"]) for r in these)/100})
    left, right = st.columns([1.7, 1], gap="large")
    with left:
        st.markdown("#### Recorded transaction value")
        st.altair_chart(val_chart, use_container_width=True)
    with right:
        st.markdown("#### Paid fare methods")
        if method_data:
            pie = (alt.Chart(pd.DataFrame(method_data)).mark_arc(innerRadius=63, outerRadius=103)
                .encode(theta=alt.Theta("amount:Q", title="Paid fares (JMD)"),
                        color=alt.Color("method:N", scale=alt.Scale(domain=["Fare card", "Cash"],
                                       range=["#00ae96", "#f0b644"]),
                                        legend=alt.Legend(orient="bottom", title="Method")),
                        tooltip=[alt.Tooltip("method:N", title="Method"),
                                 alt.Tooltip("amount:Q", title="JMD", format=",.2f"),
                                 alt.Tooltip("rides:Q", title="Paid rides")])
                .properties(height=265 if compact else 315))
            st.altair_chart(pie, use_container_width=True)
        else:
            st.info("No paid rides in this period. Top-ups are not counted as fare revenue.")

    if not compact:
        chart_col, table_col = st.columns([1.05,1], gap="large")
        with chart_col:
            st.markdown("#### Number of transactions by day")
            counts = (alt.Chart(daily).mark_line(point=True, strokeWidth=3)
                .encode(x=alt.X("day:T", title="Date (UTC)"),
                        y=alt.Y("sum(count):Q", title="Number of transactions", axis=alt.Axis(tickMinStep=1)),
                        color=alt.Color("type:N", scale=brand, legend=alt.Legend(orient="bottom", title="Type")),
                        tooltip=[alt.Tooltip("day:T", title="Date", format="%d %b %Y"),
                                 alt.Tooltip("type:N", title="Type"),
                                 alt.Tooltip("sum(count):Q", title="Transactions")])
                .properties(height=265))
            st.altair_chart(counts, use_container_width=True)
        with table_col:
            st.markdown("#### Highest earning drivers (recorded fares)")
            drivers = {}
            for r in fare_rows:
                driver_id = r.get("driver_id")
                if not driver_id:
                    continue
                key = f"{r.get('driver_name','Driver')} ({user_ref(driver_id,'DRIVER')})"
                drivers[key] = drivers.get(key, 0) + r["amount_cents"]
            if drivers:
                leaders = pd.DataFrame([{"driver": name, "JMD": cents / 100}
                                        for name, cents in drivers.items()])
                leaders = leaders.sort_values("JMD", ascending=False).head(7)
                chart = (alt.Chart(leaders).mark_bar(cornerRadiusEnd=6, color="#00ae96")
                    .encode(y=alt.Y("driver:N", sort="-x", title=None),
                            x=alt.X("JMD:Q", title="Paid fares (JMD)", axis=alt.Axis(format=",.0f")),
                            tooltip=[alt.Tooltip("driver:N",title="Driver"),
                                     alt.Tooltip("JMD:Q", title="JMD",format=",.2f")])
                    .properties(height=265))
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("Driver totals appear when rides are paid.")
    st.caption("All graphs use the live transaction log. Amounts are in JMD, dates use UTC. Simulated top-ups are shown separately from paid fares.")


def admin_analytics(store: ZimiFareStore, user: dict) -> None:
    main_header(user, "Analytics & reports", "Live financial insights, interactive filters and downloadable operational records.")
    transactions = store.list_transactions(user["user_id"])
    st.markdown('<span class="report-tag">LIVE DATA · NO SAMPLE TRANSACTIONS</span>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("#### Explore recorded activity")
        c1, c2, c3 = st.columns(3)
        with c1:
            period = st.selectbox("Period", ["All time", "Last 7 days", "Last 30 days", "Last 90 days", "Custom dates"], index=0)
        with c2:
            transaction_type = st.selectbox("Transaction type", ["All types", "Fare payments", "Simulated top-ups"])
        with c3:
            method_choice = st.selectbox("Payment method", ["All methods", "Fare card", "Cash", "Simulated top-up"])
        start_date = end_date = None
        today = datetime.now(timezone.utc).date()
        if period == "Last 7 days": start_date = today - timedelta(days=6)
        elif period == "Last 30 days": start_date = today - timedelta(days=29)
        elif period == "Last 90 days": start_date = today - timedelta(days=89)
        elif period == "Custom dates":
            chosen = st.date_input("Date range (UTC, inclusive)", value=(today - timedelta(days=30), today))
            if isinstance(chosen, tuple) and len(chosen) == 2:
                start_date, end_date = chosen
            else:
                st.info("Select both a start and end date to apply the custom filter.")
                return
        c1, c2 = st.columns([2, 1])
        with c1:
            search = st.text_input("Search passenger, driver, or reference", placeholder="Name, ride number, or transaction number")
        with c2:
            flagged_only = st.checkbox("Show flagged transactions only")
    type_set = {"FARE_PAYMENT"} if transaction_type == "Fare payments" else ({"TOP_UP"} if transaction_type == "Simulated top-ups" else None)
    method_set = {"FARE_CARD"} if method_choice == "Fare card" else ({"CASH"} if method_choice == "Cash" else ({"SIMULATED_TOP_UP"} if method_choice == "Simulated top-up" else None))
    rows = filter_transactions(transactions, start=start_date, end=end_date, types=type_set,
                               methods=method_set, flagged=flagged_only, keyword=search)
    report = summarise_transactions(rows)
    a,b,c,d = st.columns(4)
    a.metric("Transactions", f"{report['transactions']:,}")
    b.metric("Paid fare value", money(report["fare_cents"]))
    c.metric("Simulated top-ups", money(report["topup_cents"]))
    d.metric("Review flags", report["flagged_count"])
    st.markdown('<div class="insight"><b>Accounting note:</b> Top-ups add simulated value to fare cards; they are not fare revenue. '
                'The paid-fare value counts successful card and cash settlements only. '
                'The selected date range applies to the transaction recording time (UTC).</div>', unsafe_allow_html=True)
    analytics_charts(rows)
    st.markdown("### Filtered transaction ledger")
    transactions_table(rows, admin=True)
    export_rows = []
    for t in rows:
        export_rows.append({"Transaction reference": transaction_ref(t["transaction_id"]),
                            "Ride reference": ride_ref(t["ride_id"]) if t["ride_id"] else "",
                            "Recorded UTC": t["recorded_at"], "Type": t["tx_type"],
                            "Method": t["method"], "Amount JMD": f"{t['amount_cents']//100}.{t['amount_cents']%100:02d}",
                            "Passenger": t["passenger_name"], "Driver": t["driver_name"],
                            "Review flag": "Flagged" if t["flagged"] else "Clear"})
    buf = StringIO()
    fieldnames = ["Transaction reference", "Ride reference", "Recorded UTC", "Type",
                  "Method", "Amount JMD", "Passenger", "Driver", "Review flag"]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for item in export_rows:
        # Prevent spreadsheet formula injection via user-controlled names.
        for field in ("Passenger", "Driver"):
            if str(item[field]).lstrip().startswith(("=", "+", "-", "@")):
                item[field] = "'" + str(item[field])
        writer.writerow(item)
    st.download_button("↓  Download filtered transactions (CSV)", data=buf.getvalue().encode("utf-8-sig"),
                       file_name="ZimiFare_Transactions_Report.csv", mime="text/csv")
    with st.expander("View all ride records (administrator only)"):
        rides = store.admin_list_rides(user["user_id"])
        ride_table_admin(rides)


def ride_table_admin(rows: list[dict]) -> None:
    if not rows:
        empty("No ride records yet.")
        return
    st.dataframe([{
        "Ride": ride_ref(r["ride_id"]),
        "Passenger": f"{r['passenger_name']} ({user_ref(r['passenger_id'], 'PASSENGER')})",
        "Driver": f"{r['driver_name']} ({user_ref(r['driver_id'], 'DRIVER')})",
        "Date": r["ride_date"], "From":r["pickup"], "To":r["destination"],
        "Fare":money(r["fare_cents"]), "Status":r["payment_status"],
        "Method":r["payment_method"],
        "Transaction":transaction_ref(r["transaction_id"]) if r["transaction_id"] else "—"
    } for r in rows], hide_index=True, use_container_width=True)


def admin_overview(store: ZimiFareStore, user: dict) -> None:
    main_header(user, "Administration overview", "A clear view of users, fare activity and transactions needing review.")
    if getattr(store, "backend_name", ""):
        st.caption("☁️ Persistent database connected · PostgreSQL · Shared across devices")
    else:
        st.warning("Temporary SQLite storage is active. For reliable shared data, configure DATABASE_URL in Streamlit secrets.")
    totals = store.system_totals(user["user_id"])
    a,b,c,d = st.columns(4)
    a.metric("Registered users", totals["users"])
    b.metric("Rides created", totals["rides"])
    c.metric("Transactions", totals["transactions"])
    d.metric("Flagged for review", totals["flagged"])
    st.markdown("### Operational summary")
    a,b,c = st.columns(3)
    a.metric("Passengers", totals["passengers"])
    b.metric("Drivers", totals["drivers"])
    c.metric("Paid fare value", money(totals["fares_cents"]))
    if totals["flagged"]:
        st.warning(f"{totals['flagged']} transaction(s) exceed the JMD 50,000 review threshold. A review flag is not proof of fraud.")
    st.markdown("### Transaction trends")
    analytics_charts(store.list_transactions(user["user_id"]), compact=True)
    if st.button("Open interactive analytics and reports →", use_container_width=True):
        nav_to("Analytics & reports")
    section("Latest transactions")
    transactions_table(store.list_transactions(user["user_id"])[:8], admin=True)


def admin_users(store: ZimiFareStore, user: dict) -> None:
    main_header(user, "Manage users", "View accounts, update contact details and restrict non-administrator access.")
    users = store.list_users(user["user_id"])
    section("Account directory")
    st.dataframe([{
        "ID":user_ref(u["user_id"],u["role"]), "Name":u["full_name"], "Email":u["email"],
        "Phone":u["phone_num"], "Role":u["role"], "Status":u["status"],
        "Fare card": money(u["balance_cents"]) if u["role"] == "PASSENGER" else "—"
    } for u in users], hide_index=True, use_container_width=True)
    edit_tab,status_tab,create_admin_tab = st.tabs(["Update account", "Disable / block account", "Create administrator"])
    with edit_tab:
        with st.form("admin_update_user"):
            target = st.selectbox("Select user", users, format_func=lambda u: f"{user_ref(u['user_id'],u['role'])} · {u['full_name']} · {u['role']}")
            name = st.text_input("New full name (optional)")
            phone = st.text_input("New phone number (optional)")
            submitted = st.form_submit_button("Save user changes", type="primary")
        if submitted:
            try:
                store.admin_edit_user(user["user_id"], target["user_id"], name, phone)
                flash(f"Account {user_ref(target['user_id'], target['role'])} updated.")
                st.rerun()
            except Exception as exc:
                friendly_error(exc)
    with status_tab:
        eligible = [u for u in users if u["role"] != "ADMIN"]
        if not eligible:
            empty("There are no passenger or driver accounts to restrict.")
        else:
            with st.form("admin_status_change"):
                target = st.selectbox("Passenger / driver", eligible, format_func=lambda u: f"{user_ref(u['user_id'],u['role'])} · {u['full_name']} · {u['status']}")
                status = st.radio("New status", ["DISABLED", "BLOCKED"], horizontal=True)
                confirmed = st.checkbox("I confirm this access restriction and understand ride and payment history remains intact.")
                submitted = st.form_submit_button("Apply account restriction", type="primary")
            if submitted:
                if not confirmed:
                    st.error("Confirm the access restriction to continue.")
                else:
                    try:
                        store.set_user_status(user["user_id"], target["user_id"], status)
                        flash(f"Account {user_ref(target['user_id'], target['role'])} status changed to {status}.")
                        st.rerun()
                    except Exception as exc:
                        friendly_error(exc)
        st.caption("As defined in the pseudocode, blocking cannot be downgraded to disabling; reactivation is not included in this prototype.")

    with create_admin_tab:
        st.info("Only an active administrator can create another administrator. "
                "For security, you must re-enter your own password to approve this action.")
        with st.form("create_additional_admin", clear_on_submit=True):
            admin_name = st.text_input("New administrator's full name")
            admin_email = st.text_input("New administrator's email address")
            admin_phone = st.text_input("New administrator's phone number")
            admin_password = st.text_input("Set new administrator password (at least 8 characters)", type="password")
            admin_confirm_password = st.text_input("Confirm new administrator password", type="password")
            authorising_password = st.text_input("Your current administrator password", type="password")
            authorised = st.checkbox("I confirm that this person should have full administrator access.")
            add_admin = st.form_submit_button("Create administrator", type="primary")
        if add_admin:
            if not authorised:
                st.error("Confirm the administrator access grant before continuing.")
            elif admin_password != admin_confirm_password:
                st.error("The new administrator passwords do not match.")
            else:
                try:
                    new_id = store.create_administrator(
                        user["user_id"], authorising_password, admin_name,
                        admin_email, admin_phone, admin_password,
                    )
                    flash(f"Administrator account {user_ref(new_id, 'ADMIN')} created successfully. "
                          "The new administrator can now sign in using their own email and password.")
                    st.rerun()
                except Exception as exc:
                    friendly_error(exc)


def admin_transactions(store: ZimiFareStore, user: dict) -> None:
    main_header(user, "Transaction monitor", "Inspect successful top-ups and fare settlements from the shared transaction log.")
    a,b = st.columns([2,1])
    with a:
        filter_by = st.radio("View", ["All transactions", "Flagged only", "Search by transaction ID"], horizontal=True)
    transaction_id = None
    if filter_by == "Search by transaction ID":
        reference = st.text_input("Transaction reference", placeholder="ZF-TXN-000001 or 1")
        if reference.strip():
            try:
                transaction_id = parse_transaction_ref(reference)
            except ValueError as exc:
                st.warning(str(exc))
                return
        else:
            st.info("Enter a transaction reference to search.")
            return
    rows = store.list_transactions(user["user_id"], transaction_id=transaction_id, flagged_only=filter_by=="Flagged only")
    transactions_table(rows, admin=True)
    st.caption(f"Maximum log capacity: {MAX_TRANSACTIONS:,} transactions. This screen never creates payments.")


def admin_fraud(store: ZimiFareStore, user: dict) -> None:
    main_header(user, "Fraud review", "Identify high-value transactions for administrative assessment, not automatic punishment.")
    st.metric("Review threshold", money(FRAUD_THRESHOLD_CENTS))
    st.info("Only transaction amounts **strictly greater** than JMD 50,000.00 are flagged. A flag does not prove fraud or automatically block a user.")
    if st.button("↻  Run fraud detection", type="primary"):
        try:
            found = store.detect_fraud(user["user_id"])
            st.success(f"Review complete: {len(found)} transaction(s) flagged.")
        except Exception as exc:
            friendly_error(exc)
    st.markdown("### Flagged transactions")
    flagged = store.list_transactions(user["user_id"], flagged_only=True)
    transactions_table(flagged, admin=True)


def main() -> None:
    store = get_store()
    if not store.has_admin():
        admin_setup(store)
        return
    user_id = st.session_state.get("user_id")
    user = store.current_user(user_id) if user_id is not None else None
    if not user or user["status"] != "ACTIVE":
        st.session_state.pop("user_id", None)
        st.session_state.pop("nav", None)
        public_page(store)
        return
    route = sidebar(user)
    show_flash()
    routes = {
        "PASSENGER": {
            "Overview": passenger_overview,
            "Top up fare card": passenger_topup,
            "Pay a fare": passenger_pay,
            "Ride history": passenger_history,
            "My profile": profile_page,
        },
        "DRIVER": {
            "Overview": driver_overview,
            "Receive a fare": driver_receive,
            "My earnings": driver_earnings,
            "Ride history": driver_history,
            "My profile": profile_page,
        },
        "ADMIN": {
            "Overview": admin_overview,
            "Analytics & reports": admin_analytics,
            "Manage users": admin_users,
            "Transactions": admin_transactions,
            "Fraud review": admin_fraud,
            "My profile": profile_page,
        },
    }
    try:
        routes[user["role"]][route](store, user)
    except (ZimiFareError, AccessDenied) as exc:
        st.error(str(exc))


if __name__ == "__main__":
    main()
