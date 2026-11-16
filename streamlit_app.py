"""
📚 Assignment Tracker — Zero-Latency @st.fragment, Live SHS Bell Schedule, Classroom Sync, Theme Studio & Beta/Fallback Engine
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import threading
import traceback
import urllib.request
import uuid
from datetime import datetime, date, timedelta, time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

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

CURRENT_APP_VERSION = "3.9"
ADMIN_EMAILS = {"30guptaa@simsburyschools.net"}


def is_admin_user(email: str) -> bool:
    return str(email or "").strip().lower() in ADMIN_EMAILS


# -----------------------
# Central Beta & Feature Release Registry
# -----------------------
FEATURE_REGISTRY: Dict[str, Dict[str, str]] = {
    "classroom_sync_v2": {
        "name": "Google Classroom Auto-Expand & Full To-Do Sync",
        "version": "3.9",
        "default_status": "beta",
        "location_hint": "Sync button in the top toolbar",
        "beta_summary": "Auto-expands collapsed To-do sections (No due date, This week, Later), imports forms/materials/clubs into Other, and fetches instructions.",
        "release_summary": "Google Classroom Full To-Do Sync is now officially live! It auto-expands all To-do sections, handles club posts, and pulls instructions into notes.",
    },
}


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
div[data-testid="stRadio"] label > div:has(input[type="radio"]),
div[data-testid="stRadio"] div[data-baseweb="radio"] > div:first-child,
div[data-testid="stRadio"] input[type="radio"] {
    appearance: none !important;
    -moz-appearance: none !important;
    -webkit-appearance: none !important;
    display: none !important;
    opacity: 0 !important;
    width: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    position: absolute !important;
    pointer-events: none !important;
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

.beta-banner-box {
    background: rgba(245, 158, 11, 0.14);
    border: 1.5px solid rgba(245, 158, 11, 0.55);
    border-radius: 11px;
    padding: 10px 14px;
    margin-bottom: 10px;
}

.admin-workbench-box {
    background: rgba(99, 102, 241, 0.15);
    border: 1.5px solid rgba(99, 102, 241, 0.55);
    border-radius: 11px;
    padding: 10px 14px;
    margin-bottom: 10px;
}

.crash-alert-box {
    background: rgba(244, 63, 94, 0.16);
    border: 1.5px solid rgba(244, 63, 94, 0.65);
    border-radius: 11px;
    padding: 11px 14px;
    margin-bottom: 12px;
}

.release-banner-box {
    background: rgba(16, 185, 129, 0.15);
    border: 1.5px solid rgba(16, 185, 129, 0.55);
    border-radius: 11px;
    padding: 11px 14px;
    margin-bottom: 12px;
}

.msg-bubble-user {
    background: var(--card-bg);
    border: 1.5px solid var(--card-border);
    border-radius: 10px;
    padding: 9px 12px;
    margin-bottom: 6px;
}

.msg-bubble-admin {
    background: var(--accent-soft);
    border: 1.5px solid var(--accent-border);
    border-radius: 10px;
    padding: 9px 12px;
    margin-left: 18px;
    margin-bottom: 6px;
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
    line-height: 1.35;
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

.update-beta-badge {
    background: #f59e0b;
    color: #0f172a !important;
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
    return out


# -----------------------
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
    "__SYSTEM_SEEN_RELEASES__",
    "__SYSTEM_THEME_CONFIG__",
    "__SYSTEM_SHS_CONFIG__",
    "__SYSTEM_IGNORED_SYNC__",
}


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
        if ("/pub?" in url and "output=csv" in url) or ("/export?" in url and "format=csv" in url):
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


@st.cache_data(ttl=300, show_spinner=False)
def fetch_live_shs_spreadsheet_map(sheet_url: str) -> Dict[str, Dict[str, str]]:
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
    iso_key = target_date.isoformat()
    active_url = str(custom_sheet_url or "").strip() or get_default_shs_sheet_url()

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
    elif "DATABASE_URL" in st.secrets:
        url = st.secrets["DATABASE_URL"]
    else:
        raise ValueError("Missing PostgreSQL database URL in secrets configuration.")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
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
                created_at TEXT NOT NULL,
                is_read_admin INTEGER DEFAULT 0,
                is_read_user INTEGER DEFAULT 1
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS feedback_replies (
                id TEXT PRIMARY KEY,
                feedback_id TEXT NOT NULL,
                sender_email TEXT NOT NULL,
                is_admin INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS feature_flags (
                feature_key TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS feature_errors (
                id TEXT PRIMARY KEY,
                feature_key TEXT NOT NULL,
                feature_name TEXT NOT NULL,
                error_msg TEXT NOT NULL,
                traceback_txt TEXT,
                user_email TEXT,
                is_resolved INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
        """))

    for alter_sql in [
        "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS is_read_admin INTEGER DEFAULT 0;",
        "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS is_read_user INTEGER DEFAULT 1;",
    ]:
        try:
            with engine.begin() as conn:
                conn.execute(text(alter_sql))
        except Exception:
            pass
    return True


try:
    init_db_once()
except Exception as e:
    st.error(f"Database Connection Error: {e}")


# -----------------------
# Global Feature Flags, Fallback Guard & Error Alerting
# -----------------------
def get_global_feature_statuses(force_refresh: bool = False) -> Dict[str, str]:
    if not force_refresh and "_global_feature_statuses" in st.session_state:
        return st.session_state["_global_feature_statuses"]

    statuses: Dict[str, str] = {k: v.get("default_status", "released") for k, v in FEATURE_REGISTRY.items()}
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT feature_key, status FROM feature_flags")).mappings().all()
        db_map = {str(r["feature_key"]): str(r["status"]) for r in rows}
        missing = []
        for f_key, meta in FEATURE_REGISTRY.items():
            if f_key in db_map:
                statuses[f_key] = db_map[f_key]
            else:
                missing.append((f_key, meta.get("default_status", "released")))
        if missing:
            now_iso = get_local_now().isoformat()
            with engine.begin() as conn:
                for fk, st_val in missing:
                    conn.execute(
                        text("INSERT INTO feature_flags (feature_key, status, updated_at) VALUES (:k, :s, :u) ON CONFLICT (feature_key) DO NOTHING"),
                        {"k": fk, "s": st_val, "u": now_iso},
                    )
    except Exception:
        pass

    st.session_state["_global_feature_statuses"] = statuses
    return statuses


def is_feature_in_beta(feature_key: str) -> bool:
    return get_global_feature_statuses().get(feature_key, "released") == "beta"


def promote_feature_to_public(feature_key: str) -> None:
    now_iso = get_local_now().isoformat()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO feature_flags (feature_key, status, updated_at)
                VALUES (:k, 'released', :u)
                ON CONFLICT (feature_key) DO UPDATE SET status = 'released', updated_at = EXCLUDED.updated_at;
            """),
            {"k": feature_key, "u": now_iso},
        )
    st.session_state.pop("_global_feature_statuses", None)


def revert_feature_to_beta(feature_key: str) -> None:
    now_iso = get_local_now().isoformat()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO feature_flags (feature_key, status, updated_at)
                VALUES (:k, 'beta', :u)
                ON CONFLICT (feature_key) DO UPDATE SET status = 'beta', updated_at = EXCLUDED.updated_at;
            """),
            {"k": feature_key, "u": now_iso},
        )
    st.session_state.pop("_global_feature_statuses", None)


def report_feature_error(feature_key: str, error_msg: str, traceback_txt: str, user_email: str) -> None:
    meta = FEATURE_REGISTRY.get(feature_key, {})
    f_name = meta.get("name", feature_key)
    now_iso = get_local_now().isoformat()
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM feature_errors WHERE feature_key = :fk AND error_msg = :em AND is_resolved = 0 LIMIT 1"),
                {"fk": feature_key, "em": error_msg[:400]},
            ).fetchone()
            if existing:
                conn.execute(
                    text("UPDATE feature_errors SET created_at = :ca, user_email = :ue WHERE id = :id"),
                    {"ca": now_iso, "ue": user_email, "id": existing.id},
                )
            else:
                conn.execute(
                    text("""
                        INSERT INTO feature_errors (id, feature_key, feature_name, error_msg, traceback_txt, user_email, is_resolved, created_at)
                        VALUES (:id, :fk, :fn, :em, :tb, :ue, 0, :ca)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "fk": feature_key,
                        "fn": f_name,
                        "em": error_msg[:400],
                        "tb": traceback_txt[:2500],
                        "ue": user_email,
                        "ca": now_iso,
                    },
                )
    except Exception:
        pass


def get_unresolved_feature_errors() -> List[Dict[str, Any]]:
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM feature_errors WHERE is_resolved = 0 ORDER BY created_at DESC LIMIT 20")
            ).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        return []


def resolve_feature_error(error_id: str) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE feature_errors SET is_resolved = 1 WHERE id = :id"), {"id": error_id})
    except Exception:
        pass


def run_with_fallback(
    feature_key: str,
    primary_fn: Callable[[], Any],
    fallback_fn: Callable[[], Any],
    user_email: str,
) -> Any:
    try:
        return primary_fn()
    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        tb_txt = traceback.format_exc()
        report_feature_error(feature_key, err_msg, tb_txt, user_email)
        if not is_admin_user(user_email):
            st.info("🛡️ Standard backup mode active while we fine-tune the latest update.")
        return fallback_fn()


def render_feature_stage_header(feature_key: str, user_id: str, email: str) -> None:
    meta = FEATURE_REGISTRY.get(feature_key)
    if not meta:
        return
    in_beta = is_feature_in_beta(feature_key)
    f_name = meta.get("name", feature_key)

    if is_admin_user(email):
        if in_beta:
            st.markdown(
                f"<div class='admin-workbench-box'>"
                f"<div style='font-weight:800; font-size:0.86rem; margin-bottom:2px;'>🛠️ Admin Beta Workbench — {f_name}</div>"
                f"<div style='font-size:0.78rem;'>Regular users currently see the Beta Testing alert on this feature. You do not see user beta popups.</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            ac1, ac2 = st.columns([2.2, 1.2])
            with ac1:
                if st.button("🚀 Promote to Public Release (End Beta)", key=f"promote_beta_{feature_key}", use_container_width=True):
                    promote_feature_to_public(feature_key)
                    st.success(f"🎉 '{f_name}' is now in Public Release! All users will receive the Public Release update alert.")
                    safe_rerun("app")
            with ac2:
                if st.button("🧪 Test Fallback Alert", key=f"test_fb_{feature_key}", use_container_width=True):
                    report_feature_error(feature_key, "SimulatedAdminFallbackTest: Manual health check triggered", "Manual test from Admin Beta Workbench", email)
                    st.warning("Fallback alert logged! Check the red alert banner at the top of your dashboard.")
        else:
            with st.expander("🛠️ Admin Feature Status: Public Release (Live)", expanded=False):
                st.caption(f"'{f_name}' is currently live for all users.")
                if st.button("↩️ Revert Back to Beta Testing", key=f"revert_beta_{feature_key}"):
                    revert_feature_to_beta(feature_key)
                    safe_rerun("app")
    else:
        if in_beta:
            st.markdown(
                f"<div class='beta-banner-box'>"
                f"<div style='font-weight:800; font-size:0.86rem; margin-bottom:2px;'>🧪 Beta Feature (In Testing) — {f_name}</div>"
                f"<div style='font-size:0.79rem;'>This feature is currently in testing. Tell me if anything is wrong or buggy!</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("💬 Report Beta Issue / Send Feedback", key=f"beta_fb_btn_{feature_key}", use_container_width=True):
                st.session_state["_open_feedback_prefill"] = f"Beta Issue: {f_name}"
                safe_rerun("app")


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
        elif any(k in c for k in ["SPAN", "ESP", "FRENCH", "LANG", "LATIN"]):
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
        elif any(k in c for k in ["SPAN", "ESP", "FRENCH", "LANG", "LATIN"]):
            bg, fg, border = "#581c87", "#e9d5ff", "#9333ea"
        elif c in ("OTHER", "STUDY HALL", "FREE / UNASSIGNED", "CONNECT") or c.startswith("PERIOD "):
            bg, fg, border = "#1e293b", "#e2e8f0", "#475569"
        else:
            bg, fg, border = "#0c4a6e", "#7dd3fc", "#0284c7"

    return (
        f"<span style='background-color:{bg}; color:{fg} !important; border:1.5px solid {border}; "
        f"padding:3px 9px; border-radius:6px; font-weight:800; font-size:0.73rem; letter-spacing:0.03em; "
        f"font-family:inherit; display:inline-block;'>{c}</span>"
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
        "cfg_seen_updates", "cfg_seen_releases", "cfg_theme", "cfg_shs",
        "cfg_ignored_sync", "_ai_plan_result", "_undo_slot_state",
        "_hydrated_uid", "_pending_edit_aid", "_classroom_sync_preview",
        "_classroom_auto_sync", "_sync_banner_msg", "_global_feature_statuses",
        "_open_feedback_prefill",
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
    seen_releases: List[str] = []
    ignored_sync: List[str] = []
    theme_cfg: Dict[str, Any] = dict(DEFAULT_THEME_CONFIG)
    shs_cfg: Dict[str, Any] = {
        "lunches": {"A": "L2", "B": "L2", "C": "L2", "D": "L2", "X": "L2"},
        "periods": {str(i): "" for i in range(1, 9)},
        "study_rooms": {"A": "", "B": "", "C": "", "D": "", "X": ""},
        "sheet_url": "",
        "app_url": "",
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
        elif r_title == "__SYSTEM_SEEN_RELEASES__":
            try:
                parsed = json.loads(str(r_notes or "[]"))
                if isinstance(parsed, list):
                    seen_releases = [str(x) for x in parsed]
            except Exception:
                pass
        elif r_title == "__SYSTEM_IGNORED_SYNC__":
            try:
                parsed = json.loads(str(r_notes or "[]"))
                if isinstance(parsed, list):
                    ignored_sync = [str(x).strip().lower() for x in parsed if str(x).strip()]
            except Exception:
                pass
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
    st.session_state["cfg_seen_releases"] = seen_releases
    st.session_state["cfg_ignored_sync"] = ignored_sync
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


def get_ignored_sync_cached(user_id: str) -> List[str]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_ignored_sync", [])


def _write_ignored_sync(user_id: str, ignored_titles: List[str]) -> None:
    cleaned = list(dict.fromkeys([str(x).strip().lower() for x in ignored_titles if str(x).strip()]))[-80:]
    st.session_state["cfg_ignored_sync"] = cleaned
    _run_bg_sql(_db_upsert_config_worker, _cfg_uuid("user_ignored_sync_config", user_id), user_id, "__SYSTEM_IGNORED_SYNC__", json.dumps(cleaned), get_local_now().isoformat())


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


def get_seen_releases_cached(user_id: str) -> List[str]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_seen_releases", [])


def _write_seen_releases(user_id: str, release_keys: List[str]) -> None:
    cleaned = list(dict.fromkeys([str(k) for k in release_keys if str(k)]))
    st.session_state["cfg_seen_releases"] = cleaned
    _run_bg_sql(_db_upsert_config_worker, _cfg_uuid("user_seen_releases_config", user_id), user_id, "__SYSTEM_SEEN_RELEASES__", json.dumps(cleaned), get_local_now().isoformat())


def get_theme_cached(user_id: str) -> Dict[str, Any]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_theme", dict(DEFAULT_THEME_CONFIG))


def _write_theme_config(user_id: str, theme_cfg: Dict[str, Any]) -> None:
    st.session_state["cfg_theme"] = theme_cfg
    _run_bg_sql(_db_upsert_config_worker, _cfg_uuid("user_theme_config", user_id), user_id, "__SYSTEM_THEME_CONFIG__", json.dumps(theme_cfg), get_local_now().isoformat())


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
            "app_url": "",
        },
    )
    if "lunches" not in cfg:
        old_l = cfg.get("lunch", "L2")
        cfg["lunches"] = {k: old_l for k in ("A", "B", "C", "D", "X")}
    if "study_rooms" not in cfg:
        cfg["study_rooms"] = dict(default_rooms)
    if "sheet_url" not in cfg:
        cfg["sheet_url"] = ""
    if "app_url" not in cfg:
        cfg["app_url"] = ""
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
        matches = df[df["id"] == assignment_id]
        if not matches.empty:
            rec = matches.iloc[0]
            note_low = str(rec.get("notes") or "").lower()
            if "classroom" in note_low:
                uid = str(rec.get("user_id") or "")
                t_low = str(rec.get("title") or "").strip().lower()
                if uid and t_low:
                    ign = list(get_ignored_sync_cached(uid))
                    if t_low not in ign:
                        ign.append(t_low)
                        _write_ignored_sync(uid, ign)
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
                st.session_state[key] = prev_st


# -----------------------
# Authentication & Two-Way Feedback Messaging System
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


def submit_user_feedback(user_id: str, email: str, category: str, rating: int, message: str) -> bool:
    msg_clean = str(message or "").strip()
    if not msg_clean:
        return False
    fb_id = str(uuid.uuid4())
    now_iso = get_local_now().isoformat()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO feedback (id, user_id, email, category, rating, message, created_at, is_read_admin, is_read_user)
                VALUES (:id, :uid, :em, :cat, :rat, :msg, :ca, 0, 1)
            """),
            {
                "id": fb_id,
                "uid": user_id,
                "em": email,
                "cat": category,
                "rat": int(rating),
                "msg": msg_clean,
                "ca": now_iso,
            },
        )
    return True


def post_feedback_reply(feedback_id: str, sender_email: str, message: str) -> bool:
    msg_clean = str(message or "").strip()
    if not msg_clean:
        return False
    admin_flag = 1 if is_admin_user(sender_email) else 0
    now_iso = get_local_now().isoformat()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO feedback_replies (id, feedback_id, sender_email, is_admin, message, created_at)
                VALUES (:id, :fid, :se, :ia, :msg, :ca)
            """),
            {
                "id": str(uuid.uuid4()),
                "fid": feedback_id,
                "se": sender_email,
                "ia": admin_flag,
                "msg": msg_clean,
                "ca": now_iso,
            },
        )
        if admin_flag:
            conn.execute(
                text("UPDATE feedback SET is_read_user = 0, is_read_admin = 1 WHERE id = :fid"),
                {"fid": feedback_id},
            )
        else:
            conn.execute(
                text("UPDATE feedback SET is_read_admin = 0, is_read_user = 1 WHERE id = :fid"),
                {"fid": feedback_id},
            )
    return True


def get_unread_feedback_count(user_id: str, email: str) -> int:
    try:
        with engine.connect() as conn:
            if is_admin_user(email):
                res = conn.execute(text("SELECT COUNT(*) FROM feedback WHERE COALESCE(is_read_admin, 0) = 0")).scalar()
            else:
                res = conn.execute(
                    text("SELECT COUNT(*) FROM feedback WHERE user_id = :uid AND COALESCE(is_read_user, 1) = 0"),
                    {"uid": user_id},
                ).scalar()
            return int(res or 0)
    except Exception:
        return 0


def get_feedback_threads(user_id: str, email: str) -> List[Dict[str, Any]]:
    try:
        with engine.connect() as conn:
            if is_admin_user(email):
                fb_rows = conn.execute(text("SELECT * FROM feedback ORDER BY created_at DESC LIMIT 60")).mappings().all()
            else:
                fb_rows = conn.execute(
                    text("SELECT * FROM feedback WHERE user_id = :uid ORDER BY created_at DESC LIMIT 30"),
                    {"uid": user_id},
                ).mappings().all()

            rep_rows = conn.execute(text("SELECT * FROM feedback_replies ORDER BY created_at ASC")).mappings().all()

        replies_by_fb: Dict[str, List[Dict[str, Any]]] = {}
        for r in rep_rows:
            fid = str(r["feedback_id"])
            replies_by_fb.setdefault(fid, []).append(dict(r))

        threads = []
        for fb in fb_rows:
            d = dict(fb)
            d["replies"] = replies_by_fb.get(str(d["id"]), [])
            threads.append(d)
        return threads
    except Exception:
        return []


def mark_feedback_threads_read(user_id: str, email: str, feedback_id: Optional[str] = None) -> None:
    try:
        with engine.begin() as conn:
            if is_admin_user(email):
                if feedback_id:
                    conn.execute(text("UPDATE feedback SET is_read_admin = 1 WHERE id = :fid"), {"fid": feedback_id})
                else:
                    conn.execute(text("UPDATE feedback SET is_read_admin = 1"))
            else:
                if feedback_id:
                    conn.execute(text("UPDATE feedback SET is_read_user = 1 WHERE id = :fid AND user_id = :uid"), {"fid": feedback_id, "uid": user_id})
                else:
                    conn.execute(text("UPDATE feedback SET is_read_user = 1 WHERE user_id = :uid"), {"uid": user_id})
    except Exception:
        pass


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


def generate_ai_study_plan(
    df_tasks: pd.DataFrame,
    schedule: List[Dict[str, Any]],
    max_daily_mins_config: Union[Dict[str, int], int] = 60,
) -> Dict[str, Any]:
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
                            pending_preview = st.session_state.get("_classroom_sync_preview")
                            pending_auto = st.session_state.get("_classroom_auto_sync")
                            clear_all_session_caches()
                            if pending_preview:
                                st.session_state["_classroom_sync_preview"] = pending_preview
                            if pending_auto:
                                st.session_state["_classroom_auto_sync"] = pending_auto
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


@dialog_decorator("🎉 New Feature Now in Public Release!")
def show_public_release_dialog(user_id: str, newly_released_keys: List[str]):
    st.caption("A feature you may have seen in Beta testing has officially graduated to full Public Release!")
    for fk in newly_released_keys:
        meta = FEATURE_REGISTRY.get(fk, {})
        st.markdown(
            f"<div class='update-card'>"
            f"<div style='margin-bottom:5px;'><span class='update-ver-badge'>PUBLIC RELEASE</span> <b>{meta.get('name', fk)}</b></div>"
            f"<div style='font-size:0.84rem; line-height:1.45;'>{meta.get('release_summary', 'This feature is now officially live and ready for everyday use!')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    if st.button("Awesome, Got It!", key="dismiss_public_release_btn", use_container_width=True):
        seen_rel = list(get_seen_releases_cached(user_id))
        seen_rel.extend(newly_released_keys)
        _write_seen_releases(user_id, seen_rel)
        safe_rerun("app")


@dialog_decorator(f"Welcome to Assignment Tracker v{CURRENT_APP_VERSION}")
def show_updates_dialog(user_id: str, email: str, is_first_time: bool = False):
    st.caption("What's new, active Beta features, changelog history, and quick tips.")

    statuses = get_global_feature_statuses()
    active_betas = [
        (fk, FEATURE_REGISTRY[fk])
        for fk, st_val in statuses.items()
        if st_val == "beta" and fk in FEATURE_REGISTRY
    ]

    if active_betas and not is_admin_user(email):
        for fk, meta in active_betas:
            st.markdown(
                f"<div class='beta-banner-box'>"
                f"<div style='margin-bottom:4px;'><span class='update-beta-badge'>BETA UPDATE</span> <b>{meta['name']}</b></div>"
                f"<div style='font-size:0.82rem; line-height:1.4;'>{meta.get('beta_summary', '')} <i>(Find it in: {meta.get('location_hint', 'the app')})</i></div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    tab_latest, tab_prev, tab_tips = st.tabs(["✨ Latest Updates", "📜 Previous Updates", "💡 Things to Know"])

    with tab_latest:
        st.markdown(
            """
            <div class='update-card'>
                <div style='margin-bottom:5px;'><span class='update-ver-badge'>v3.9 NEW</span> <b>Auto-Expand Full Classroom To-Do & Club Routing</b></div>
                <div style='font-size:0.83rem; line-height:1.45;'>
                    The Classroom bookmarklet now automatically expands collapsed sections (<i>No due date</i>, <i>This week</i>, <i>Next week</i>, <i>Later</i>), imports forms/materials/club announcements into the <b>Other</b> tab, and fixes dates on <i>Posted</i> and <i>Sunday, Dec 6</i> items. <b>Re-copy the bookmarklet once from Sync!</b>
                </div>
            </div>
            <div class='update-card'>
                <div style='margin-bottom:5px;'><span class='update-ver-badge'>v3.8</span> <b>Classroom Instruction Fetch, Smart Stability Guard & Two-Way Feedback</b></div>
                <div style='font-size:0.83rem; line-height:1.45;'>
                    Pulls teacher instructions into task notes, maps <i>Español</i> to <b>SPANISH</b>, keeps <i>(on paper)</i> tasks as <b>Homework</b>, and lets you view replies to your feedback!
                </div>
            </div>
            <div class='update-card'>
                <div style='margin-bottom:5px;'><span class='update-ver-badge'>v3.4</span> <b>Live SHS Bell Schedule & Spreadsheet Sync</b></div>
                <div style='font-size:0.83rem; line-height:1.45;'>
                    Auto-detects A/B/C/D/X days, Connect Wednesdays, delays, and early dismissals with live class countdowns, per-day lunch waves (L1/L2/L3), Study Hall rooms, and optional Google Sheet calendar sync.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with tab_prev:
        st.markdown(
            """
            <div class='update-card'>
                <div style='margin-bottom:4px;'><span class='update-old-badge'>v3.2</span> <b>Theme Studio & Eye-Friendly Light Mode</b></div>
                <div style='font-size:0.81rem; line-height:1.4;'>
                    Customize Dark or low-glare Light modes, 10 color presets, custom solid colors, multi-stop gradients, and custom photo backgrounds.
                </div>
            </div>
            <div class='update-card'>
                <div style='margin-bottom:4px;'><span class='update-old-badge'>v3.0</span> <b>Zero-Latency @st.fragment Engine</b></div>
                <div style='font-size:0.81rem; line-height:1.4;'>
                    Instantaneous task checkoffs, status changes, and schedule edits without full-page reloads.
                </div>
            </div>
            <div class='update-card'>
                <div style='margin-bottom:4px;'><span class='update-old-badge'>v2.5</span> <b>Smart AI Time-Slot Planner & Daily Limits</b></div>
                <div style='font-size:0.81rem; line-height:1.4;'>
                    Automatic daily time-slot scheduling around recurring commitments, per-day study caps, and 15-second Undo toasts.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with tab_tips:
        st.markdown(
            """
            <div class='tip-card'>
                <b>1. 1-Click Classroom Bookmarklet:</b><br/>
                Save the bookmarklet from the <b>Sync</b> button to your bookmarks bar. Clicking it from any website opens Classroom To-do; clicking it on Classroom auto-expands all sections and imports everything.
            </div>
            <div class='tip-card'>
                <b>2. Personalize Your SHS Bell Schedule:</b><br/>
                Open the <b>SHS Bell Schedule</b> tab to assign your Period 1–8 classes, set your lunch wave (L1/L2/L3) for each rotation letter, and enter Study Hall room numbers.
            </div>
            <div class='tip-card'>
                <b>3. Auto-Repeating Study & Daily Tasks:</b><br/>
                Any task set to <i>Test & Quizzes</i>, containing words like <i>"study"</i>, <i>"review"</i>, or <i>"prep"</i>, or using <b>/day</b> in its duration (e.g. <code>30 mins/day</code>) automatically schedules a session every day leading up to its due date.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.button("Got it, Let's Go!" if is_first_time else "Close", key="dismiss_updates_modal_btn", use_container_width=True):
        _write_seen_updates(user_id, CURRENT_APP_VERSION)
        safe_rerun("app")


@dialog_decorator("💬 Feedback & Messages")
def show_feedback_dialog(user_id: str, email: str, prefill_cat: str = ""):
    st.caption("Send bug reports, Beta feature feedback, or ideas—and view direct replies from the creator.")
    tab_send, tab_msgs = st.tabs(["✍️ Send New Feedback", "📬 My Threads & Replies"])

    with tab_send:
        cat_opts = ["Beta Feature Issue", "Bug Report", "Feature Request", "SHS Bell Schedule Issue", "General Feedback"]
        default_idx = 0 if prefill_cat else 2
        with st.form("student_feedback_form"):
            category = st.selectbox("Feedback Category", cat_opts, index=default_idx, key="fb_category_sel")
            rating = st.slider("Overall Rating (1 = Needs Work, 5 = Love It)", min_value=1, max_value=5, value=5, key="fb_rating_slider")
            default_msg = f"[{prefill_cat}] " if prefill_cat else ""
            message = st.text_area("Your Message", value=default_msg, placeholder="Tell me what happened or share your idea...", height=120, key="fb_message_txt")
            if st.form_submit_button("Submit Feedback", use_container_width=True):
                if not message.strip():
                    st.error("Please enter a short message before submitting.")
                else:
                    if submit_user_feedback(user_id, email, category, rating, message):
                        st.success("Thank you! Your feedback was sent. Check 'My Threads & Replies' for responses.")
                    else:
                        st.error("Unable to submit feedback right now.")

    with tab_msgs:
        mark_feedback_threads_read(user_id, email)
        threads = get_feedback_threads(user_id, email)
        if not threads:
            st.info("You haven't sent any feedback messages yet.")
        else:
            for th in threads:
                fid = str(th["id"])
                ts_short = str(th.get("created_at", ""))[:16].replace("T", " ")
                with st.expander(f"{th.get('category')} ({'⭐' * int(th.get('rating') or 5)}) — {ts_short}", expanded=True):
                    st.markdown(
                        f"<div class='msg-bubble-user'><b>You</b> <span class='slot-meta-text'>({ts_short})</span><br/>{th.get('message')}</div>",
                        unsafe_allow_html=True,
                    )
                    for rep in th.get("replies", []):
                        r_ts = str(rep.get("created_at", ""))[:16].replace("T", " ")
                        if int(rep.get("is_admin") or 0) == 1:
                            st.markdown(
                                f"<div class='msg-bubble-admin'><b>Creator Reply</b> <span class='slot-meta-text'>({r_ts})</span><br/>{rep.get('message')}</div>",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                f"<div class='msg-bubble-user'><b>You</b> <span class='slot-meta-text'>({r_ts})</span><br/>{rep.get('message')}</div>",
                                unsafe_allow_html=True,
                            )
                    with st.form(f"user_reply_form_{fid}", clear_on_submit=True):
                        u_rep_txt = st.text_input("Follow-up message", placeholder="Write a follow-up...", key=f"u_rep_in_{fid}", label_visibility="collapsed")
                        if st.form_submit_button("Send Follow-Up", use_container_width=True):
                            if u_rep_txt.strip():
                                post_feedback_reply(fid, email, u_rep_txt.strip())
                                safe_rerun("app")


@dialog_decorator("📬 Admin Feedback Inbox & System Health")
def show_admin_feedback_inbox_dialog(user_id: str, email: str):
    if not is_admin_user(email):
        st.error("Admin access only.")
        return

    tab_inbox, tab_health = st.tabs(["💬 User Feedback & Messages", "🛡️ Feature Health & Fallbacks"])

    with tab_inbox:
        c_filt, c_mark = st.columns([2, 1.3])
        with c_filt:
            unread_only = st.checkbox("Show Unread Threads Only", value=False, key="admin_inbox_unread_chk")
        with c_mark:
            if st.button("Mark All Read", key="admin_mark_all_read_btn", use_container_width=True):
                mark_feedback_threads_read(user_id, email)
                safe_rerun("app")

        threads = get_feedback_threads(user_id, email)
        if unread_only:
            threads = [t for t in threads if int(t.get("is_read_admin") or 0) == 0]

        if not threads:
            st.info("No feedback messages in this view.")
        else:
            for th in threads:
                fid = str(th["id"])
                is_unread = (int(th.get("is_read_admin") or 0) == 0)
                badge = "🔴 NEW • " if is_unread else ""
                sender = th.get("email", "Unknown")
                ts_short = str(th.get("created_at", ""))[:16].replace("T", " ")
                with st.expander(f"{badge}{sender} — {th.get('category')} ({'⭐' * int(th.get('rating') or 5)}) • {ts_short}", expanded=is_unread):
                    st.markdown(
                        f"<div class='msg-bubble-user'><b>{sender}</b> <span class='slot-meta-text'>({ts_short})</span><br/>{th.get('message')}</div>",
                        unsafe_allow_html=True,
                    )
                    for rep in th.get("replies", []):
                        r_ts = str(rep.get("created_at", ""))[:16].replace("T", " ")
                        if int(rep.get("is_admin") or 0) == 1:
                            st.markdown(
                                f"<div class='msg-bubble-admin'><b>You (Admin)</b> <span class='slot-meta-text'>({r_ts})</span><br/>{rep.get('message')}</div>",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                f"<div class='msg-bubble-user'><b>{rep.get('sender_email')}</b> <span class='slot-meta-text'>({r_ts})</span><br/>{rep.get('message')}</div>",
                                unsafe_allow_html=True,
                            )

                    with st.form(f"admin_reply_form_{fid}", clear_on_submit=True):
                        rep_txt = st.text_input("Reply to student", placeholder=f"Message {sender}...", key=f"adm_rep_in_{fid}", label_visibility="collapsed")
                        rc1, rc2 = st.columns([2.2, 1])
                        with rc1:
                            if st.form_submit_button("Send Reply", use_container_width=True):
                                if rep_txt.strip():
                                    post_feedback_reply(fid, email, rep_txt.strip())
                                    safe_rerun("app")
                        with rc2:
                            if is_unread and st.form_submit_button("Mark Read", use_container_width=True):
                                mark_feedback_threads_read(user_id, email, feedback_id=fid)
                                safe_rerun("app")

    with tab_health:
        st.caption("Automatic fallback status and error alerts across all Beta and live features.")
        errs = get_unresolved_feature_errors()
        if not errs:
            st.success("✅ All features healthy — zero fallback triggers reported.")
        else:
            for er in errs:
                eid = str(er["id"])
                st.markdown(
                    f"<div class='crash-alert-box'>"
                    f"<div style='font-weight:800; font-size:0.86rem;'>🚨 {er.get('feature_name')} ({er.get('feature_key')})</div>"
                    f"<div style='font-size:0.80rem; margin-top:3px;'><b>Error:</b> {er.get('error_msg')}</div>"
                    f"<div class='slot-meta-text'>Triggered by {er.get('user_email')} at {str(er.get('created_at'))[:16].replace('T', ' ')}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if er.get("traceback_txt"):
                    st.code(er["traceback_txt"], language="text")
                if st.button("✅ Mark Resolved", key=f"res_err_modal_{eid}"):
                    resolve_feature_error(eid)
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


# -----------------------
# Google Classroom Bookmarklet & Paste Sync Engine (v3.9 Full To-Do)
# -----------------------
CLUB_ACTIVITY_KEYWORDS = [
    "club", "league", "robotics", "deca", "counseling", "market", "trojan",
    "aviation", "council", "nhs", "national honor", "band", "choir",
    "orchestra", "athletics", "team", "class of 20", "announcements",
    "neml", "connect", "koski",
]


def _detect_live_app_url(saved_url: str = "") -> str:
    clean_saved = str(saved_url or "").strip().rstrip("/")
    if clean_saved:
        return clean_saved
    try:
        ctx = getattr(st, "context", None)
        if ctx and hasattr(ctx, "headers"):
            host = str(ctx.headers.get("Host", "")).strip()
            proto = str(ctx.headers.get("X-Forwarded-Proto", "https")).strip() or "https"
            if host and "localhost" not in host and "127.0.0.1" not in host:
                return f"{proto}://{host}"
    except Exception:
        pass
    return ""


def _is_club_or_activity(raw_course: str, user_courses: List[str]) -> bool:
    rc_low = str(raw_course or "").strip().lower()
    if not rc_low:
        return False
    # If the user explicitly created a course matching it, treat it as a class
    for c in user_courses:
        c_low = c.strip().lower()
        if c_low and c_low != "other" and c_low == rc_low:
            return False
    return any(kw in rc_low for kw in CLUB_ACTIVITY_KEYWORDS)


def _infer_classroom_atype(title: str, raw_course: str = "", user_courses: Optional[List[str]] = None) -> str:
    if _is_club_or_activity(raw_course, user_courses or []):
        return "Other"
    t = str(title or "").lower()
    if any(k in t for k in ["test", "quiz", "exam", "midterm", "final", "assessment"]):
        return "Test & Quizzes"
    if re.search(r"\b(essay|research paper|term paper|dbq|frq|rough draft|final draft)\b", t):
        return "Essay"
    if any(k in t for k in ["presentation", "slides", "slideshow", "poster", "speech"]):
        return "Presentation"
    if any(k in t for k in ["volunteer", "sponsorship", "permission", "syllabus", "sign up", "registration", "bake sale"]):
        return "Other"
    return "Homework"


def _match_classroom_course(raw_course: str, user_courses: List[str]) -> str:
    rc = str(raw_course or "").strip()
    if not rc:
        return "GENERAL"
    rc_up = rc.upper()

    # Keep clean club names (e.g. FIRST ROBOTICS, DECA, MATH LEAGUE) instead of matching "Math league" -> "MATH"
    if _is_club_or_activity(rc, user_courses):
        cleaned_club = re.split(r"[:–—|•(]", rc_up)[0].strip()
        return cleaned_club[:24] if cleaned_club else "OTHER"

    for c in user_courses:
        c_up = c.strip().upper()
        if c_up and c_up != "OTHER" and (c_up == rc_up or c_up in rc_up or rc_up in c_up):
            return c_up
    keyword_map = {
        "MATH": ["ALGEBRA", "GEOMETRY", "CALCULUS", "PRECALC", "STATISTICS", "MATH"],
        "SCIENCE": ["BIOLOGY", "CHEMISTRY", "PHYSICS", "ENVIRONMENTAL", "ANATOMY", "SCIENCE"],
        "ENGLISH": ["ENGLISH", "LITERATURE", "WRITING", "LANG", "COMPOSITION", "HUMANITIES"],
        "HISTORY": ["HISTORY", "WORLD", "APUSH", "GOVERNMENT", "CIVICS", "ECONOMICS", "PSYCHOLOGY"],
        "SPANISH": ["ESPAÑOL", "ESPANOL", "SPANISH"],
        "FRENCH": ["FRANÇAIS", "FRANCAIS", "FRENCH"],
    }
    for user_c in user_courses:
        u_up = user_c.strip().upper()
        for bucket, kws in keyword_map.items():
            if bucket in u_up and any(k in rc_up for k in kws):
                return u_up
    cleaned = re.split(r"[-–—|•(]", rc_up)[0].strip()
    return cleaned[:24] if cleaned else "GENERAL"


def _title_tokens(title: str) -> List[str]:
    stopwords = {
        "the", "a", "an", "of", "for", "to", "in", "on", "and", "all",
        "before", "class", "take", "paper", "complete", "finish", "do",
    }
    cleaned = re.sub(r"[^a-z0-9\s]", " ", str(title or "").lower().replace("&", " and "))
    tokens: List[str] = []
    for w in cleaned.split():
        if w in stopwords:
            continue
        if len(w) > 3 and w.endswith("s"):
            w = w[:-1]
        tokens.append(w)
    return tokens


def _is_duplicate_task(
    new_title: str,
    new_course: str,
    new_due: str,
    existing_records: List[Dict[str, str]],
) -> bool:
    nt_low = new_title.strip().lower()
    if not nt_low:
        return True
    new_toks = _title_tokens(new_title)
    for rec in existing_records:
        ex_title = rec.get("title", "").strip()
        if ex_title.lower() == nt_low:
            return True
        same_course = (rec.get("course", "").upper() == new_course.upper())
        ex_due = rec.get("due_date", "")
        same_or_open_due = (not ex_due or not new_due or ex_due == new_due)
        if same_course and same_or_open_due and new_toks:
            ex_toks = _title_tokens(ex_title)
            if not ex_toks:
                continue
            matches = 0
            for t1 in new_toks:
                if any(t1 == t2 or (len(t1) >= 4 and len(t2) >= 4 and (t1.startswith(t2) or t2.startswith(t1))) for t2 in ex_toks):
                    matches += 1
            min_len = min(len(new_toks), len(ex_toks))
            if matches >= 2 and (matches / max(1, min_len)) >= 0.6:
                return True
    return False


def _parse_classroom_due_date(raw_due: str) -> str:
    s = str(raw_due or "").strip()
    low = s.lower()
    # "Posted Tuesday, Nov 10" is a creation timestamp on "No due date" items, NOT a due date!
    if not s or "no due date" in low or low.startswith("posted"):
        return ""

    today = get_local_now().date()
    if "today" in low:
        return today.isoformat()
    if "tomorrow" in low:
        return (today + timedelta(days=1)).isoformat()
    if "yesterday" in low:
        return (today - timedelta(days=1)).isoformat()

    # Strip leading "Due ", leading weekday ("Sunday, Dec 6" -> "Dec 6"), and trailing time (", 11:59 PM")
    s_clean = re.sub(r"^due\s+", "", s, flags=re.I)
    s_clean = re.sub(
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+",
        "",
        s_clean,
        flags=re.I,
    )
    s_clean = re.sub(r",?\s*\d{1,2}:\d{2}\s*(?:AM|PM)?$", "", s_clean, flags=re.I).strip()

    # 1. Try explicit Month/Day or Full Date FIRST (so "Sunday, Dec 6" parses as Dec 6, not Sunday!)
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s_clean, fmt).date().isoformat()
        except ValueError:
            pass
    for fmt_no_yr in ("%b %d", "%B %d", "%m/%d"):
        try:
            parsed = datetime.strptime(s_clean, fmt_no_yr)
            yr = today.year + 1 if (today.month >= 11 and parsed.month <= 2) else today.year
            return date(yr, parsed.month, parsed.day).isoformat()
        except ValueError:
            pass

    # 2. Fallback to standalone weekday name (e.g. "Tuesday, 11:59 PM")
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for idx_d, d_name in enumerate(day_names):
        if re.search(rf"\b{d_name}\b", low):
            diff = (idx_d - today.weekday()) % 7
            return (today + timedelta(days=diff)).isoformat()

    return ""


def _decode_classroom_sync_payload(sync_b64: str) -> List[Dict[str, str]]:
    if not sync_b64:
        return []
    try:
        padded = sync_b64 + "=" * (-len(sync_b64) % 4)
        raw_json = base64.b64decode(padded).decode("utf-8", errors="replace")
        data = json.loads(raw_json)
        if not isinstance(data, list):
            return []
        out = []
        for item in data:
            if isinstance(item, dict) and item.get("t"):
                out.append({
                    "title": str(item.get("t", "")).strip(),
                    "raw_course": str(item.get("c", "")).strip(),
                    "raw_due": str(item.get("d", "")).strip(),
                    "details": str(item.get("n", "")).strip(),
                })
        return out
    except Exception:
        return []


def _parse_classroom_pasted_text(raw_text: str) -> List[Dict[str, str]]:
    skip_exact = {
        "to-do", "to do", "assigned", "missing", "done", "all classes",
        "no due date", "this week", "next week", "later", "earlier",
        "last week", "assignment", "quiz", "description", "more_vert",
        "work with a due date", "work without a due date",
    }
    date_line_re = re.compile(
        r"^(due\s+|posted\s+|today|tomorrow|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
        r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}/\d{1,2})",
        re.I,
    )
    lines = [
        ln.strip()
        for ln in str(raw_text or "").splitlines()
        if ln.strip() and ln.strip().lower() not in skip_exact and not ln.strip().isdigit()
    ]
    items: List[Dict[str, str]] = []
    i = 0
    while i + 1 < len(lines):
        t_cand = lines[i]
        c_cand = lines[i + 1]
        if date_line_re.match(t_cand):
            i += 1
            continue
        d_cand = ""
        step = 2
        if i + 2 < len(lines) and date_line_re.match(lines[i + 2]):
            d_cand = lines[i + 2]
            step = 3
        items.append({"title": t_cand, "raw_course": c_cand, "raw_due": d_cand, "details": ""})
        i += step
    return items


def build_classroom_bookmarklet(app_url: str, auto_import: bool = True) -> str:
    clean_url = str(app_url or "").strip().rstrip("/") or "https://YOUR-APP.streamlit.app"
    auto_suffix = "&auto=1" if auto_import else ""
    return (
        "javascript:(function(){try{"
        "if(!location.hostname.includes('classroom.google.com')){"
        "location.href='https://classroom.google.com/a/not-turned-in/all';return;}"
        "var root=document.querySelector('[role=\"main\"]')||document.body;"
        "root.querySelectorAll('[aria-expanded=\"false\"]').forEach(function(b){try{b.click();}catch(e){}});"
        "setTimeout(function(){"
        "var rows=[],seen={},skip=/^(assignment|quiz|question|material|description|more_vert|event|expand_more|expand_less)$/i;"
        "root.querySelectorAll('a[href*=\"/c/\"]').forEach(function(a){"
        "var h=a.getAttribute('href')||'';"
        "if(h.includes('/not-turned-in')||h.includes('/missing')||h.includes('/done'))return;"
        "var row=a.closest('li,[role=\"listitem\"]')||a;"
        "var lines=(row.innerText||a.innerText||'').split('\\n').map(function(s){return s.trim();}).filter(function(s){return s&&!skip.test(s);});"
        "if(lines.length>=2){var t=lines[0],c=lines[1],d=lines.slice(2).join(' ');var k=t+'|'+c;"
        "if(!seen[k]&&t.length>1){seen[k]=1;rows.push({t:t,c:c,d:d,href:a.href});}}});"
        "if(!rows.length){alert('Open your Google Classroom To-do list first, then click Sync to Tracker again!');return;}"
        "var fetchWithTimeout=function(url){"
        "return Promise.race(["
        "fetch(url,{credentials:'include'}).then(function(r){return r.text();}),"
        "new Promise(function(_,rej){setTimeout(function(){rej('timeout');},1800);})"
        "]);};"
        "Promise.all(rows.map(function(it){"
        "return fetchWithTimeout(it.href).then(function(html){"
        "var desc='',idx=html.indexOf(JSON.stringify(it.t));"
        "if(idx>-1){var chunk=html.slice(idx+it.t.length+2,idx+2500),es=chunk.indexOf('</script>');"
        "if(es>-1)chunk=chunk.slice(0,es);"
        "var strs=chunk.match(/\"((?:\\\\.|[^\"\\\\]){8,500})\"/g)||[];"
        "for(var i=0;i<strs.length;i++){try{var v=JSON.parse(strs[i]).replace(/<[^>]+>/g,' ').replace(/\\s+/g,' ').trim();"
        "if(v&&v!==it.t&&v!==it.c&&!/^https?:\\/\\//i.test(v)&&!/^(drive|docs|forms|classroom|google)/i.test(v)&&/\\s/.test(v)){desc=v.slice(0,220);break;}}catch(e){}}}"
        "return {t:it.t,c:it.c,d:it.d,n:desc};"
        "}).catch(function(){return {t:it.t,c:it.c,d:it.d,n:''};});"
        "})).then(function(items){"
        "var payload=btoa(unescape(encodeURIComponent(JSON.stringify(items))));"
        f"location.href='{clean_url}/?sync='+encodeURIComponent(payload)+'{auto_suffix}';"
        "});"
        "},450);"
        "}catch(e){alert('Bookmarklet error: '+e.message);}})();"
    )


def _get_existing_task_signatures(df_existing: pd.DataFrame) -> List[Dict[str, str]]:
    if df_existing.empty:
        return []
    sigs: List[Dict[str, str]] = []
    for _, r in df_existing.iterrows():
        sigs.append({
            "title": str(r.get("title") or ""),
            "course": str(r.get("course") or "").upper(),
            "due_date": str(r.get("due_date") or ""),
        })
    return sigs


def _format_synced_note(details: str, raw_course: str) -> str:
    d_clean = str(details or "").strip()
    c_clean = str(raw_course or "").strip()
    if d_clean and c_clean:
        return f"{d_clean} (Classroom: {c_clean})"
    if d_clean:
        return d_clean
    return f"Synced from Google Classroom ({c_clean})".strip()


def process_auto_classroom_sync(user_id: str, email: str, incoming_items: List[Dict[str, str]]) -> str:
    def _primary():
        if not incoming_items:
            return ""
        user_courses = get_courses_cached(user_id) or ["MATH", "SCIENCE", "ENGLISH", "HISTORY", "OTHER"]
        existing_sigs = _get_existing_task_signatures(get_assignments_cached(user_id))
        ignored_set = set(get_ignored_sync_cached(user_id))

        to_add: List[Dict[str, Any]] = []
        skipped_dups = 0
        skipped_ignored = 0
        for item in incoming_items:
            t_clean = str(item.get("title", "")).strip()
            raw_c = str(item.get("raw_course", "")).strip()
            if not t_clean:
                continue
            if t_clean.lower() in ignored_set:
                skipped_ignored += 1
                continue
            mapped_c = _match_classroom_course(raw_c, user_courses)
            parsed_due = _parse_classroom_due_date(item.get("raw_due", ""))
            if _is_duplicate_task(t_clean, mapped_c, parsed_due, existing_sigs):
                skipped_dups += 1
                continue
            details_txt = str(item.get("details", "")).strip()
            existing_sigs.append({"title": t_clean, "course": mapped_c, "due_date": parsed_due})
            to_add.append({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "title": t_clean,
                "course": mapped_c,
                "due_date": parsed_due,
                "status": "Not Started",
                "priority": priority_to_int("Medium"),
                "atype": _infer_classroom_atype(f"{t_clean} {details_txt}", raw_c, user_courses),
                "eta": "",
                "notes": _format_synced_note(details_txt, raw_c),
                "created_at": get_local_now().isoformat(),
                "prev_status": "Not Started",
            })

        notes_parts = []
        if skipped_dups:
            notes_parts.append(f"{skipped_dups} already tracked")
        if skipped_ignored:
            notes_parts.append(f"{skipped_ignored} previously deleted — click Sync to restore")
        extra_str = f" ({', '.join(notes_parts)})" if notes_parts else ""

        if to_add:
            upsert_assignments(to_add)
            return f"⚡ Auto-synced {len(to_add)} new assignment{'s' if len(to_add) != 1 else ''} from Google Classroom!{extra_str}"
        return f"✅ Google Classroom checked ({len(incoming_items)} found) — no new items to add{extra_str}."

    def _fallback():
        return "⚠️ Classroom auto-sync switched to manual backup mode. Open Sync → Quick Paste Backup to import."

    return run_with_fallback("classroom_sync_v2", _primary, _fallback, email)


def _render_classroom_sync_v1_fallback(user_id: str):
    user_courses = get_courses_cached(user_id) or ["MATH", "SCIENCE", "ENGLISH", "HISTORY", "OTHER"]
    st.caption("Open your Google Classroom To-do page, press **Ctrl+A** then **Ctrl+C**, and paste below:")
    pasted_blob = st.text_area("Paste Classroom To-do Page Text Here", height=150, key="classroom_paste_fallback_area")
    if st.button("Import Pasted Assignments", key="parse_pasted_fallback_btn", use_container_width=True):
        parsed_items = _parse_classroom_pasted_text(pasted_blob)
        if not parsed_items:
            st.error("Could not detect assignments from that text.")
        else:
            to_add = []
            for item in parsed_items:
                raw_c = item.get("raw_course", "")
                mapped_c = _match_classroom_course(raw_c, user_courses)
                parsed_due = _parse_classroom_due_date(item.get("raw_due", ""))
                to_add.append({
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "title": item["title"],
                    "course": mapped_c,
                    "due_date": parsed_due,
                    "status": "Not Started",
                    "priority": priority_to_int("Medium"),
                    "atype": _infer_classroom_atype(item["title"], raw_c, user_courses),
                    "eta": "",
                    "notes": f"Synced from Google Classroom ({raw_c})",
                    "created_at": get_local_now().isoformat(),
                    "prev_status": "Not Started",
                })
            upsert_assignments(to_add)
            safe_rerun("app")


def _render_classroom_sync_v2_body(user_id: str, email: str, user_prio_mode: str):
    render_feature_stage_header("classroom_sync_v2", user_id, email)

    shs_cfg = get_shs_cached(user_id)
    user_courses = get_courses_cached(user_id) or ["MATH", "SCIENCE", "ENGLISH", "HISTORY", "OTHER"]
    existing_sigs = _get_existing_task_signatures(get_assignments_cached(user_id))
    ignored_set = set(get_ignored_sync_cached(user_id))

    incoming_items = st.session_state.get("_classroom_sync_preview", [])

    if incoming_items:
        st.success(f"Found {len(incoming_items)} item(s) from Google Classroom! Uncheck any you want to skip:")
        default_prio = st.selectbox("Default Priority for Imported Tasks", PRIORITY_OPTIONS, index=1, key="sync_def_prio")
        selected_to_import: List[Dict[str, Any]] = []

        for idx, item in enumerate(incoming_items):
            t_clean = item["title"]
            raw_c = str(item.get("raw_course", "")).strip()
            details_txt = str(item.get("details", "")).strip()
            mapped_c = _match_classroom_course(raw_c, user_courses)
            parsed_due = _parse_classroom_due_date(item.get("raw_due", ""))
            inferred_type = _infer_classroom_atype(f"{t_clean} {details_txt}", raw_c, user_courses)
            is_dup = (t_clean.lower() in ignored_set) or _is_duplicate_task(t_clean, mapped_c, parsed_due, existing_sigs)

            due_lbl = f"Due {parsed_due}" if parsed_due else "No due date"
            dup_lbl = " (Already in tracker / dismissed)" if is_dup else ""
            detail_preview = f" — \"{details_txt[:70]}...\"" if len(details_txt) > 70 else (f" — \"{details_txt}\"" if details_txt else "")
            checked = st.checkbox(
                f"{t_clean} [{mapped_c} • {inferred_type} • {due_lbl}]{detail_preview}{dup_lbl}",
                value=(not is_dup),
                key=f"sync_chk_{idx}",
            )
            if checked:
                selected_to_import.append({
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "title": t_clean,
                    "course": mapped_c,
                    "due_date": parsed_due,
                    "status": "Not Started",
                    "priority": priority_to_int(default_prio),
                    "atype": inferred_type,
                    "eta": "",
                    "notes": _format_synced_note(details_txt, raw_c),
                    "created_at": get_local_now().isoformat(),
                    "prev_status": "Not Started",
                })

        c_imp, c_clr = st.columns([2, 1])
        with c_imp:
            if st.button(f"Import {len(selected_to_import)} Selected Task(s)", key="confirm_classroom_import_btn", use_container_width=True):
                if selected_to_import:
                    upsert_assignments(selected_to_import)
                st.session_state.pop("_classroom_sync_preview", None)
                safe_rerun("app")
        with c_clr:
            if st.button("Discard", key="discard_classroom_import_btn", use_container_width=True):
                st.session_state.pop("_classroom_sync_preview", None)
                safe_rerun("app")
        st.markdown("---")

    tab_bm, tab_paste = st.tabs(["⚡ 1-Click Bookmarklet Setup", "📋 Quick Paste Backup"])

    with tab_bm:
        st.caption("Save this bookmarklet once to your bookmarks bar. Clicking it on Google Classroom auto-expands all To-do sections (No due date, This week, Later) and imports everything.")
        detected_url = _detect_live_app_url(shs_cfg.get("app_url", ""))
        app_url_input = st.text_input(
            "1. Your Streamlit App URL (auto-detected)",
            value=detected_url,
            placeholder="https://your-app-name.streamlit.app",
            key="classroom_app_url_input",
        )
        if app_url_input.strip() and app_url_input.strip().rstrip("/") != str(shs_cfg.get("app_url", "")).strip():
            updated_cfg = dict(shs_cfg)
            updated_cfg["app_url"] = app_url_input.strip().rstrip("/")
            _write_shs_config(user_id, updated_cfg)

        auto_mode_chk = st.checkbox(
            "Instant Auto-Import (skip preview screen and import new tasks automatically)",
            value=True,
            key="classroom_auto_mode_chk",
        )

        bm_code = build_classroom_bookmarklet(app_url_input or detected_url, auto_import=auto_mode_chk)
        st.markdown("**2. Copy this entire bookmarklet code (click the copy icon on the right):**")
        st.code(bm_code, language="text")
        st.markdown(
            """
            **3. How to save or update it:**
            1. Press **Ctrl+Shift+B** (or **Cmd+Shift+B** on Mac) to show your bookmarks bar.
            2. Right-click **`Sync to Tracker`** → **Edit...** (or right-click the bar → **Add Bookmark...**).
            3. Paste the updated code above into the **URL** box and click **Save**.
            4. Click **`Sync to Tracker`** from any website to jump to Classroom To-do, then click **`Sync to Tracker`** again to import all sections!
            """
        )
        if ignored_set:
            st.info(f"You have {len(ignored_set)} previously deleted Classroom item(s) hidden from auto-sync: {', '.join(sorted(ignored_set))}")
            if st.button("Allow Previously Deleted Classroom Items to Re-Sync", key="reset_ignored_sync_btn"):
                _write_ignored_sync(user_id, [])
                st.success("Cleared! Click Sync to Tracker on Classroom to re-import them.")

    with tab_paste:
        st.caption("If your school Chromebook blocks bookmarklets, open your Google Classroom To-do page, press **Ctrl+A** then **Ctrl+C**, and paste below:")
        pasted_blob = st.text_area("Paste Classroom To-do Page Text Here", height=140, key="classroom_paste_area")
        if st.button("Scan Pasted Text", key="parse_pasted_classroom_btn", use_container_width=True):
            parsed_items = _parse_classroom_pasted_text(pasted_blob)
            if not parsed_items:
                st.error("Could not detect assignments from that text. Make sure you copied the Google Classroom To-do page.")
            else:
                st.session_state["_classroom_sync_preview"] = parsed_items
                safe_rerun("app")


@dialog_decorator("📥 Sync Google Classroom")
def show_classroom_sync_dialog(user_id: str, email: str, user_prio_mode: str):
    run_with_fallback(
        "classroom_sync_v2",
        lambda: _render_classroom_sync_v2_body(user_id, email, user_prio_mode),
        lambda: _render_classroom_sync_v1_fallback(user_id),
        email,
    )


# -----------------------
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
                    has_due = bool(str(row.get("due_date") or "").strip() and due_d)
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
                    due_display = f"Due {due_text} ({days_text}){eta_snippet}" if has_due else f"No due date{eta_snippet}"
                    st.markdown(
                        f"<div class='card-footer-row'>"
                        f"<div class='card-due-text'>{due_display}</div>"
                        f"<div class='prio-{prio_label.lower()}'>Priority: {format_priority_display(prio_num, user_prio_mode)}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    if notes:
                        note_preview = notes if len(notes) <= 180 else notes[:177] + "..."
                        st.markdown(f"<div class='card-note-text'>Note: {note_preview}</div>", unsafe_allow_html=True)


@fragment_decorator
def render_shs_bell_schedule_fragment(user_id: str, is_light: bool):
    shs_cfg = get_shs_cached(user_id)
    now_local = get_local_now()
    today_date = now_local.date()

    st.markdown("<div class='section-heading'>🔔 Simsbury High School Bell Schedule</div>", unsafe_allow_html=True)
    st.caption("Live A/B/C/D/X rotation, Connect Wednesdays, delays, early dismissals, lunch waves, and class countdowns.")

    ctrl1, ctrl2, ctrl3 = st.columns([1.2, 1.1, 1.3])
    with ctrl1:
        selected_date = st.date_input("Select Date", value=today_date, key="shs_bell_date_input")
    detected_info = get_shs_day_info(selected_date, shs_cfg.get("sheet_url", ""))

    with ctrl2:
        letter_opts = ["Auto", "A", "B", "C", "D", "X"]
        override_letter = st.selectbox("Rotation Day", options=letter_opts, index=0, key="shs_letter_override")
    with ctrl3:
        sched_opts = ["Auto"] + SHS_SCHEDULE_TYPES
        override_sched = st.selectbox("Bell Schedule", options=sched_opts, index=0, key="shs_sched_override")

    active_letter = detected_info.get("letter", "A") if override_letter == "Auto" else override_letter
    active_sched = detected_info.get("schedule", "Daily") if override_sched == "Auto" else override_sched
    if override_letter == "X" and override_sched == "Auto":
        active_sched = "X Day"

    with st.expander("⚙️ Customize My Periods, Lunch Waves & Study Hall Rooms", expanded=False):
        user_courses = [c for c in get_courses_cached(user_id) if c != "OTHER"]
        course_choices = ["", "Study Hall", "Free / Unassigned"] + user_courses

        st.markdown("**1. Assign Your Classes (Periods 1 – 8)**")
        p_cols_top = st.columns(4)
        p_cols_bot = st.columns(4)
        new_periods = dict(shs_cfg.get("periods", {}))
        for p_idx in range(1, 9):
            target_col = p_cols_top[p_idx - 1] if p_idx <= 4 else p_cols_bot[p_idx - 5]
            cur_val = str(new_periods.get(str(p_idx), "")).strip()
            opts_for_p = list(course_choices)
            if cur_val and cur_val not in opts_for_p:
                opts_for_p.append(cur_val)
            with target_col:
                new_periods[str(p_idx)] = st.selectbox(
                    f"Period {p_idx}",
                    options=opts_for_p,
                    index=opts_for_p.index(cur_val) if cur_val in opts_for_p else 0,
                    key=f"shs_p_sel_{p_idx}",
                    format_func=lambda x: x if x else "— Unassigned —",
                )

        st.markdown("**2. Lunch Wave by Letter Day (L1, L2, or L3)**")
        l_cols = st.columns(5)
        new_lunches = dict(shs_cfg.get("lunches", {"A": "L2", "B": "L2", "C": "L2", "D": "L2", "X": "L2"}))
        lunch_opts = ["L1", "L2", "L3"]
        for idx_l, l_day in enumerate(["A", "B", "C", "D", "X"]):
            cur_l = new_lunches.get(l_day, "L2")
            with l_cols[idx_l]:
                new_lunches[l_day] = st.selectbox(
                    f"{l_day} Day Lunch",
                    options=lunch_opts,
                    index=lunch_opts.index(cur_l) if cur_l in lunch_opts else 1,
                    key=f"shs_lunch_{l_day}",
                )

        st.markdown("**3. Study Hall Room Number by Letter Day (Optional)**")
        r_cols = st.columns(5)
        new_rooms = dict(shs_cfg.get("study_rooms", {"A": "", "B": "", "C": "", "D": "", "X": ""}))
        for idx_r, r_day in enumerate(["A", "B", "C", "D", "X"]):
            with r_cols[idx_r]:
                new_rooms[r_day] = st.text_input(
                    f"{r_day} Study Rm",
                    value=str(new_rooms.get(r_day, "")),
                    placeholder="e.g. 214",
                    key=f"shs_room_{r_day}",
                )

        st.markdown("**4. Live SHS Calendar Spreadsheet Link (Optional)**")
        new_sheet_url = st.text_input(
            "Google Sheet URL (auto-syncs A/B/C/D/X days, holidays & special schedules)",
            value=str(shs_cfg.get("sheet_url", "")),
            placeholder="https://docs.google.com/spreadsheets/d/...",
            key="shs_sheet_url_input",
        )

        sc1, sc2 = st.columns([2, 1])
        with sc1:
            if st.button("Save My SHS Schedule", key="save_shs_cfg_btn", use_container_width=True):
                updated_shs = dict(shs_cfg)
                updated_shs.update({
                    "lunches": new_lunches,
                    "periods": new_periods,
                    "study_rooms": new_rooms,
                    "sheet_url": new_sheet_url.strip(),
                })
                _write_shs_config(user_id, updated_shs)
                st.success("Saved your personalized SHS bell schedule!")
        with sc2:
            if st.button("Refresh Calendar Sync", key="refresh_shs_sheet_btn", use_container_width=True):
                fetch_live_shs_spreadsheet_map.clear()
                st.success("Calendar cache refreshed!")

    if active_letter in ("NO SCHOOL", "WEEKEND") and override_letter == "Auto":
        note_str = detected_info.get("note") or ("Weekend" if active_letter == "WEEKEND" else "No School")
        st.markdown(
            f"<div class='ai-day-card' style='text-align:center; padding:26px;'>"
            f"<div style='font-size:1.25rem; font-weight:800; margin-bottom:6px;'>🎉 {note_str}</div>"
            f"<div class='card-note-text'>No classes scheduled for {selected_date.strftime('%A, %B %d, %Y')}. Select a rotation day above to preview any bell schedule.</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        return

    day_lunch_wave = shs_cfg.get("lunches", {}).get(active_letter, "L2")
    blocks = build_shs_bell_blocks(
        letter_day=active_letter,
        schedule_type=active_sched,
        lunch_wave=day_lunch_wave,
        period_classes=shs_cfg.get("periods", {}),
        study_rooms=shs_cfg.get("study_rooms", {}),
    )

    now_mins = now_local.hour * 60 + now_local.minute
    is_today = (selected_date == today_date)
    live_banner_msg = ""
    active_block_idx = -1

    if is_today and blocks:
        parsed_ranges: List[Tuple[int, int]] = []
        for b in blocks:
            st_t, en_t = parse_time_str(b["start"]), parse_time_str(b["end"])
            if st_t and en_t:
                parsed_ranges.append((st_t.hour * 60 + st_t.minute, en_t.hour * 60 + en_t.minute))
            else:
                parsed_ranges.append((-1, -1))

        first_start = parsed_ranges[0][0]
        last_end = parsed_ranges[-1][1]
        if first_start > 0 and now_mins < first_start:
            live_banner_msg = f"⏰ First bell ({blocks[0]['class_name']}) starts in {first_start - now_mins} mins ({blocks[0]['start']})"
        elif last_end > 0 and now_mins >= last_end:
            live_banner_msg = "✅ School day complete!"
        else:
            for idx_b, (b_s, b_e) in enumerate(parsed_ranges):
                if b_s <= now_mins < b_e:
                    active_block_idx = idx_b
                    mins_left = b_e - now_mins
                    live_banner_msg = f"🟢 In Session: {blocks[idx_b]['label']} ({blocks[idx_b]['class_name']}) — {mins_left} min{'s' if mins_left != 1 else ''} remaining"
                    break
                if idx_b + 1 < len(parsed_ranges):
                    next_s = parsed_ranges[idx_b + 1][0]
                    if b_e <= now_mins < next_s:
                        mins_to_next = next_s - now_mins
                        live_banner_msg = f"🚶 Passing Time — {blocks[idx_b + 1]['label']} ({blocks[idx_b + 1]['class_name']}) starts in {mins_to_next} min{'s' if mins_to_next != 1 else ''}"
                        break

    dropped_txt = SHS_DROPPED_PERIODS.get(active_letter, "")
    note_extra = f" • {detected_info['note']}" if detected_info.get("note") else ""
    src_label = detected_info.get("source", "Calendar")
    live_banner_html = (
        f"<div style='font-weight:800; font-size:0.86rem; color:var(--accent-readable) !important;'>{live_banner_msg}</div>"
        if live_banner_msg
        else ""
    )

    st.markdown(
        f"<div class='ai-day-card'>"
        f"<div class='ai-day-header'>"
        f"<div><span class='ai-day-title'>{active_letter} DAY — {active_sched}</span> <span class='slot-meta-text'>({dropped_txt}{note_extra})</span></div>"
        f"<div class='day-time-badge'>Lunch: {day_lunch_wave} &bull; Source: {src_label}</div>"
        f"</div>"
        f"{live_banner_html}"
        f"</div>",
        unsafe_allow_html=True,
    )

    for idx_b, b in enumerate(blocks):
        is_active = (idx_b == active_block_idx)
        row_cls = "bell-row bell-row-active" if is_active else "bell-row"
        live_tag = "<span class='bell-live-tag'>LIVE NOW</span>" if is_active else ""
        ann_tag = "<span class='slot-meta-text'> &bull; 📢 Announcements</span>" if b.get("ann") == "1" else ""
        room_tag = f"<span class='slot-meta-text'> &bull; 📍 {b['room']}</span>" if b.get("room") else ""
        lunch_style = "opacity: 0.92;" if b.get("is_lunch") == "1" else ""

        st.markdown(
            f"<div class='{row_cls}' style='{lunch_style}'>"
            f"<div style='display:flex; align-items:center; flex-wrap:wrap; gap:6px;'>"
            f"<span class='bell-period-badge'>{b['label']}</span>"
            f"{get_course_badge_html(b['class_name'], is_light=is_light)}"
            f"{room_tag}{ann_tag}{live_tag}"
            f"</div>"
            f"<div style='display:flex; align-items:center; gap:8px;'>"
            f"<span class='slot-badge'>{b['start']} – {b['end']}</span>"
            f"<span class='slot-meta-text'>({b['mins']})</span>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )


@fragment_decorator
def render_schedule_and_ai_fragment(user_id: str, user_prio_mode: str, is_light: bool):
    col_sched_side, col_ai_main = st.columns([1.15, 1.85])

    user_schedule = list(get_schedule_cached(user_id))
    stored_max_daily_work_dict = get_max_work_cached(user_id)

    with col_sched_side:
        st.markdown("<div class='section-heading'>Weekly Commitments</div>", unsafe_allow_html=True)
        st.caption("Enter recurring busy blocks so the AI plans around them.")

        with st.form("add_schedule_event_form", clear_on_submit=True):
            s_day = st.selectbox("Day of Week", DAYS_OF_WEEK)
            s_title = st.text_input("Event Name", placeholder="e.g. Robotics, Practice")
            c_time1, c_time2 = st.columns(2)
            with c_time1:
                s_start_raw = st.text_input("Start Time", value="3:30 PM", key="sched_start_input")
            with c_time2:
                s_end_raw = st.text_input("End Time", value="5:00 PM", key="sched_end_input")

            if st.form_submit_button("Add Block", use_container_width=True):
                st_time, end_time = parse_time_str(s_start_raw), parse_time_str(s_end_raw)
                if s_title.strip() and st_time and end_time:
                    user_schedule.append({
                        "id": str(uuid.uuid4()), "day": s_day, "title": s_title.strip(),
                        "start": st_time.strftime("%I:%M %p").lstrip("0"),
                        "end": end_time.strftime("%I:%M %p").lstrip("0"),
                    })
                    _write_schedule_file(user_id, user_schedule)

        st.markdown("---")
        if user_schedule:
            for idx, item in enumerate(user_schedule):
                b_id = item.get("id", str(idx))
                col_item_a, col_item_b = st.columns([4, 1.3])
                with col_item_a:
                    st.markdown(f"<span class='sched-item-text'><b>{item.get('day')}</b>: {item.get('title')} ({item.get('start')} - {item.get('end')})</span>", unsafe_allow_html=True)
                with col_item_b:
                    st.button("Remove", key=f"del_sched_{b_id}", on_click=on_remove_schedule_block, args=(user_id, b_id), use_container_width=True)

    with col_ai_main:
        st.markdown("<div class='section-heading'>AI Daily Action Plan</div>", unsafe_allow_html=True)
        st.caption("Optimized timeline across available days based on due dates & priority.")

        undo_state = st.session_state.get("_undo_slot_state")
        if undo_state:
            if (get_local_now() - undo_state["time"]).total_seconds() < 15:
                u_col1, u_col2 = st.columns([4.2, 1.2])
                with u_col1:
                    st.markdown(f"<div class='undo-toast-box'><span style='font-size:0.84rem;'>Finished <b>{undo_state['title']}</b> for today</span></div>", unsafe_allow_html=True)
                with u_col2:
                    st.button("Undo", key="btn_undo_slot", on_click=on_undo_daily_slot, args=(user_id,), use_container_width=True)
            else:
                st.session_state.pop("_undo_slot_state", None)

        ctrl_col1, ctrl_col2 = st.columns([1.5, 1.2])
        with ctrl_col1:
            gen_plan_click = st.button("Re-Calculate Plan", key="btn_gen_ai_plan", use_container_width=True)
        with ctrl_col2:
            show_time_slots = st.toggle("Show Time Slots", value=True, key="toggle_show_time_slots")

        with st.expander("⏱️ Customize Daily Work Limits (Per Day)", expanded=False):
            st.caption("Set maximum allowed study/work time independently for each day of the week:")
            opts = [0, 15, 30, 45, 60, 90, 120, 150, 180, 210, 240, 300]
            day_cols = st.columns(7)
            new_limits_dict = {}
            for d_idx, d_name in enumerate(DAYS_OF_WEEK):
                with day_cols[d_idx]:
                    cur_val = stored_max_daily_work_dict.get(d_name, 60)
                    new_limits_dict[d_name] = st.selectbox(d_name[:3], options=opts, index=opts.index(cur_val) if cur_val in opts else 4, key=f"p_limit_{d_name}", format_func=lambda x: f"{x}m")
            if new_limits_dict != stored_max_daily_work_dict:
                _write_max_work_config(user_id, new_limits_dict)
                stored_max_daily_work_dict = new_limits_dict

        cached_assignments = get_assignments_cached(user_id)
        if gen_plan_click or "_ai_plan_result" not in st.session_state:
            st.session_state["_ai_plan_result"] = generate_ai_study_plan(cached_assignments, user_schedule, max_daily_mins_config=stored_max_daily_work_dict)

        plan_res = st.session_state["_ai_plan_result"]
        status, plan = plan_res.get("status"), plan_res.get("plan", {})

        if status == "no_tasks":
            st.info("No active assignments. Add items in the 'Assignments', 'Tests & Quizzes', or 'Other' tab.")
        elif status == "all_done":
            st.success("All assignments marked completed!")
        elif status == "success" and plan:
            completed_set = set(get_completed_slots_cached(user_id).keys())
            for day_name, day_data in plan.items():
                if not isinstance(day_data, dict):
                    continue
                visible_slots = [s for s in day_data.get("slots", []) if s.get("slot_key") not in completed_set]
                day_cap_mins = stored_max_daily_work_dict.get(day_name, 60)
                scheduled_mins = sum(s.get("eta_mins", 0) for s in visible_slots)

                st.markdown(
                    f'<div class="ai-day-card"><div class="ai-day-header">'
                    f'<span class="ai-day-title">{day_name}</span>'
                    f'<div class="day-time-badge">{format_mins_to_hrs_mins(scheduled_mins)} scheduled <span class="time-max-cap">/ Max {format_mins_to_hrs_mins(day_cap_mins)}</span></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if day_data.get("busy"):
                    st.caption("Busy: " + ", ".join(day_data["busy"]))

                if visible_slots:
                    for idx_slot, s in enumerate(visible_slots):
                        s_key = s.get("slot_key")
                        slot_prio_str = format_priority_display(s.get("priority"), user_prio_mode)
                        slot_dur_str = format_mins_to_hrs_mins(s.get("eta_mins", 0))
                        c_chk, c_text = st.columns([0.45, 7.55])
                        with c_chk:
                            st.checkbox("Done Today", value=False, key=f"chk_{s_key}_{idx_slot}", label_visibility="collapsed", on_change=on_daily_slot_check, args=(s_key, s.get("title"), s, user_id))
                        with c_text:
                            if show_time_slots:
                                st.markdown(f"<div style='padding-top:3px;'><span class='slot-badge'>{s['time']}</span> &nbsp; {get_course_badge_html(s['course'], is_light=is_light)} <span class='slot-title-text'>{s['title']}</span> <span class='slot-meta-text'>({slot_dur_str} • {slot_prio_str} Priority)</span></div>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div style='padding-top:3px;'>• {get_course_badge_html(s['course'], is_light=is_light)} <span class='slot-title-text'>{s['title']}</span> <span class='slot-meta-text'>({slot_dur_str} • {slot_prio_str} Priority)</span></div>", unsafe_allow_html=True)
                else:
                    st.caption("Free / No assignments scheduled")
                st.markdown("</div>", unsafe_allow_html=True)


@fragment_decorator
def render_completed_recovery_fragment(user_id: str, is_light: bool):
    df_all = get_assignments_cached(user_id)
    st.markdown("<div class='section-heading'>Completed & Recovery Center</div>", unsafe_allow_html=True)
    st.caption("Tasks you checked off today or finished before their due date can be restored right here.")

    completed_slots_dict = get_completed_slots_cached(user_id)
    st.markdown("#### Today's Completed Study Sessions")
    if completed_slots_dict:
        for s_key, s_info in list(completed_slots_dict.items()):
            rc1, rc2 = st.columns([5.5, 1.5])
            with rc1:
                st.markdown(f"<div class='recovery-card'><div>{get_course_badge_html(s_info.get('course', 'GENERAL'), is_light=is_light)} &nbsp; <span class='slot-title-text'>{s_info.get('title', 'Session')}</span> <span class='slot-meta-text'>({s_info.get('day_name', '')} • {s_info.get('time', '')})</span></div></div>", unsafe_allow_html=True)
            with rc2:
                st.button("Undo / Restore", key=f"rec_slot_{s_key}", on_click=restore_single_daily_slot, args=(s_key, user_id), use_container_width=True)
    else:
        st.caption("No daily study slots have been checked off today.")

    st.markdown("---")
    st.markdown("#### Completed Assignments (Not Yet Expired)")
    df_done = df_all[df_all["status"] == "Done"]
    if not df_done.empty:
        for _, row in df_done.iterrows():
            aid = row.get("id")
            due_d = parse_date_iso_or_empty(row.get("due_date"))
            rc1, rc2 = st.columns([5.5, 1.5])
            with rc1:
                st.markdown(f"<div class='recovery-card'><div>{get_course_badge_html(row.get('course', 'GENERAL'), is_light=is_light)} &nbsp; <span class='slot-title-text'>{row.get('title', 'Assignment')}</span> <span class='slot-meta-text'>(Due {format_mdy(due_d)} • {row.get('atype', 'Homework')})</span></div></div>", unsafe_allow_html=True)
            with rc2:
                st.button("Restore Task", key=f"rec_task_{aid}", on_click=restore_single_assignment, args=(row.to_dict(),), use_container_width=True)
    else:
        st.caption("No completed assignments waiting in recovery.")


# -----------------------
# Main Application Entry
# -----------------------
def main():
    try:
        qp = st.query_params
        if "sync" in qp:
            raw_sync = qp.get("sync")
            if isinstance(raw_sync, list):
                raw_sync = raw_sync[0] if raw_sync else ""
            raw_auto = qp.get("auto", "")
            if isinstance(raw_auto, list):
                raw_auto = raw_auto[0] if raw_auto else ""
            decoded_items = _decode_classroom_sync_payload(str(raw_sync or ""))
            if decoded_items:
                if str(raw_auto) == "1":
                    st.session_state["_classroom_auto_sync"] = decoded_items
                else:
                    st.session_state["_classroom_sync_preview"] = decoded_items
            st.query_params.clear()
    except Exception:
        pass

    user = st.session_state.get("user")
    if not user:
        render_terminal_auth_page()
        return

    user_id = user.get("id")
    email = user.get("email", "")
    hydrate_user_session(user_id)

    theme_cfg = get_theme_cached(user_id)
    is_light = (theme_cfg.get("mode", "Dark") == "Light")
    st.markdown(build_theme_css(theme_cfg), unsafe_allow_html=True)

    user_prio_mode = get_prio_cached(user_id) or "Low / Medium / High"
    shs_cfg = get_shs_cached(user_id)

    if "_classroom_auto_sync" in st.session_state:
        auto_items = st.session_state.pop("_classroom_auto_sync")
        st.session_state["_sync_banner_msg"] = process_auto_classroom_sync(user_id, email, auto_items)

    # Admin System Crash / Fallback Alert Banner
    if is_admin_user(email):
        unresolved_errs = get_unresolved_feature_errors()
        if unresolved_errs:
            latest_err = unresolved_errs[0]
            st.markdown(
                f"<div class='crash-alert-box'>"
                f"<div style='font-weight:800; font-size:0.88rem;'>🚨 Feature Fallback Alert ({len(unresolved_errs)} active) — {latest_err.get('feature_name')}</div>"
                f"<div style='font-size:0.80rem; margin-top:2px;'><b>Error:</b> {latest_err.get('error_msg')} &bull; <i>Users were safely routed to fallback mode.</i></div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            ec1, ec2 = st.columns([2, 1])
            with ec1:
                if st.button("🔍 Inspect Error & Logs in Inbox", key="top_inspect_err_btn", use_container_width=True):
                    show_admin_feedback_inbox_dialog(user_id, email)
            with ec2:
                if st.button("✅ Dismiss Alert", key="top_dismiss_err_btn", use_container_width=True):
                    resolve_feature_error(str(latest_err["id"]))
                    safe_rerun("app")

    # Header Toolbar (8 actions)
    col_brand, col_actions = st.columns([1.85, 3.15])
    with col_brand:
        creator_tag = " &bull; Creator Mode" if is_admin_user(email) else ""
        st.markdown(
            f"""
            <div class='header-brand-box'>
                <div style='display:flex; align-items:center; gap:9px;'>
                    <svg width='24' height='24' viewBox='0 0 24 24' fill='none' xmlns='http://www.w3.org/2000/svg'>
                        <rect x='2' y='3' width='12' height='12' rx='2' fill='currentColor' opacity='0.45'/>
                        <rect x='6' y='7' width='12' height='12' rx='2' fill='currentColor' opacity='0.75'/>
                        <rect x='10' y='11' width='12' height='12' rx='2' fill='currentColor'/>
                    </svg>
                    <span class='app-title'>Assignment Tracker</span>
                </div>
                <div class='app-subtitle'>{email} &bull; System: <span class='accent-text'>{user_prio_mode}</span>{creator_tag}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    unread_fb_count = get_unread_feedback_count(user_id, email)
    inbox_btn_label = f"Inbox ({unread_fb_count})" if (is_admin_user(email) and unread_fb_count > 0) else (
        "Inbox" if is_admin_user(email) else (f"Feedback ({unread_fb_count})" if unread_fb_count > 0 else "Feedback")
    )
    sync_btn_label = "Sync 🧪" if (is_feature_in_beta("classroom_sync_v2") and not is_admin_user(email)) else "Sync"

    with col_actions:
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        b1, b2, b3, b4, b5, b6, b7, b8 = st.columns(8)
        with b1:
            add_btn = st.button("+ Task", key="top_add_btn", use_container_width=True)
        with b2:
            sync_btn = st.button(sync_btn_label, key="top_sync_btn", use_container_width=True)
        with b3:
            courses_btn = st.button("Courses", key="top_courses_btn", use_container_width=True)
        with b4:
            prio_btn = st.button("Priority", key="top_prio_btn", use_container_width=True)
        with b5:
            theme_btn = st.button("Theme", key="top_theme_btn", use_container_width=True)
        with b6:
            updates_btn = st.button("Updates", key="top_updates_btn", use_container_width=True)
        with b7:
            feedback_btn = st.button(inbox_btn_label, key="top_feedback_btn", use_container_width=True)
        with b8:
            signout_btn = st.button("Sign Out", key="top_signout_btn", use_container_width=True)

    # Today's Date + Live SHS Rotation Pill Banner
    now_local = get_local_now()
    shs_today_info = get_shs_day_info(now_local.date(), shs_cfg.get("sheet_url", ""))
    t_letter = shs_today_info.get("letter", "A")
    t_sched = shs_today_info.get("schedule", "Daily")
    if t_letter == "WEEKEND":
        shs_pill_text = "SHS: Weekend"
    elif t_letter == "NO SCHOOL":
        shs_pill_text = f"SHS: No School ({shs_today_info.get('note', 'Holiday')})"
    else:
        sched_tag = f" • {t_sched}" if t_sched != "Daily" else ""
        shs_pill_text = f"SHS: {t_letter} Day{sched_tag}"

    st.markdown(
        f"<div class='date-banner'>Today's Date: {now_local.strftime('%A, %B %d, %Y')} "
        f"<span class='shs-day-pill'>{shs_pill_text}</span></div>",
        unsafe_allow_html=True,
    )

    if "_sync_banner_msg" in st.session_state:
        st.success(st.session_state.pop("_sync_banner_msg"))

    if signout_btn:
        sign_out_user()
        return

    # Modal Routing
    pending_edit_aid = st.session_state.pop("_pending_edit_aid", None)
    prefill_fb = st.session_state.pop("_open_feedback_prefill", None)
    seen_ver = get_seen_updates_cached(user_id)

    global_statuses = get_global_feature_statuses()
    seen_releases = get_seen_releases_cached(user_id)
    newly_released_for_user = [
        fk for fk, st_val in global_statuses.items()
        if st_val == "released" and fk in FEATURE_REGISTRY and fk not in seen_releases
    ]

    if add_btn:
        show_add_assignment_dialog(user_id, user_prio_mode)
    elif sync_btn or "_classroom_sync_preview" in st.session_state:
        show_classroom_sync_dialog(user_id, email, user_prio_mode)
    elif pending_edit_aid:
        show_edit_assignment_dialog(user_id, pending_edit_aid, user_prio_mode)
    elif courses_btn:
        show_manage_courses_dialog(user_id)
    elif prio_btn:
        show_prio_config_dialog(user_id)
    elif theme_btn:
        show_theme_dialog(user_id)
    elif updates_btn:
        show_updates_dialog(user_id, email, is_first_time=False)
    elif feedback_btn or prefill_fb:
        if is_admin_user(email):
            show_admin_feedback_inbox_dialog(user_id, email)
        else:
            show_feedback_dialog(user_id, email, prefill_cat=prefill_fb or "")
    elif seen_ver != CURRENT_APP_VERSION:
        show_updates_dialog(user_id, email, is_first_time=True)
    elif newly_released_for_user and not is_admin_user(email):
        show_public_release_dialog(user_id, newly_released_for_user)
    elif not get_courses_cached(user_id):
        show_welcome_courses_dialog(user_id)
    elif get_prio_cached(user_id) is None:
        show_prio_config_dialog(user_id)

    # Top Navigation Pill Bar
    nav_options = ["Assignments", "Tests & Quizzes", "Other", "Schedule & AI Planner", "SHS Bell Schedule", "Completed & Recovery"]
    active_view = st.radio("Workspace Navigation", nav_options, horizontal=True, label_visibility="collapsed", key="main_workspace_nav")

    if active_view == "Assignments":
        render_assignment_grid_fragment(user_id, "regular", user_prio_mode, is_light, "reg_")
    elif active_view == "Tests & Quizzes":
        render_assignment_grid_fragment(user_id, "tests", user_prio_mode, is_light, "tst_")
    elif active_view == "Other":
        render_assignment_grid_fragment(user_id, "other", user_prio_mode, is_light, "oth_")
    elif active_view == "Schedule & AI Planner":
        render_schedule_and_ai_fragment(user_id, user_prio_mode, is_light)
    elif active_view == "SHS Bell Schedule":
        render_shs_bell_schedule_fragment(user_id, is_light)
    elif active_view == "Completed & Recovery":
        render_completed_recovery_fragment(user_id, is_light)


if __name__ == "__main__":
    main()
