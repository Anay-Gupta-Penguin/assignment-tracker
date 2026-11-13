"""
📚 Assignment Tracker — Zero-Latency @st.fragment, SHS Bell Schedule & Theme Studio
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
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

CURRENT_APP_VERSION = "3.3"


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

/* High-Contrast Text Enforcement */
.stApp p, .stApp label, .stApp span, .stMarkdown,
div[data-testid="stMarkdownContainer"] p,
div[data-testid="stWidgetLabel"] p,
div[data-testid="stWidgetLabel"] label {
    color: var(--text-primary) !important;
}
div[data-testid="stCaptionContainer"] p {
    color: var(--text-muted) !important;
}

/* Crisp Checkbox Borders */
div[data-testid="stCheckbox"] label > span:first-child,
div[data-testid="stCheckbox"] div[role="checkbox"] {
    border: 1.5px solid var(--accent-readable) !important;
    border-radius: 5px !important;
}

/* Inputs, Selectboxes, Textareas & Dropdown Popovers */
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

/* Buttons */
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

/* Pill Navigation Bar */
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

/* Frosted Card Containers, Forms & Expanders */
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

/* Dialog Modal Surface */
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
    font-size: 0.78rem;
    font-weight: 800;
    margin-right: 8px;
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

.prio-high {
    __PRIO_HIGH_CSS__
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 800;
}

.prio-medium {
    __PRIO_MED_CSS__
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 800;
}

.prio-low {
    __PRIO_LOW_CSS__
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 800;
}

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

.time-max-cap {
    color: var(--text-muted) !important;
    font-weight: 600;
}

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

.slot-title-text {
    color: var(--text-primary) !important;
    font-weight: 800;
}

.slot-meta-text {
    color: var(--text-muted) !important;
    font-size: 0.78rem;
    font-weight: 600;
}

.sched-item-text {
    color: var(--text-primary) !important;
    font-size: 0.83rem;
    font-weight: 600;
}

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
    .main .block-container {
        padding-top: 0.5rem !important;
        padding-left: 0.45rem !important;
        padding-right: 0.45rem !important;
    }
    .app-title { font-size: 1.25rem !important; }
    .app-subtitle { font-size: 0.73rem !important; }
    div[data-testid="stHorizontalBlock"]:not(:has(.card-task-title)) {
        flex-wrap: nowrap !important;
        gap: 4px !important;
    }
    div[data-testid="stHorizontalBlock"]:not(:has(.card-task-title)) > div[data-testid="stColumn"] {
        min-width: 0 !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        padding: 4px !important;
        gap: 4px !important;
        margin-bottom: 12px !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label {
        padding: 6px 10px !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label p {
        font-size: 0.75rem !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"],
    div[data-testid="stColumn"] div[data-testid="stVerticalBlock"] > div > div[data-testid="stVerticalBlock"]:has(.card-task-title),
    div[data-testid="stColumn"] div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"]:has(.card-task-title) {
        padding: 12px 13px !important;
        margin-bottom: 10px !important;
        border-radius: 12px !important;
    }
    .stButton button {
        padding: 4px 4px !important;
        font-size: 0.68rem !important;
        min-height: 31px !important;
    }
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
# Application Constants
# -----------------------
DEFAULT_DOMAIN = "@simsburyschools.net"
STATUS_OPTIONS = ["Not Started", "In Progress", "Done"]
TYPE_OPTIONS = ["Homework", "Essay", "Presentation", "Test & Quizzes", "Other"]
PRIORITY_OPTIONS = ["Low", "Medium", "High"]
PRIORITY_SYSTEM_MODES = ["Low / Medium / High", "1 to 10 Scale (Slider)", "Both Systems"]
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

SYSTEM_TITLES = {
    "__SYSTEM_COURSES__",
    "__SYSTEM_SCHEDULE__",
    "__SYSTEM_PRIO_CONFIG__",
    "__SYSTEM_MAX_WORK_CONFIG__",
    "__SYSTEM_COMPLETED_SLOTS__",
    "__SYSTEM_SEEN_UPDATES__",
    "__SYSTEM_THEME_CONFIG__",
    "__SYSTEM_SHS_CONFIG__",
}

SHS_SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1oKpAjRBmpZcNkSK4PGqxLwynwcRIfZjVpnn2VPy_eGw/export?format=csv&gid=930331453"

SHS_SCHEDULE_TYPES = [
    "Daily",
    "Connect",
    "2 Hour Delay",
    "Early Dismissal",
    "Emergency Early Dismissal",
    "X Day",
    "X Day 2 Hour Delay",
    "X Day Early Dismissal",
]

# Full 2026-2027 SHS Letter Day & Schedule Calendar: (letter_day, schedule_type, note)
SHS_CALENDAR_2026_2027: Dict[str, Tuple[str, str, str]] = {
    # August / September 2026
    "2026-08-26": ("X", "X Day Early Dismissal", "First Day of School"),
    "2026-08-27": ("A", "Early Dismissal", "Per. 1, 3, 5, 7 Early Dismissal"),
    "2026-08-28": ("D", "Early Dismissal", "Per. 2, 4, 6, 8 Early Dismissal"),
    "2026-08-31": ("A", "Connect", ""),
    "2026-09-01": ("B", "Daily", ""),
    "2026-09-02": ("C", "Daily", ""),
    "2026-09-03": ("D", "Daily", ""),
    "2026-09-04": ("A", "Daily", ""),
    "2026-09-07": ("NO SCHOOL", "No School", "Labor Day"),
    "2026-09-08": ("B", "Daily", ""),
    "2026-09-09": ("C", "Daily", ""),
    "2026-09-10": ("D", "Daily", ""),
    "2026-09-11": ("A", "Daily", ""),
    "2026-09-14": ("B", "Daily", ""),
    "2026-09-15": ("C", "Daily", ""),
    "2026-09-16": ("D", "Daily", ""),
    "2026-09-17": ("A", "Daily", ""),
    "2026-09-18": ("B", "Daily", ""),
    "2026-09-21": ("NO SCHOOL", "No School", "Yom Kippur"),
    "2026-09-22": ("C", "Daily", ""),
    "2026-09-23": ("D", "Early Dismissal", ""),
    "2026-09-24": ("A", "Daily", ""),
    "2026-09-25": ("B", "Daily", ""),
    "2026-09-28": ("C", "Daily", ""),
    "2026-09-29": ("D", "Daily", ""),
    "2026-09-30": ("A", "Daily", ""),
    # October 2026
    "2026-10-01": ("B", "Daily", ""),
    "2026-10-02": ("C", "Daily", ""),
    "2026-10-05": ("D", "Daily", ""),
    "2026-10-06": ("A", "Daily", ""),
    "2026-10-07": ("B", "Daily", ""),
    "2026-10-08": ("C", "Connect", ""),
    "2026-10-09": ("D", "Daily", ""),
    "2026-10-12": ("NO SCHOOL", "No School", "Columbus Day"),
    "2026-10-13": ("A", "Daily", ""),
    "2026-10-14": ("SPECIAL", "Early Dismissal", "PSAT Testing"),
    "2026-10-15": ("B", "Daily", ""),
    "2026-10-16": ("C", "Daily", ""),
    "2026-10-19": ("D", "Daily", ""),
    "2026-10-20": ("A", "Daily", ""),
    "2026-10-21": ("B", "Daily", ""),
    "2026-10-22": ("C", "Daily", ""),
    "2026-10-23": ("D", "Daily", ""),
    "2026-10-26": ("A", "Connect", ""),
    "2026-10-27": ("B", "Daily", ""),
    "2026-10-28": ("C", "Daily", ""),
    "2026-10-29": ("D", "Daily", "End of Q1"),
    "2026-10-30": ("A", "Daily", ""),
    # November 2026
    "2026-11-02": ("B", "Daily", ""),
    "2026-11-03": ("NO SCHOOL", "No School", "Election Day"),
    "2026-11-04": ("C", "Daily", ""),
    "2026-11-05": ("D", "Connect", ""),
    "2026-11-06": ("A", "Daily", ""),
    "2026-11-09": ("B", "Daily", ""),
    "2026-11-10": ("C", "Daily", ""),
    "2026-11-11": ("D", "Connect", ""),
    "2026-11-12": ("A", "Daily", ""),
    "2026-11-13": ("B", "Daily", ""),
    "2026-11-16": ("C", "Daily", ""),
    "2026-11-17": ("D", "Daily", ""),
    "2026-11-18": ("A", "Daily", ""),
    "2026-11-19": ("B", "Daily", ""),
    "2026-11-20": ("C", "Daily", ""),
    "2026-11-23": ("D", "Daily", ""),
    "2026-11-24": ("A", "Daily", ""),
    "2026-11-25": ("B", "Early Dismissal", ""),
    "2026-11-26": ("NO SCHOOL", "No School", "Thanksgiving Break"),
    "2026-11-27": ("NO SCHOOL", "No School", "Thanksgiving Break"),
    "2026-11-30": ("C", "Daily", ""),
    # December 2026
    "2026-12-01": ("D", "Daily", ""),
    "2026-12-02": ("A", "Daily", ""),
    "2026-12-03": ("B", "Connect", ""),
    "2026-12-04": ("C", "Daily", ""),
    "2026-12-07": ("D", "Daily", ""),
    "2026-12-08": ("A", "Daily", ""),
    "2026-12-09": ("B", "Connect", ""),
    "2026-12-10": ("C", "Daily", ""),
    "2026-12-11": ("D", "Daily", ""),
    "2026-12-14": ("A", "Daily", ""),
    "2026-12-15": ("B", "Daily", ""),
    "2026-12-16": ("C", "Early Dismissal", ""),
    "2026-12-17": ("D", "Daily", ""),
    "2026-12-18": ("A", "Daily", ""),
    "2026-12-21": ("B", "Daily", ""),
    "2026-12-22": ("C", "Daily", ""),
    "2026-12-23": ("D", "Early Dismissal", ""),
    "2026-12-24": ("NO SCHOOL", "No School", "Holiday Break"),
    "2026-12-25": ("NO SCHOOL", "No School", "Holiday Break"),
    "2026-12-28": ("NO SCHOOL", "No School", "Holiday Break"),
    "2026-12-29": ("NO SCHOOL", "No School", "Holiday Break"),
    "2026-12-30": ("NO SCHOOL", "No School", "Holiday Break"),
    "2026-12-31": ("NO SCHOOL", "No School", "Holiday Break"),
    # January 2027
    "2027-01-01": ("NO SCHOOL", "No School", "New Year's Day"),
    "2027-01-04": ("A", "Daily", ""),
    "2027-01-05": ("B", "Daily", ""),
    "2027-01-06": ("C", "Daily", ""),
    "2027-01-07": ("D", "Daily", ""),
    "2027-01-08": ("X", "X Day", ""),
    "2027-01-11": ("X", "X Day", "End of Q2"),
    "2027-01-12": ("EXAMS", "Early Dismissal", "Mid Term Exams"),
    "2027-01-13": ("EXAMS", "Early Dismissal", "Mid Term Exams"),
    "2027-01-14": ("EXAMS", "Early Dismissal", "Mid Term Exams"),
    "2027-01-15": ("EXAMS", "Early Dismissal", "Mid Term Exams"),
    "2027-01-18": ("NO SCHOOL", "No School", "MLK Jr. Day"),
    "2027-01-19": ("A", "Daily", ""),
    "2027-01-20": ("B", "Daily", ""),
    "2027-01-21": ("C", "Daily", ""),
    "2027-01-22": ("D", "Daily", ""),
    "2027-01-25": ("A", "Connect", ""),
    "2027-01-26": ("B", "Daily", ""),
    "2027-01-27": ("C", "Daily", ""),
    "2027-01-28": ("D", "Daily", ""),
    "2027-01-29": ("X", "X Day", ""),
    # February 2027
    "2027-02-01": ("A", "Daily", ""),
    "2027-02-02": ("B", "Daily", ""),
    "2027-02-03": ("C", "Daily", ""),
    "2027-02-04": ("D", "Daily", ""),
    "2027-02-05": ("X", "X Day", ""),
    "2027-02-08": ("A", "Daily", ""),
    "2027-02-09": ("B", "Connect", ""),
    "2027-02-10": ("C", "Early Dismissal", ""),
    "2027-02-11": ("D", "Daily", ""),
    "2027-02-12": ("X", "X Day", ""),
    "2027-02-15": ("NO SCHOOL", "No School", "February Break"),
    "2027-02-16": ("NO SCHOOL", "No School", "February Break"),
    "2027-02-17": ("A", "Daily", "Per. 1, 3, 5, 7"),
    "2027-02-18": ("D", "Daily", "Per. 2, 4, 6, 8"),
    "2027-02-19": ("X", "X Day", ""),
    "2027-02-22": ("A", "Daily", ""),
    "2027-02-23": ("B", "Daily", ""),
    "2027-02-24": ("C", "Daily", ""),
    "2027-02-25": ("D", "Daily", ""),
    "2027-02-26": ("X", "X Day", ""),
    # March 2027
    "2027-03-01": ("A", "Daily", ""),
    "2027-03-02": ("B", "Daily", ""),
    "2027-03-03": ("C", "Daily", ""),
    "2027-03-04": ("D", "Daily", ""),
    "2027-03-05": ("A", "Daily", ""),
    "2027-03-08": ("B", "Daily", ""),
    "2027-03-09": ("NO SCHOOL", "No School", "Professional Development"),
    "2027-03-10": ("C", "Connect", ""),
    "2027-03-11": ("D", "Daily", ""),
    "2027-03-12": ("A", "Daily", ""),
    "2027-03-15": ("B", "Daily", ""),
    "2027-03-16": ("C", "Daily", ""),
    "2027-03-17": ("D", "Daily", "SAT Testing"),
    "2027-03-18": ("A", "Daily", ""),
    "2027-03-19": ("B", "Daily", ""),
    "2027-03-22": ("C", "Daily", ""),
    "2027-03-23": ("D", "Daily", "End of Q3"),
    "2027-03-24": ("A", "Daily", ""),
    "2027-03-25": ("B", "Daily", ""),
    "2027-03-26": ("NO SCHOOL", "No School", "Good Friday"),
    "2027-03-29": ("C", "Daily", ""),
    "2027-03-30": ("D", "Daily", ""),
    "2027-03-31": ("A", "Daily", ""),
    # April 2027
    "2027-04-01": ("B", "Daily", ""),
    "2027-04-02": ("C", "Daily", ""),
    "2027-04-05": ("D", "Daily", ""),
    "2027-04-06": ("A", "Connect", ""),
    "2027-04-07": ("B", "Daily", ""),
    "2027-04-08": ("C", "Daily", ""),
    "2027-04-09": ("D", "Daily", ""),
    "2027-04-12": ("NO SCHOOL", "No School", "Spring Break"),
    "2027-04-13": ("NO SCHOOL", "No School", "Spring Break"),
    "2027-04-14": ("NO SCHOOL", "No School", "Spring Break"),
    "2027-04-15": ("NO SCHOOL", "No School", "Spring Break"),
    "2027-04-16": ("NO SCHOOL", "No School", "Spring Break"),
    "2027-04-19": ("A", "Daily", ""),
    "2027-04-20": ("B", "Daily", "NGSS Testing"),
    "2027-04-21": ("C", "Early Dismissal", ""),
    "2027-04-22": ("D", "Daily", ""),
    "2027-04-23": ("A", "Daily", ""),
    "2027-04-26": ("B", "Daily", ""),
    "2027-04-27": ("C", "Connect", ""),
    "2027-04-28": ("D", "Daily", ""),
    "2027-04-29": ("A", "Daily", ""),
    "2027-04-30": ("B", "Daily", ""),
    # May 2027
    "2027-05-03": ("C", "Daily", "AP Exams"),
    "2027-05-04": ("D", "Daily", "AP Exams"),
    "2027-05-05": ("A", "Daily", "AP Exams"),
    "2027-05-06": ("B", "Daily", "AP Exams"),
    "2027-05-07": ("C", "Daily", "AP Exams"),
    "2027-05-10": ("D", "Daily", "AP Exams"),
    "2027-05-11": ("A", "Daily", "AP Exams"),
    "2027-05-12": ("B", "Daily", "AP Exams"),
    "2027-05-13": ("C", "Daily", "AP Exams"),
    "2027-05-14": ("D", "Daily", "AP Exams"),
    "2027-05-17": ("A", "Daily", ""),
    "2027-05-18": ("B", "Daily", ""),
    "2027-05-19": ("SPECIAL", "Early Dismissal", "Capstone Day"),
    "2027-05-20": ("C", "Daily", ""),
    "2027-05-21": ("D", "Daily", ""),
    "2027-05-24": ("A", "Daily", ""),
    "2027-05-25": ("B", "Daily", ""),
    "2027-05-26": ("C", "Connect", ""),
    "2027-05-27": ("D", "Daily", ""),
    "2027-05-28": ("X", "X Day", ""),
    "2027-05-31": ("NO SCHOOL", "No School", "Memorial Day"),
    # June 2027
    "2027-06-01": ("X", "X Day", "End of Q4"),
    "2027-06-02": ("EXAMS", "Early Dismissal", "Final Exams"),
    "2027-06-03": ("EXAMS", "Early Dismissal", "Final Exams"),
    "2027-06-04": ("EXAMS", "Early Dismissal", "Final Exams"),
    "2027-06-07": ("EXAMS", "Early Dismissal", "Final Exams (Tentative Last Day)"),
}

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


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_live_shs_sheet_override(date_iso: str) -> Optional[Tuple[str, str, str]]:
    """Attempts to read today's row from the live SHS Google Sheet if accessible."""
    try:
        req = urllib.request.Request(SHS_SHEET_CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            csv_text = resp.read().decode("utf-8", errors="ignore")
        d_obj = datetime.strptime(date_iso, "%Y-%m-%d").date()
        variants = {
            date_iso,
            f"{d_obj.month}/{d_obj.day}/{d_obj.year}",
            f"{d_obj.month:02d}/{d_obj.day:02d}/{d_obj.year}",
            f"{d_obj.month}/{d_obj.day}/{str(d_obj.year)[2:]}",
        }
        for line in csv_text.splitlines():
            parts = [p.strip().strip('"') for p in line.split(",")]
            if any(v in parts for v in variants):
                joined = " ".join(parts).upper()
                if "NO SCHOOL" in joined:
                    return ("NO SCHOOL", "No School", "Live Sheet Update")
                letter = ""
                for tok in parts:
                    t_clean = tok.strip().upper().replace("DAY", "").strip()
                    if t_clean in ("A", "B", "C", "D", "X"):
                        letter = t_clean
                        break
                if letter:
                    sched = "X Day" if letter == "X" else "Daily"
                    if "2 HOUR" in joined or "DELAY" in joined:
                        sched = "X Day 2 Hour Delay" if letter == "X" else "2 Hour Delay"
                    elif "EMERGENCY" in joined:
                        sched = "Emergency Early Dismissal"
                    elif "EARLY" in joined:
                        sched = "X Day Early Dismissal" if letter == "X" else "Early Dismissal"
                    elif "CONNECT" in joined:
                        sched = "Connect"
                    return (letter, sched, "Live Sheet")
    except Exception:
        pass
    return None


def get_shs_day_info(target_date: date) -> Dict[str, str]:
    iso = target_date.isoformat()
    if target_date.weekday() >= 5:
        return {"letter": "WEEKEND", "schedule": "No School", "note": "Weekend"}
    live = fetch_live_shs_sheet_override(iso)
    if live:
        return {"letter": live[0], "schedule": live[1], "note": live[2]}
    if iso in SHS_CALENDAR_2026_2027:
        l_day, s_type, note = SHS_CALENDAR_2026_2027[iso]
        return {"letter": l_day, "schedule": s_type, "note": note}
    return {"letter": "A", "schedule": "Daily", "note": ""}


def build_shs_bell_blocks(letter_day: str, schedule_type: str, lunch_wave: str, period_classes: Dict[str, str]) -> List[Dict[str, str]]:
    """Builds exact period-by-period bell blocks from all 8 official SHS PDF schedules."""
    l_clean = letter_day if letter_day in ("A", "B", "C", "D") else "A"
    rot = SHS_ROTATIONS[l_clean]

    def _cls(p_num: int) -> str:
        c_name = str(period_classes.get(str(p_num), "")).strip()
        return c_name if c_name else f"Period {p_num}"

    def _lunch_split(p_num: int, l1: Tuple[str, str], c1: Tuple[str, str],
                     c2a: Tuple[str, str], l2: Tuple[str, str], c2b: Tuple[str, str],
                     c3: Tuple[str, str], l3: Tuple[str, str]) -> List[Dict[str, str]]:
        cname = _cls(p_num)
        if lunch_wave == "L1":
            return [
                {"label": "Lunch Wave 1", "class_name": "Lunch (L1)", "start": l1[0], "end": l1[1], "mins": "30m", "is_lunch": "1"},
                {"label": f"Period {p_num}", "class_name": cname, "start": c1[0], "end": c1[1], "mins": "56-60m", "is_lunch": "0"},
            ]
        elif lunch_wave == "L3":
            return [
                {"label": f"Period {p_num}", "class_name": cname, "start": c3[0], "end": c3[1], "mins": "56-60m", "is_lunch": "0"},
                {"label": "Lunch Wave 3", "class_name": "Lunch (L3)", "start": l3[0], "end": l3[1], "mins": "30m", "is_lunch": "1"},
            ]
        else:  # L2 default
            return [
                {"label": f"Period {p_num} (Part 1)", "class_name": cname, "start": c2a[0], "end": c2a[1], "mins": "26-28m", "is_lunch": "0"},
                {"label": "Lunch Wave 2", "class_name": "Lunch (L2)", "start": l2[0], "end": l2[1], "mins": "30m", "is_lunch": "1"},
                {"label": f"Period {p_num} (Part 2)", "class_name": cname, "start": c2b[0], "end": c2b[1], "mins": "26-28m", "is_lunch": "0"},
            ]

    if schedule_type == "Connect":
        blocks = [
            {"label": f"Period {rot[0]}", "class_name": _cls(rot[0]), "start": "7:32 AM", "end": "8:23 AM", "mins": "51m", "is_lunch": "0"},
            {"label": f"Period {rot[1]}", "class_name": _cls(rot[1]), "start": "8:27 AM", "end": "9:18 AM", "mins": "51m", "is_lunch": "0"},
            {"label": "CONNECT", "class_name": "Connect / Announcements", "start": "9:22 AM", "end": "9:53 AM", "mins": "31m", "is_lunch": "0"},
            {"label": f"Period {rot[2]}", "class_name": _cls(rot[2]), "start": "9:57 AM", "end": "10:48 AM", "mins": "51m", "is_lunch": "0"},
        ]
        blocks.extend(_lunch_split(
            rot[3],
            ("10:50 AM", "11:20 AM"), ("11:24 AM", "12:20 PM"),
            ("10:52 AM", "11:18 AM"), ("11:20 AM", "11:50 AM"), ("11:54 AM", "12:20 PM"),
            ("10:52 AM", "11:48 AM"), ("11:50 AM", "12:20 PM"),
        ))
        blocks.extend([
            {"label": f"Period {rot[4]}", "class_name": _cls(rot[4]), "start": "12:24 PM", "end": "1:15 PM", "mins": "51m", "is_lunch": "0"},
            {"label": f"Period {rot[5]}", "class_name": _cls(rot[5]), "start": "1:19 PM", "end": "2:10 PM", "mins": "51m", "is_lunch": "0"},
        ])
        return blocks

    if schedule_type == "2 Hour Delay":
        blocks = [
            {"label": f"Period {rot[0]}", "class_name": _cls(rot[0]), "start": "9:32 AM", "end": "10:06 AM", "mins": "34m", "is_lunch": "0"},
            {"label": f"Period {rot[1]}", "class_name": _cls(rot[1]), "start": "10:10 AM", "end": "10:44 AM", "mins": "34m", "is_lunch": "0"},
            {"label": f"Period {rot[2]}", "class_name": _cls(rot[2]) + " (Ann.)", "start": "10:48 AM", "end": "11:24 AM", "mins": "34m", "is_lunch": "0"},
        ]
        blocks.extend(_lunch_split(
            rot[3],
            ("11:24 AM", "11:54 AM"), ("11:58 AM", "12:54 PM"),
            ("11:28 AM", "11:54 AM"), ("11:54 AM", "12:24 PM"), ("12:28 PM", "12:54 PM"),
            ("11:28 AM", "12:24 PM"), ("12:24 PM", "12:54 PM"),
        ))
        blocks.extend([
            {"label": f"Period {rot[4]}", "class_name": _cls(rot[4]), "start": "12:58 PM", "end": "1:32 PM", "mins": "34m", "is_lunch": "0"},
            {"label": f"Period {rot[5]}", "class_name": _cls(rot[5]), "start": "1:36 PM", "end": "2:10 PM", "mins": "34m", "is_lunch": "0"},
        ])
        return blocks

    if schedule_type == "Early Dismissal":
        times_ed = [("7:32 AM", "8:05 AM", "33m"), ("8:09 AM", "8:42 AM", "33m"), ("8:46 AM", "9:24 AM", "38m"),
                    ("9:28 AM", "10:01 AM", "33m"), ("10:05 AM", "10:38 AM", "33m"), ("10:42 AM", "11:15 AM", "33m")]
        return [
            {"label": f"Period {rot[idx]}", "class_name": _cls(rot[idx]) + (" (Ann.)" if idx == 2 else ""), "start": t[0], "end": t[1], "mins": t[2], "is_lunch": "0"}
            for idx, t in enumerate(times_ed)
        ]

    if schedule_type == "Emergency Early Dismissal":
        times_eed = [("7:32 AM", "8:25 AM", "53m"), ("8:29 AM", "8:57 AM", "28m"), ("9:01 AM", "9:29 AM", "28m"),
                     ("9:33 AM", "10:01 AM", "28m"), ("10:05 AM", "10:33 AM", "28m"), ("10:37 AM", "11:05 AM", "28m")]
        blocks = [
            {"label": f"Period {rot[idx]}", "class_name": _cls(rot[idx]) + (" (Ann.)" if idx == 1 else ""), "start": t[0], "end": t[1], "mins": t[2], "is_lunch": "0"}
            for idx, t in enumerate(times_eed)
        ]
        blocks.append({"label": "Express Lunch", "class_name": "Express Lunch Pick Up", "start": "11:05 AM", "end": "11:15 AM", "mins": "10m", "is_lunch": "1"})
        return blocks

    if schedule_type == "X Day":
        blocks = [
            {"label": "Period 1", "class_name": _cls(1), "start": "7:32 AM", "end": "8:12 AM", "mins": "40m", "is_lunch": "0"},
            {"label": "Period 2", "class_name": _cls(2), "start": "8:16 AM", "end": "8:56 AM", "mins": "40m", "is_lunch": "0"},
            {"label": "Period 3", "class_name": _cls(3) + " (Ann.)", "start": "9:00 AM", "end": "9:42 AM", "mins": "42m", "is_lunch": "0"},
            {"label": "Period 4", "class_name": _cls(4), "start": "9:46 AM", "end": "10:26 AM", "mins": "40m", "is_lunch": "0"},
            {"label": "Period 5", "class_name": _cls(5), "start": "10:30 AM", "end": "11:10 AM", "mins": "40m", "is_lunch": "0"},
        ]
        blocks.extend(_lunch_split(
            6,
            ("11:12 AM", "11:42 AM"), ("11:46 AM", "12:42 PM"),
            ("11:14 AM", "11:40 AM"), ("11:42 AM", "12:12 PM"), ("12:16 PM", "12:42 PM"),
            ("11:14 AM", "12:10 PM"), ("12:12 PM", "12:42 PM"),
        ))
        blocks.extend([
            {"label": "Period 7", "class_name": _cls(7), "start": "12:46 PM", "end": "1:26 PM", "mins": "40m", "is_lunch": "0"},
            {"label": "Period 8", "class_name": _cls(8), "start": "1:30 PM", "end": "2:10 PM", "mins": "40m", "is_lunch": "0"},
        ])
        return blocks

    if schedule_type == "X Day 2 Hour Delay":
        blocks = [
            {"label": "Period 1", "class_name": _cls(1), "start": "9:32 AM", "end": "9:55 AM", "mins": "23m", "is_lunch": "0"},
            {"label": "Period 2", "class_name": _cls(2), "start": "9:59 AM", "end": "10:22 AM", "mins": "23m", "is_lunch": "0"},
            {"label": "Period 3", "class_name": _cls(3) + " (Ann.)", "start": "10:26 AM", "end": "10:50 AM", "mins": "24m", "is_lunch": "0"},
            {"label": "Period 4", "class_name": _cls(4), "start": "10:54 AM", "end": "11:17 AM", "mins": "23m", "is_lunch": "0"},
            {"label": "Period 5", "class_name": _cls(5), "start": "11:21 AM", "end": "11:44 AM", "mins": "23m", "is_lunch": "0"},
        ]
        blocks.extend(_lunch_split(
            6,
            ("11:46 AM", "12:16 PM"), ("12:20 PM", "1:16 PM"),
            ("11:48 AM", "12:14 PM"), ("12:16 PM", "12:46 PM"), ("12:50 PM", "1:16 PM"),
            ("11:48 AM", "12:44 PM"), ("12:46 PM", "1:16 PM"),
        ))
        blocks.extend([
            {"label": "Period 7", "class_name": _cls(7), "start": "1:20 PM", "end": "1:43 PM", "mins": "23m", "is_lunch": "0"},
            {"label": "Period 8", "class_name": _cls(8), "start": "1:47 PM", "end": "2:10 PM", "mins": "23m", "is_lunch": "0"},
        ])
        return blocks

    if schedule_type == "X Day Early Dismissal":
        times_xed = [("7:32 AM", "7:56 AM", "24m"), ("8:00 AM", "8:24 AM", "24m"), ("8:28 AM", "8:55 AM", "27m"),
                     ("8:59 AM", "9:23 AM", "24m"), ("9:27 AM", "9:51 AM", "24m"), ("9:55 AM", "10:19 AM", "24m"),
                     ("10:23 AM", "10:47 AM", "24m"), ("10:51 AM", "11:15 AM", "24m")]
        return [
            {"label": f"Period {idx + 1}", "class_name": _cls(idx + 1) + (" (Ann.)" if idx == 2 else ""), "start": t[0], "end": t[1], "mins": t[2], "is_lunch": "0"}
            for idx, t in enumerate(times_xed)
        ]

    # Default: Daily Schedule
    blocks = [
        {"label": f"Period {rot[0]}", "class_name": _cls(rot[0]), "start": "7:32 AM", "end": "8:29 AM", "mins": "57m", "is_lunch": "0"},
        {"label": f"Period {rot[1]}", "class_name": _cls(rot[1]) + " (Ann.)", "start": "8:33 AM", "end": "9:31 AM", "mins": "58m", "is_lunch": "0"},
        {"label": f"Period {rot[2]}", "class_name": _cls(rot[2]), "start": "9:35 AM", "end": "10:32 AM", "mins": "57m", "is_lunch": "0"},
    ]
    blocks.extend(_lunch_split(
        rot[3],
        ("10:34 AM", "11:04 AM"), ("11:08 AM", "12:08 PM"),
        ("10:36 AM", "11:04 AM"), ("11:06 AM", "11:36 AM"), ("11:40 AM", "12:08 PM"),
        ("10:36 AM", "11:36 AM"), ("11:38 AM", "12:08 PM"),
    ))
    blocks.extend([
        {"label": f"Period {rot[4]}", "class_name": _cls(rot[4]), "start": "12:12 PM", "end": "1:09 PM", "mins": "57m", "is_lunch": "0"},
        {"label": f"Period {rot[5]}", "class_name": _cls(rot[5]), "start": "1:13 PM", "end": "2:10 PM", "mins": "57m", "is_lunch": "0"},
    ])
    return blocks


# -----------------------
# Database Engine & Thread-Safe Background Worker
# -----------------------
def get_connection_url() -> str:
    url = ""
    if "postgres" in st.secrets and "url" in st.secrets["postgres"]:
        url = st.secrets["postgres"]["url"]
    elif "connections" in st.secrets and "neon" in st.secrets["connections"]:
        url = st.secrets["connections"]["neon"]["url"]
    else:
        raise ValueError("Missing PostgreSQL database URL in secrets configuration.")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


@st.cache_resource
def get_db_engine():
    return create_engine(get_connection_url(), pool_pre_ping=True, pool_size=5, max_overflow=10)


@st.cache_resource
def get_db_write_lock() -> threading.Lock:
    return threading.Lock()


engine = get_db_engine()
db_write_lock = get_db_write_lock()


def _run_bg_sql(worker_fn: Callable[..., None], *args: Any, **kwargs: Any) -> None:
    def _target():
        with db_write_lock:
            try:
                worker_fn(*args, **kwargs)
            except Exception:
                pass
    threading.Thread(target=_target, daemon=True).start()


@st.cache_resource
def init_db_once():
    with engine.begin() as conn:
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
                title TEXT,
                course TEXT,
                due_date TEXT,
                status TEXT,
                priority INTEGER,
                atype TEXT,
                eta TEXT,
                notes TEXT,
                created_at TEXT
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
    return True


try:
    init_db_once()
except Exception as e:
    st.error(f"Database Connection Error: {e}")


# -----------------------
# Helper Utilities
# -----------------------
def format_mins_to_hrs_mins(mins: int) -> str:
    if mins <= 0:
        return "0 mins"
    h, m = mins // 60, mins % 60
    if h == 0:
        return f"{m} mins"
    if m == 0:
        return f"{h} hr" if h == 1 else f"{h} hrs"
    return f"{h} hr {m} mins" if h == 1 else f"{h} hrs {m} mins"


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
        elif c == "OTHER":
            bg, fg, border = "#e0e7ff", "#3730a3", "#818cf8"
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
        elif c == "OTHER":
            bg, fg, border = "#312e81", "#c7d2fe", "#4f46e5"
        else:
            bg, fg, border = "#0c4a6e", "#7dd3fc", "#0284c7"

    return (
        f"<span style='background-color:{bg}; color:{fg} !important; border:1.5px solid {border}; "
        f"padding:3px 9px; border-radius:6px; font-weight:800; font-size:0.73rem; letter-spacing:0.03em; display:inline-block;'>{c}</span>"
    )


def priority_to_label(val: Any) -> str:
    if pd.isna(val) or val is None:
        return "Medium"
    if isinstance(val, (int, float)):
        v = int(val)
        return "Low" if v <= 3 else ("Medium" if v <= 7 else "High")
    s = str(val).strip().title()
    if s in PRIORITY_OPTIONS:
        return s
    return priority_to_label(int(s)) if s.isdigit() else "Medium"


def priority_to_int(label_or_val: Any) -> int:
    if isinstance(label_or_val, (int, float)):
        return max(1, min(10, int(label_or_val)))
    return {"Low": 2, "Medium": 5, "High": 9}.get(str(label_or_val).strip().title(), 5)


def format_priority_display(val: Any, mode: str) -> str:
    p_num = priority_to_int(val)
    p_label = priority_to_label(p_num)
    if mode == "1 to 10 Scale (Slider)":
        return f"{p_num}/10"
    if mode == "Both Systems":
        return f"{p_label} ({p_num}/10)"
    return p_label


def parse_eta_to_mins(eta_raw: Any) -> int:
    if not eta_raw or pd.isna(eta_raw):
        return 30
    s = str(eta_raw).lower().strip()
    nums = [int(n) for n in re.findall(r"\d+", s)]
    if not nums:
        return 30
    return max(15, nums[0] * 60) if ("hr" in s or "hour" in s) else max(10, nums[0])


def is_study_task(atype: str, title: str, notes: str) -> bool:
    content = f"{atype} {title} {notes}".lower()
    return any(kw in content for kw in ["study", "studying", "review", "prep", "prepping", "practice", "flashcard", "quiz", "test", "exam"])


def is_daily_recurring_task(eta_raw: Any, title: str, notes: str) -> bool:
    content = f"{str(eta_raw)} {title} {notes}".lower()
    return any(kw in content for kw in ["/day", "per day", "a day", "daily", "every day", "each day", "per-day", "/ d"])


def format_study_display_title(raw_title: str) -> str:
    t_lower = raw_title.lower()
    return raw_title if any(w in t_lower for w in ["study", "review", "prep", "practice", "flashcard"]) else f"Study for {raw_title}"


def encode_uploaded_photo_to_data_uri(uploaded_file: Any) -> str:
    raw_bytes = uploaded_file.getvalue()
    if HAS_PIL:
        try:
            img = Image.open(io.BytesIO(raw_bytes))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            if max(img.size) > 1280:
                img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=72, optimize=True)
            return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
        except Exception:
            pass
    mime = getattr(uploaded_file, "type", "image/jpeg") or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(raw_bytes).decode('ascii')}"


def _cfg_uuid(prefix: str, user_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{prefix}_{user_id}"))


def _pack_notes(notes_text: str, prev_status: str) -> str:
    return json.dumps({"text": notes_text, "prev_status": prev_status})


def _unpack_notes(raw_notes: Any) -> Tuple[str, str]:
    if not raw_notes or pd.isna(raw_notes):
        return ("", "Not Started")
    try:
        data = json.loads(str(raw_notes))
        if isinstance(data, dict):
            return (data.get("text", ""), data.get("prev_status", "Not Started"))
    except Exception:
        pass
    return (str(raw_notes), "Not Started")


def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# -----------------------
# Single-Query Hydration & Background DB Writers
# -----------------------
def clear_all_session_caches():
    for k in [
        "df_cached", "cfg_courses", "cfg_schedule", "cfg_prio_mode",
        "cfg_max_work", "cfg_completed_slots", "cfg_completed_slots_date",
        "cfg_seen_updates", "cfg_theme", "cfg_shs", "_ai_plan_result",
        "_undo_slot_state", "_hydrated_uid", "_pending_edit_aid"
    ]:
        st.session_state.pop(k, None)


def _db_purge_ids_worker(user_id: str, expired_ids: List[str]) -> None:
    if not expired_ids:
        return
    sql = text("DELETE FROM assignments WHERE user_id = :uid AND id = :id")
    with engine.begin() as conn:
        for aid in expired_ids:
            conn.execute(sql, {"uid": user_id, "id": aid})


def _db_upsert_config_worker(cfg_id: str, user_id: str, sys_title: str, notes_payload: str, created_at: str) -> None:
    sql = text("""
        INSERT INTO assignments (id, user_id, title, course, due_date, status, priority, atype, eta, notes, created_at)
        VALUES (:id, :user_id, :title, 'CONFIG', '', 'Not Started', 0, 'Other', '', :notes, :created_at)
        ON CONFLICT (id) DO UPDATE SET notes = EXCLUDED.notes, user_id = EXCLUDED.user_id;
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"id": cfg_id, "user_id": user_id, "title": sys_title, "notes": notes_payload, "created_at": created_at})


def _db_upsert_assignments_worker(db_rows: List[Dict[str, Any]]) -> None:
    if not db_rows:
        return
    sql = text("""
        INSERT INTO assignments (id, user_id, title, course, due_date, status, priority, atype, eta, notes, created_at)
        VALUES (:id, :user_id, :title, :course, :due_date, :status, :priority, :atype, :eta, :notes, :created_at)
        ON CONFLICT (id) DO UPDATE SET
            user_id = EXCLUDED.user_id, title = EXCLUDED.title, course = EXCLUDED.course,
            due_date = EXCLUDED.due_date, status = EXCLUDED.status, priority = EXCLUDED.priority,
            atype = EXCLUDED.atype, eta = EXCLUDED.eta, notes = EXCLUDED.notes, created_at = EXCLUDED.created_at;
    """)
    with engine.begin() as conn:
        for row in db_rows:
            conn.execute(sql, row)


def _db_delete_assignment_worker(assignment_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM assignments WHERE id = :id"), {"id": assignment_id})


def hydrate_user_session(user_id: str, force: bool = False) -> None:
    if not force and st.session_state.get("_hydrated_uid") == user_id:
        return

    today_iso = get_local_now().date().isoformat()
    with engine.connect() as conn:
        raw_rows = conn.execute(text("SELECT * FROM assignments WHERE user_id = :uid"), {"uid": user_id}).mappings().all()

    courses: List[str] = []
    schedule: List[Dict[str, Any]] = []
    prio_mode: Optional[str] = None
    max_work: Dict[str, int] = {d: 60 for d in DAYS_OF_WEEK}
    completed_slots: Dict[str, Dict[str, Any]] = {}
    seen_updates_ver: str = ""
    theme_cfg: Dict[str, Any] = dict(DEFAULT_THEME_CONFIG)
    shs_cfg: Dict[str, Any] = {
        "lunches": {"A": "L2", "B": "L2", "C": "L2", "D": "L2", "X": "L2"},
        "periods": {str(i): "" for i in range(1, 9)},
    }

    assignment_rows: List[Dict[str, Any]] = []
    expired_done_ids: List[str] = []

    for r in raw_rows:
        r_title = str(r.get("title") or "")
        r_notes = r.get("notes")

        if r_title == "__SYSTEM_COURSES__":
            try:
                parsed = json.loads(str(r_notes or "[]"))
                if isinstance(parsed, list):
                    courses = parsed
            except Exception:
                pass
        elif r_title == "__SYSTEM_SCHEDULE__":
            try:
                parsed = json.loads(str(r_notes or "[]"))
                if isinstance(parsed, list):
                    schedule = parsed
            except Exception:
                pass
        elif r_title == "__SYSTEM_PRIO_CONFIG__":
            val = str(r_notes or "").strip()
            if val in PRIORITY_SYSTEM_MODES:
                prio_mode = val
        elif r_title == "__SYSTEM_MAX_WORK_CONFIG__":
            try:
                parsed = json.loads(str(r_notes or "{}"))
                if isinstance(parsed, dict):
                    for d in DAYS_OF_WEEK:
                        if d in parsed and isinstance(parsed[d], int):
                            max_work[d] = parsed[d]
            except Exception:
                pass
        elif r_title == "__SYSTEM_COMPLETED_SLOTS__":
            try:
                parsed = json.loads(str(r_notes or "{}"))
                if isinstance(parsed, dict) and isinstance(parsed.get(today_iso), dict):
                    completed_slots = parsed[today_iso]
            except Exception:
                pass
        elif r_title == "__SYSTEM_SEEN_UPDATES__":
            seen_updates_ver = str(r_notes or "").strip()
        elif r_title == "__SYSTEM_THEME_CONFIG__":
            try:
                parsed = json.loads(str(r_notes or "{}"))
                if isinstance(parsed, dict):
                    theme_cfg.update(parsed)
            except Exception:
                pass
        elif r_title == "__SYSTEM_SHS_CONFIG__":
            try:
                parsed = json.loads(str(r_notes or "{}"))
                if isinstance(parsed, dict):
                    if "lunch" in parsed and "lunches" not in parsed:
                        old_l = parsed["lunch"] if parsed["lunch"] in ("L1", "L2", "L3") else "L2"
                        shs_cfg["lunches"] = {k: old_l for k in ("A", "B", "C", "D", "X")}
                    shs_cfg.update(parsed)
            except Exception:
                pass
        elif r_title not in SYSTEM_TITLES:
            status_val = str(r.get("status") or "Not Started")
            due_val = str(r.get("due_date") or "")
            aid_val = str(r.get("id"))
            if status_val == "Done" and due_val and due_val < today_iso:
                expired_done_ids.append(aid_val)
                continue
            n_text, prev_st = _unpack_notes(r_notes)
            assignment_rows.append({
                "id": aid_val, "user_id": str(r.get("user_id")), "title": r_title,
                "course": str(r.get("course") or "GENERAL").strip().upper(),
                "due_date": due_val, "status": status_val,
                "priority": priority_to_int(r.get("priority")),
                "atype": str(r.get("atype") or "Homework"),
                "eta": str(r.get("eta") or ""),
                "created_at": str(r.get("created_at") or ""),
                "notes": n_text, "prev_status": prev_st,
            })

    if expired_done_ids:
        _run_bg_sql(_db_purge_ids_worker, user_id, expired_done_ids)

    cols = ["id", "user_id", "title", "course", "due_date", "status", "priority", "atype", "eta", "created_at", "notes", "prev_status"]
    st.session_state["df_cached"] = pd.DataFrame(assignment_rows) if assignment_rows else pd.DataFrame(columns=cols)
    st.session_state["cfg_courses"] = courses
    st.session_state["cfg_schedule"] = schedule
    st.session_state["cfg_prio_mode"] = prio_mode
    st.session_state["cfg_max_work"] = max_work
    st.session_state["cfg_completed_slots"] = completed_slots
    st.session_state["cfg_completed_slots_date"] = today_iso
    st.session_state["cfg_seen_updates"] = seen_updates_ver
    st.session_state["cfg_theme"] = theme_cfg
    st.session_state["cfg_shs"] = shs_cfg
    st.session_state["_hydrated_uid"] = user_id


# -----------------------
# Instant In-Memory Getters & Optimistic Writers
# -----------------------
def get_courses_cached(user_id: str) -> List[str]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_courses", [])


def _write_courses_file(user_id: str, courses: List[str]) -> None:
    st.session_state["cfg_courses"] = courses
    _run_bg_sql(_db_upsert_config_worker, _cfg_uuid("user_courses_config", user_id), user_id, "__SYSTEM_COURSES__", json.dumps(courses), get_local_now().isoformat())


def get_schedule_cached(user_id: str) -> List[Dict[str, Any]]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_schedule", [])


def _write_schedule_file(user_id: str, schedule: List[Dict[str, Any]]) -> None:
    st.session_state["cfg_schedule"] = schedule
    st.session_state.pop("_ai_plan_result", None)
    _run_bg_sql(_db_upsert_config_worker, _cfg_uuid("user_schedule_config", user_id), user_id, "__SYSTEM_SCHEDULE__", json.dumps(schedule), get_local_now().isoformat())


def get_prio_cached(user_id: str) -> Optional[str]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_prio_mode")


def _write_prio_config(user_id: str, mode: str) -> None:
    if mode in PRIORITY_SYSTEM_MODES:
        st.session_state["cfg_prio_mode"] = mode
        _run_bg_sql(_db_upsert_config_worker, _cfg_uuid("user_prio_config", user_id), user_id, "__SYSTEM_PRIO_CONFIG__", mode, get_local_now().isoformat())


def get_seen_updates_cached(user_id: str) -> str:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_seen_updates", "")


def _write_seen_updates(user_id: str, version_str: str) -> None:
    st.session_state["cfg_seen_updates"] = version_str
    _run_bg_sql(_db_upsert_config_worker, _cfg_uuid("user_seen_updates_config", user_id), user_id, "__SYSTEM_SEEN_UPDATES__", version_str, get_local_now().isoformat())


def get_theme_cached(user_id: str) -> Dict[str, Any]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_theme", dict(DEFAULT_THEME_CONFIG))


def _write_theme_config(user_id: str, theme_cfg: Dict[str, Any]) -> None:
    st.session_state["cfg_theme"] = theme_cfg
    _run_bg_sql(_db_upsert_config_worker, _cfg_uuid("user_theme_config", user_id), user_id, "__SYSTEM_THEME_CONFIG__", json.dumps(theme_cfg), get_local_now().isoformat())


def get_shs_cached(user_id: str) -> Dict[str, Any]:
    hydrate_user_session(user_id)
    default_lunches = {"A": "L2", "B": "L2", "C": "L2", "D": "L2", "X": "L2"}
    cfg = st.session_state.get("cfg_shs", {"lunches": dict(default_lunches), "periods": {str(i): "" for i in range(1, 9)}})
    if "lunches" not in cfg:
        old_l = cfg.get("lunch", "L2")
        cfg["lunches"] = {k: old_l for k in ("A", "B", "C", "D", "X")}
    return cfg


def _write_shs_config(user_id: str, shs_cfg: Dict[str, Any]) -> None:
    st.session_state["cfg_shs"] = shs_cfg
    _run_bg_sql(_db_upsert_config_worker, _cfg_uuid("user_shs_config", user_id), user_id, "__SYSTEM_SHS_CONFIG__", json.dumps(shs_cfg), get_local_now().isoformat())


def get_max_work_cached(user_id: str) -> Dict[str, int]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_max_work", {d: 60 for d in DAYS_OF_WEEK})


def _write_max_work_config(user_id: str, max_mins_dict: Dict[str, int]) -> None:
    st.session_state["cfg_max_work"] = max_mins_dict
    st.session_state.pop("_ai_plan_result", None)
    _run_bg_sql(_db_upsert_config_worker, _cfg_uuid("user_max_work_config", user_id), user_id, "__SYSTEM_MAX_WORK_CONFIG__", json.dumps(max_mins_dict), get_local_now().isoformat())


def get_completed_slots_cached(user_id: str) -> Dict[str, Dict[str, Any]]:
    hydrate_user_session(user_id)
    today_str = get_local_now().date().isoformat()
    if st.session_state.get("cfg_completed_slots_date") != today_str:
        st.session_state["cfg_completed_slots"] = {}
        st.session_state["cfg_completed_slots_date"] = today_str
    return st.session_state.get("cfg_completed_slots", {})


def _write_completed_slots(user_id: str, today_slots: Dict[str, Dict[str, Any]]) -> None:
    today_str = get_local_now().date().isoformat()
    st.session_state["cfg_completed_slots"] = today_slots
    st.session_state["cfg_completed_slots_date"] = today_str
    _run_bg_sql(_db_upsert_config_worker, _cfg_uuid("user_completed_slots_config", user_id), user_id, "__SYSTEM_COMPLETED_SLOTS__", json.dumps({today_str: today_slots}), get_local_now().isoformat())


def get_assignments_cached(user_id: str) -> pd.DataFrame:
    hydrate_user_session(user_id)
    return st.session_state["df_cached"]


def upsert_assignments(rows_to_upsert: List[Dict[str, Any]]) -> None:
    if not rows_to_upsert:
        return
    normalized_rows, db_payloads = [], []
    for row in rows_to_upsert:
        n_text = str(row.get("notes", "")).strip()
        prev_st = str(row.get("prev_status", "Not Started"))
        clean_row = {
            "id": str(row.get("id")), "user_id": str(row.get("user_id")),
            "title": str(row.get("title", "")).strip() or "Untitled Assignment",
            "course": str(row.get("course", "GENERAL")).strip().upper(),
            "due_date": str(row.get("due_date") or ""),
            "status": str(row.get("status", "Not Started")),
            "priority": priority_to_int(row.get("priority")),
            "atype": str(row.get("atype", "Homework")),
            "eta": str(row.get("eta", "")).strip(),
            "notes": n_text,
            "created_at": str(row.get("created_at") or get_local_now().isoformat()),
            "prev_status": prev_st,
        }
        normalized_rows.append(clean_row)
        db_payloads.append({**clean_row, "notes": _pack_notes(n_text, prev_st)})

    if "df_cached" in st.session_state:
        df = st.session_state["df_cached"]
        for c_row in normalized_rows:
            if df.empty:
                df = pd.DataFrame([c_row])
            elif (df["id"] == c_row["id"]).any():
                idx = df.index[df["id"] == c_row["id"]][0]
                for col, val in c_row.items():
                    df.at[idx, col] = val
            else:
                df = pd.concat([df, pd.DataFrame([c_row])], ignore_index=True)
        st.session_state["df_cached"] = df

    st.session_state.pop("_ai_plan_result", None)
    _run_bg_sql(_db_upsert_assignments_worker, db_payloads)


def delete_assignment(assignment_id: str) -> None:
    if "df_cached" in st.session_state and not st.session_state["df_cached"].empty:
        df = st.session_state["df_cached"]
        st.session_state["df_cached"] = df[df["id"] != assignment_id].reset_index(drop=True)
    st.session_state.pop("_ai_plan_result", None)
    _run_bg_sql(_db_delete_assignment_worker, assignment_id)


def restore_single_assignment(row_dict: Dict[str, Any]):
    aid = str(row_dict.get("id"))
    prev_st = row_dict.get("prev_status") or "In Progress"
    if prev_st == "Done":
        prev_st = "In Progress"
    row_dict["status"] = prev_st
    upsert_assignments([row_dict])
    for key in list(st.session_state.keys()):
        if aid in key:
            if "chk_done" in key:
                st.session_state[key] = False
            elif "status_sel" in key:
                st.session_state[key] = prev_st# -----------------------
# Authentication Handlers
# -----------------------
def sign_up_user(email: str, password: str) -> Dict[str, Any]:
    email_clean = email.lower().strip()
    user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, email_clean))
    with engine.begin() as conn:
        if conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email_clean}).fetchone():
            return {"error": "User with this email already exists."}
        conn.execute(
            text("INSERT INTO users (id, email, password_hash, created_at) VALUES (:id, :email, :password_hash, :created_at)"),
            {"id": user_id, "email": email_clean, "password_hash": _hash_pw(password.strip()), "created_at": get_local_now().isoformat()},
        )
    return {"data": {"id": user_id, "email": email_clean}}


def sign_in_user(email: str, password: str) -> Dict[str, Any]:
    email_clean = email.lower().strip()
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id, email, password_hash FROM users WHERE email = :email"), {"email": email_clean}).fetchone()
        if not row or row.password_hash != _hash_pw(password.strip()):
            return {"error": "Invalid email or password."}
        return {"data": {"id": row.id, "email": row.email}}


def sign_out_user() -> None:
    clear_all_session_caches()
    st.session_state.pop("user", None)
    safe_rerun("app")


# -----------------------
# Instant Fragment Callbacks
# -----------------------
def on_checkbox_toggle(aid: str, chk_key: str, sel_key: str):
    chk_val = st.session_state.get(chk_key, False)
    df = st.session_state.get("df_cached")
    if df is None or df.empty or not (df["id"] == aid).any():
        return
    row_dict = df.loc[df["id"] == aid].iloc[0].to_dict()
    current_st = row_dict.get("status", "Not Started")
    if chk_val:
        if current_st != "Done":
            row_dict["prev_status"] = current_st
            st.session_state[f"prev_st_{aid}"] = current_st
        new_status = "Done"
    else:
        prev_st = st.session_state.get(f"prev_st_{aid}") or row_dict.get("prev_status", "In Progress")
        new_status = "In Progress" if (prev_st == "Done" or not prev_st) else prev_st
    row_dict["status"] = new_status
    st.session_state[sel_key] = new_status
    upsert_assignments([row_dict])


def on_status_change(aid: str, sel_key: str, chk_key: str):
    new_status = st.session_state.get(sel_key)
    df = st.session_state.get("df_cached")
    if not new_status or df is None or df.empty or not (df["id"] == aid).any():
        return
    row_dict = df.loc[df["id"] == aid].iloc[0].to_dict()
    if new_status != "Done":
        row_dict["prev_status"] = new_status
        st.session_state[f"prev_st_{aid}"] = new_status
    row_dict["status"] = new_status
    st.session_state[chk_key] = (new_status == "Done")
    upsert_assignments([row_dict])


def on_remove_schedule_block(user_id: str, block_id: str):
    _write_schedule_file(user_id, [item for item in get_schedule_cached(user_id) if item.get("id") != block_id])


def on_daily_slot_check(slot_key: str, task_title: str, slot_dict: Dict[str, Any], user_id: str):
    completed_today = get_completed_slots_cached(user_id).copy()
    completed_today[slot_key] = slot_dict
    _write_completed_slots(user_id, completed_today)
    st.session_state["_undo_slot_state"] = {"slot_key": slot_key, "title": task_title, "user_id": user_id, "time": get_local_now()}


def on_undo_daily_slot(user_id: str):
    undo_info = st.session_state.pop("_undo_slot_state", None)
    if undo_info:
        s_key = undo_info["slot_key"]
        completed_today = get_completed_slots_cached(user_id).copy()
        completed_today.pop(s_key, None)
        _write_completed_slots(user_id, completed_today)
        for k in list(st.session_state.keys()):
            if s_key in k:
                st.session_state[k] = False


def restore_single_daily_slot(slot_key: str, user_id: str):
    completed_today = get_completed_slots_cached(user_id).copy()
    completed_today.pop(slot_key, None)
    _write_completed_slots(user_id, completed_today)
    for k in list(st.session_state.keys()):
        if slot_key in k:
            st.session_state[k] = False


# -----------------------
# Date & Time Helpers + AI Scheduler
# -----------------------
def parse_date_iso_or_empty(s: Any) -> Optional[date]:
    if s is None or pd.isna(s):
        return None
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, date):
        return s
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None


def parse_time_str(t_str: str) -> Optional[time]:
    if not t_str or pd.isna(t_str):
        return None
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(str(t_str).strip().upper(), fmt).time()
        except ValueError:
            pass
    return None


def format_mdy(d: Optional[date]) -> str:
    return (d or get_local_now().date()).strftime("%m/%d/%Y")


def days_left(d: Optional[date]) -> Tuple[str, int]:
    if not d:
        return ("0d", 0)
    delta = (d - get_local_now().date()).days
    return (f"{delta}d left" if delta >= 0 else f"{delta}d overdue", delta)


def generate_ai_study_plan(df_tasks: pd.DataFrame, schedule: List[Dict[str, Any]], max_daily_mins_config: Dict[str, int] | int = 60) -> Dict[str, Any]:
    if df_tasks.empty:
        return {"status": "no_tasks", "plan": {}}
    incomplete = df_tasks[df_tasks["status"] != "Done"].copy()
    if incomplete.empty:
        return {"status": "all_done", "plan": {}}

    now_local = get_local_now()
    today = now_local.date()
    now_mins = now_local.hour * 60 + now_local.minute
    if now_mins % 5 != 0:
        now_mins += (5 - (now_mins % 5))

    task_queue = []
    for _, row in incomplete.iterrows():
        due_d = parse_date_iso_or_empty(row.get("due_date")) or (today + timedelta(days=7))
        days_until = max(0, (due_d - today).days)
        prio_val = priority_to_int(row.get("priority"))
        eta_raw = str(row.get("eta") or "")
        atype = str(row.get("atype") or "Homework")
        title = str(row.get("title") or "Untitled")
        notes = str(row.get("notes") or "")
        is_study = is_study_task(atype, title, notes)
        task_queue.append({
            "id": row.get("id"),
            "title": format_study_display_title(title) if is_study else title,
            "course": row.get("course") or "GENERAL",
            "priority": priority_to_label(prio_val),
            "score": prio_val * (10.0 / max(1, days_until)),
            "eta_mins": parse_eta_to_mins(eta_raw),
            "days_until": days_until,
            "repeat_daily": is_study or is_daily_recurring_task(eta_raw, title, notes),
        })

    task_queue.sort(key=lambda x: x["score"], reverse=True)
    plan = {DAYS_OF_WEEK[(today.weekday() + i) % 7]: {"busy": [], "slots": []} for i in range(7)}

    for i in range(7):
        day_date = today + timedelta(days=i)
        day_name = DAYS_OF_WEEK[day_date.weekday()]
        max_daily_mins = max_daily_mins_config.get(day_name, 60) if isinstance(max_daily_mins_config, dict) else int(max_daily_mins_config)
        default_start = (10 * 60) if day_date.weekday() in (5, 6) else (15 * 60 + 30)
        day_end = (20 * 60) if day_date.weekday() in (5, 6) else (21 * 60)
        day_start = max(default_start, now_mins) if i == 0 else default_start

        busy_intervals = []
        for ev in [s for s in schedule if s.get("day") == day_name]:
            st_t, end_t = parse_time_str(ev.get("start")), parse_time_str(ev.get("end"))
            if st_t and end_t:
                busy_intervals.append((st_t.hour * 60 + st_t.minute, end_t.hour * 60 + end_t.minute))
                plan[day_name]["busy"].append(f"{ev.get('title')} ({ev.get('start')} - {ev.get('end')})")
        busy_intervals.sort(key=lambda x: x[0])

        free_slots, curr = [], day_start
        for b_s, b_e in busy_intervals:
            if b_s > curr and min(b_s, day_end) > curr:
                free_slots.append([curr, min(b_s, day_end)])
            curr = max(curr, b_e)
        if curr < day_end:
            free_slots.append([curr, day_end])

        day_sched_mins, remaining = 0, []
        for t in task_queue:
            target_max_day = max(0, t["days_until"] - 1) if t["days_until"] > 0 else 0
            if i <= target_max_day and day_sched_mins < max_daily_mins:
                scheduled, needed = False, t["eta_mins"]
                for slot in free_slots:
                    if (slot[1] - slot[0]) >= needed:
                        st_m, end_m = slot[0], slot[0] + needed
                        plan[day_name]["slots"].append({
                            "slot_key": f"daily_{t['id']}_{day_date.isoformat()}",
                            "task_id": t["id"], "day_name": day_name, "day_date_str": day_date.isoformat(),
                            "time": f"{time(st_m // 60, st_m % 60).strftime('%I:%M %p').lstrip('0')} - {time(end_m // 60, end_m % 60).strftime('%I:%M %p').lstrip('0')}",
                            "title": t["title"], "course": t["course"], "priority": t["priority"], "eta_mins": needed,
                        })
                        slot[0] = end_m
                        day_sched_mins += needed
                        scheduled = True
                        break
                if not scheduled or t["repeat_daily"]:
                    remaining.append(t)
            else:
                remaining.append(t)
        task_queue = remaining

    return {"status": "success", "plan": plan}


# -----------------------
# Auth Page
# -----------------------
def render_terminal_auth_page():
    st.markdown(build_theme_css(DEFAULT_THEME_CONFIG), unsafe_allow_html=True)
    auth_container = st.empty()
    with auth_container.container():
        _, c_center, _ = st.columns([1, 1.6, 1])
        with c_center:
            st.markdown(
                """
                <div style='background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 32px 28px; text-align: center; margin-bottom: 20px; backdrop-filter: blur(12px); box-shadow: 0 10px 30px rgba(0,0,0,0.5);'>
                    <div style='display:flex; align-items:center; justify-content:center; gap:12px; margin-bottom: 4px;'>
                        <svg width='34' height='34' viewBox='0 0 24 24' fill='none' xmlns='http://www.w3.org/2000/svg'>
                            <rect x='2' y='3' width='12' height='12' rx='2' fill='white' opacity='0.5'/>
                            <rect x='6' y='7' width='12' height='12' rx='2' fill='white' opacity='0.8'/>
                            <rect x='10' y='11' width='12' height='12' rx='2' fill='white'/>
                        </svg>
                        <span style='font-size: 1.9rem; font-weight: 800; color: #ffffff !important; letter-spacing: -0.03em;'>Assignment Tracker</span>
                    </div>
                    <div style='font-size: 0.85rem; color: #94a3b8 !important;'>Simsbury High School Portal</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            mode = st.radio("Action Mode", ["Sign In", "Sign Up"], horizontal=True, label_visibility="collapsed", key="terminal_mode")
            with st.form("auth_credentials_form", clear_on_submit=False):
                raw_user_input = st.text_input("Username or Email", placeholder="e.g. 30guptaa or username@simsburyschools.net", key="terminal_user")
                password = st.text_input("Password", type="password", key="terminal_pw")
                if st.form_submit_button("Sign In" if mode == "Sign In" else "Register Account", use_container_width=True):
                    email_val = raw_user_input.strip()
                    if email_val and "@" not in email_val:
                        email_val = f"{email_val}{DEFAULT_DOMAIN}"
                    password_val = password.strip()
                    if not email_val or not password_val:
                        st.error("Please enter both credentials.")
                    elif mode == "Sign Up":
                        res = sign_up_user(email_val, password_val)
                        if "error" in res:
                            st.error(f"Sign up failed: {res['error']}")
                        else:
                            st.success(f"Registered {email_val}. You can now sign in.")
                    else:
                        res = sign_in_user(email_val, password_val)
                        if "error" in res:
                            st.error(f"Sign in failed: {res['error']}")
                        else:
                            clear_all_session_caches()
                            st.session_state.user = res["data"]
                            hydrate_user_session(res["data"]["id"], force=True)
                            auth_container.empty()
                            safe_rerun("app")


# -----------------------
# Modal Dialogs
# -----------------------
def _valid_hex(val: Any, fallback: str) -> str:
    s = str(val or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", s):
        return s
    return fallback


@dialog_decorator("🎨 Theme & Appearance Studio")
def show_theme_dialog(user_id: str):
    cur = {**DEFAULT_THEME_CONFIG, **get_theme_cached(user_id)}
    preset_names = list(THEME_PRESETS.keys())
    cur_preset = cur.get("preset") if cur.get("preset") in preset_names else preset_names[0]

    st.caption("Switch between Dark & eye-friendly Light modes, choose presets, build custom gradients, or upload a photo background.")

    c1, c2 = st.columns([1.6, 1.0])
    with c1:
        selected_preset = st.selectbox("Theme Preset", options=preset_names, index=preset_names.index(cur_preset), key="theme_preset_sel")
    preset_defaults = THEME_PRESETS[selected_preset]
    preset_changed = (selected_preset != cur_preset)

    default_mode = preset_defaults["mode"] if preset_changed else cur.get("mode", "Dark")
    with c2:
        selected_mode = st.radio("Base Mode", ["Dark", "Light"], index=0 if default_mode == "Dark" else 1, horizontal=True, key="theme_base_mode_radio")

    default_accent = _valid_hex(preset_defaults["accent"] if preset_changed else cur.get("accent", "#6366f1"), "#6366f1")
    c_acc1, c_acc2 = st.columns([1, 2.2])
    with c_acc1:
        selected_accent = st.color_picker("Accent Color", value=default_accent, key="theme_accent_picker")
    with c_acc2:
        btn_txt_c = "#0f172a" if _relative_luminance(selected_accent) > 0.45 else "#ffffff"
        st.markdown(
            f"<div style='margin-top:26px; padding:7px 12px; border-radius:8px; background:{selected_accent}; color:{btn_txt_c} !important; font-weight:800; font-size:0.8rem; text-align:center;'>Accent Preview ({selected_accent})</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    bg_type_map = {"preset": "Preset Theme", "solid": "Custom Solid Color", "gradient": "Custom Gradient", "photo": "Custom Photo Background"}
    rev_bg_map = {v: k for k, v in bg_type_map.items()}
    bg_opts = list(bg_type_map.values())
    cur_bg_label = bg_type_map.get(cur.get("bg_type", "preset"), "Preset Theme")

    selected_bg_type = rev_bg_map[st.radio("Background Style", bg_opts, index=bg_opts.index(cur_bg_label), horizontal=True, key="theme_bg_style_radio")]

    solid_bg_val = _valid_hex(preset_defaults["solid_bg"] if preset_changed else cur.get("solid_bg", "#070a12"), "#070a12")
    grad_1_val = _valid_hex(preset_defaults["grad_1"] if preset_changed else cur.get("grad_1", "#0f172a"), "#0f172a")
    grad_2_val = _valid_hex(preset_defaults["grad_2"] if preset_changed else cur.get("grad_2", "#312e81"), "#312e81")
    grad_3_val = _valid_hex(preset_defaults["grad_3"] if preset_changed else cur.get("grad_3", "#070a12"), "#070a12")
    use_grad_3_val = bool(cur.get("use_grad_3", False))
    grad_angle_val = cur.get("grad_angle", "135deg")
    photo_source_val = cur.get("photo_source", "")
    overlay_opacity_val = int(cur.get("overlay_opacity", 45))
    card_opacity_val = int(cur.get("card_opacity", 88))

    if selected_bg_type == "solid":
        solid_bg_val = st.color_picker("Custom Background Color", value=solid_bg_val, key="theme_solid_picker")
    elif selected_bg_type == "gradient":
        gc1, gc2, gc3 = st.columns(3)
        with gc1:
            grad_1_val = st.color_picker("Gradient Color 1", value=grad_1_val, key="theme_grad1_picker")
        with gc2:
            grad_2_val = st.color_picker("Gradient Color 2", value=grad_2_val, key="theme_grad2_picker")
        with gc3:
            use_grad_3_val = st.checkbox("3rd Color Stop", value=use_grad_3_val, key="theme_use_grad3")
            if use_grad_3_val:
                grad_3_val = st.color_picker("Gradient Color 3", value=grad_3_val, key="theme_grad3_picker")
        angle_opts = ["135deg", "90deg", "180deg", "45deg", "radial"]
        grad_angle_val = st.selectbox("Gradient Direction", options=angle_opts, index=angle_opts.index(grad_angle_val) if grad_angle_val in angle_opts else 0, key="theme_grad_angle_sel")
        stops = f"{grad_1_val}, {grad_2_val}, {grad_3_val}" if use_grad_3_val else f"{grad_1_val}, {grad_2_val}"
        preview_css = f"radial-gradient(circle, {stops})" if grad_angle_val == "radial" else f"linear-gradient({grad_angle_val}, {stops})"
        st.markdown(f"<div style='height:40px; border-radius:10px; background:{preview_css}; border:1.5px solid var(--card-border); margin-top:6px;'></div>", unsafe_allow_html=True)
    elif selected_bg_type == "photo":
        uploaded_photo = st.file_uploader("Upload Custom Photo (JPG, PNG, WEBP)", type=["png", "jpg", "jpeg", "webp"], key="theme_photo_uploader")
        existing_url = "" if str(photo_source_val).startswith("data:") else str(photo_source_val)
        pasted_url = st.text_input("Or Paste Direct Image URL", value=existing_url, placeholder="https://images.unsplash.com/...", key="theme_photo_url_input")
        if uploaded_photo is not None:
            photo_source_val = encode_uploaded_photo_to_data_uri(uploaded_photo)
            st.success("Photo ready! Click 'Apply & Save Theme' below.")
        elif pasted_url.strip():
            photo_source_val = pasted_url.strip()
        overlay_opacity_val = st.slider("Background Tint / Dim Overlay (%) — keeps text readable", min_value=0, max_value=85, value=overlay_opacity_val, key="theme_overlay_slider")

    card_opacity_val = st.slider("Card Surface Opacity (%)", min_value=55, max_value=98, value=card_opacity_val, key="theme_card_opacity_slider")

    b1, b2 = st.columns([2, 1])
    with b1:
        if st.button("Apply & Save Theme", key="save_theme_btn", use_container_width=True):
            _write_theme_config(user_id, {
                "preset": selected_preset, "mode": selected_mode, "accent": selected_accent,
                "bg_type": selected_bg_type, "solid_bg": solid_bg_val,
                "grad_1": grad_1_val, "grad_2": grad_2_val, "grad_3": grad_3_val,
                "use_grad_3": use_grad_3_val, "grad_angle": grad_angle_val,
                "photo_source": photo_source_val, "overlay_opacity": overlay_opacity_val,
                "card_opacity": card_opacity_val,
            })
            safe_rerun("app")
    with b2:
        if st.button("Reset Default", key="reset_theme_btn", use_container_width=True):
            _write_theme_config(user_id, dict(DEFAULT_THEME_CONFIG))
            safe_rerun("app")


@dialog_decorator(f"Welcome to Assignment Tracker v{CURRENT_APP_VERSION}")
def show_updates_dialog(user_id: str, is_first_time: bool = False):
    st.caption("What's new, recent changelog history, and quick tips to get the most out of your tracker.")

    tab_latest, tab_prev, tab_tips = st.tabs(["✨ Latest Updates", "📜 Previous Updates", "💡 Things to Know"])

    with tab_latest:
        st.markdown(
            """
            <div class='update-card'>
                <div style='margin-bottom:5px;'><span class='update-ver-badge'>v3.3 NEW</span> <b>SHS Letter Day & Bell Schedule Tab</b></div>
                <div style='font-size:0.83rem; line-height:1.45;'>
                    Automatically displays today's Simsbury High School letter day (<b>A / B / C / D / X</b>) and supports all 8 SHS schedules (Daily, Connect, 2 Hour Delay, Early Dismissal, Emergency Early Dismissal, and X Day schedules). Map your classes to Periods 1–8 and pick your Lunch Wave!
                </div>
            </div>
            <div class='update-card'>
                <div style='margin-bottom:5px;'><span class='update-ver-badge'>v3.2</span> <b>Theme Studio & Eye-Friendly Light Mode</b></div>
                <div style='font-size:0.83rem; line-height:1.45;'>
                    Customize Dark or low-glare Light modes, 10 color presets, custom solid colors, multi-stop gradients, and personal photo backgrounds from the <b>Theme</b> button.
                </div>
            </div>
            <div class='update-card'>
                <div style='margin-bottom:5px;'><span class='update-ver-badge'>FEEDBACK</span> <b>Built-In Feedback Form</b></div>
                <div style='font-size:0.83rem; line-height:1.45;'>
                    Click <b>Feedback</b> in the top toolbar anytime to report a bug or suggest a new feature.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with tab_prev:
        st.markdown(
            """
            <div class='update-card'>
                <div style='margin-bottom:4px;'><span class='update-old-badge'>v2.5</span> <b>Smart AI Time-Slot Planner & Daily Limits</b></div>
                <div style='font-size:0.81rem; line-height:1.4;'>
                    Automatic daily time-slot scheduling around recurring commitments, per-day study caps, and 15-second Undo toasts.
                </div>
            </div>
            <div class='update-card'>
                <div style='margin-bottom:4px;'><span class='update-old-badge'>v2.0</span> <b>Completed & Recovery Center</b></div>
                <div style='font-size:0.81rem; line-height:1.4;'>
                    Restore accidentally checked-off assignments or daily study slots, with automatic cleanup of past-due finished work.
                </div>
            </div>
            <div class='update-card'>
                <div style='margin-bottom:4px;'><span class='update-old-badge'>v1.5</span> <b>Flexible Priority Scales</b></div>
                <div style='font-size:0.81rem; line-height:1.4;'>
                    Switch between Low / Medium / High badges, a 1–10 numeric slider, or both combined.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with tab_tips:
        st.markdown(
            """
            <div class='tip-card'>
                <b>1. Auto-Repeating Study & Daily Tasks:</b><br/>
                Any task set to <i>Test & Quizzes</i>, containing words like <i>"study"</i>, <i>"review"</i>, or <i>"prep"</i>, or using <b>/day</b> in its duration (e.g. <code>30 mins/day</code>) automatically schedules a session every day leading up to its due date.
            </div>
            <div class='tip-card'>
                <b>2. Map Your SHS Periods:</b><br/>
                Open the <b>SHS Bell Schedule</b> tab to assign your classes to Periods 1–8 and choose Lunch Wave 1, 2, or 3 so your daily bell times show your actual classes.
            </div>
            <div class='tip-card'>
                <b>3. Easy Recovery & Auto-Cleanup:</b><br/>
                Checked-off items stay in <b>Completed & Recovery</b> until their due date passes so you can restore anything anytime.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.button("Got it, Let's Go!" if is_first_time else "Close", key="dismiss_updates_modal_btn", use_container_width=True):
        _write_seen_updates(user_id, CURRENT_APP_VERSION)
        safe_rerun("app")


@dialog_decorator("Welcome! Setup Your Classes")
def show_welcome_courses_dialog(user_id: str):
    st.markdown("### Setup Your Courses")
    courses_input = st.text_area("Enter your subjects (comma separated):", value="MATH, SCIENCE, ENGLISH, HISTORY, OTHER")
    if st.button("Save Schedule", key="save_initial_courses_btn", use_container_width=True):
        parsed = [c.strip().upper() for c in courses_input.replace("\n", ",").split(",") if c.strip()]
        if parsed:
            _write_courses_file(user_id, parsed)
            safe_rerun("app")


@dialog_decorator("Choose Your Priority System")
def show_prio_config_dialog(user_id: str):
    st.markdown("### How would you like to view & set task priorities?")
    current_mode = get_prio_cached(user_id) or "Low / Medium / High"
    prio_choice = st.radio("Select System Preference:", PRIORITY_SYSTEM_MODES, index=PRIORITY_SYSTEM_MODES.index(current_mode) if current_mode in PRIORITY_SYSTEM_MODES else 0, key="prio_modal_radio")
    if st.button("Save Preference", key="save_prio_choice_btn", use_container_width=True):
        _write_prio_config(user_id, prio_choice)
        safe_rerun("app")


@dialog_decorator("Create New Assignment")
def show_add_assignment_dialog(user_id: str, prio_mode: str):
    courses = get_courses_cached(user_id) or ["MATH", "SCIENCE", "ENGLISH", "HISTORY", "OTHER"]
    if "OTHER" not in courses:
        courses = courses + ["OTHER"]

    with st.form("add_assignment_form"):
        title = st.text_input("Assignment Title", key="add_title")
        course_choice = st.selectbox("Course", options=[""] + courses, index=0, key="add_course_choice")
        course_free = st.text_input("Or custom course name", value="", key="add_course_free")
        status = st.selectbox("Status", STATUS_OPTIONS, index=0, key="add_status")
        due = st.date_input("Due Date", value=get_local_now().date(), key="add_due")

        if prio_mode == "1 to 10 Scale (Slider)":
            prio_val_to_save = st.slider("Priority Rating (1 - 10)", 1, 10, 5, key="add_prio_slider")
        elif prio_mode == "Both Systems":
            c1, c2 = st.columns(2)
            with c1:
                p_lbl = st.selectbox("Priority Category", PRIORITY_OPTIONS, index=1, key="add_prio_select")
            with c2:
                prio_val_to_save = st.slider("Priority Rating (1 - 10)", 1, 10, priority_to_int(p_lbl), key="add_prio_slider_both")
        else:
            prio_val_to_save = priority_to_int(st.selectbox("Priority", PRIORITY_OPTIONS, index=1, key="add_prio_select"))

        atype = st.selectbox("Type", TYPE_OPTIONS, index=0, key="add_atype")
        eta = st.text_input("Estimated Duration (e.g. 30 mins/day)", key="add_eta")
        notes = st.text_area("Notes", value="", key="add_notes")

        if st.form_submit_button("Add Assignment"):
            course_val = (course_free.strip() or course_choice or "GENERAL").upper()
            upsert_assignments([{
                "id": str(uuid.uuid4()), "user_id": user_id,
                "title": title.strip() or "Untitled Assignment", "course": course_val,
                "due_date": due.isoformat() if isinstance(due, date) else "",
                "status": status, "priority": prio_val_to_save, "atype": atype,
                "eta": eta.strip(), "created_at": get_local_now().isoformat(),
                "notes": notes.strip(), "prev_status": status if status != "Done" else "Not Started",
            }])
            if course_free.strip():
                c_list = list(get_courses_cached(user_id))
                if course_free.strip().upper() not in c_list:
                    c_list.append(course_free.strip().upper())
                    _write_courses_file(user_id, c_list)
            safe_rerun("app")


@dialog_decorator("Edit Assignment Details")
def show_edit_assignment_dialog(user_id: str, aid: str, prio_mode: str):
    df_current = get_assignments_cached(user_id)
    records = df_current[df_current["id"] == aid].to_dict(orient="records") if not df_current.empty else []
    rec = records[0] if records else None
    if not rec:
        st.warning("Assignment no longer exists.")
        return

    courses = get_courses_cached(user_id) or ["MATH", "SCIENCE", "ENGLISH", "HISTORY", "OTHER"]
    if "OTHER" not in courses:
        courses = courses + ["OTHER"]

    with st.form("edit_assignment_form"):
        title = st.text_input("Assignment Title", value=rec.get("title", ""), key=f"edit_title_{aid}")
        course_choice = st.selectbox("Course", options=[""] + courses, index=(0 if rec.get("course", "") not in courses else courses.index(rec.get("course", "")) + 1), key=f"edit_course_choice_{aid}")
        course_free = st.text_input("Or custom course name", value=rec.get("course", ""), key=f"edit_course_free_{aid}")
        status = st.selectbox("Status", STATUS_OPTIONS, index=(STATUS_OPTIONS.index(rec.get("status")) if rec.get("status") in STATUS_OPTIONS else 0), key=f"edit_status_{aid}")
        due = st.date_input("Due Date", value=parse_date_iso_or_empty(rec.get("due_date")) or get_local_now().date(), key=f"edit_due_{aid}")

        curr_num = priority_to_int(rec.get("priority"))
        curr_lbl = priority_to_label(curr_num)
        if prio_mode == "1 to 10 Scale (Slider)":
            prio_val_to_save = st.slider("Priority Rating (1 - 10)", 1, 10, curr_num, key=f"edit_prio_slider_{aid}")
        elif prio_mode == "Both Systems":
            c1, c2 = st.columns(2)
            with c1:
                st.selectbox("Priority Category", PRIORITY_OPTIONS, index=PRIORITY_OPTIONS.index(curr_lbl), key=f"edit_prio_select_{aid}")
            with c2:
                prio_val_to_save = st.slider("Priority Rating (1 - 10)", 1, 10, curr_num, key=f"edit_prio_slider_both_{aid}")
        else:
            prio_val_to_save = priority_to_int(st.selectbox("Priority", PRIORITY_OPTIONS, index=PRIORITY_OPTIONS.index(curr_lbl), key=f"edit_prio_select_{aid}"))

        atype = st.selectbox("Type", TYPE_OPTIONS, index=(TYPE_OPTIONS.index(rec.get("atype")) if rec.get("atype") in TYPE_OPTIONS else 0), key=f"edit_atype_{aid}")
        eta = st.text_input("Estimated Duration", value=rec.get("eta", ""), key=f"edit_eta_{aid}")
        notes = st.text_area("Notes", value=rec.get("notes", ""), key=f"edit_notes_{aid}")

        c_save, c_del = st.columns(2)
        with c_save:
            updated_click = st.form_submit_button("Save Changes")
        with c_del:
            delete_click = st.form_submit_button("Delete Assignment")

        if updated_click:
            upsert_assignments([{
                "id": aid, "user_id": user_id, "title": title.strip(),
                "course": (course_free.strip() or course_choice or "GENERAL").upper(),
                "due_date": due.isoformat() if isinstance(due, date) else "",
                "status": status, "priority": prio_val_to_save, "atype": atype,
                "eta": eta.strip(), "notes": notes.strip(),
                "created_at": rec.get("created_at") or get_local_now().isoformat(),
                "prev_status": status if status != "Done" else rec.get("prev_status", "Not Started"),
            }])
            safe_rerun("app")
        if delete_click:
            delete_assignment(aid)
            safe_rerun("app")


@dialog_decorator("Manage Courses")
def show_manage_courses_dialog(user_id: str):
    courses = list(get_courses_cached(user_id))
    to_remove = []
    for i, c in enumerate(courses):
        col_a, col_b = st.columns([6, 2])
        with col_a:
            st.write(f"• **{c}**")
        with col_b:
            if st.button("Remove", key=f"remove_course_{i}"):
                to_remove.append(c)
    if to_remove:
        _write_courses_file(user_id, [c for c in courses if c not in to_remove])
        safe_rerun("app")
    st.markdown("---")
    new_course = st.text_input("Add a new course", key="new_course_field")
    if st.button("Add Course", key="add_course_button"):
        v = new_course.strip().upper()
        if v and v not in courses:
            courses.append(v)
            _write_courses_file(user_id, courses)
            safe_rerun("app")


def _save_feedback_entry(user_id: str, email: str, category: str, rating: int, message: str) -> None:
    with engine.begin() as conn:
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
        conn.execute(
            text("""
                INSERT INTO feedback (id, user_id, email, category, rating, message, created_at)
                VALUES (:id, :user_id, :email, :category, :rating, :message, :created_at)
            """),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "email": email,
                "category": category,
                "rating": rating,
                "message": message.strip(),
                "created_at": get_local_now().isoformat(),
            },
        )


@dialog_decorator("💬 Send Feedback")
def show_feedback_dialog(user_id: str, email: str):
    is_admin = (email.lower().strip() == "30guptaa@simsburyschools.net")

    def _render_form():
        st.caption("Found a bug, have a feature idea, or want to share thoughts on the app? Let me know below.")
        with st.form("user_feedback_form", clear_on_submit=True):
            fb_cat = st.selectbox(
                "Category",
                ["Feature Request", "Bug Report", "Theme / Design Idea", "General Feedback"],
                key="fb_category_sel",
            )
            fb_rating = st.slider("Overall Experience (1 - 5)", min_value=1, max_value=5, value=5, key="fb_rating_slider")
            fb_msg = st.text_area(
                "Your Message",
                placeholder="Describe your idea or issue...",
                height=120,
                key="fb_message_input",
            )
            if st.form_submit_button("Submit Feedback", use_container_width=True):
                if not fb_msg.strip():
                    st.error("Please enter a message before submitting.")
                else:
                    _save_feedback_entry(user_id, email, fb_cat, fb_rating, fb_msg)
                    st.success("Thank you! Your feedback has been submitted.")

    if is_admin:
        tab_submit, tab_inbox = st.tabs(["✍️ Submit Feedback", "📥 Admin Inbox"])
        with tab_submit:
            _render_form()
        with tab_inbox:
            try:
                with engine.connect() as conn:
                    rows = conn.execute(text("SELECT * FROM feedback ORDER BY created_at DESC")).mappings().all()
                if not rows:
                    st.info("No feedback submissions yet.")
                else:
                    for r in rows:
                        st.markdown(
                            f"<div class='update-card'>"
                            f"<div style='margin-bottom:4px;'><span class='update-ver-badge'>{r['category']}</span> "
                            f"<b>{r['email']}</b> &bull; Rating: {r['rating']}/5</div>"
                            f"<div style='font-size:0.84rem; margin-top:4px;'>{r['message']}</div>"
                            f"<div class='card-note-text'>{str(r['created_at'])[:16].replace('T', ' ')}</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
            except Exception as e:
                st.error(f"Could not load feedback: {e}")
    else:
        _render_form()# -----------------------
# Isolated @st.fragment Workspaces
# -----------------------
@fragment_decorator
def render_assignment_grid_fragment(user_id: str, view_filter: str, user_prio_mode: str, is_light: bool, key_prefix: str):
    df_all = get_assignments_cached(user_id)
    if view_filter == "regular":
        df_grid = df_all[(df_all["status"] != "Done") & (df_all["atype"] != "Test & Quizzes") & (df_all["atype"] != "Other") & (df_all["course"] != "OTHER")]
    elif view_filter == "tests":
        df_grid = df_all[(df_all["status"] != "Done") & (df_all["atype"] == "Test & Quizzes")]
    else:
        df_grid = df_all[(df_all["status"] != "Done") & ((df_all["atype"] == "Other") | (df_all["course"] == "OTHER"))]

    if df_grid.empty:
        st.markdown("<div style='padding:45px 0; text-align:center; font-size:0.9rem;' class='card-note-text'>No active assignments in this view.</div>", unsafe_allow_html=True)
        return

    df_sorted = df_grid.copy()
    df_sorted["due_parsed"] = df_sorted["due_date"].apply(parse_date_iso_or_empty)
    df_sorted = df_sorted.sort_values(by=["due_parsed", "priority"], ascending=[True, False]).drop(columns=["due_parsed"])

    for row_df in [df_sorted.iloc[i:i + 3] for i in range(0, len(df_sorted), 3)]:
        cols = st.columns(3)
        for idx, (_, row) in enumerate(row_df.iterrows()):
            with cols[idx]:
                with st.container(border=True):
                    aid = row.get("id")
                    title = row.get("title") or "Untitled"
                    course = (row.get("course") or "MATH").upper()
                    atype = row.get("atype") or "Homework"
                    due_d = parse_date_iso_or_empty(row.get("due_date"))
                    due_text = format_mdy(due_d)
                    days_text, _ = days_left(due_d)

                    chk_key = f"{key_prefix}chk_done_{aid}"
                    sel_key = f"{key_prefix}status_sel_{aid}"
                    status = st.session_state.get(sel_key) or row.get("status") or "Not Started"
                    prio_num = priority_to_int(row.get("priority"))
                    prio_label = priority_to_label(prio_num)

                    c_top_a, c_top_b, c_top_c = st.columns([0.55, 3.45, 1.2])
                    with c_top_a:
                        st.checkbox("Done", value=(status == "Done"), key=chk_key, label_visibility="collapsed", on_change=on_checkbox_toggle, args=(aid, chk_key, sel_key))
                    with c_top_b:
                        st.markdown(get_course_badge_html(course, is_light=is_light), unsafe_allow_html=True)
                    with c_top_c:
                        if st.button("Edit", key=f"{key_prefix}edit_btn_{aid}", use_container_width=True):
                            st.session_state["_pending_edit_aid"] = aid
                            safe_rerun("app")

                    st.selectbox("Status", STATUS_OPTIONS, index=STATUS_OPTIONS.index(status) if status in STATUS_OPTIONS else 0, key=sel_key, label_visibility="collapsed", on_change=on_status_change, args=(aid, sel_key, chk_key))
                    st.markdown(f"<div class='card-task-title'>{title}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='card-task-meta'>{atype}</div>", unsafe_allow_html=True)

                    eta = str(row.get("eta") or "").strip()
                    notes = str(row.get("notes") or "").strip()
                    eta_snippet = f" &bull; Est: {eta}" if eta else ""
                    st.markdown(
                        f"<div class='card-footer-row'>"
                        f"<div class='card-due-text'>Due {due_text} ({days_text}){eta_snippet}</div>"
                        f"<div class='prio-{prio_label.lower()}'>Priority: {format_priority_display(prio_num, user_prio_mode)}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    if notes:
                        note_preview = notes if len(notes) <= 90 else notes[:87] + "..."
                        st.markdown(f"<div class='card-note-text'>Note: {note_preview}</div>", unsafe_allow_html=True)


@fragment_decorator
def render_shs_bell_schedule_fragment(user_id: str, is_light: bool):
    shs_cfg = get_shs_cached(user_id)
    saved_lunches = dict(shs_cfg.get("lunches", {"A": "L2", "B": "L2", "C": "L2", "D": "L2", "X": "L2"}))
    saved_periods = dict(shs_cfg.get("periods", {str(i): "" for i in range(1, 9)}))
    user_courses = get_courses_cached(user_id)

    col_bells, col_mapper = st.columns([1.8, 1.2])

    with col_bells:
        st.markdown("<div class='section-heading'>SHS Daily Letter Day & Bell Schedule</div>", unsafe_allow_html=True)
        st.caption("Synced with the SHS 2026–2027 letter-day calendar and all 8 official bell rotations.")

        now_local = get_local_now()
        c_d1, c_d2, c_d3 = st.columns([1.15, 0.95, 1.35])
        with c_d1:
            view_date = st.date_input("Schedule Date", value=now_local.date(), key="shs_bell_date_input")

        day_info = get_shs_day_info(view_date)
        detected_letter = day_info.get("letter", "A")
        detected_sched = day_info.get("schedule", "Daily")
        day_note = day_info.get("note", "")

        letter_opts = ["A", "B", "C", "D", "X"]
        default_letter = detected_letter if detected_letter in letter_opts else "A"
        default_sched = detected_sched if detected_sched in SHS_SCHEDULE_TYPES else ("X Day" if default_letter == "X" else "Daily")

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

        if detected_letter in ("NO SCHOOL", "WEEKEND"):
            st.info(f"**{view_date.strftime('%A, %b %d')}**: {detected_letter} ({day_note}). Previewing **{active_letter} Day ({active_sched})** below.")
        elif day_note:
            st.caption(f"Calendar Note: **{day_note}** • {SHS_DROPPED_PERIODS.get(active_letter, '')} • {active_letter} Day Lunch: **{active_lunch}**")
        else:
            st.caption(f"Rotation Info: **{SHS_DROPPED_PERIODS.get(active_letter, '')}** • {active_letter} Day Lunch: **{active_lunch}**")

        blocks = build_shs_bell_blocks(active_letter, active_sched, active_lunch, saved_periods)
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
            class_disp = blk["class_name"]
            if not is_lunch_blk and class_disp.upper() in user_courses:
                class_html = get_course_badge_html(class_disp, is_light=is_light)
            else:
                class_html = f"<span class='slot-title-text'>{class_disp}</span>"

            st.markdown(
                f"<div class='{row_cls}'>"
                f"<div><span class='bell-period-badge'>{blk['label']}</span> {class_html}{live_badge}</div>"
                f"<div class='card-due-text'><b>{blk['start']} – {blk['end']}</b> <span class='slot-meta-text'>({blk['mins']})</span></div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    with col_mapper:
        st.markdown("<div class='section-heading'>My Periods & Lunch Waves</div>", unsafe_allow_html=True)
        st.caption("Set your lunch wave for each letter day and map your classes to Periods 1–8.")

        with st.form("shs_period_mapper_form"):
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

            if st.form_submit_button("Save My SHS Schedule", use_container_width=True):
                _write_shs_config(user_id, {"lunches": new_lunches, "periods": new_periods})
                st.success("SHS period schedule & lunch waves saved!")

@fragment_decorator
def render_completed_recovery_fragment(user_id: str, is_light: bool):
    st.markdown("<div class='section-heading'>Completed Tasks & Recovery Center</div>", unsafe_allow_html=True)
    st.caption("Finished assignments stay here until their due date passes. Restoring an item returns it to your active tab with its previous status.")

    rec_col1, rec_col2 = st.columns(2)
    with rec_col1:
        st.markdown("<div class='section-heading' style='font-size:0.95rem;'>1. Daily Planner Slots Checked Today</div>", unsafe_allow_html=True)
        completed_slots_dict = get_completed_slots_cached(user_id)
        if completed_slots_dict:
            for s_key, s_data in list(completed_slots_dict.items()):
                c_info, c_act = st.columns([3.8, 1.6])
                with c_info:
                    st.markdown(
                        f"<div class='recovery-card'><div><b>{s_data.get('title')}</b> {get_course_badge_html(s_data.get('course'), is_light=is_light)}"
                        f"<div class='card-note-text'>{s_data.get('day_name')} &bull; {s_data.get('time')}</div></div></div>",
                        unsafe_allow_html=True,
                    )
                with c_act:
                    st.button("Restore", key=f"rec_slot_{s_key}", on_click=restore_single_daily_slot, args=(s_key, user_id), use_container_width=True)
        else:
            st.info("No daily planner slots marked completed today.")

    with rec_col2:
        st.markdown("<div class='section-heading' style='font-size:0.95rem;'>2. Finished Assignments (Database)</div>", unsafe_allow_html=True)
        df_all = get_assignments_cached(user_id)
        df_done_db = df_all[df_all["status"] == "Done"].copy()
        if not df_done_db.empty:
            for _, r_done in df_done_db.iterrows():
                r_aid = r_done.get("id")
                c_info_db, c_act_db = st.columns([3.8, 1.6])
                with c_info_db:
                    st.markdown(
                        f"<div class='recovery-card'><div><b>{r_done.get('title')}</b> {get_course_badge_html(r_done.get('course'), is_light=is_light)}"
                        f"<div class='card-note-text'>Type: {r_done.get('atype')} &bull; Due: {r_done.get('due_date')}</div></div></div>",
                        unsafe_allow_html=True,
                    )
                with c_act_db:
                    st.button("Restore", key=f"rec_db_{r_aid}", on_click=restore_single_assignment, args=(r_done.to_dict(),), use_container_width=True)
        else:
            st.info("No main database assignments currently marked as 'Done'.")


# -----------------------
# Main Application Entry
# -----------------------
user = st.session_state.get("user")
if not user:
    render_terminal_auth_page()
    st.stop()

user_id = str(user.get("id"))
email = str(user.get("email", "User"))

hydrate_user_session(user_id)
user_theme = get_theme_cached(user_id)
is_light_theme = (user_theme.get("mode") == "Light")
st.markdown(build_theme_css(user_theme), unsafe_allow_html=True)

active_prio_mode = get_prio_cached(user_id)
seen_updates_ver = get_seen_updates_cached(user_id)
user_prio_mode = active_prio_mode or "Low / Medium / High"

pending_edit_aid = st.session_state.pop("_pending_edit_aid", None)
if pending_edit_aid:
    show_edit_assignment_dialog(user_id, pending_edit_aid, user_prio_mode)
elif seen_updates_ver != CURRENT_APP_VERSION:
    show_updates_dialog(user_id, is_first_time=True)
elif not get_courses_cached(user_id):
    show_welcome_courses_dialog(user_id)
elif not active_prio_mode:
    show_prio_config_dialog(user_id)

logo_fill = "#0f172a" if is_light_theme else "#ffffff"
col_header_left, col_header_right = st.columns([1.75, 3.25])

with col_header_left:
    st.markdown(
        f"""
        <div class='header-brand-box'>
            <div style='display:flex; align-items:center; gap:10px;'>
                <svg width='26' height='26' viewBox='0 0 24 24' fill='none' xmlns='http://www.w3.org/2000/svg'>
                    <rect x='2' y='3' width='12' height='12' rx='2' fill='{logo_fill}' opacity='0.45'/>
                    <rect x='6' y='7' width='12' height='12' rx='2' fill='{logo_fill}' opacity='0.75'/>
                    <rect x='10' y='11' width='12' height='12' rx='2' fill='{logo_fill}'/>
                </svg>
                <span class='app-title' style='line-height:1;'>Assignment Tracker</span>
            </div>
            <div class='app-subtitle'>{email} &bull; <span class='accent-text'>System: {user_prio_mode}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_header_right:
    b1, b2, b3, b4, b5, b6, b7 = st.columns([1.05, 1.0, 1.0, 0.95, 1.15, 1.0, 1.05])
    with b1:
        if st.button("+ Task", key="toolbar_add", use_container_width=True):
            show_add_assignment_dialog(user_id, user_prio_mode)
    with b2:
        if st.button("Courses", key="toolbar_courses", use_container_width=True):
            show_manage_courses_dialog(user_id)
    with b3:
        if st.button("Priority", key="toolbar_prio_sys", use_container_width=True):
            show_prio_config_dialog(user_id)
    with b4:
        if st.button("Theme", key="toolbar_theme", use_container_width=True):
            show_theme_dialog(user_id)
    with b5:
        if st.button("Feedback", key="toolbar_feedback", use_container_width=True):
            show_feedback_dialog(user_id, email)
    with b6:
        if st.button("Updates", key="toolbar_updates", use_container_width=True):
            show_updates_dialog(user_id, is_first_time=False)
    with b7:
        if st.button("Sign Out", key="toolbar_signout", use_container_width=True):
            sign_out_user()

now_dt = get_local_now()
today_str = now_dt.strftime("%A, %B %d, %Y")
shs_today = get_shs_day_info(now_dt.date())
l_day_today = shs_today.get("letter", "A")
sched_today = shs_today.get("schedule", "Daily")
note_today = shs_today.get("note", "")

if l_day_today in ("A", "B", "C", "D", "X"):
    pill_label = f"{l_day_today} Day &bull; {sched_today}" + (f" ({note_today})" if note_today else "")
else:
    pill_label = f"{l_day_today}" + (f" &bull; {note_today}" if note_today else "")

st.markdown(
    f'<div class="date-banner">Today\'s Date: {today_str} <span class="shs-day-pill">{pill_label}</span></div>',
    unsafe_allow_html=True,
)

NAV_OPTIONS = ["Assignments", "Tests & Quizzes", "Other", "SHS Bell Schedule", "Weekly Schedule & AI Planner", "Completed & Recovery"]
active_tab = st.radio("Navigation", NAV_OPTIONS, horizontal=True, label_visibility="collapsed", key="main_nav_pill")

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
