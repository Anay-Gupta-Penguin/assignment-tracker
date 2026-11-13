"""
📚 Assignment Tracker — Zero-Latency @st.fragment, Live SHS Bell Schedule & Theme Studio
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import threading
import urllib.request
import uuid
from datetime import datetime, date, timedelta, time
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(
    page_title="Assignment Tracker",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="collapsed",
)

try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    HAS_PIL = False

CURRENT_APP_VERSION = "3.4"


def get_local_now() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.utcnow() - timedelta(hours=4)


# -----------------------
# Streamlit Decorators & Rerun Helpers
# -----------------------
def safe_rerun(scope: str = "app") -> None:
    if hasattr(st, "rerun"):
        try:
            st.rerun(scope=scope)
        except TypeError:
            st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


if hasattr(st, "fragment"):
    fragment_decorator = st.fragment
elif hasattr(st, "experimental_fragment"):
    fragment_decorator = st.experimental_fragment
else:
    def fragment_decorator(func=None, **kwargs):
        return (lambda f: f) if func is None else func


if hasattr(st, "dialog"):
    dialog_decorator = st.dialog
elif hasattr(st, "experimental_dialog"):
    dialog_decorator = st.experimental_dialog
else:
    def dialog_decorator(title: str):
        def decorator(func):
            def wrapper(*args, **kwargs):
                st.subheader(title)
                return func(*args, **kwargs)
            return wrapper
        return decorator


# -----------------------
# Theme Presets & WCAG Contrast Engine
# -----------------------
THEME_PRESETS: Dict[str, Dict[str, Any]] = {
    "Midnight Indigo (Default Dark)": {
        "mode": "Dark",
        "bg_css": (
            "background-color: #070a12;"
            "background-image: radial-gradient(at 15% 15%, rgba(99, 102, 241, 0.14) 0px, transparent 50%),"
            "radial-gradient(at 85% 85%, rgba(14, 165, 233, 0.10) 0px, transparent 50%);"
        ),
        "accent": "#6366f1",
        "solid_bg": "#070a12",
        "grad_1": "#0f172a",
        "grad_2": "#1e1b4b",
        "grad_3": "#070a12",
    },
    "Daylight Mist (Eye-Friendly Light)": {
        "mode": "Light",
        "bg_css": (
            "background-color: #d6dfeb;"
            "background-image: linear-gradient(135deg, #d8e1ed 0%, #cbd5e1 100%);"
        ),
        "accent": "#4338ca",
        "solid_bg": "#d6dfeb",
        "grad_1": "#dce4ef",
        "grad_2": "#c7d4e6",
        "grad_3": "#d6dfeb",
    },
    "Warm Stone (Soft Light)": {
        "mode": "Light",
        "bg_css": (
            "background-color: #dddad3;"
            "background-image: linear-gradient(135deg, #e5e2dc 0%, #d2cec4 100%);"
        ),
        "accent": "#b45309",
        "solid_bg": "#dddad3",
        "grad_1": "#e5e2dc",
        "grad_2": "#cfc9bd",
        "grad_3": "#dddad3",
    },
    "Sage Breeze (Muted Light)": {
        "mode": "Light",
        "bg_css": (
            "background-color: #cfe0da;"
            "background-image: linear-gradient(135deg, #d8e7e2 0%, #bdd4cc 100%);"
        ),
        "accent": "#047857",
        "solid_bg": "#cfe0da",
        "grad_1": "#d8e7e2",
        "grad_2": "#b8d0c7",
        "grad_3": "#cfe0da",
    },
    "Nordic Slate (Cool Light)": {
        "mode": "Light",
        "bg_css": (
            "background-color: #cdd9e5;"
            "background-image: linear-gradient(135deg, #d7e2ec 0%, #bcccdc 100%);"
        ),
        "accent": "#0369a1",
        "solid_bg": "#cdd9e5",
        "grad_1": "#d7e2ec",
        "grad_2": "#b6c7d8",
        "grad_3": "#cdd9e5",
    },
    "Cyberpunk Neon (Dark)": {
        "mode": "Dark",
        "bg_css": (
            "background-color: #090414;"
            "background-image: radial-gradient(at 20% 20%, rgba(236, 72, 153, 0.18) 0px, transparent 50%),"
            "radial-gradient(at 80% 80%, rgba(6, 182, 212, 0.18) 0px, transparent 50%);"
        ),
        "accent": "#ec4899",
        "solid_bg": "#090414",
        "grad_1": "#19072b",
        "grad_2": "#082f49",
        "grad_3": "#090414",
    },
    "Emerald Forest (Dark)": {
        "mode": "Dark",
        "bg_css": (
            "background-color: #04120e;"
            "background-image: radial-gradient(at 15% 15%, rgba(16, 185, 129, 0.16) 0px, transparent 50%),"
            "radial-gradient(at 85% 85%, rgba(20, 184, 166, 0.12) 0px, transparent 50%);"
        ),
        "accent": "#10b981",
        "solid_bg": "#04120e",
        "grad_1": "#06241b",
        "grad_2": "#04120e",
        "grad_3": "#0b2e26",
    },
    "Sunset Synthwave (Dark)": {
        "mode": "Dark",
        "bg_css": (
            "background-color: #140818;"
            "background-image: linear-gradient(135deg, #1e0b2b 0%, #3b1236 50%, #170d24 100%);"
        ),
        "accent": "#f97316",
        "solid_bg": "#140818",
        "grad_1": "#1e0b2b",
        "grad_2": "#4c1d3d",
        "grad_3": "#170d24",
    },
    "Royal Amethyst (Dark)": {
        "mode": "Dark",
        "bg_css": (
            "background-color: #0d071a;"
            "background-image: radial-gradient(at 20% 10%, rgba(168, 85, 247, 0.18) 0px, transparent 50%),"
            "radial-gradient(at 80% 90%, rgba(99, 102, 241, 0.14) 0px, transparent 50%);"
        ),
        "accent": "#a855f7",
        "solid_bg": "#0d071a",
        "grad_1": "#1e1035",
        "grad_2": "#0d071a",
        "grad_3": "#170d2e",
    },
    "Trojan Navy & Gold (Dark)": {
        "mode": "Dark",
        "bg_css": (
            "background-color: #060d1f;"
            "background-image: radial-gradient(at 15% 15%, rgba(234, 179, 8, 0.15) 0px, transparent 50%),"
            "radial-gradient(at 85% 85%, rgba(37, 99, 235, 0.18) 0px, transparent 50%);"
        ),
        "accent": "#eab308",
        "solid_bg": "#060d1f",
        "grad_1": "#0a1938",
        "grad_2": "#060d1f",
        "grad_3": "#172554",
    },
}

DEFAULT_THEME_CONFIG: Dict[str, Any] = {
    "preset": "Midnight Indigo (Default Dark)",
    "mode": "Dark",
    "accent": "#6366f1",
    "bg_type": "preset",
    "solid_bg": "#070a12",
    "grad_1": "#0f172a",
    "grad_2": "#312e81",
    "grad_3": "#070a12",
    "use_grad_3": False,
    "grad_angle": "135deg",
    "photo_source": "",
    "overlay_opacity": 45,
    "card_opacity": 88,
}


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = str(hex_color or "#6366f1").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except Exception:
        return (99, 102, 241)


def _relative_luminance(hex_color: str) -> float:
    r, g, b = [c / 255.0 for c in _hex_to_rgb(hex_color)]
    r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
    g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
    b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


CSS_TEMPLATE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {
    --text-primary: __TEXT_PRIMARY__;
    --text-secondary: __TEXT_SECONDARY__;
    --text-muted: __TEXT_MUTED__;
    --card-bg: __CARD_BG__;
    --popover-bg: __POPOVER_BG__;
    --card-border: __CARD_BORDER__;
    --nav-bg: __NAV_BG__;
    --input-bg: __INPUT_BG__;
    --input-border: __INPUT_BORDER__;
    --btn-bg: __BTN_BG__;
    --btn-hover-bg: __BTN_HOVER_BG__;
    --accent: __ACCENT__;
    --accent-readable: __ACCENT_READABLE__;
    --on-accent-text: __ON_ACCENT_TEXT__;
    --accent-soft: __ACCENT_SOFT__;
    --accent-border: __ACCENT_BORDER__;
    --accent-glow: __ACCENT_GLOW__;
    --slot-bg: __SLOT_BG__;
    --shadow-color: __SHADOW_COLOR__;
}

html, body, .stApp {
    __BG_RULE__
    color: var(--text-primary) !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

.main .block-container {
    padding-top: 1rem !important;
    padding-bottom: 3rem !important;
    max-width: 1420px;
}

#MainMenu, header, footer {visibility: hidden;}
div[data-testid="stToolbar"], div[data-testid="stDecoration"], div[data-testid="stStatusWidget"] {display: none !important;}
section[data-testid="stSidebar"], div[data-testid="collapsedControl"], button[data-testid="stSidebarCollapseButton"] {display: none !important;}

.stApp p, .stApp label, .stApp span, .stMarkdown,
div[data-testid="stMarkdownContainer"] p,
div[data-testid="stWidgetLabel"] p,
div[data-testid="stWidgetLabel"] label {
    color: var(--text-primary) !important;
}
div[data-testid="stCaptionContainer"] p {
    color: var(--text-muted) !important;
}

div[data-testid="stCheckbox"] label > span:first-child,
div[data-testid="stCheckbox"] div[role="checkbox"] {
    border: 1.5px solid var(--accent-readable) !important;
    border-radius: 5px !important;
}

div[data-baseweb="input"] > div,
div[data-baseweb="base-input"] > input,
div[data-baseweb="select"] > div,
textarea {
    background-color: var(--input-bg) !important;
    color: var(--text-primary) !important;
    border: 1.5px solid var(--input-border) !important;
    caret-color: var(--text-primary) !important;
}
div[data-baseweb="select"] span,
div[data-baseweb="select"] div,
div[data-baseweb="select"] svg {
    color: var(--text-primary) !important;
    fill: var(--text-primary) !important;
}

div[data-baseweb="popover"],
div[data-baseweb="popover"] > div,
ul[role="listbox"],
li[role="option"] {
    background-color: var(--popover-bg) !important;
    color: var(--text-primary) !important;
}
li[role="option"]:hover,
li[aria-selected="true"] {
    background-color: var(--accent-soft) !important;
    color: var(--text-primary) !important;
}

.stButton > button, div[data-testid="stFormSubmitButton"] > button {
    background-color: var(--btn-bg) !important;
    color: var(--text-primary) !important;
    border: 1.5px solid var(--card-border) !important;
    border-radius: 9px !important;
    font-weight: 700 !important;
    transition: all 0.15s ease;
}
.stButton > button p, div[data-testid="stFormSubmitButton"] > button p {
    color: var(--text-primary) !important;
}
.stButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover {
    background-color: var(--btn-hover-bg) !important;
    border-color: var(--accent-readable) !important;
    box-shadow: 0 4px 12px var(--accent-glow) !important;
}

div[data-testid="stRadio"] > div[role="radiogroup"] {
    display: flex;
    flex-wrap: nowrap;
    gap: 6px;
    background-color: var(--nav-bg) !important;
    border: 1.5px solid var(--card-border) !important;
    border-radius: 12px;
    padding: 5px;
    margin-bottom: 18px;
    backdrop-filter: blur(12px);
    overflow-x: auto;
    scrollbar-width: none;
}
div[data-testid="stRadio"] > div[role="radiogroup"]::-webkit-scrollbar {
    display: none;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label {
    background-color: transparent !important;
    border-radius: 8px !important;
    padding: 7px 15px !important;
    margin: 0 !important;
    cursor: pointer;
    border: none !important;
    white-space: nowrap;
    transition: all 0.15s ease-in-out;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child,
div[data-testid="stRadio"] > div[role="radiogroup"] > label > span:first-child,
div[data-testid="stRadio"] input[type="radio"] {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label p {
    color: var(--text-secondary) !important;
    font-weight: 700 !important;
    font-size: 0.84rem !important;
    margin: 0 !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label[data-checked="true"],
div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
    background: var(--accent) !important;
    background-color: var(--accent) !important;
    box-shadow: 0 4px 14px var(--accent-glow) !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label[data-checked="true"] p,
div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) p {
    color: var(--on-accent-text) !important;
}

div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stColumn"] div[data-testid="stVerticalBlock"] > div > div[data-testid="stVerticalBlock"]:has(.card-task-title),
div[data-testid="stColumn"] div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"]:has(.card-task-title),
div[data-testid="stForm"],
div[data-testid="stExpander"] {
    background: var(--card-bg) !important;
    background-color: var(--card-bg) !important;
    border: 1.5px solid var(--card-border) !important;
    border-radius: 14px !important;
    box-shadow: 0 8px 24px var(--shadow-color) !important;
    backdrop-filter: blur(14px) !important;
}
div[data-testid="stExpander"] summary,
div[data-testid="stExpander"] summary p,
div[data-testid="stExpander"] summary svg {
    color: var(--text-primary) !important;
    fill: var(--text-primary) !important;
    font-weight: 700 !important;
}
div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stColumn"] div[data-testid="stVerticalBlock"] > div > div[data-testid="stVerticalBlock"]:has(.card-task-title),
div[data-testid="stColumn"] div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"]:has(.card-task-title) {
    padding: 16px 18px !important;
    margin-bottom: 16px !important;
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover,
div[data-testid="stColumn"] div[data-testid="stVerticalBlock"] > div > div[data-testid="stVerticalBlock"]:has(.card-task-title):hover,
div[data-testid="stColumn"] div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"]:has(.card-task-title):hover {
    border-color: var(--accent-readable) !important;
    box-shadow: 0 10px 28px var(--accent-glow) !important;
}

div[data-testid="stDialog"] div[role="dialog"] {
    background-color: var(--popover-bg) !important;
    color: var(--text-primary) !important;
    border: 1.5px solid var(--card-border) !important;
}

.header-brand-box {
    background: var(--card-bg);
    border: 1.5px solid var(--card-border);
    border-radius: 12px;
    padding: 9px 14px;
    margin-bottom: 6px;
    backdrop-filter: blur(12px);
    display: inline-block;
}

.app-title {
    font-size: 1.55rem;
    font-weight: 800;
    color: var(--text-primary) !important;
    letter-spacing: -0.03em;
    margin: 0;
}

.app-subtitle {
    font-size: 0.80rem;
    color: var(--text-muted) !important;
    font-weight: 600;
    margin-top: 3px;
}

.accent-text {
    color: var(--accent-readable) !important;
    font-weight: 800;
}

.card-task-title {
    font-size: 1.08rem;
    font-weight: 800;
    color: var(--text-primary) !important;
    margin-top: 6px;
}

.card-task-meta {
    color: var(--text-muted) !important;
    font-size: 0.78rem;
    font-weight: 600;
    margin-top: 1px;
    margin-bottom: 10px;
}

.card-footer-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid var(--card-border);
}

.card-due-text {
    font-size: 0.76rem;
    font-weight: 600;
    color: var(--text-secondary) !important;
}

.card-note-text {
    font-size: 0.74rem;
    color: var(--text-muted) !important;
    margin-top: 6px;
}

.section-heading {
    font-weight: 800;
    font-size: 1.08rem;
    color: var(--text-primary) !important;
    background: var(--card-bg);
    border: 1.5px solid var(--card-border);
    border-radius: 10px;
    padding: 7px 12px;
    margin-bottom: 4px;
    display: inline-block;
}

.date-banner {
    background: var(--card-bg);
    border: 1.5px solid var(--accent-border);
    border-radius: 10px;
    padding: 9px 16px;
    font-size: 0.86rem;
    font-weight: 800;
    color: var(--text-primary) !important;
    text-align: center;
    margin-bottom: 14px;
    backdrop-filter: blur(10px);
    box-shadow: 0 2px 10px var(--shadow-color);
}

.shs-day-pill {
    background: var(--accent);
    color: var(--on-accent-text) !important;
    padding: 2px 10px;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 800;
    margin-left: 8px;
    display: inline-block;
}

.bell-row {
    background: var(--card-bg);
    border: 1.5px solid var(--card-border);
    border-radius: 12px;
    padding: 12px 16px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    backdrop-filter: blur(12px);
}

.bell-row-active {
    border: 2px solid var(--accent-readable) !important;
    box-shadow: 0 0 18px var(--accent-glow) !important;
    background: var(--accent-soft) !important;
}

.bell-period-badge {
    background: var(--slot-bg);
    color: var(--accent-readable) !important;
    border: 1.5px solid var(--accent-border);
    padding: 3px 9px;
    border-radius: 6px;
    font-size: 0.76rem;
    font-weight: 800;
    margin-right: 6px;
    display: inline-block;
}

.bell-live-tag {
    background: var(--accent);
    color: var(--on-accent-text) !important;
    padding: 2px 8px;
    border-radius: 5px;
    font-size: 0.70rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    margin-left: 6px;
}

.prio-high { __PRIO_HIGH_CSS__ padding: 3px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 800; }
.prio-medium { __PRIO_MED_CSS__ padding: 3px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 800; }
.prio-low { __PRIO_LOW_CSS__ padding: 3px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 800; }

.ai-day-card {
    background: var(--card-bg);
    border: 1.5px solid var(--card-border);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 14px;
    backdrop-filter: blur(14px);
}

.ai-day-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1.5px solid var(--card-border);
    padding-bottom: 8px;
    margin-bottom: 10px;
    flex-wrap: wrap;
    gap: 6px;
}

.ai-day-title {
    color: var(--accent-readable) !important;
    font-size: 0.96rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.day-time-badge {
    background: var(--accent-soft);
    border: 1.5px solid var(--accent-border);
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 0.78rem;
    font-weight: 800;
    color: var(--text-primary) !important;
}

.time-max-cap { color: var(--text-muted) !important; font-weight: 600; }

.slot-badge {
    background: var(--slot-bg);
    color: var(--accent-readable) !important;
    border: 1.5px solid var(--accent-border);
    padding: 3px 8px;
    border-radius: 6px;
    font-family: monospace;
    font-size: 0.78rem;
    font-weight: 800;
}

.slot-title-text { color: var(--text-primary) !important; font-weight: 800; }
.slot-meta-text { color: var(--text-muted) !important; font-size: 0.78rem; font-weight: 600; }
.sched-item-text { color: var(--text-primary) !important; font-size: 0.83rem; font-weight: 600; }

.undo-toast-box {
    position: relative;
    background-color: var(--card-bg);
    border: 1.5px solid var(--accent-readable);
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.recovery-card {
    background: var(--card-bg);
    border: 1.5px solid var(--card-border);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.update-card {
    background: var(--card-bg);
    border: 1.5px solid var(--accent-border);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 10px;
}

.update-ver-badge {
    background: var(--accent);
    color: var(--on-accent-text) !important;
    padding: 2px 8px;
    border-radius: 5px;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.03em;
    margin-right: 6px;
}

.update-old-badge {
    background: var(--accent-soft);
    color: var(--text-primary) !important;
    border: 1px solid var(--card-border);
    padding: 2px 8px;
    border-radius: 5px;
    font-size: 0.72rem;
    font-weight: 700;
    margin-right: 6px;
}

.tip-card {
    background: var(--accent-soft);
    border-left: 3.5px solid var(--accent-readable);
    border-radius: 6px;
    padding: 10px 12px;
    margin-bottom: 9px;
    font-size: 0.84rem;
    color: var(--text-primary) !important;
}

@media (max-width: 768px) {
    .main .block-container { padding-top: 0.5rem !important; padding-left: 0.45rem !important; padding-right: 0.45rem !important; }
    .app-title { font-size: 1.25rem !important; }
    .app-subtitle { font-size: 0.73rem !important; }
    div[data-testid="stHorizontalBlock"]:not(:has(.card-task-title)) { flex-wrap: nowrap !important; gap: 4px !important; }
    div[data-testid="stHorizontalBlock"]:not(:has(.card-task-title)) > div[data-testid="stColumn"] { min-width: 0 !important; }
    div[data-testid="stRadio"] > div[role="radiogroup"] { padding: 4px !important; gap: 4px !important; margin-bottom: 12px !important; }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label { padding: 6px 10px !important; }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label p { font-size: 0.75rem !important; }
    div[data-testid="stVerticalBlockBorderWrapper"],
    div[data-testid="stColumn"] div[data-testid="stVerticalBlock"] > div > div[data-testid="stVerticalBlock"]:has(.card-task-title),
    div[data-testid="stColumn"] div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"]:has(.card-task-title) {
        padding: 12px 13px !important;
        margin-bottom: 10px !important;
        border-radius: 12px !important;
    }
    .stButton button { padding: 4px 4px !important; font-size: 0.68rem !important; min-height: 31px !important; }
    .ai-day-card { padding: 12px !important; margin-bottom: 10px !important; }
    .day-time-badge { font-size: 0.70rem; padding: 2px 7px; }
    .date-banner { padding: 7px 10px !important; font-size: 0.75rem !important; margin-bottom: 10px !important; }
}
</style>
"""


def build_theme_css(theme_cfg: Dict[str, Any]) -> str:
    cfg = {**DEFAULT_THEME_CONFIG, **(theme_cfg or {})}
    preset_name = cfg.get("preset", "Midnight Indigo (Default Dark)")
    preset_data = THEME_PRESETS.get(preset_name, THEME_PRESETS["Midnight Indigo (Default Dark)"])

    mode = cfg.get("mode", preset_data["mode"])
    is_light = (mode == "Light")

    accent = cfg.get("accent") or preset_data["accent"]
    ar, ag, ab = _hex_to_rgb(accent)
    accent_lum = _relative_luminance(accent)

    on_accent_text = "#0f172a" if accent_lum > 0.45 else "#ffffff"

    if is_light and accent_lum > 0.35:
        accent_readable = f"rgb({max(0, int(ar * 0.48))}, {max(0, int(ag * 0.48))}, {max(0, int(ab * 0.48))})"
    elif not is_light and accent_lum < 0.15:
        accent_readable = f"rgb({min(255, int(ar + 110))}, {min(255, int(ag + 110))}, {min(255, int(ab + 110))})"
    else:
        accent_readable = accent

    accent_soft = f"rgba({ar}, {ag}, {ab}, 0.18)"
    accent_border = f"rgba({ar}, {ag}, {ab}, {0.55 if is_light else 0.45})"
    accent_glow = f"rgba({ar}, {ag}, {ab}, {0.24 if is_light else 0.32})"

    card_alpha = max(0.55, min(0.98, int(cfg.get("card_opacity", 88)) / 100.0))
    overlay_alpha = max(0.0, min(0.88, int(cfg.get("overlay_opacity", 45)) / 100.0))

    if is_light:
        text_primary = "#0f172a"
        text_secondary = "#1e293b"
        text_muted = "#475569"
        card_bg = f"rgba(238, 242, 247, {max(0.85, card_alpha):.2f})"
        popover_bg = "#eef2f7"
        card_border = "rgba(30, 41, 59, 0.24)"
        nav_bg = "rgba(226, 232, 240, 0.94)"
        input_bg = "#f8fafc"
        input_border = "rgba(30, 41, 59, 0.32)"
        btn_bg = "#e2e8f0"
        btn_hover_bg = "#cbd5e1"
        slot_bg = f"rgba({ar}, {ag}, {ab}, 0.16)"
        overlay_rgb = "214, 223, 235"
        shadow_color = "rgba(15, 23, 42, 0.10)"
        prio_high_css = "background: #ffe4e6; color: #9f1239; border: 1.5px solid #fb7185;"
        prio_med_css = "background: #fef3c7; color: #92400e; border: 1.5px solid #f59e0b;"
        prio_low_css = "background: #d1fae5; color: #065f46; border: 1.5px solid #34d399;"
    else:
        text_primary = "#f8fafc"
        text_secondary = "#cbd5e1"
        text_muted = "#94a3b8"
        card_bg = f"rgba(15, 23, 42, {card_alpha:.2f})"
        popover_bg = "#0f172a"
        card_border = "rgba(255, 255, 255, 0.10)"
        nav_bg = f"rgba(15, 23, 42, {min(0.96, card_alpha + 0.05):.2f})"
        input_bg = "rgba(15, 23, 42, 0.90)"
        input_border = "rgba(255, 255, 255, 0.16)"
        btn_bg = "rgba(30, 41, 59, 0.85)"
        btn_hover_bg = "rgba(51, 65, 85, 0.95)"
        slot_bg = f"rgba({ar}, {ag}, {ab}, 0.22)"
        overlay_rgb = "7, 10, 18"
        shadow_color = "rgba(0, 0, 0, 0.45)"
        prio_high_css = "background: rgba(244, 63, 94, 0.16); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.38);"
        prio_med_css = "background: rgba(245, 158, 11, 0.16); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.38);"
        prio_low_css = "background: rgba(16, 185, 129, 0.16); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.38);"

    bg_type = cfg.get("bg_type", "preset")
    if bg_type == "solid":
        solid_c = cfg.get("solid_bg", "#070a12")
        if is_light and _relative_luminance(solid_c) > 0.93:
            solid_c = "#dfe6ef"
        bg_rule = f"background-color: {solid_c} !important; background-image: none !important;"
    elif bg_type == "gradient":
        g1 = cfg.get("grad_1", "#0f172a")
        g2 = cfg.get("grad_2", "#312e81")
        g3 = cfg.get("grad_3", "#070a12")
        angle = cfg.get("grad_angle", "135deg")
        stops = f"{g1}, {g2}, {g3}" if cfg.get("use_grad_3") else f"{g1}, {g2}"
        if angle == "radial":
            bg_rule = f"background-image: radial-gradient(circle at top left, {stops}) !important; background-attachment: fixed !important;"
        else:
            bg_rule = f"background-image: linear-gradient({angle}, {stops}) !important; background-attachment: fixed !important;"
    elif bg_type == "photo" and str(cfg.get("photo_source", "")).strip():
        p_src = str(cfg.get("photo_source")).strip().replace('"', "%22").replace("'", "%27")
        bg_rule = (
            f'background-image: linear-gradient(rgba({overlay_rgb}, {overlay_alpha:.2f}), rgba({overlay_rgb}, {overlay_alpha:.2f})), url("{p_src}") !important;'
            "background-size: cover !important;"
            "background-position: center center !important;"
            "background-attachment: fixed !important;"
            "background-repeat: no-repeat !important;"
        )
    else:
        bg_rule = preset_data["bg_css"].replace(";", " !important;")

    replacements = {
        "__TEXT_PRIMARY__": text_primary,
        "__TEXT_SECONDARY__": text_secondary,
        "__TEXT_MUTED__": text_muted,
        "__CARD_BG__": card_bg,
        "__POPOVER_BG__": popover_bg,
        "__CARD_BORDER__": card_border,
        "__NAV_BG__": nav_bg,
        "__INPUT_BG__": input_bg,
        "__INPUT_BORDER__": input_border,
        "__BTN_BG__": btn_bg,
        "__BTN_HOVER_BG__": btn_hover_bg,
        "__ACCENT__": accent,
        "__ACCENT_READABLE__": accent_readable,
        "__ON_ACCENT_TEXT__": on_accent_text,
        "__ACCENT_SOFT__": accent_soft,
        "__ACCENT_BORDER__": accent_border,
        "__ACCENT_GLOW__": accent_glow,
        "__SLOT_BG__": slot_bg,
        "__SHADOW_COLOR__": shadow_color,
        "__BG_RULE__": bg_rule,
        "__PRIO_HIGH_CSS__": prio_high_css,
        "__PRIO_MED_CSS__": prio_med_css,
        "__PRIO_LOW_CSS__": prio_low_css,
    }
    out = CSS_TEMPLATE
    for token, val in replacements.items():
        out = out.replace(token, val)
    return out# -----------------------
# Photo Upload Encoder & App Constants
# -----------------------
def encode_uploaded_photo_to_data_uri(uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    raw_bytes = uploaded_file.getvalue()
    mime = uploaded_file.type or "image/jpeg"
    if HAS_PIL:
        try:
            img = Image.open(io.BytesIO(raw_bytes))
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            img.thumbnail((1920, 1080))
            buf = io.BytesIO()
            if img.mode == "RGBA":
                img.save(buf, format="PNG", optimize=True)
                mime = "image/png"
            else:
                img.save(buf, format="JPEG", quality=82, optimize=True)
                mime = "image/jpeg"
            raw_bytes = buf.getvalue()
        except Exception:
            pass
    b64_str = base64.b64encode(raw_bytes).decode("ascii")
    return f"data:{mime};base64,{b64_str}"


DEFAULT_DOMAIN = "@simsburyschools.net"
STATUS_OPTIONS = ["Not Started", "In Progress", "Halfway Done", "Almost Done", "Done"]
PRIORITY_OPTIONS = ["Low", "Medium", "High"]
PRIORITY_SYSTEM_MODES = ["Low / Medium / High", "1 to 10 Scale (Slider)", "Both Systems"]
TYPE_OPTIONS = ["Homework", "Project", "Test & Quizzes", "Essay", "Lab", "Other"]
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
STUDY_KEYWORDS = ("study", "studying", "review", "prep", "prepare", "practice", "flashcard", "memorize", "quizlet")

# -----------------------
# SHS Bell Schedule & Live Spreadsheet Calendar Engine
# -----------------------
SHS_ROTATIONS: Dict[str, List[int]] = {
    "A": [1, 2, 3, 5, 6, 7],
    "B": [4, 1, 2, 8, 5, 6],
    "C": [3, 4, 1, 7, 8, 5],
    "D": [2, 3, 4, 6, 7, 8],
}

SHS_DROPPED_PERIODS: Dict[str, str] = {
    "A": "Drops Period 4 & 8",
    "B": "Drops Period 3 & 7",
    "C": "Drops Period 2 & 6",
    "D": "Drops Period 1 & 5",
    "X": "All 8 Periods Meet",
}

SHS_SCHEDULE_TYPES: List[str] = [
    "Daily",
    "Connect",
    "2 Hour Delay",
    "Early Dismissal",
    "Emergency Early Dismissal",
    "X Day",
    "X Day 2 Hour Delay",
    "X Day Early Dismissal",
]

SHS_FALLBACK_HOLIDAYS: Dict[str, str] = {
    "2026-09-07": "Labor Day",
    "2026-09-21": "Yom Kippur",
    "2026-10-12": "Indigenous Peoples' Day",
    "2026-11-03": "Election Day / PD",
    "2026-11-26": "Thanksgiving Recess",
    "2026-11-27": "Thanksgiving Recess",
    "2026-12-24": "Winter Recess",
    "2026-12-25": "Winter Recess",
    "2026-12-28": "Winter Recess",
    "2026-12-29": "Winter Recess",
    "2026-12-30": "Winter Recess",
    "2026-12-31": "Winter Recess",
    "2027-01-01": "New Year's Day",
    "2027-01-18": "MLK Jr. Day",
    "2027-02-15": "Presidents' Day",
    "2027-02-16": "February Break",
    "2027-03-26": "Good Friday",
    "2027-04-12": "Spring Recess",
    "2027-04-13": "Spring Recess",
    "2027-04-14": "Spring Recess",
    "2027-04-15": "Spring Recess",
    "2027-04-16": "Spring Recess",
    "2027-05-31": "Memorial Day",
}

SHS_FALLBACK_SPECIAL_DAYS: Dict[str, Dict[str, str]] = {
    "2026-08-31": {"letter": "X", "schedule": "X Day", "note": "First Day of School"},
    "2026-11-25": {"letter": "D", "schedule": "Early Dismissal", "note": "Thanksgiving Early Dismissal"},
    "2026-12-23": {"letter": "B", "schedule": "Early Dismissal", "note": "Winter Break Early Dismissal"},
}


def _normalize_google_sheet_csv_url(raw_url: str) -> str:
    url = str(raw_url or "").strip()
    if not url:
        return ""
    if "docs.google.com/spreadsheets" in url:
        if "/pub?" in url and "output=csv" in url:
            return url
        if "/export?" in url and "format=csv" in url:
            return url
        m_id = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
        m_gid = re.search(r"[?#&]gid=(\d+)", url)
        if m_id:
            sheet_id = m_id.group(1)
            gid_part = f"&gid={m_gid.group(1)}" if m_gid else ""
            return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv{gid_part}"
    return url


def _parse_flexible_sheet_date(raw_val: str) -> Optional[date]:
    s = str(raw_val or "").strip()
    if not s:
        return None
    s_clean = re.sub(
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s*",
        "",
        s,
        flags=re.I,
    ).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(s_clean, fmt).date()
        except ValueError:
            pass
    for fmt_no_yr in ("%m/%d", "%b %d", "%B %d"):
        try:
            parsed = datetime.strptime(s_clean, fmt_no_yr)
            yr = 2026 if parsed.month >= 8 else 2027
            return date(yr, parsed.month, parsed.day)
        except ValueError:
            pass
    return None


def _extract_letter_and_sched(text_blob: str) -> Optional[Dict[str, str]]:
    raw = str(text_blob or "").strip()
    if not raw:
        return None
    up = raw.upper()

    if any(k in up for k in ("NO SCHOOL", "HOLIDAY", "RECESS", "BREAK", "SNOW DAY", "CLOSED", "PD DAY", "PROFESSIONAL DEVELOPMENT")):
        return {"letter": "NO SCHOOL", "schedule": "Daily", "note": raw}

    letter = ""
    m_exact = re.fullmatch(r"([ABCDX])(?:\s*DAY)?", up)
    if m_exact:
        letter = m_exact.group(1)
    else:
        m_word = re.search(r"\b([ABCDX])\s*DAY\b", up) or re.search(r"\bDAY\s*([ABCDX])\b", up)
        if m_word:
            letter = m_word.group(1)
        elif up in ("A", "B", "C", "D", "X"):
            letter = up

    if not letter:
        return None

    sched = "X Day" if letter == "X" else "Daily"
    if "CONNECT" in up:
        sched = "Connect"
    elif "2 HOUR" in up or "2-HOUR" in up or "TWO HOUR" in up or "DELAY" in up:
        sched = "X Day 2 Hour Delay" if letter == "X" else "2 Hour Delay"
    elif "EMERGENCY" in up:
        sched = "Emergency Early Dismissal"
    elif "EARLY" in up or "DISMISSAL" in up or "HALF DAY" in up:
        sched = "X Day Early Dismissal" if letter == "X" else "Early Dismissal"

    note_clean = re.sub(r"\b([ABCDX])\s*DAY\b", "", raw, flags=re.I).strip(" -:|•")
    if note_clean.upper() in ("A", "B", "C", "D", "X", "DAILY"):
        note_clean = ""

    return {"letter": letter, "schedule": sched, "note": note_clean}


@st.cache_data(ttl=180, show_spinner=False)
def fetch_live_shs_spreadsheet_map(sheet_url: str) -> Dict[str, Dict[str, str]]:
    """Fetches and parses live letter-day rows from a published/shared Google Spreadsheet CSV."""
    csv_url = _normalize_google_sheet_csv_url(sheet_url)
    if not csv_url:
        return {}
    try:
        req = urllib.request.Request(csv_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(content))
        mapping: Dict[str, Dict[str, str]] = {}
        for row in reader:
            cells = [c.strip() for c in row if c and c.strip()]
            if len(cells) < 2:
                continue
            found_date: Optional[date] = None
            date_idx = -1
            for idx, cell in enumerate(cells):
                d_parsed = _parse_flexible_sheet_date(cell)
                if d_parsed:
                    found_date = d_parsed
                    date_idx = idx
                    break
            if not found_date:
                continue
            other_cells = [c for i, c in enumerate(cells) if i != date_idx]
            combined_info = " | ".join(other_cells)
            parsed_day = _extract_letter_and_sched(combined_info)
            if parsed_day:
                if len(other_cells) >= 2 and not parsed_day.get("note"):
                    extra = " • ".join(other_cells[1:])
                    if extra.upper() not in ("DAILY", "A", "B", "C", "D", "X"):
                        parsed_day["note"] = extra
                parsed_day["source"] = "Live Spreadsheet"
                mapping[found_date.isoformat()] = parsed_day
        return mapping
    except Exception:
        return {}


def get_default_shs_sheet_url() -> str:
    try:
        return str(st.secrets.get("SHS_CALENDAR_URL", "")).strip()
    except Exception:
        return ""


def get_shs_day_info(target_date: date, custom_sheet_url: str = "") -> Dict[str, str]:
    """Resolves the letter day & schedule for target_date: checks live spreadsheet first, then built-in 2026-2027 SHS calendar."""
    iso_key = target_date.isoformat()
    user_saved_url = str(st.session_state.get("cfg_shs", {}).get("sheet_url", "")).strip()
    active_url = str(custom_sheet_url or "").strip() or user_saved_url or get_default_shs_sheet_url()

    if active_url:
        live_map = fetch_live_shs_spreadsheet_map(active_url)
        if iso_key in live_map:
            return live_map[iso_key]

    if target_date.weekday() >= 5:
        return {"letter": "WEEKEND", "schedule": "Daily", "note": "Weekend", "source": "Calendar"}

    if iso_key in SHS_FALLBACK_HOLIDAYS:
        return {"letter": "NO SCHOOL", "schedule": "Daily", "note": SHS_FALLBACK_HOLIDAYS[iso_key], "source": "Calendar"}

    if iso_key in SHS_FALLBACK_SPECIAL_DAYS:
        res = dict(SHS_FALLBACK_SPECIAL_DAYS[iso_key])
        res["source"] = "Calendar"
        return res

    school_start = date(2026, 9, 1)
    school_end = date(2027, 6, 18)
    if target_date < school_start or target_date > school_end:
        return {"letter": "A", "schedule": "Daily", "note": "Standard Rotation", "source": "Calendar"}

    letters = ["A", "B", "C", "D"]
    idx = 0
    curr = school_start
    while curr < target_date:
        if curr.weekday() < 5 and curr.isoformat() not in SHS_FALLBACK_HOLIDAYS:
            idx = (idx + 1) % 4
        curr += timedelta(days=1)

    sched = "Connect" if target_date.weekday() == 2 else "Daily"
    return {"letter": letters[idx], "schedule": sched, "note": "", "source": "Calendar"}


def build_shs_bell_blocks(
    letter_day: str,
    schedule_type: str,
    lunch_wave: str,
    period_classes: Dict[str, str],
    study_rooms: Optional[Dict[str, str]] = None,
) -> List[Dict[str, str]]:
    """Builds exact period-by-period bell blocks from all 8 official SHS schedules."""
    l_clean = letter_day if letter_day in ("A", "B", "C", "D") else "A"
    rot = SHS_ROTATIONS[l_clean]
    rooms_map = study_rooms or {}
    day_room_raw = str(rooms_map.get(letter_day, "")).strip()
    day_room = f"Rm {day_room_raw}" if (day_room_raw and day_room_raw[0].isdigit()) else day_room_raw

    def _cls(p_num: int) -> str:
        c_name = str(period_classes.get(str(p_num), "")).strip()
        return c_name if c_name else f"Period {p_num}"

    def _room_for(p_num: int) -> str:
        return day_room if (_cls(p_num).upper() == "STUDY HALL" and day_room) else ""

    def _lunch_split(
        p_num: int,
        l1: Tuple[str, str], c1: Tuple[str, str],
        c2a: Tuple[str, str], l2: Tuple[str, str], c2b: Tuple[str, str],
        c3: Tuple[str, str], l3: Tuple[str, str],
    ) -> List[Dict[str, str]]:
        cname = _cls(p_num)
        rm = _room_for(p_num)
        if lunch_wave == "L1":
            return [
                {"label": "Lunch Wave 1", "class_name": "Lunch (L1)", "start": l1[0], "end": l1[1], "mins": "30m", "is_lunch": "1", "ann": "0", "room": ""},
                {"label": f"Period {p_num}", "class_name": cname, "start": c1[0], "end": c1[1], "mins": "56-60m", "is_lunch": "0", "ann": "0", "room": rm},
            ]
        elif lunch_wave == "L3":
            return [
                {"label": f"Period {p_num}", "class_name": cname, "start": c3[0], "end": c3[1], "mins": "56-60m", "is_lunch": "0", "ann": "0", "room": rm},
                {"label": "Lunch Wave 3", "class_name": "Lunch (L3)", "start": l3[0], "end": l3[1], "mins": "30m", "is_lunch": "1", "ann": "0", "room": ""},
            ]
        else:
            return [
                {"label": f"Period {p_num} (Part 1)", "class_name": cname, "start": c2a[0], "end": c2a[1], "mins": "26-28m", "is_lunch": "0", "ann": "0", "room": rm},
                {"label": "Lunch Wave 2", "class_name": "Lunch (L2)", "start": l2[0], "end": l2[1], "mins": "30m", "is_lunch": "1", "ann": "0", "room": ""},
                {"label": f"Period {p_num} (Part 2)", "class_name": cname, "start": c2b[0], "end": c2b[1], "mins": "26-28m", "is_lunch": "0", "ann": "0", "room": rm},
            ]

    if schedule_type == "Connect":
        blocks = [
            {"label": f"Period {rot[0]}", "class_name": _cls(rot[0]), "start": "7:32 AM", "end": "8:23 AM", "mins": "51m", "is_lunch": "0", "ann": "0", "room": _room_for(rot[0])},
            {"label": f"Period {rot[1]}", "class_name": _cls(rot[1]), "start": "8:27 AM", "end": "9:18 AM", "mins": "51m", "is_lunch": "0", "ann": "0", "room": _room_for(rot[1])},
            {"label": "CONNECT", "class_name": "CONNECT", "start": "9:22 AM", "end": "9:53 AM", "mins": "31m", "is_lunch": "0", "ann": "1", "room": ""},
            {"label": f"Period {rot[2]}", "class_name": _cls(rot[2]), "start": "9:57 AM", "end": "10:48 AM", "mins": "51m", "is_lunch": "0", "ann": "0", "room": _room_for(rot[2])},
        ]
        blocks.extend(_lunch_split(
            rot[3],
            ("10:50 AM", "11:20 AM"), ("11:24 AM", "12:20 PM"),
            ("10:52 AM", "11:18 AM"), ("11:20 AM", "11:50 AM"), ("11:54 AM", "12:20 PM"),
            ("10:52 AM", "11:48 AM"), ("11:50 AM", "12:20 PM"),
        ))
        blocks.extend([
            {"label": f"Period {rot[4]}", "class_name": _cls(rot[4]), "start": "12:24 PM", "end": "1:15 PM", "mins": "51m", "is_lunch": "0", "ann": "0", "room": _room_for(rot[4])},
            {"label": f"Period {rot[5]}", "class_name": _cls(rot[5]), "start": "1:19 PM", "end": "2:10 PM", "mins": "51m", "is_lunch": "0", "ann": "0", "room": _room_for(rot[5])},
        ])
        return blocks

    if schedule_type == "2 Hour Delay":
        blocks = [
            {"label": f"Period {rot[0]}", "class_name": _cls(rot[0]), "start": "9:32 AM", "end": "10:06 AM", "mins": "34m", "is_lunch": "0", "ann": "0", "room": _room_for(rot[0])},
            {"label": f"Period {rot[1]}", "class_name": _cls(rot[1]), "start": "10:10 AM", "end": "10:44 AM", "mins": "34m", "is_lunch": "0", "ann": "0", "room": _room_for(rot[1])},
            {"label": f"Period {rot[2]}", "class_name": _cls(rot[2]), "start": "10:48 AM", "end": "11:24 AM", "mins": "34m", "is_lunch": "0", "ann": "1", "room": _room_for(rot[2])},
        ]
        blocks.extend(_lunch_split(
            rot[3],
            ("11:24 AM", "11:54 AM"), ("11:58 AM", "12:54 PM"),
            ("11:28 AM", "11:54 AM"), ("11:54 AM", "12:24 PM"), ("12:28 PM", "12:54 PM"),
            ("11:28 AM", "12:24 PM"), ("12:24 PM", "12:54 PM"),
        ))
        blocks.extend([
            {"label": f"Period {rot[4]}", "class_name": _cls(rot[4]), "start": "12:58 PM", "end": "1:32 PM", "mins": "34m", "is_lunch": "0", "ann": "0", "room": _room_for(rot[4])},
            {"label": f"Period {rot[5]}", "class_name": _cls(rot[5]), "start": "1:36 PM", "end": "2:10 PM", "mins": "34m", "is_lunch": "0", "ann": "0", "room": _room_for(rot[5])},
        ])
        return blocks

    if schedule_type == "Early Dismissal":
        times_ed = [("7:32 AM", "8:05 AM", "33m"), ("8:09 AM", "8:42 AM", "33m"), ("8:46 AM", "9:24 AM", "38m"),
                    ("9:28 AM", "10:01 AM", "33m"), ("10:05 AM", "10:38 AM", "33m"), ("10:42 AM", "11:15 AM", "33m")]
        return [
            {"label": f"Period {rot[idx]}", "class_name": _cls(rot[idx]), "start": t[0], "end": t[1], "mins": t[2], "is_lunch": "0", "ann": "1" if idx == 2 else "0", "room": _room_for(rot[idx])}
            for idx, t in enumerate(times_ed)
        ]

    if schedule_type == "Emergency Early Dismissal":
        times_eed = [("7:32 AM", "8:25 AM", "53m"), ("8:29 AM", "8:57 AM", "28m"), ("9:01 AM", "9:29 AM", "28m"),
                     ("9:33 AM", "10:01 AM", "28m"), ("10:05 AM", "10:33 AM", "28m"), ("10:37 AM", "11:05 AM", "28m")]
        blocks = [
            {"label": f"Period {rot[idx]}", "class_name": _cls(rot[idx]), "start": t[0], "end": t[1], "mins": t[2], "is_lunch": "0", "ann": "1" if idx == 1 else "0", "room": _room_for(rot[idx])}
            for idx, t in enumerate(times_eed)
        ]
        blocks.append({"label": "Express Lunch", "class_name": "Express Lunch Pick Up", "start": "11:05 AM", "end": "11:15 AM", "mins": "10m", "is_lunch": "1", "ann": "0", "room": ""})
        return blocks

    if schedule_type == "X Day":
        blocks = [
            {"label": "Period 1", "class_name": _cls(1), "start": "7:32 AM", "end": "8:12 AM", "mins": "40m", "is_lunch": "0", "ann": "0", "room": _room_for(1)},
            {"label": "Period 2", "class_name": _cls(2), "start": "8:16 AM", "end": "8:56 AM", "mins": "40m", "is_lunch": "0", "ann": "0", "room": _room_for(2)},
            {"label": "Period 3", "class_name": _cls(3), "start": "9:00 AM", "end": "9:42 AM", "mins": "42m", "is_lunch": "0", "ann": "1", "room": _room_for(3)},
            {"label": "Period 4", "class_name": _cls(4), "start": "9:46 AM", "end": "10:26 AM", "mins": "40m", "is_lunch": "0", "ann": "0", "room": _room_for(4)},
            {"label": "Period 5", "class_name": _cls(5), "start": "10:30 AM", "end": "11:10 AM", "mins": "40m", "is_lunch": "0", "ann": "0", "room": _room_for(5)},
        ]
        blocks.extend(_lunch_split(
            6,
            ("11:12 AM", "11:42 AM"), ("11:46 AM", "12:42 PM"),
            ("11:14 AM", "11:40 AM"), ("11:42 AM", "12:12 PM"), ("12:16 PM", "12:42 PM"),
            ("11:14 AM", "12:10 PM"), ("12:12 PM", "12:42 PM"),
        ))
        blocks.extend([
            {"label": "Period 7", "class_name": _cls(7), "start": "12:46 PM", "end": "1:26 PM", "mins": "40m", "is_lunch": "0", "ann": "0", "room": _room_for(7)},
            {"label": "Period 8", "class_name": _cls(8), "start": "1:30 PM", "end": "2:10 PM", "mins": "40m", "is_lunch": "0", "ann": "0", "room": _room_for(8)},
        ])
        return blocks

    if schedule_type == "X Day 2 Hour Delay":
        blocks = [
            {"label": "Period 1", "class_name": _cls(1), "start": "9:32 AM", "end": "9:55 AM", "mins": "23m", "is_lunch": "0", "ann": "0", "room": _room_for(1)},
            {"label": "Period 2", "class_name": _cls(2), "start": "9:59 AM", "end": "10:22 AM", "mins": "23m", "is_lunch": "0", "ann": "0", "room": _room_for(2)},
            {"label": "Period 3", "class_name": _cls(3), "start": "10:26 AM", "end": "10:50 AM", "mins": "24m", "is_lunch": "0", "ann": "1", "room": _room_for(3)},
            {"label": "Period 4", "class_name": _cls(4), "start": "10:54 AM", "end": "11:17 AM", "mins": "23m", "is_lunch": "0", "ann": "0", "room": _room_for(4)},
            {"label": "Period 5", "class_name": _cls(5), "start": "11:21 AM", "end": "11:44 AM", "mins": "23m", "is_lunch": "0", "ann": "0", "room": _room_for(5)},
        ]
        blocks.extend(_lunch_split(
            6,
            ("11:46 AM", "12:16 PM"), ("12:20 PM", "1:16 PM"),
            ("11:48 AM", "12:14 PM"), ("12:16 PM", "12:46 PM"), ("12:50 PM", "1:16 PM"),
            ("11:48 AM", "12:44 PM"), ("12:46 PM", "1:16 PM"),
        ))
        blocks.extend([
            {"label": "Period 7", "class_name": _cls(7), "start": "1:20 PM", "end": "1:43 PM", "mins": "23m", "is_lunch": "0", "ann": "0", "room": _room_for(7)},
            {"label": "Period 8", "class_name": _cls(8), "start": "1:47 PM", "end": "2:10 PM", "mins": "23m", "is_lunch": "0", "ann": "0", "room": _room_for(8)},
        ])
        return blocks

    if schedule_type == "X Day Early Dismissal":
        times_xed = [("7:32 AM", "7:56 AM", "24m"), ("8:00 AM", "8:24 AM", "24m"), ("8:28 AM", "8:55 AM", "27m"),
                     ("8:59 AM", "9:23 AM", "24m"), ("9:27 AM", "9:51 AM", "24m"), ("9:55 AM", "10:19 AM", "24m"),
                     ("10:23 AM", "10:47 AM", "24m"), ("10:51 AM", "11:15 AM", "24m")]
        return [
            {"label": f"Period {idx + 1}", "class_name": _cls(idx + 1), "start": t[0], "end": t[1], "mins": t[2], "is_lunch": "0", "ann": "1" if idx == 2 else "0", "room": _room_for(idx + 1)}
            for idx, t in enumerate(times_xed)
        ]

    # Default: Daily Schedule
    blocks = [
        {"label": f"Period {rot[0]}", "class_name": _cls(rot[0]), "start": "7:32 AM", "end": "8:29 AM", "mins": "57m", "is_lunch": "0", "ann": "0", "room": _room_for(rot[0])},
        {"label": f"Period {rot[1]}", "class_name": _cls(rot[1]), "start": "8:33 AM", "end": "9:31 AM", "mins": "58m", "is_lunch": "0", "ann": "1", "room": _room_for(rot[1])},
        {"label": f"Period {rot[2]}", "class_name": _cls(rot[2]), "start": "9:35 AM", "end": "10:32 AM", "mins": "57m", "is_lunch": "0", "ann": "0", "room": _room_for(rot[2])},
    ]
    blocks.extend(_lunch_split(
        rot[3],
        ("10:34 AM", "11:04 AM"), ("11:08 AM", "12:08 PM"),
        ("10:36 AM", "11:04 AM"), ("11:06 AM", "11:36 AM"), ("11:40 AM", "12:08 PM"),
        ("10:36 AM", "11:36 AM"), ("11:38 AM", "12:08 PM"),
    ))
    blocks.extend([
        {"label": f"Period {rot[4]}", "class_name": _cls(rot[4]), "start": "12:12 PM", "end": "1:09 PM", "mins": "57m", "is_lunch": "0", "ann": "0", "room": _room_for(rot[4])},
        {"label": f"Period {rot[5]}", "class_name": _cls(rot[5]), "start": "1:13 PM", "end": "2:10 PM", "mins": "57m", "is_lunch": "0", "ann": "0", "room": _room_for(rot[5])},
    ])
    return blocks# -----------------------
# Database Engine & Thread-Safe Background Worker
# -----------------------
def _get_database_url() -> str:
    url = ""
    try:
        url = str(st.secrets.get("DATABASE_URL", "")).strip()
    except Exception:
        pass
    if not url:
        url = str(os.environ.get("DATABASE_URL", "")).strip()
    if not url:
        return "sqlite:///assignments_local.db"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


@st.cache_resource
def get_db_engine():
    db_url = _get_database_url()
    if db_url.startswith("sqlite"):
        eng = create_engine(db_url, connect_args={"check_same_thread": False}, future=True)
    else:
        eng = create_engine(db_url, pool_pre_ping=True, pool_size=5, max_overflow=10, future=True)
    with eng.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS assignments (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                course TEXT,
                due_date TEXT,
                status TEXT,
                priority INTEGER,
                atype TEXT,
                eta TEXT,
                created_at TEXT,
                notes TEXT,
                prev_status TEXT
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                email TEXT NOT NULL,
                category TEXT NOT NULL,
                rating INTEGER,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """))
    return eng


engine = get_db_engine()
_DB_WRITE_LOCK = threading.Lock()


def _run_bg_db_task(fn: Callable[[], None]) -> None:
    def _worker():
        with _DB_WRITE_LOCK:
            try:
                fn()
            except Exception as e:
                print(f"[DB Background Write Error] {e}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def save_user_feedback(user_id: str, email: str, category: str, rating: int, message: str) -> None:
    fid = str(uuid.uuid4())
    now_iso = get_local_now().isoformat()

    def _db_op():
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO feedback (id, user_id, email, category, rating, message, created_at)
                    VALUES (:id, :user_id, :email, :category, :rating, :message, :created_at)
                """),
                {
                    "id": fid,
                    "user_id": user_id,
                    "email": email,
                    "category": category,
                    "rating": int(rating),
                    "message": message.strip(),
                    "created_at": now_iso,
                },
            )

    _run_bg_db_task(_db_op)


# -----------------------
# UI Badges, Priority & Duration Helpers
# -----------------------
def get_course_badge_html(course_name: str, is_light: bool = False) -> str:
    c = str(course_name or "GENERAL").strip().upper()
    if is_light:
        if any(k in c for k in ["MATH", "CALC", "STAT", "ALG", "GEO"]):
            bg, fg, border = "#e0e7ff", "#312e81", "#6366f1"
        elif any(k in c for k in ["SCI", "BIO", "CHEM", "PHYS", "ENV"]):
            bg, fg, border = "#d1fae5", "#064e3b", "#10b981"
        elif any(k in c for k in ["ENG", "LIT", "WRIT", "READ"]):
            bg, fg, border = "#ffe4e6", "#881337", "#f43f5e"
        elif any(k in c for k in ["HIST", "CIV", "GOV", "SOC", "APUSH"]):
            bg, fg, border = "#fef3c7", "#78350f", "#f59e0b"
        elif any(k in c for k in ["SPAN", "FRENCH", "LANG", "LATIN"]):
            bg, fg, border = "#f3e8ff", "#581c87", "#a855f7"
        elif c in ("OTHER", "STUDY HALL", "FREE / UNASSIGNED", "CONNECT") or c.startswith("PERIOD "):
            bg, fg, border = "#e2e8f0", "#1e293b", "#64748b"
        else:
            bg, fg, border = "#e0f2fe", "#0c4a6e", "#0284c7"
    else:
        if any(k in c for k in ["MATH", "CALC", "STAT", "ALG", "GEO"]):
            bg, fg, border = "#1e1b4b", "#a5b4fc", "#4338ca"
        elif any(k in c for k in ["SCI", "BIO", "CHEM", "PHYS", "ENV"]):
            bg, fg, border = "#064e3b", "#6ee7b7", "#059669"
        elif any(k in c for k in ["ENG", "LIT", "WRIT", "READ"]):
            bg, fg, border = "#881337", "#fda4af", "#e11d48"
        elif any(k in c for k in ["HIST", "CIV", "GOV", "SOC", "APUSH"]):
            bg, fg, border = "#78350f", "#fcd34d", "#d97706"
        elif any(k in c for k in ["SPAN", "FRENCH", "LANG", "LATIN"]):
            bg, fg, border = "#581c87", "#e9d5ff", "#9333ea"
        elif c in ("OTHER", "STUDY HALL", "FREE / UNASSIGNED", "CONNECT") or c.startswith("PERIOD "):
            bg, fg, border = "#1e293b", "#e2e8f0", "#475569"
        else:
            bg, fg, border = "#0c4a6e", "#7dd3fc", "#0284c7"

    return (
        f"<span style='background-color:{bg}; color:{fg} !important; border:1.5px solid {border}; "
        f"padding:3px 9px; border-radius:6px; font-weight:800; font-size:0.73rem; letter-spacing:0.03em; display:inline-block;'>{c}</span>"
    )


def priority_to_int(val: Any) -> int:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 5
    if isinstance(val, (int, float)):
        return max(1, min(10, int(val)))
    s = str(val).strip().lower()
    if s.isdigit():
        return max(1, min(10, int(s)))
    if s == "high":
        return 8
    if s == "low":
        return 2
    return 5


def priority_to_label(val: Any) -> str:
    n = priority_to_int(val)
    if n >= 7:
        return "High"
    if n <= 3:
        return "Low"
    return "Medium"


def format_priority_display(val: Any, mode: str) -> str:
    n = priority_to_int(val)
    lbl = priority_to_label(n)
    if mode == "1 to 10 Scale (Slider)":
        return f"{n}/10"
    if mode == "Both Systems":
        return f"{lbl} ({n}/10)"
    return lbl


def parse_eta_to_mins(eta_str: str) -> int:
    if not eta_str or pd.isna(eta_str):
        return 30
    s = str(eta_str).lower().strip()
    s = re.sub(r"(/day|per day|daily|a day)", "", s).strip()
    total = 0
    hr_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)", s)
    min_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)", s)
    if hr_m:
        total += int(float(hr_m.group(1)) * 60)
    if min_m:
        total += int(float(min_m.group(1)))
    if not hr_m and not min_m:
        num_m = re.search(r"(\d+(?:\.\d+)?)", s)
        if num_m:
            v = float(num_m.group(1))
            total = int(v * 60) if v <= 5 else int(v)
    return max(10, total) if total > 0 else 30


def format_mins_to_hrs_mins(mins: int) -> str:
    m = max(0, int(mins))
    if m == 0:
        return "0m"
    h, rem = divmod(m, 60)
    if h > 0 and rem > 0:
        return f"{h}h {rem}m"
    if h > 0:
        return f"{h}h"
    return f"{rem}m"


def is_study_task(atype: str, title: str, notes: str = "") -> bool:
    if str(atype or "").strip() == "Test & Quizzes":
        return True
    blob = f"{title} {notes}".lower()
    return any(k in blob for k in STUDY_KEYWORDS)


def is_daily_recurring_task(eta_str: str, title: str = "", notes: str = "") -> bool:
    blob = f"{eta_str} {title} {notes}".lower()
    return any(k in blob for k in ("/day", "per day", "daily", "each day", "every day"))


def format_study_display_title(title: str) -> str:
    t = str(title or "").strip()
    if t.lower().startswith("study"):
        return t
    return f"Study: {t}"


# -----------------------
# Session Hydration, Cache Getters & Config Writers
# -----------------------
ASSIGNMENT_COLS = [
    "id", "user_id", "title", "course", "due_date", "status",
    "priority", "atype", "eta", "created_at", "notes", "prev_status",
]

SYSTEM_TITLES = {
    "__SYSTEM_COURSES_CONFIG__",
    "__SYSTEM_SCHEDULE_CONFIG__",
    "__SYSTEM_PRIO_CONFIG__",
    "__SYSTEM_MAX_WORK_CONFIG__",
    "__SYSTEM_COMPLETED_SLOTS__",
    "__SYSTEM_SEEN_UPDATES__",
    "__SYSTEM_THEME_CONFIG__",
    "__SYSTEM_SHS_CONFIG__",
}


def clear_all_session_caches() -> None:
    for k in [
        "hydrated_uid", "df_cached", "cfg_courses", "cfg_schedule",
        "cfg_prio", "cfg_max_work", "cfg_completed_slots",
        "cfg_seen_updates", "cfg_theme", "cfg_shs", "_ai_plan_result",
    ]:
        st.session_state.pop(k, None)


def hydrate_user_session(user_id: str, force: bool = False) -> None:
    if not user_id:
        return
    if not force and st.session_state.get("hydrated_uid") == user_id and "df_cached" in st.session_state:
        return

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM assignments WHERE user_id = :uid"),
            {"uid": user_id},
        ).mappings().all()

    courses_list: List[str] = []
    schedule_list: List[Dict[str, Any]] = []
    prio_mode: str = ""
    max_work_dict: Dict[str, int] = {d: 60 for d in DAYS_OF_WEEK}
    completed_slots: Dict[str, Any] = {}
    seen_updates: str = ""
    theme_cfg: Dict[str, Any] = dict(DEFAULT_THEME_CONFIG)
    shs_cfg: Dict[str, Any] = {
        "lunches": {"A": "L2", "B": "L2", "C": "L2", "D": "L2", "X": "L2"},
        "periods": {str(i): "" for i in range(1, 9)},
        "study_rooms": {"A": "", "B": "", "C": "", "D": "", "X": ""},
        "sheet_url": "",
    }

    today_iso = get_local_now().date().isoformat()
    task_records: List[Dict[str, Any]] = []
    expired_done_ids: List[str] = []

    for r in rows:
        r_dict = dict(r)
        r_title = str(r_dict.get("title") or "")
        r_notes = str(r_dict.get("notes") or "")

        if r_title == "__SYSTEM_COURSES_CONFIG__":
            try:
                parsed = json.loads(r_notes or "[]")
                if isinstance(parsed, list):
                    courses_list = [str(x).strip().upper() for x in parsed if str(x).strip()]
            except Exception:
                pass
        elif r_title == "__SYSTEM_SCHEDULE_CONFIG__":
            try:
                parsed = json.loads(r_notes or "[]")
                if isinstance(parsed, list):
                    schedule_list = parsed
            except Exception:
                pass
        elif r_title == "__SYSTEM_PRIO_CONFIG__":
            prio_mode = r_notes.strip()
        elif r_title == "__SYSTEM_MAX_WORK_CONFIG__":
            try:
                parsed = json.loads(r_notes or "{}")
                if isinstance(parsed, dict):
                    for d in DAYS_OF_WEEK:
                        if d in parsed:
                            max_work_dict[d] = int(parsed[d])
            except Exception:
                pass
        elif r_title == "__SYSTEM_COMPLETED_SLOTS__":
            try:
                parsed = json.loads(r_notes or "{}")
                if isinstance(parsed, dict):
                    completed_slots = {
                        k: v for k, v in parsed.items()
                        if isinstance(v, dict) and v.get("day_date_str") == today_iso
                    }
            except Exception:
                pass
        elif r_title == "__SYSTEM_SEEN_UPDATES__":
            seen_updates = r_notes.strip()
        elif r_title == "__SYSTEM_THEME_CONFIG__":
            try:
                parsed = json.loads(r_notes or "{}")
                if isinstance(parsed, dict):
                    theme_cfg.update(parsed)
            except Exception:
                pass
        elif r_title == "__SYSTEM_SHS_CONFIG__":
            try:
                parsed = json.loads(r_notes or "{}")
                if isinstance(parsed, dict):
                    if "lunch" in parsed and "lunches" not in parsed:
                        old_l = parsed["lunch"] if parsed["lunch"] in ("L1", "L2", "L3") else "L2"
                        shs_cfg["lunches"] = {k: old_l for k in ("A", "B", "C", "D", "X")}
                    shs_cfg.update(parsed)
            except Exception:
                pass
        elif r_title not in SYSTEM_TITLES:
            due_s = str(r_dict.get("due_date") or "").strip()
            if r_dict.get("status") == "Done" and due_s and due_s < today_iso:
                expired_done_ids.append(str(r_dict["id"]))
            else:
                task_records.append(r_dict)

    if expired_done_ids:
        def _cleanup_expired():
            with engine.begin() as conn:
                for eid in expired_done_ids:
                    conn.execute(text("DELETE FROM assignments WHERE id = :id"), {"id": eid})
        _run_bg_db_task(_cleanup_expired)

    df_tasks = pd.DataFrame(task_records, columns=ASSIGNMENT_COLS) if task_records else pd.DataFrame(columns=ASSIGNMENT_COLS)
    st.session_state["df_cached"] = df_tasks
    st.session_state["cfg_courses"] = courses_list
    st.session_state["cfg_schedule"] = schedule_list
    st.session_state["cfg_prio"] = prio_mode
    st.session_state["cfg_max_work"] = max_work_dict
    st.session_state["cfg_completed_slots"] = completed_slots
    st.session_state["cfg_seen_updates"] = seen_updates
    st.session_state["cfg_theme"] = theme_cfg
    st.session_state["cfg_shs"] = shs_cfg
    st.session_state["hydrated_uid"] = user_id


def _upsert_system_config(user_id: str, sys_title: str, notes_payload: str) -> None:
    sys_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{user_id}:{sys_title}"))
    now_iso = get_local_now().isoformat()

    def _db_op():
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO assignments (id, user_id, title, course, due_date, status, priority, atype, eta, created_at, notes, prev_status)
                    VALUES (:id, :user_id, :title, 'SYSTEM', '', 'Done', 1, 'System', '', :created_at, :notes, 'Done')
                    ON CONFLICT (id) DO UPDATE SET
                        notes = EXCLUDED.notes,
                        created_at = EXCLUDED.created_at
                """),
                {"id": sys_id, "user_id": user_id, "title": sys_title, "created_at": now_iso, "notes": notes_payload},
            )

    _run_bg_db_task(_db_op)


def get_assignments_cached(user_id: str) -> pd.DataFrame:
    hydrate_user_session(user_id)
    return st.session_state.get("df_cached", pd.DataFrame(columns=ASSIGNMENT_COLS))


def get_courses_cached(user_id: str) -> List[str]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_courses", [])


def _write_courses_file(user_id: str, courses: List[str]) -> None:
    clean = [str(c).strip().upper() for c in courses if str(c).strip()]
    st.session_state["cfg_courses"] = clean
    _upsert_system_config(user_id, "__SYSTEM_COURSES_CONFIG__", json.dumps(clean))


def get_schedule_cached(user_id: str) -> List[Dict[str, Any]]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_schedule", [])


def _write_schedule_file(user_id: str, schedule: List[Dict[str, Any]]) -> None:
    st.session_state["cfg_schedule"] = schedule
    st.session_state.pop("_ai_plan_result", None)
    _upsert_system_config(user_id, "__SYSTEM_SCHEDULE_CONFIG__", json.dumps(schedule))


def get_prio_cached(user_id: str) -> str:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_prio", "")


def _write_prio_config(user_id: str, prio_mode: str) -> None:
    st.session_state["cfg_prio"] = prio_mode
    _upsert_system_config(user_id, "__SYSTEM_PRIO_CONFIG__", prio_mode)


def get_max_work_cached(user_id: str) -> Dict[str, int]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_max_work", {d: 60 for d in DAYS_OF_WEEK})


def _write_max_work_config(user_id: str, max_work: Dict[str, int]) -> None:
    st.session_state["cfg_max_work"] = max_work
    st.session_state.pop("_ai_plan_result", None)
    _upsert_system_config(user_id, "__SYSTEM_MAX_WORK_CONFIG__", json.dumps(max_work))


def get_completed_slots_cached(user_id: str) -> Dict[str, Any]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_completed_slots", {})


def _write_completed_slots(user_id: str, slots_dict: Dict[str, Any]) -> None:
    st.session_state["cfg_completed_slots"] = slots_dict
    _upsert_system_config(user_id, "__SYSTEM_COMPLETED_SLOTS__", json.dumps(slots_dict))


def get_seen_updates_cached(user_id: str) -> str:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_seen_updates", "")


def _write_seen_updates(user_id: str, ver: str) -> None:
    st.session_state["cfg_seen_updates"] = ver
    _upsert_system_config(user_id, "__SYSTEM_SEEN_UPDATES__", ver)


def get_theme_cached(user_id: str) -> Dict[str, Any]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_theme", dict(DEFAULT_THEME_CONFIG))


def _write_theme_config(user_id: str, theme_cfg: Dict[str, Any]) -> None:
    st.session_state["cfg_theme"] = theme_cfg
    _upsert_system_config(user_id, "__SYSTEM_THEME_CONFIG__", json.dumps(theme_cfg))


def get_shs_cached(user_id: str) -> Dict[str, Any]:
    hydrate_user_session(user_id)
    default_lunches = {"A": "L2", "B": "L2", "C": "L2", "D": "L2", "X": "L2"}
    default_rooms = {"A": "", "B": "", "C": "", "D": "", "X": ""}
    cfg = st.session_state.get(
        "cfg_shs",
        {
            "lunches": dict(default_lunches),
            "periods": {str(i): "" for i in range(1, 9)},
            "study_rooms": dict(default_rooms),
            "sheet_url": "",
        },
    )
    if "lunches" not in cfg:
        old_l = cfg.get("lunch", "L2")
        cfg["lunches"] = {k: old_l for k in ("A", "B", "C", "D", "X")}
    if "study_rooms" not in cfg:
        cfg["study_rooms"] = dict(default_rooms)
    if "sheet_url" not in cfg:
        cfg["sheet_url"] = ""
    return cfg


def _write_shs_config(user_id: str, shs_cfg: Dict[str, Any]) -> None:
    st.session_state["cfg_shs"] = shs_cfg
    _upsert_system_config(user_id, "__SYSTEM_SHS_CONFIG__", json.dumps(shs_cfg))


def upsert_assignments(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    df = st.session_state.get("df_cached", pd.DataFrame(columns=ASSIGNMENT_COLS)).copy()
    for r in rows:
        clean_r = {col: r.get(col, "") for col in ASSIGNMENT_COLS}
        clean_r["priority"] = priority_to_int(clean_r.get("priority"))
        aid = clean_r["id"]
        if not df.empty and (df["id"] == aid).any():
            for col in ASSIGNMENT_COLS:
                df.loc[df["id"] == aid, col] = clean_r[col]
        else:
            df = pd.concat([df, pd.DataFrame([clean_r])], ignore_index=True)

    st.session_state["df_cached"] = df
    st.session_state.pop("_ai_plan_result", None)

    rows_copy = [dict(r) for r in rows]

    def _db_op():
        with engine.begin() as conn:
            for r in rows_copy:
                conn.execute(
                    text("""
                        INSERT INTO assignments (id, user_id, title, course, due_date, status, priority, atype, eta, created_at, notes, prev_status)
                        VALUES (:id, :user_id, :title, :course, :due_date, :status, :priority, :atype, :eta, :created_at, :notes, :prev_status)
                        ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title,
                            course = EXCLUDED.course,
                            due_date = EXCLUDED.due_date,
                            status = EXCLUDED.status,
                            priority = EXCLUDED.priority,
                            atype = EXCLUDED.atype,
                            eta = EXCLUDED.eta,
                            notes = EXCLUDED.notes,
                            prev_status = EXCLUDED.prev_status
                    """),
                    {
                        "id": r.get("id"),
                        "user_id": r.get("user_id"),
                        "title": r.get("title", "Untitled"),
                        "course": r.get("course", "GENERAL"),
                        "due_date": str(r.get("due_date") or ""),
                        "status": r.get("status", "Not Started"),
                        "priority": priority_to_int(r.get("priority")),
                        "atype": r.get("atype", "Homework"),
                        "eta": str(r.get("eta") or ""),
                        "created_at": str(r.get("created_at") or get_local_now().isoformat()),
                        "notes": str(r.get("notes") or ""),
                        "prev_status": str(r.get("prev_status") or "Not Started"),
                    },
                )

    _run_bg_db_task(_db_op)


def delete_assignment(aid: str) -> None:
    df = st.session_state.get("df_cached", pd.DataFrame(columns=ASSIGNMENT_COLS))
    if not df.empty:
        st.session_state["df_cached"] = df[df["id"] != aid].reset_index(drop=True)
    st.session_state.pop("_ai_plan_result", None)

    def _db_op():
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM assignments WHERE id = :id"), {"id": aid})

    _run_bg_db_task(_db_op)


def restore_single_assignment(row_dict: Dict[str, Any]) -> None:
    updated = dict(row_dict)
    prev_st = str(updated.get("prev_status") or "Not Started").strip()
    updated["status"] = "Not Started" if (not prev_st or prev_st == "Done") else prev_st
    upsert_assignments([updated])@dialog_decorator("Preferences & Priority System")
def open_settings_dialog(user_id: str) -> None:
    cur_prio = get_prio_cached(user_id) or "Low / Medium / High"
    with st.form("settings_modal_form"):
        selected_mode = st.selectbox(
            "Priority Rating Style",
            options=PRIORITY_SYSTEM_MODES,
            index=PRIORITY_SYSTEM_MODES.index(cur_prio) if cur_prio in PRIORITY_SYSTEM_MODES else 0,
        )
        st.caption("Choose between classic Low / Medium / High badges, a 1–10 numerical slider, or both combined.")
        if st.form_submit_button("Save Preferences", use_container_width=True):
            _write_prio_config(user_id, selected_mode)
            st.rerun()


@dialog_decorator("Theme & Appearance Studio")
def open_theme_studio_dialog(user_id: str) -> None:
    cur_theme = dict(get_theme_cached(user_id))
    preset_names = list(THEME_PRESETS.keys())
    cur_preset = cur_theme.get("preset", preset_names[0])
    if cur_preset not in preset_names:
        cur_preset = preset_names[0]

    sel_preset = st.selectbox("Quick Theme Preset", options=preset_names, index=preset_names.index(cur_preset))
    preset_defaults = THEME_PRESETS[sel_preset]

    c_m1, c_m2 = st.columns(2)
    with c_m1:
        mode_opts = ["Dark", "Light"]
        cur_mode = cur_theme.get("mode", preset_defaults["mode"]) if sel_preset == cur_preset else preset_defaults["mode"]
        sel_mode = st.selectbox("Base Text Contrast Mode", options=mode_opts, index=mode_opts.index(cur_mode))
    with c_m2:
        default_acc = cur_theme.get("accent", preset_defaults["accent"]) if sel_preset == cur_preset else preset_defaults["accent"]
        sel_accent = st.color_picker("Accent Color", value=default_acc)

    bg_modes = ["preset", "solid", "gradient", "photo"]
    bg_labels = {
        "preset": "Preset Theme Background",
        "solid": "Solid Custom Color",
        "gradient": "Custom Multi-Color Gradient",
        "photo": "Custom Wallpaper Photo (Upload or URL)",
    }
    cur_bg_type = cur_theme.get("bg_type", "preset")
    sel_bg_type = st.selectbox(
        "Background Style",
        options=bg_modes,
        format_func=lambda x: bg_labels[x],
        index=bg_modes.index(cur_bg_type) if cur_bg_type in bg_modes else 0,
    )

    solid_bg = cur_theme.get("solid_bg", preset_defaults["solid_bg"])
    grad_1 = cur_theme.get("grad_1", preset_defaults["grad_1"])
    grad_2 = cur_theme.get("grad_2", preset_defaults["grad_2"])
    grad_3 = cur_theme.get("grad_3", preset_defaults["grad_3"])
    use_grad_3 = bool(cur_theme.get("use_grad_3", False))
    grad_angle = cur_theme.get("grad_angle", "135deg")
    photo_source = cur_theme.get("photo_source", "")
    overlay_opacity = int(cur_theme.get("overlay_opacity", 45))

    if sel_bg_type == "solid":
        solid_bg = st.color_picker("Solid Background Color", value=solid_bg)
    elif sel_bg_type == "gradient":
        gc1, gc2, gc3 = st.columns(3)
        with gc1:
            grad_1 = st.color_picker("Gradient Start", value=grad_1)
        with gc2:
            grad_2 = st.color_picker("Gradient End", value=grad_2)
        with gc3:
            grad_3 = st.color_picker("3rd Stop (Optional)", value=grad_3)
        use_grad_3 = st.checkbox("Enable 3-Color Gradient", value=use_grad_3)
        grad_angle = st.selectbox(
            "Gradient Direction",
            options=["135deg", "90deg", "180deg", "45deg", "radial"],
            index=["135deg", "90deg", "180deg", "45deg", "radial"].index(grad_angle)
            if grad_angle in ["135deg", "90deg", "180deg", "45deg", "radial"] else 0,
        )
    elif sel_bg_type == "photo":
        uploaded_img = st.file_uploader("Upload Wallpaper Image (PNG/JPG)", type=["png", "jpg", "jpeg", "webp"])
        url_img = st.text_input(
            "Or Paste Image URL",
            value="" if str(photo_source).startswith("data:") else str(photo_source),
            placeholder="https://...",
        )
        if uploaded_img is not None:
            photo_source = encode_uploaded_photo_to_data_uri(uploaded_img)
        elif url_img.strip():
            photo_source = url_img.strip()
        overlay_opacity = st.slider("Background Readability Tint (%)", min_value=0, max_value=85, value=overlay_opacity)

    card_opacity = st.slider(
        "Card Glass Opacity (%)",
        min_value=60,
        max_value=98,
        value=int(cur_theme.get("card_opacity", 88)),
    )

    c_save, c_reset = st.columns(2)
    with c_save:
        if st.button("Apply & Save Theme", use_container_width=True):
            new_cfg = {
                "preset": sel_preset,
                "mode": sel_mode,
                "accent": sel_accent,
                "bg_type": sel_bg_type,
                "solid_bg": solid_bg,
                "grad_1": grad_1,
                "grad_2": grad_2,
                "grad_3": grad_3,
                "use_grad_3": use_grad_3,
                "grad_angle": grad_angle,
                "photo_source": photo_source,
                "overlay_opacity": overlay_opacity,
                "card_opacity": card_opacity,
            }
            _write_theme_config(user_id, new_cfg)
            st.rerun()
    with c_reset:
        if st.button("Reset to Default Dark", use_container_width=True):
            _write_theme_config(user_id, dict(DEFAULT_THEME_CONFIG))
            st.rerun()


@dialog_decorator("What's New, Tips & Feedback")
def open_feedback_updates_dialog(user_id: str, user_email: str) -> None:
    _write_seen_updates(user_id, CURRENT_APP_VERSION)
    tab_upd, tab_tips, tab_fb = st.tabs(["What's New", "Study Tips", "Send Feedback"])

    with tab_upd:
        st.markdown(
            f"<div class='update-card'><span class='update-ver-badge'>v{CURRENT_APP_VERSION} NEW</span>"
            "<b>Live SHS Spreadsheet Sync, Per-Day Lunch Waves & Study Hall Rooms</b>"
            "<div class='card-note-text'>• Letter days automatically sync from your live Google Spreadsheet.<br>"
            "• Set separate Lunch Waves (L1, L2, L3) and Study Hall rooms for A, B, C, D, and X Days.<br>"
            "• Unified class pill badges and automatic 1-minute live period tracking.</div></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='update-card'><span class='update-old-badge'>v3.2</span>"
            "<b>Theme & Appearance Studio + Zero-Latency Fragments</b>"
            "<div class='card-note-text'>Instant tab switching, WCAG high-contrast light/dark presets, and custom wallpapers.</div></div>",
            unsafe_allow_html=True,
        )

    with tab_tips:
        st.markdown(
            "<div class='tip-card'><b>Daily Recurring Tasks:</b> Put <code>20m/day</code> in the ETA field (like reading or vocab review) so the AI Planner schedules a block every day until the due date.</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='tip-card'><b>Auto-Split Test Prep:</b> Any assignment marked <b>Test & Quizzes</b> or containing words like <i>study</i> or <i>review</i> automatically splits across multiple days before test day.</div>",
            unsafe_allow_html=True,
        )

    with tab_fb:
        with st.form("user_feedback_modal_form"):
            cat = st.selectbox("Feedback Type", ["Feature Request", "Bug Report", "SHS Schedule Correction", "General Praise"])
            rating = st.slider("App Rating", min_value=1, max_value=5, value=5)
            msg = st.text_area("Message", placeholder="Share an idea or report an issue...")
            if st.form_submit_button("Submit Feedback", use_container_width=True):
                if not msg.strip():
                    st.error("Please enter a message before submitting.")
                else:
                    save_user_feedback(user_id, user_email, cat, rating, msg)
                    st.success("Thank you! Your feedback was saved to the database.")


# -----------------------
# Fragment 1: Assignment Cards Grid (Assignments / Tests & Quizzes / Other)
# -----------------------
@fragment_decorator
def render_assignment_grid_fragment(
    user_id: str,
    tab_kind: str,
    prio_mode: str,
    is_light: bool,
    key_prefix: str,
) -> None:
    df = get_assignments_cached(user_id)
    today_d = get_local_now().date()

    # Undo toast banner if a task was just marked Done
    undo_payload = st.session_state.get("_last_completed_task")
    if isinstance(undo_payload, dict) and undo_payload.get("tab") == tab_kind:
        u_col1, u_col2 = st.columns([4, 1])
        with u_col1:
            st.markdown(
                f"<div class='undo-toast-box'><span>Completed <b>{undo_payload.get('title', 'Task')}</b>!</span></div>",
                unsafe_allow_html=True,
            )
        with u_col2:
            if st.button("Undo", key=f"{key_prefix}undo_done_btn", use_container_width=True):
                restore_single_assignment(undo_payload["row"])
                st.session_state.pop("_last_completed_task", None)
                safe_rerun(scope="fragment")

    if df.empty:
        active_df = pd.DataFrame(columns=ASSIGNMENT_COLS)
    else:
        active_df = df[df["status"] != "Done"].copy()
        if tab_kind == "tests":
            active_df = active_df[active_df["atype"] == "Test & Quizzes"]
        elif tab_kind == "other":
            active_df = active_df[active_df["atype"].isin(["Project", "Essay", "Lab", "Other"])]
        else:
            active_df = active_df[active_df["atype"] == "Homework"]

    # Filter & Sort Controls
    courses_present = sorted(list(set(active_df["course"].dropna().astype(str).str.upper().tolist()))) if not active_df.empty else []
    f_c1, f_c2, f_c3 = st.columns([1.4, 1.4, 1.2])
    with f_c1:
        course_filter = st.selectbox(
            "Filter by Course",
            options=["All Courses"] + courses_present,
            key=f"{key_prefix}crs_filter",
        )
    with f_c2:
        sort_by = st.selectbox(
            "Sort By",
            options=["Due Date (Earliest First)", "Priority (Highest First)", "Course (A–Z)"],
            key=f"{key_prefix}sort_sel",
        )
    with f_c3:
        st.markdown("<div style='height:27px;'></div>", unsafe_allow_html=True)
        default_cat = "Test & Quizzes" if tab_kind == "tests" else ("Project" if tab_kind == "other" else "Homework")
        if st.button("+ Add Item", key=f"{key_prefix}quick_add_btn", use_container_width=True):
            open_add_task_dialog(user_id, default_type=default_cat)

    if active_df.empty:
        st.info("Nothing active in this section right now. Click **+ Add Item** to create one!")
        return

    if course_filter != "All Courses":
        active_df = active_df[active_df["course"].astype(str).str.upper() == course_filter]

    if active_df.empty:
        st.info(f"No active items for **{course_filter}**.")
        return

    active_df["_prio_num"] = active_df["priority"].apply(priority_to_int)
    active_df["_due_sort"] = active_df["due_date"].fillna("9999-12-31").replace("", "9999-12-31")

    if sort_by == "Priority (Highest First)":
        active_df = active_df.sort_values(by=["_prio_num", "_due_sort"], ascending=[False, True])
    elif sort_by == "Course (A–Z)":
        active_df = active_df.sort_values(by=["course", "_due_sort"], ascending=[True, True])
    else:
        active_df = active_df.sort_values(by=["_due_sort", "_prio_num"], ascending=[True, False])

    records = active_df.to_dict(orient="records")
    cols = st.columns(3)

    for idx, row in enumerate(records):
        aid = str(row.get("id"))
        title = str(row.get("title") or "Untitled")
        course = str(row.get("course") or "GENERAL").upper()
        atype = str(row.get("atype") or "Homework")
        eta = str(row.get("eta") or "30m")
        status = str(row.get("status") or "Not Started")
        notes = str(row.get("notes") or "").strip()
        prio_n = priority_to_int(row.get("priority"))
        prio_lbl = priority_to_label(prio_n)
        prio_disp = format_priority_display(prio_n, prio_mode)
        prio_cls = "prio-high" if prio_lbl == "High" else ("prio-low" if prio_lbl == "Low" else "prio-medium")

        due_raw = str(row.get("due_date") or "").strip()
        due_text = "No Due Date"
        if due_raw:
            try:
                d_obj = datetime.strptime(due_raw, "%Y-%m-%d").date()
                diff = (d_obj - today_d).days
                if diff < 0:
                    due_text = f"Overdue ({d_obj.strftime('%b %d')})"
                elif diff == 0:
                    due_text = "Due Today"
                elif diff == 1:
                    due_text = "Due Tomorrow"
                else:
                    due_text = f"Due {d_obj.strftime('%a, %b %d')} ({diff}d)"
            except ValueError:
                due_text = due_raw

        with cols[idx % 3]:
            with st.container(border=True):
                course_badge = get_course_badge_html(course, is_light=is_light)
                st.markdown(
                    f"<div style='display:flex; justify-content:space-between; align-items:center; gap:6px;'>"
                    f"{course_badge}<span class='{prio_cls}'>{prio_disp}</span></div>"
                    f"<div class='card-task-title'>{title}</div>"
                    f"<div class='card-task-meta'>{atype} • Est. {eta}</div>",
                    unsafe_allow_html=True,
                )

                new_status = st.selectbox(
                    "Status",
                    options=STATUS_OPTIONS,
                    index=STATUS_OPTIONS.index(status) if status in STATUS_OPTIONS else 0,
                    key=f"{key_prefix}st_{aid}",
                    label_visibility="collapsed",
                )
                if new_status != status:
                    updated = dict(row)
                    if new_status == "Done":
                        updated["prev_status"] = status
                        st.session_state["_last_completed_task"] = {
                            "tab": tab_kind,
                            "title": title,
                            "row": dict(updated),
                        }
                    updated["status"] = new_status
                    upsert_assignments([updated])
                    safe_rerun(scope="fragment")

                if notes:
                    st.markdown(f"<div class='card-note-text'>{notes}</div>", unsafe_allow_html=True)

                st.markdown(
                    f"<div class='card-footer-row'><span class='card-due-text'>{due_text}</span></div>",
                    unsafe_allow_html=True,
                )

                b1, b2, b3 = st.columns(3)
                with b1:
                    if st.button("Done", key=f"{key_prefix}done_{aid}", use_container_width=True):
                        updated = dict(row)
                        updated["prev_status"] = status
                        updated["status"] = "Done"
                        st.session_state["_last_completed_task"] = {
                            "tab": tab_kind,
                            "title": title,
                            "row": dict(updated),
                        }
                        upsert_assignments([updated])
                        safe_rerun(scope="fragment")
                with b2:
                    if st.button("Edit", key=f"{key_prefix}edit_{aid}", use_container_width=True):
                        open_edit_task_dialog(user_id, row)
                with b3:
                    if st.button("Delete", key=f"{key_prefix}del_{aid}", use_container_width=True):
                        delete_assignment(aid)
                        safe_rerun(scope="fragment")


# -----------------------
# Fragment 2: Live SHS Letter Day & Bell Schedule
# -----------------------
try:
    _shs_auto_fragment = fragment_decorator(run_every=60)
except TypeError:
    _shs_auto_fragment = fragment_decorator


@_shs_auto_fragment
def render_shs_bell_schedule_fragment(user_id: str, is_light: bool) -> None:
    shs_cfg = get_shs_cached(user_id)
    saved_lunches = dict(shs_cfg.get("lunches", {"A": "L2", "B": "L2", "C": "L2", "D": "L2", "X": "L2"}))
    saved_periods = dict(shs_cfg.get("periods", {str(i): "" for i in range(1, 9)}))
    saved_rooms = dict(shs_cfg.get("study_rooms", {"A": "", "B": "", "C": "", "D": "", "X": ""}))
    saved_sheet_url = str(shs_cfg.get("sheet_url", "") or get_default_shs_sheet_url()).strip()
    user_courses = get_courses_cached(user_id)

    col_bells, col_mapper = st.columns([1.8, 1.2])

    with col_bells:
        st.markdown("<div class='section-heading'>SHS Daily Letter Day & Bell Schedule</div>", unsafe_allow_html=True)
        st.caption("Auto-updates daily from the live SHS letter-day spreadsheet & refreshes live period status every minute.")

        now_local = get_local_now()
        c_d1, c_d2, c_d3 = st.columns([1.15, 0.95, 1.35])
        with c_d1:
            view_date = st.date_input("Schedule Date", value=now_local.date(), key="shs_bell_date_input")

        day_info = get_shs_day_info(view_date, custom_sheet_url=saved_sheet_url)
        detected_letter = day_info.get("letter", "A")
        detected_sched = day_info.get("schedule", "Daily")
        day_note = day_info.get("note", "")
        day_source = day_info.get("source", "Calendar")

        letter_opts = ["A", "B", "C", "D", "X"]
        default_letter = detected_letter if detected_letter in letter_opts else "A"
        default_sched = (
            detected_sched
            if detected_sched in SHS_SCHEDULE_TYPES
            else ("X Day" if default_letter == "X" else "Daily")
        )

        with c_d2:
            active_letter = st.selectbox(
                "Letter Day",
                options=letter_opts,
                index=letter_opts.index(default_letter),
                key=f"shs_letter_sel_{view_date.isoformat()}",
            )
        with c_d3:
            active_sched = st.selectbox(
                "Bell Schedule",
                options=SHS_SCHEDULE_TYPES,
                index=SHS_SCHEDULE_TYPES.index(default_sched),
                key=f"shs_sched_sel_{view_date.isoformat()}",
            )

        active_lunch = saved_lunches.get(active_letter, "L2")
        src_badge = f" • Source: **{day_source}**"

        if detected_letter in ("NO SCHOOL", "WEEKEND"):
            st.info(
                f"**{view_date.strftime('%A, %b %d')}**: {detected_letter} ({day_note}). "
                f"Previewing **{active_letter} Day ({active_sched})** below."
            )
        elif day_note:
            st.caption(
                f"Note: **{day_note}** • {SHS_DROPPED_PERIODS.get(active_letter, '')} • "
                f"{active_letter} Day Lunch: **{active_lunch}**{src_badge}"
            )
        else:
            st.caption(
                f"Rotation: **{SHS_DROPPED_PERIODS.get(active_letter, '')}** • "
                f"{active_letter} Day Lunch: **{active_lunch}**{src_badge}"
            )

        blocks = build_shs_bell_blocks(
            active_letter,
            active_sched,
            active_lunch,
            saved_periods,
            study_rooms=saved_rooms,
        )
        is_today = (view_date == now_local.date()) and (detected_letter not in ("NO SCHOOL", "WEEKEND"))
        now_mins = now_local.hour * 60 + now_local.minute

        for blk in blocks:
            st_t = parse_time_str(blk["start"])
            end_t = parse_time_str(blk["end"])
            is_live = False
            if is_today and st_t and end_t:
                s_m = st_t.hour * 60 + st_t.minute
                e_m = end_t.hour * 60 + end_t.minute
                if s_m <= now_mins < e_m:
                    is_live = True

            row_cls = "bell-row bell-row-active" if is_live else "bell-row"
            live_badge = "<span class='bell-live-tag'>NOW</span>" if is_live else ""
            is_lunch_blk = (blk.get("is_lunch") == "1")

            if is_lunch_blk:
                class_html = f"<span class='slot-title-text'>{blk['class_name']}</span>"
            else:
                class_html = get_course_badge_html(blk["class_name"], is_light=is_light)

            ann_html = " <span class='slot-meta-text'>(Announcements)</span>" if blk.get("ann") == "1" else ""
            room_html = (
                f" <span class='bell-period-badge' style='margin-left:6px;'>{blk['room']}</span>"
                if blk.get("room") else ""
            )

            st.markdown(
                f"<div class='{row_cls}'>"
                f"<div><span class='bell-period-badge'>{blk['label']}</span> {class_html}{room_html}{ann_html}{live_badge}</div>"
                f"<div class='card-due-text'><b>{blk['start']} – {blk['end']}</b> <span class='slot-meta-text'>({blk['mins']})</span></div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    with col_mapper:
        st.markdown("<div class='section-heading'>My Periods, Lunch & Rooms</div>", unsafe_allow_html=True)
        st.caption("Saved directly to your database account.")

        with st.form("shs_period_mapper_form"):
            st.markdown("**Live Letter-Day Google Spreadsheet URL**")
            new_sheet_url = st.text_input(
                "Google Sheet Link",
                value=saved_sheet_url,
                placeholder="https://docs.google.com/spreadsheets/d/...",
                label_visibility="collapsed",
            )

            st.markdown("---")
            st.markdown("**Lunch Wave by Letter Day**")
            lunch_opts = ["L1", "L2", "L3"]
            new_lunches: Dict[str, str] = {}

            l_row1 = st.columns(3)
            for idx, (l_code, l_lbl) in enumerate([("A", "A (Per. 5)"), ("B", "B (Per. 8)"), ("C", "C (Per. 7)")]):
                with l_row1[idx]:
                    cur_l = saved_lunches.get(l_code, "L2")
                    new_lunches[l_code] = st.selectbox(
                        l_lbl,
                        options=lunch_opts,
                        index=lunch_opts.index(cur_l) if cur_l in lunch_opts else 1,
                        key=f"shs_lunch_sel_{l_code}",
                    )

            l_row2 = st.columns(2)
            for idx, (l_code, l_lbl) in enumerate([("D", "D Day (Per. 6)"), ("X", "X Day (Per. 6)")]):
                with l_row2[idx]:
                    cur_l = saved_lunches.get(l_code, "L2")
                    new_lunches[l_code] = st.selectbox(
                        l_lbl,
                        options=lunch_opts,
                        index=lunch_opts.index(cur_l) if cur_l in lunch_opts else 1,
                        key=f"shs_lunch_sel_{l_code}",
                    )

            st.markdown("---")
            st.markdown("**Study Hall Room by Letter Day**")
            new_rooms: Dict[str, str] = {}
            r_cols = st.columns(5)
            for idx, l_code in enumerate(["A", "B", "C", "D", "X"]):
                with r_cols[idx]:
                    new_rooms[l_code] = st.text_input(
                        f"{l_code} Day",
                        value=str(saved_rooms.get(l_code, "")),
                        placeholder="214",
                        key=f"shs_room_in_{l_code}",
                    )

            st.markdown("---")
            st.markdown("**Classes by Period**")
            course_choices = [""] + sorted(list(set(user_courses + ["STUDY HALL", "FREE / UNASSIGNED"])))
            new_periods: Dict[str, str] = {}

            p_col1, p_col2 = st.columns(2)
            for p_num in range(1, 9):
                p_key = str(p_num)
                cur_val = str(saved_periods.get(p_key, "")).strip().upper()
                opts_for_p = list(course_choices)
                if cur_val and cur_val not in opts_for_p:
                    opts_for_p.insert(1, cur_val)
                target_col = p_col1 if p_num <= 4 else p_col2
                with target_col:
                    new_periods[p_key] = st.selectbox(
                        f"Period {p_num}",
                        options=opts_for_p,
                        index=opts_for_p.index(cur_val) if cur_val in opts_for_p else 0,
                        key=f"shs_p_sel_{p_num}",
                    )

            if st.form_submit_button("Save & Sync SHS Schedule", use_container_width=True):
                clean_url = new_sheet_url.strip()
                _write_shs_config(
                    user_id,
                    {
                        "lunches": new_lunches,
                        "periods": new_periods,
                        "study_rooms": {k: v.strip() for k, v in new_rooms.items()},
                        "sheet_url": clean_url,
                    },
                )
                fetch_live_shs_spreadsheet_map.clear()
                st.success("Saved to database & synced with live spreadsheet!")
                safe_rerun(scope="fragment")# -----------------------
# Fragment 3: Weekly Schedule & Smart AI Study Planner
# -----------------------
@fragment_decorator
def render_schedule_and_ai_fragment(
    user_id: str,
    prio_mode: str,
    is_light: bool,
) -> None:
    df = get_assignments_cached(user_id)
    schedule_list = list(get_schedule_cached(user_id))
    max_work_map = dict(get_max_work_cached(user_id))
    completed_slots = dict(get_completed_slots_cached(user_id))
    today_iso = get_local_now().date().isoformat()

    col_left, col_right = st.columns([1.15, 1.85])

    with col_left:
        st.markdown("<div class='section-heading'>Weekly Commitments & Daily Caps</div>", unsafe_allow_html=True)
        st.caption("Add sports, practices, work, or clubs so the planner schedules homework around them.")

        with st.form("add_commitment_form"):
            ev_title = st.text_input("Activity / Commitment", placeholder="e.g., Soccer Practice, Work Shift")
            c_d, c_s, c_e = st.columns([1.2, 1, 1])
            with c_d:
                ev_day = st.selectbox("Day", options=DAYS_OF_WEEK)
            with c_s:
                ev_start = st.text_input("Start", value="3:30 PM", placeholder="3:30 PM")
            with c_e:
                ev_end = st.text_input("End", value="5:00 PM", placeholder="5:00 PM")

            if st.form_submit_button("Add Commitment", use_container_width=True):
                if not ev_title.strip():
                    st.error("Please enter an activity name.")
                elif not parse_time_str(ev_start) or not parse_time_str(ev_end):
                    st.error("Enter valid times like 3:30 PM and 5:00 PM.")
                else:
                    schedule_list.append({
                        "id": str(uuid.uuid4()),
                        "day": ev_day,
                        "title": ev_title.strip(),
                        "start": ev_start.strip().upper(),
                        "end": ev_end.strip().upper(),
                    })
                    _write_schedule_file(user_id, schedule_list)
                    safe_rerun(scope="fragment")

        if schedule_list:
            with st.expander(f"Saved Weekly Commitments ({len(schedule_list)})", expanded=False):
                for idx, ev in enumerate(schedule_list):
                    ec1, ec2 = st.columns([4, 1.2])
                    with ec1:
                        st.markdown(
                            f"<div class='sched-item-text'><b>{ev.get('day')}</b> • {ev.get('title')} "
                            f"<span class='slot-meta-text'>({ev.get('start')} – {ev.get('end')})</span></div>",
                            unsafe_allow_html=True,
                        )
                    with ec2:
                        if st.button("Remove", key=f"del_ev_{ev.get('id', idx)}", use_container_width=True):
                            schedule_list.pop(idx)
                            _write_schedule_file(user_id, schedule_list)
                            safe_rerun(scope="fragment")

        st.markdown("---")
        with st.form("daily_max_work_form"):
            st.markdown("**Max Homework / Study Minutes per Day**")
            new_caps: Dict[str, int] = {}
            cap_c1, cap_c2 = st.columns(2)
            for idx, d_name in enumerate(DAYS_OF_WEEK):
                target_c = cap_c1 if idx < 4 else cap_c2
                with target_c:
                    new_caps[d_name] = st.number_input(
                        d_name[:3],
                        min_value=15,
                        max_value=360,
                        step=15,
                        value=int(max_work_map.get(d_name, 60)),
                        key=f"cap_in_{d_name}",
                    )
            if st.form_submit_button("Save Daily Caps", use_container_width=True):
                _write_max_work_config(user_id, new_caps)
                st.success("Daily study caps updated!")
                safe_rerun(scope="fragment")

    with col_right:
        hdr_c1, hdr_c2 = st.columns([3, 1])
        with hdr_c1:
            st.markdown("<div class='section-heading'>Smart 7-Day Study & Homework Plan</div>", unsafe_allow_html=True)
        with hdr_c2:
            if st.button("Refresh Plan", key="refresh_ai_plan_btn", use_container_width=True):
                st.session_state.pop("_ai_plan_result", None)
                safe_rerun(scope="fragment")

        plan_data = st.session_state.get("_ai_plan_result")
        if plan_data is None:
            plan_data = generate_smart_weekly_plan(df, schedule_list, max_work_map)
            st.session_state["_ai_plan_result"] = plan_data

        unscheduled = plan_data.get("unscheduled", [])
        if unscheduled:
            warn_items = ", ".join(
                f"{u['title']} ({format_mins_to_hrs_mins(u['remaining_mins'])} left, due {u['due_str']})"
                for u in unscheduled
            )
            st.warning(f"Daily caps are tight! Extra workload overflows capacity: **{warn_items}**")

        for day_entry in plan_data.get("days", []):
            d_str = day_entry["date_str"]
            d_label = "TODAY" if day_entry["offset"] == 0 else day_entry["day_name"]
            date_pretty = day_entry["date"].strftime("%b %d")
            used_txt = format_mins_to_hrs_mins(day_entry["used_mins"])
            cap_txt = format_mins_to_hrs_mins(day_entry["cap_mins"])

            slots = day_entry.get("slots", [])
            events = day_entry.get("events", [])

            inner_html_parts: List[str] = []
            for ev in events:
                inner_html_parts.append(
                    f"<div style='margin-bottom:6px;'><span class='bell-period-badge'>BUSY</span> "
                    f"<span class='sched-item-text'>{ev.get('title')} ({ev.get('start')} – {ev.get('end')})</span></div>"
                )

            if not slots and not events:
                inner_html_parts.append("<div class='slot-meta-text'>Free evening — no tasks or commitments scheduled.</div>")
            elif not slots:
                inner_html_parts.append("<div class='slot-meta-text'>No homework blocks assigned on this day.</div>")

            st.markdown(
                f"<div class='ai-day-card'>"
                f"<div class='ai-day-header'>"
                f"<span class='ai-day-title'>{d_label} • {date_pretty}</span>"
                f"<span class='day-time-badge'>{used_txt} <span class='time-max-cap'>/ {cap_txt} max</span></span>"
                f"</div>"
                f"{''.join(inner_html_parts)}"
                f"</div>",
                unsafe_allow_html=True,
            )

            for s_idx, sl in enumerate(slots):
                slot_key = f"{d_str}:{sl['task_id']}:{s_idx}"
                is_checked = slot_key in completed_slots
                sc1, sc2 = st.columns([0.45, 5.55])
                with sc1:
                    checked_now = st.checkbox(
                        "Done",
                        value=is_checked,
                        key=f"chk_slot_{slot_key}",
                        label_visibility="collapsed",
                    )
                with sc2:
                    c_badge = get_course_badge_html(sl["course"], is_light=is_light)
                    strike_style = "text-decoration: line-through; opacity: 0.6;" if checked_now else ""
                    st.markdown(
                        f"<div style='padding:2px 0 8px 0; {strike_style}'>"
                        f"<span class='slot-badge'>{sl['start_str']} – {sl['end_str']}</span> "
                        f"{c_badge} <span class='slot-title-text'>{sl['title']}</span> "
                        f"<span class='slot-meta-text'>({format_mins_to_hrs_mins(sl['mins'])} • Due {sl['due_str']})</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                if checked_now != is_checked:
                    if checked_now:
                        completed_slots[slot_key] = {"day_date_str": today_iso, "title": sl["title"]}
                    else:
                        completed_slots.pop(slot_key, None)
                    _write_completed_slots(user_id, completed_slots)
                    safe_rerun(scope="fragment")


# -----------------------
# Fragment 4: Completed Tasks & 1-Click Recovery
# -----------------------
@fragment_decorator
def render_completed_recovery_fragment(user_id: str, is_light: bool) -> None:
    df = get_assignments_cached(user_id)
    st.markdown("<div class='section-heading'>Completed Assignments & Recovery</div>", unsafe_allow_html=True)
    st.caption("Completed tasks stay here for quick 1-click recovery until their due date passes.")

    if df.empty or (df["status"] == "Done").sum() == 0:
        st.info("No completed assignments waiting for recovery right now.")
        return

    done_df = df[df["status"] == "Done"].copy()
    records = done_df.to_dict(orient="records")

    for row in records:
        aid = str(row.get("id"))
        title = str(row.get("title") or "Untitled")
        course = str(row.get("course") or "GENERAL").upper()
        atype = str(row.get("atype") or "Homework")
        due_raw = str(row.get("due_date") or "").strip()

        rc1, rc2, rc3 = st.columns([4.2, 1.1, 1.1])
        with rc1:
            c_badge = get_course_badge_html(course, is_light=is_light)
            st.markdown(
                f"<div class='recovery-card'>"
                f"<div>{c_badge} <span class='slot-title-text' style='margin-left:6px;'>{title}</span> "
                f"<span class='slot-meta-text'>• {atype} • Due {due_raw or 'N/A'}</span></div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with rc2:
            if st.button("Restore", key=f"rest_{aid}", use_container_width=True):
                restore_single_assignment(row)
                safe_rerun(scope="fragment")
        with rc3:
            if st.button("Delete", key=f"perm_del_{aid}", use_container_width=True):
                delete_assignment(aid)
                safe_rerun(scope="fragment")


# -----------------------
# Authentication Screen & Main App Router
# -----------------------
def render_auth_screen() -> None:
    st.markdown(build_theme_css(DEFAULT_THEME_CONFIG), unsafe_allow_html=True)
    _, mid, _ = st.columns([1.1, 1.4, 1.1])
    with mid:
        st.markdown(
            "<div style='text-align:center; margin-top:28px; margin-bottom:18px;'>"
            "<div class='app-title'>📑 Assignment Tracker</div>"
            "<div class='app-subtitle'>Smart Homework Planner & Live SHS Bell Schedule</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        tab_in, tab_up = st.tabs(["Sign In", "Create Account"])

        with tab_in:
            with st.form("login_form"):
                email_in = st.text_input("School Username or Email", placeholder="e.g., jsmith or jsmith@simsburyschools.net")
                pw_in = st.text_input("Password", type="password")
                if st.form_submit_button("Sign In", use_container_width=True):
                    user = authenticate_user(email_in, pw_in)
                    if user:
                        clear_all_session_caches()
                        st.session_state["auth_user"] = user
                        st.rerun()
                    else:
                        st.error("Invalid email/username or password.")

        with tab_up:
            with st.form("register_form"):
                reg_email = st.text_input("School Username or Email", placeholder="e.g., jsmith")
                reg_pw = st.text_input("Choose Password (min 4 chars)", type="password")
                if st.form_submit_button("Create Account", use_container_width=True):
                    ok, msg, new_user = register_user(reg_email, reg_pw)
                    if ok and new_user:
                        clear_all_session_caches()
                        st.session_state["auth_user"] = new_user
                        st.rerun()
                    else:
                        st.error(msg)


def main() -> None:
    auth_user = st.session_state.get("auth_user")
    if not auth_user or not auth_user.get("id"):
        render_auth_screen()
        return

    user_id = str(auth_user["id"])
    user_email = str(auth_user.get("email", ""))

    hydrate_user_session(user_id)
    theme_cfg = get_theme_cached(user_id)
    is_light_theme = (theme_cfg.get("mode", "Dark") == "Light")
    user_prio_mode = get_prio_cached(user_id) or "Low / Medium / High"
    seen_ver = get_seen_updates_cached(user_id)
    shs_cfg = get_shs_cached(user_id)

    st.markdown(build_theme_css(theme_cfg), unsafe_allow_html=True)

    # Top Header & Action Controls
    h_left, h_right = st.columns([2.2, 2.8])
    with h_left:
        st.markdown(
            f"<div class='header-brand-box'>"
            f"<div class='app-title'>📑 Assignment Tracker</div>"
            f"<div class='app-subtitle'>Signed in as <span class='accent-text'>{user_email}</span></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with h_right:
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        b1, b2, b3, b4, b5, b6 = st.columns([1.05, 1.0, 0.95, 1.0, 1.15, 0.95])
        with b1:
            if st.button("+ Add", key="hdr_add_btn", use_container_width=True):
                open_add_task_dialog(user_id)
        with b2:
            if st.button("Courses", key="hdr_crs_btn", use_container_width=True):
                open_courses_dialog(user_id)
        with b3:
            if st.button("Theme", key="hdr_thm_btn", use_container_width=True):
                open_theme_studio_dialog(user_id)
        with b4:
            if st.button("Settings", key="hdr_set_btn", use_container_width=True):
                open_settings_dialog(user_id)
        with b5:
            upd_lbl = "Updates • NEW" if seen_ver != CURRENT_APP_VERSION else "Updates"
            if st.button(upd_lbl, key="hdr_upd_btn", use_container_width=True):
                open_feedback_updates_dialog(user_id, user_email)
        with b6:
            if st.button("Log Out", key="hdr_out_btn", use_container_width=True):
                clear_all_session_caches()
                st.session_state.pop("auth_user", None)
                st.rerun()

    # Live Date & SHS Letter Day Banner
    now_local = get_local_now()
    today_str = now_local.strftime("%A, %B %d, %Y")
    day_info = get_shs_day_info(now_local.date(), custom_sheet_url=shs_cfg.get("sheet_url", ""))
    det_letter = day_info.get("letter", "A")
    det_sched = day_info.get("schedule", "Daily")
    det_note = day_info.get("note", "")

    if det_letter in ("NO SCHOOL", "WEEKEND"):
        pill_label = f"{det_letter} • {det_note}" if det_note else det_letter
    else:
        pill_label = f"{det_letter} Day • {det_sched}"
        if det_note:
            pill_label += f" ({det_note})"

    st.markdown(
        f'<div class="date-banner">Today\'s Date: {today_str} <span class="shs-day-pill">{pill_label}</span></div>',
        unsafe_allow_html=True,
    )

    # Navigation Pills
    NAV_OPTIONS = [
        "Assignments",
        "Tests & Quizzes",
        "Other",
        "SHS Bell Schedule",
        "Weekly Schedule & AI Planner",
        "Completed & Recovery",
    ]
    active_tab = st.radio(
        "Navigation",
        NAV_OPTIONS,
        horizontal=True,
        label_visibility="collapsed",
        key="main_nav_pill",
    )

    if active_tab == "Assignments":
        render_assignment_grid_fragment(user_id, "regular", user_prio_mode, is_light=is_light_theme, key_prefix="reg_")
    elif active_tab == "Tests & Quizzes":
        render_assignment_grid_fragment(user_id, "tests", user_prio_mode, is_light=is_light_theme, key_prefix="tests_")
    elif active_tab == "Other":
        render_assignment_grid_fragment(user_id, "other", user_prio_mode, is_light=is_light_theme, key_prefix="other_")
    elif active_tab == "SHS Bell Schedule":
        render_shs_bell_schedule_fragment(user_id, is_light=is_light_theme)
    elif active_tab == "Weekly Schedule & AI Planner":
        render_schedule_and_ai_fragment(user_id, user_prio_mode, is_light=is_light_theme)
    elif active_tab == "Completed & Recovery":
        render_completed_recovery_fragment(user_id, is_light=is_light_theme)


if __name__ == "__main__":
    main()
