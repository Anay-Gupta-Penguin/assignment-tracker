"""
📚 Assignment Tracker v3.11
Zero-Latency @st.fragment, Live SHS Bell Schedule, Classroom Sync,
Theme Studio & Creator Admin Feature Control Center
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
import urllib.parse
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

CURRENT_APP_VERSION = "3.11"
ADMIN_EMAILS = {"30guptaa@simsburyschools.net"}


def is_admin_user(email: str) -> bool:
    return str(email or "").strip().lower() in ADMIN_EMAILS


# -----------------------
# Central Beta & Feature Release Registry
# -----------------------
FEATURE_REGISTRY: Dict[str, Dict[str, str]] = {
    "classroom_sync_v2": {
        "name": "Google Classroom Sync",
        "version": "3.11",
        "default_status": "beta",
        "location_hint": "Sync button in the top toolbar",
        "beta_summary": "Syncs Classroom assignments, club posts, and instructions via bookmarklet or Ctrl+A paste.",
        "release_summary": "Google Classroom Sync is now officially live for everyone!",
    },
    "shs_bell_schedule": {
        "name": "SHS Bell Schedule",
        "version": "3.11",
        "default_status": "released",
        "location_hint": "SHS Bell Schedule tab",
        "beta_summary": "Live A/B/C/D/X rotation, Connect Wednesdays, delays, and class countdowns.",
        "release_summary": "Live SHS Bell Schedule is now officially released!",
    },
    "ai_study_planner": {
        "name": "Schedule & AI Planner",
        "version": "3.11",
        "default_status": "released",
        "location_hint": "Schedule & AI Planner tab",
        "beta_summary": "Smart daily time-slot planner around your weekly commitments.",
        "release_summary": "Schedule & AI Planner is now officially released!",
    },
    "theme_studio": {
        "name": "Theme & Appearance Studio",
        "version": "3.11",
        "default_status": "released",
        "location_hint": "Theme button in the top toolbar",
        "beta_summary": "Dark/Light themes, custom gradients, and photo backgrounds.",
        "release_summary": "Theme & Appearance Studio is now officially released!",
    },
}


def get_local_now() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.utcnow() - timedelta(hours=5)


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
        return decorator# -----------------------
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
    return blocks# -----------------------
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
            CREATE TABLE IF NOT EXISTS feature_catalog (
                feature_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                location_hint TEXT,
                beta_summary TEXT,
                release_summary TEXT,
                announce_release INTEGER DEFAULT 0
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
# Global Feature Flags, Catalog, Fallback Guard & Error Alerting
# -----------------------
def get_all_feature_catalog(force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    if not force_refresh and "_all_feature_catalog" in st.session_state:
        return st.session_state["_all_feature_catalog"]

    catalog: Dict[str, Dict[str, Any]] = {}
    for k, v in FEATURE_REGISTRY.items():
        catalog[k] = {**v, "announce_release": 0, "is_custom": False}

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT * FROM feature_catalog")).mappings().all()
        for r in rows:
            fk = str(r["feature_key"])
            if fk in catalog:
                catalog[fk]["announce_release"] = int(r.get("announce_release") or 0)
            else:
                catalog[fk] = {
                    "name": str(r.get("name") or fk),
                    "default_status": "beta",
                    "location_hint": str(r.get("location_hint") or "App"),
                    "beta_summary": str(r.get("beta_summary") or "Feature currently in Beta testing."),
                    "release_summary": str(r.get("release_summary") or "This feature is now officially live!"),
                    "announce_release": int(r.get("announce_release") or 0),
                    "is_custom": True,
                }
    except Exception:
        pass

    st.session_state["_all_feature_catalog"] = catalog
    return catalog


def get_global_feature_statuses(force_refresh: bool = False) -> Dict[str, str]:
    if not force_refresh and "_global_feature_statuses" in st.session_state:
        return st.session_state["_global_feature_statuses"]

    catalog = get_all_feature_catalog(force_refresh=force_refresh)
    statuses: Dict[str, str] = {k: v.get("default_status", "released") for k, v in catalog.items()}
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT feature_key, status FROM feature_flags")).mappings().all()
        db_map = {str(r["feature_key"]): str(r["status"]) for r in rows}
        missing = []
        for f_key, meta in catalog.items():
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


def is_feature_enabled(feature_key: str) -> bool:
    return get_global_feature_statuses().get(feature_key, "released") != "disabled"


def is_feature_in_beta(feature_key: str) -> bool:
    return get_global_feature_statuses().get(feature_key, "released") == "beta"


def set_feature_status(feature_key: str, new_status: str, announce_public: bool = False) -> None:
    now_iso = get_local_now().isoformat()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO feature_flags (feature_key, status, updated_at)
                VALUES (:k, :s, :u)
                ON CONFLICT (feature_key) DO UPDATE SET status = EXCLUDED.status, updated_at = EXCLUDED.updated_at;
            """),
            {"k": feature_key, "s": new_status, "u": now_iso},
        )
        if new_status == "released" and announce_public:
            meta = get_all_feature_catalog().get(feature_key, {})
            conn.execute(
                text("""
                    INSERT INTO feature_catalog (feature_key, name, location_hint, beta_summary, release_summary, announce_release)
                    VALUES (:k, :n, :lh, :bs, :rs, 1)
                    ON CONFLICT (feature_key) DO UPDATE SET announce_release = 1;
                """),
                {
                    "k": feature_key,
                    "n": meta.get("name", feature_key),
                    "lh": meta.get("location_hint", ""),
                    "bs": meta.get("beta_summary", ""),
                    "rs": meta.get("release_summary", ""),
                },
            )
    st.session_state.pop("_global_feature_statuses", None)
    st.session_state.pop("_all_feature_catalog", None)


def register_custom_feature(feature_key: str, name: str, status: str, location_hint: str, summary: str) -> None:
    fk = re.sub(r"[^a-z0-9_]", "_", feature_key.strip().lower()).strip("_")
    if not fk:
        return
    now_iso = get_local_now().isoformat()
    ann = 1 if status == "released" else 0
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO feature_catalog (feature_key, name, location_hint, beta_summary, release_summary, announce_release)
                VALUES (:k, :n, :lh, :bs, :rs, :ann)
                ON CONFLICT (feature_key) DO UPDATE SET
                    name = EXCLUDED.name, location_hint = EXCLUDED.location_hint,
                    beta_summary = EXCLUDED.beta_summary, release_summary = EXCLUDED.release_summary,
                    announce_release = EXCLUDED.announce_release;
            """),
            {
                "k": fk,
                "n": name.strip() or fk,
                "lh": location_hint.strip() or "App",
                "bs": summary.strip() or "Currently in Beta testing.",
                "rs": summary.strip() or "Now officially live for everyone!",
                "ann": ann,
            },
        )
        conn.execute(
            text("""
                INSERT INTO feature_flags (feature_key, status, updated_at)
                VALUES (:k, :s, :u)
                ON CONFLICT (feature_key) DO UPDATE SET status = EXCLUDED.status, updated_at = EXCLUDED.updated_at;
            """),
            {"k": fk, "s": status, "u": now_iso},
        )
    st.session_state.pop("_global_feature_statuses", None)
    st.session_state.pop("_all_feature_catalog", None)


def delete_custom_feature(feature_key: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM feature_catalog WHERE feature_key = :k"), {"k": feature_key})
        conn.execute(text("DELETE FROM feature_flags WHERE feature_key = :k"), {"k": feature_key})
    st.session_state.pop("_global_feature_statuses", None)
    st.session_state.pop("_all_feature_catalog", None)


def promote_feature_to_public(feature_key: str) -> None:
    set_feature_status(feature_key, "released", announce_public=True)


def revert_feature_to_beta(feature_key: str) -> None:
    set_feature_status(feature_key, "beta", announce_public=False)


def report_feature_error(feature_key: str, error_msg: str, traceback_txt: str, user_email: str) -> None:
    meta = get_all_feature_catalog().get(feature_key, {})
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
    catalog = get_all_feature_catalog()
    meta = catalog.get(feature_key)
    if not meta:
        return
    status = get_global_feature_statuses().get(feature_key, "released")
    f_name = meta.get("name", feature_key)

    if is_admin_user(email):
        status_label = {
            "released": "🟢 Public Released",
            "beta": "🟡 Beta Testing",
            "disabled": "🔴 Removed / Hidden",
        }.get(status, status)
        with st.expander(f"🛠️ Creator Controls: {f_name} ({status_label})", expanded=(status != "released")):
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("✅ Public Release", key=f"hdr_rel_{feature_key}", use_container_width=True):
                    set_feature_status(feature_key, "released", announce_public=(status == "beta"))
                    safe_rerun("app")
            with c2:
                if st.button("🧪 Set Beta", key=f"hdr_beta_{feature_key}", use_container_width=True):
                    set_feature_status(feature_key, "beta")
                    safe_rerun("app")
            with c3:
                if st.button("🚫 Remove / Hide", key=f"hdr_dis_{feature_key}", use_container_width=True):
                    set_feature_status(feature_key, "disabled")
                    safe_rerun("app")
    else:
        if status == "beta":
            st.markdown(
                f"<div class='beta-banner-box'>"
                f"<div style='font-weight:800; font-size:0.86rem; margin-bottom:2px;'>🧪 Beta Feature (In Testing) — {f_name}</div>"
                f"<div style='font-size:0.79rem;'>This feature is currently in testing. Tell me if anything is wrong or buggy!</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("💬 Report Beta Issue / Send Feedback", key=f"beta_fb_btn_{feature_key}", use_container_width=True):
                st.session_state["_open_feedback_prefill"] = f"Beta Issue: {f_name}"
                safe_rerun("app")# -----------------------
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
        "_all_feature_catalog", "_open_feedback_prefill",
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
    st.session_state["_hydrated_uid"] = user_id# -----------------------
# Session Getters & Instant State + Background DB Writers
# -----------------------
def get_df_cached(user_id: str) -> pd.DataFrame:
    hydrate_user_session(user_id)
    return st.session_state["df_cached"]


def save_df_and_db(user_id: str, df: pd.DataFrame) -> None:
    st.session_state["df_cached"] = df.copy()
    db_rows = []
    for _, r in df.iterrows():
        db_rows.append({
            "id": str(r["id"]),
            "user_id": user_id,
            "title": str(r.get("title", "")),
            "course": str(r.get("course", "GENERAL")).strip().upper(),
            "due_date": str(r.get("due_date", "")),
            "status": str(r.get("status", "Not Started")),
            "priority": priority_to_int(r.get("priority")),
            "atype": str(r.get("atype", "Homework")),
            "eta": str(r.get("eta", "")),
            "notes": _pack_notes(str(r.get("notes", "")), str(r.get("prev_status", "Not Started"))),
            "created_at": str(r.get("created_at") or get_local_now().isoformat()),
        })
    _run_bg_sql(_db_upsert_assignments_worker, db_rows)


def delete_assignment_instant(user_id: str, assignment_id: str) -> None:
    df = get_df_cached(user_id)
    st.session_state["df_cached"] = df[df["id"] != assignment_id].copy()
    _run_bg_sql(_db_delete_assignment_worker, assignment_id)


def get_courses_cached(user_id: str) -> List[str]:
    hydrate_user_session(user_id)
    return st.session_state["cfg_courses"]


def save_courses_cached(user_id: str, courses: List[str]) -> None:
    clean = sorted(list({c.strip().upper() for c in courses if c and c.strip()}))
    st.session_state["cfg_courses"] = clean
    _run_bg_sql(
        _db_upsert_config_worker,
        _cfg_uuid("courses", user_id),
        user_id,
        "__SYSTEM_COURSES__",
        json.dumps(clean),
        get_local_now().isoformat(),
    )


def get_schedule_cached(user_id: str) -> List[Dict[str, Any]]:
    hydrate_user_session(user_id)
    return st.session_state["cfg_schedule"]


def save_schedule_cached(user_id: str, schedule: List[Dict[str, Any]]) -> None:
    st.session_state["cfg_schedule"] = schedule
    _run_bg_sql(
        _db_upsert_config_worker,
        _cfg_uuid("schedule", user_id),
        user_id,
        "__SYSTEM_SCHEDULE__",
        json.dumps(schedule),
        get_local_now().isoformat(),
    )


def get_prio_mode_cached(user_id: str) -> Optional[str]:
    hydrate_user_session(user_id)
    return st.session_state["cfg_prio_mode"]


def save_prio_mode_cached(user_id: str, mode: str) -> None:
    st.session_state["cfg_prio_mode"] = mode
    _run_bg_sql(
        _db_upsert_config_worker,
        _cfg_uuid("prio_mode", user_id),
        user_id,
        "__SYSTEM_PRIO_CONFIG__",
        mode,
        get_local_now().isoformat(),
    )


def get_max_work_cached(user_id: str) -> Dict[str, int]:
    hydrate_user_session(user_id)
    return st.session_state["cfg_max_work"]


def save_max_work_cached(user_id: str, max_work: Dict[str, int]) -> None:
    st.session_state["cfg_max_work"] = max_work
    _run_bg_sql(
        _db_upsert_config_worker,
        _cfg_uuid("max_work", user_id),
        user_id,
        "__SYSTEM_MAX_WORK_CONFIG__",
        json.dumps(max_work),
        get_local_now().isoformat(),
    )


def get_completed_slots_cached(user_id: str) -> Dict[str, Dict[str, Any]]:
    hydrate_user_session(user_id)
    today_iso = get_local_now().date().isoformat()
    if st.session_state.get("cfg_completed_slots_date") != today_iso:
        st.session_state["cfg_completed_slots"] = {}
        st.session_state["cfg_completed_slots_date"] = today_iso
    return st.session_state["cfg_completed_slots"]


def save_completed_slots_cached(user_id: str, slots_dict: Dict[str, Dict[str, Any]]) -> None:
    today_iso = get_local_now().date().isoformat()
    st.session_state["cfg_completed_slots"] = slots_dict
    st.session_state["cfg_completed_slots_date"] = today_iso
    _run_bg_sql(
        _db_upsert_config_worker,
        _cfg_uuid("completed_slots", user_id),
        user_id,
        "__SYSTEM_COMPLETED_SLOTS__",
        json.dumps({today_iso: slots_dict}),
        get_local_now().isoformat(),
    )


def get_seen_updates_cached(user_id: str) -> str:
    hydrate_user_session(user_id)
    return st.session_state["cfg_seen_updates"]


def save_seen_updates_cached(user_id: str, ver_str: str) -> None:
    st.session_state["cfg_seen_updates"] = ver_str
    _run_bg_sql(
        _db_upsert_config_worker,
        _cfg_uuid("seen_updates", user_id),
        user_id,
        "__SYSTEM_SEEN_UPDATES__",
        ver_str,
        get_local_now().isoformat(),
    )


def get_seen_releases_cached(user_id: str) -> List[str]:
    hydrate_user_session(user_id)
    return st.session_state["cfg_seen_releases"]


def save_seen_releases_cached(user_id: str, release_keys: List[str]) -> None:
    clean = sorted(list(set(release_keys)))
    st.session_state["cfg_seen_releases"] = clean
    _run_bg_sql(
        _db_upsert_config_worker,
        _cfg_uuid("seen_releases", user_id),
        user_id,
        "__SYSTEM_SEEN_RELEASES__",
        json.dumps(clean),
        get_local_now().isoformat(),
    )


def get_ignored_sync_cached(user_id: str) -> List[str]:
    hydrate_user_session(user_id)
    return st.session_state["cfg_ignored_sync"]


def save_ignored_sync_cached(user_id: str, ignored_list: List[str]) -> None:
    clean = sorted(list({str(x).strip().lower() for x in ignored_list if str(x).strip()}))
    st.session_state["cfg_ignored_sync"] = clean
    _run_bg_sql(
        _db_upsert_config_worker,
        _cfg_uuid("ignored_sync", user_id),
        user_id,
        "__SYSTEM_IGNORED_SYNC__",
        json.dumps(clean),
        get_local_now().isoformat(),
    )


def get_theme_cached(user_id: str) -> Dict[str, Any]:
    hydrate_user_session(user_id)
    return st.session_state["cfg_theme"]


def save_theme_cached(user_id: str, theme_cfg: Dict[str, Any]) -> None:
    st.session_state["cfg_theme"] = dict(theme_cfg)
    _run_bg_sql(
        _db_upsert_config_worker,
        _cfg_uuid("theme_cfg", user_id),
        user_id,
        "__SYSTEM_THEME_CONFIG__",
        json.dumps(theme_cfg),
        get_local_now().isoformat(),
    )


def get_shs_cached(user_id: str) -> Dict[str, Any]:
    hydrate_user_session(user_id)
    return st.session_state["cfg_shs"]


def save_shs_cached(user_id: str, shs_cfg: Dict[str, Any]) -> None:
    st.session_state["cfg_shs"] = dict(shs_cfg)
    _run_bg_sql(
        _db_upsert_config_worker,
        _cfg_uuid("shs_cfg", user_id),
        user_id,
        "__SYSTEM_SHS_CONFIG__",
        json.dumps(shs_cfg),
        get_local_now().isoformat(),
    )


# -----------------------
# Authentication & Two-Way Feedback / Admin Inbox Functions
# -----------------------
def register_user(email: str, password: str) -> Tuple[bool, str, Optional[str]]:
    clean_email = email.strip().lower()
    if "@" not in clean_email:
        clean_email = f"{clean_email}{DEFAULT_DOMAIN}"
    if not clean_email.endswith(DEFAULT_DOMAIN) and not is_admin_user(clean_email):
        return (False, f"Please use your {DEFAULT_DOMAIN} email.", None)
    if len(password) < 4:
        return (False, "Password must be at least 4 characters.", None)

    uid = str(uuid.uuid4())
    pw_hash = _hash_pw(password)
    now_iso = get_local_now().isoformat()
    try:
        with engine.begin() as conn:
            existing = conn.execute(text("SELECT id FROM users WHERE email = :e"), {"e": clean_email}).fetchone()
            if existing:
                return (False, "An account with this email already exists. Please sign in.", None)
            conn.execute(
                text("INSERT INTO users (id, email, password_hash, created_at) VALUES (:id, :e, :p, :c)"),
                {"id": uid, "e": clean_email, "p": pw_hash, "c": now_iso},
            )
        return (True, "Account created!", uid)
    except Exception as exc:
        return (False, f"Database error: {exc}", None)


def authenticate_user(email: str, password: str) -> Tuple[bool, str, Optional[str], str]:
    clean_email = email.strip().lower()
    if "@" not in clean_email:
        clean_email = f"{clean_email}{DEFAULT_DOMAIN}"
    pw_hash = _hash_pw(password)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, password_hash FROM users WHERE email = :e"),
                {"e": clean_email},
            ).fetchone()
        if not row:
            return (False, "No account found with that email. Switch to Create Account.", None, clean_email)
        if row.password_hash != pw_hash:
            return (False, "Incorrect password.", None, clean_email)
        return (True, "Signed in!", str(row.id), clean_email)
    except Exception as exc:
        return (False, f"Database error: {exc}", None, clean_email)


def submit_feedback_msg(user_id: str, email: str, category: str, rating: int, message: str) -> None:
    fid = str(uuid.uuid4())
    now_iso = get_local_now().isoformat()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO feedback (id, user_id, email, category, rating, message, created_at, is_read_admin, is_read_user)
                VALUES (:id, :uid, :em, :cat, :rat, :msg, :ca, 0, 1)
            """),
            {"id": fid, "uid": user_id, "em": email, "cat": category, "rat": int(rating), "msg": message.strip(), "ca": now_iso},
        )


def reply_to_feedback_msg(feedback_id: str, sender_email: str, is_admin: bool, message: str) -> None:
    rid = str(uuid.uuid4())
    now_iso = get_local_now().isoformat()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO feedback_replies (id, feedback_id, sender_email, is_admin, message, created_at)
                VALUES (:id, :fid, :se, :ia, :msg, :ca)
            """),
            {"id": rid, "fid": feedback_id, "se": sender_email, "ia": 1 if is_admin else 0, "msg": message.strip(), "ca": now_iso},
        )
        if is_admin:
            conn.execute(
                text("UPDATE feedback SET is_read_user = 0, is_read_admin = 1 WHERE id = :fid"),
                {"fid": feedback_id},
            )
        else:
            conn.execute(
                text("UPDATE feedback SET is_read_admin = 0, is_read_user = 1 WHERE id = :fid"),
                {"fid": feedback_id},
            )


def mark_feedback_thread_read(feedback_id: str, is_admin: bool) -> None:
    col = "is_read_admin" if is_admin else "is_read_user"
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE feedback SET {col} = 1 WHERE id = :fid"), {"fid": feedback_id})


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
                threads = conn.execute(text("SELECT * FROM feedback ORDER BY created_at DESC LIMIT 60")).mappings().all()
            else:
                threads = conn.execute(
                    text("SELECT * FROM feedback WHERE user_id = :uid ORDER BY created_at DESC LIMIT 30"),
                    {"uid": user_id},
                ).mappings().all()

            t_list = [dict(t) for t in threads]
            if not t_list:
                return []
            replies = conn.execute(text("SELECT * FROM feedback_replies ORDER BY created_at ASC")).mappings().all()
            rep_map: Dict[str, List[Dict[str, Any]]] = {}
            for r in replies:
                fid = str(r["feedback_id"])
                rep_map.setdefault(fid, []).append(dict(r))
            for t in t_list:
                t["replies"] = rep_map.get(str(t["id"]), [])
            return t_list
    except Exception:
        return []


def delete_feedback_thread(feedback_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM feedback_replies WHERE feedback_id = :fid"), {"fid": feedback_id})
        conn.execute(text("DELETE FROM feedback WHERE id = :fid"), {"fid": feedback_id})# -----------------------
# Google Classroom Sync Parser & Bookmarklet Builder
# -----------------------
CLUB_KEYWORDS = (
    "CLUB", "COUNCIL", "SOCIETY", "NHS", "FBLA", "DECA", "MODEL UN", "MUN",
    "ROBOTICS", "KEY CLUB", "LEO CLUB", "INTERACT", "YEARBOOK", "NEWSPAPER",
    "BAND", "CHOIR", "ORCHESTRA", "THEATER", "DRAMA", "SPORTS", "ATHLETICS",
    "TEAM", "ADVISORY", "CLASS OF 20", "STUDENT GOV", "AMBASSADOR", "PEER",
)


def _is_club_or_activity(class_name: str, title: str) -> bool:
    blob = f"{class_name} {title}".upper()
    return any(kw in blob for kw in CLUB_KEYWORDS)


def _match_classroom_course(raw_class: str, title: str, user_courses: List[str]) -> str:
    if _is_club_or_activity(raw_class, title):
        return "OTHER"
    rc_clean = re.sub(r"\s+", " ", str(raw_class or "")).strip().upper()
    if not rc_clean:
        return "GENERAL"

    for uc in user_courses:
        uc_up = uc.strip().upper()
        if uc_up == rc_clean or uc_up in rc_clean or rc_clean in uc_up:
            return uc_up

    tokens = [t for t in re.split(r"[^A-Z0-9]+", rc_clean) if len(t) >= 3 and t not in ("PERIOD", "PER", "BLOCK", "CLASS", "HONORS", "AP", "CP", "SEM", "FALL", "SPRING", "2026", "2027")]
    best_course = ""
    best_score = 0
    for uc in user_courses:
        uc_up = uc.strip().upper()
        score = sum(1 for tok in tokens if tok in uc_up)
        if score > best_score:
            best_score = score
            best_course = uc_up
    if best_score >= 1 and best_course:
        return best_course

    short_name = re.sub(r"\b(PERIOD|PER|BLOCK)\s*\d+\b", "", rc_clean).strip(" -:|•")
    return short_name[:28] if short_name else "GENERAL"


def _guess_assignment_type(title: str, notes: str, course: str) -> str:
    if course == "OTHER":
        return "Other"
    blob = f"{title} {notes}".lower()
    if any(w in blob for w in ("test", "quiz", "exam", "midterm", "final", "assessment", "frq", "dbq")):
        return "Test & Quizzes"
    if any(w in blob for w in ("essay", "paper", "thesis", "rough draft", "final draft", "composition", "rhetorical")):
        return "Essay"
    if any(w in blob for w in ("presentation", "slides", "slideshow", "poster", "speech", "pitch", "skit")):
        return "Presentation"
    if any(w in blob for w in ("form", "survey", "sign up", "signup", "permission", "field trip", "club", "meeting", "bake sale")):
        return "Other"
    return "Homework"


def _parse_classroom_due_str(raw_due: str, ref_today: date) -> str:
    s = str(raw_due or "").strip()
    if not s or any(k in s.lower() for k in ("no due date", "none", "unscheduled")):
        return ""
    s_clean = re.sub(r"^(due\s*:?\s*)", "", s, flags=re.I).strip()
    s_clean = re.sub(r",?\s*\d{1,2}:\d{2}\s*(AM|PM)?$", "", s_clean, flags=re.I).strip()
    s_clean = re.sub(r"\b11:59\s*PM\b", "", s_clean, flags=re.I).strip(" ,-")

    low = s_clean.lower()
    if low == "today":
        return ref_today.isoformat()
    if low == "tomorrow":
        return (ref_today + timedelta(days=1)).isoformat()
    if low == "yesterday":
        return (ref_today - timedelta(days=1)).isoformat()

    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for idx, wd in enumerate(weekdays):
        if low == wd or low == wd[:3]:
            diff = (idx - ref_today.weekday()) % 7
            return (ref_today + timedelta(days=diff)).isoformat()

    s_no_wd = re.sub(
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s*",
        "",
        s_clean,
        flags=re.I,
    ).strip()

    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s_no_wd, fmt).date().isoformat()
        except ValueError:
            pass

    for fmt_no_yr in ("%b %d", "%B %d", "%m/%d"):
        try:
            dt_obj = datetime.strptime(s_no_wd, fmt_no_yr)
            cand = date(ref_today.year, dt_obj.month, dt_obj.day)
            if (ref_today - cand).days > 180:
                cand = date(ref_today.year + 1, dt_obj.month, dt_obj.day)
            return cand.isoformat()
        except ValueError:
            pass
    return ""


def _is_due_line(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 48:
        return False
    low = s.lower()
    if low in ("no due date", "today", "tomorrow", "yesterday"):
        return True
    if low.startswith("due "):
        return True
    if re.fullmatch(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun)(,?\s*\d{1,2}:\d{2}\s*(AM|PM))?", s, flags=re.I):
        return True
    if re.fullmatch(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(,?\s*\d{4})?(,?\s*\d{1,2}:\d{2}\s*(AM|PM))?", s, flags=re.I):
        return True
    return False


def parse_classroom_sync_input(
    raw_text: str,
    user_courses: List[str],
    existing_df: pd.DataFrame,
    ignored_titles: List[str],
) -> Tuple[List[Dict[str, Any]], int]:
    ref_today = get_local_now().date()
    existing_keys = set()
    if not existing_df.empty:
        for _, r in existing_df.iterrows():
            existing_keys.add(str(r.get("title", "")).strip().lower())
    ignored_set = {x.strip().lower() for x in ignored_titles if x.strip()}

    raw_items: List[Dict[str, str]] = []
    txt = str(raw_text or "").strip()
    if not txt:
        return ([], 0)

    # 1. Try JSON payload from Bookmarklet / Apps Script
    parsed_json = None
    if txt.startswith("{") or txt.startswith("["):
        try:
            parsed_json = json.loads(txt)
        except Exception:
            parsed_json = None

    if parsed_json is not None:
        arr = parsed_json.get("items", []) if isinstance(parsed_json, dict) else (parsed_json if isinstance(parsed_json, list) else [])
        for it in arr:
            if not isinstance(it, dict):
                continue
            t = str(it.get("title") or "").strip()
            if not t:
                continue
            raw_items.append({
                "title": t,
                "course": str(it.get("course") or it.get("class") or "").strip(),
                "due": str(it.get("due") or it.get("dueDate") or "").strip(),
                "notes": str(it.get("notes") or it.get("description") or "").strip(),
            })
    else:
        # 2. Parse Ctrl+A copy-paste from Google Classroom To-do page
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        # Strip left navigation sidebar up to "To-do" / "Assigned" tabs if present
        start_idx = 0
        for idx, ln in enumerate(lines):
            if ln.lower() in ("assigned", "missing", "done"):
                start_idx = idx + 1
                break
        lines = lines[start_idx:]

        skip_exact = {
            "to-do", "to do", "assigned", "missing", "done", "all classes",
            "no due date", "this week", "next week", "later", "this month",
            "earlier", "last week", "calendar", "enrolled", "archived classes",
            "settings", "home", "classes", "work", "view all", "show more",
        }
        filtered: List[str] = []
        for ln in lines:
            low = ln.lower()
            if low in skip_exact:
                continue
            if re.fullmatch(r"\d+\s*(items?|assignments?|missing|assigned)?", low):
                continue
            if len(ln) == 1:
                continue
            filtered.append(ln)

        i = 0
        while i < len(filtered):
            t_cand = filtered[i]
            c_cand = filtered[i + 1] if (i + 1) < len(filtered) else ""
            d_cand = filtered[i + 2] if (i + 2) < len(filtered) else ""

            if c_cand and not _is_due_line(c_cand) and _is_due_line(d_cand):
                raw_items.append({"title": t_cand, "course": c_cand, "due": d_cand, "notes": ""})
                i += 3
            elif _is_due_line(c_cand):
                raw_items.append({"title": t_cand, "course": "GENERAL", "due": c_cand, "notes": ""})
                i += 2
            else:
                if len(t_cand) >= 4 and c_cand and len(c_cand) <= 45 and not _is_due_line(t_cand):
                    raw_items.append({"title": t_cand, "course": c_cand, "due": "", "notes": ""})
                    i += 2
                else:
                    i += 1

    cleaned_results: List[Dict[str, Any]] = []
    skipped_dups = 0
    seen_in_batch = set()

    for item in raw_items:
        title_clean = re.sub(r"\s+", " ", item["title"]).strip()
        t_low = title_clean.lower()
        if not title_clean or len(title_clean) < 2:
            continue
        if t_low in existing_keys or t_low in ignored_set or t_low in seen_in_batch:
            skipped_dups += 1
            continue
        seen_in_batch.add(t_low)

        matched_course = _match_classroom_course(item.get("course", ""), title_clean, user_courses)
        due_iso = _parse_classroom_due_str(item.get("due", ""), ref_today)
        notes_txt = item.get("notes", "").strip()
        atype_guess = _guess_assignment_type(title_clean, notes_txt, matched_course)

        cleaned_results.append({
            "title": title_clean,
            "course": matched_course,
            "due_date": due_iso,
            "atype": atype_guess,
            "priority": 5,
            "eta": "30 mins",
            "notes": notes_txt,
        })

    return (cleaned_results, skipped_dups)


def build_classroom_bookmarklet(app_base_url: str) -> str:
    target = str(app_base_url or "").strip().rstrip("/")
    js = (
        "javascript:(function(){"
        "var items=[];"
        "var rows=document.querySelectorAll('li,div[role=\"listitem\"],a[href*=\"/c/\"]');"
        "var seen={};"
        "rows.forEach(function(r){"
        "var tx=(r.innerText||'').split('\\n').map(function(s){return s.trim();}).filter(Boolean);"
        "if(tx.length>=2&&tx.length<=5&&tx[0].length>2&&!seen[tx[0]]){"
        "seen[tx[0]]=1;"
        "items.push({title:tx[0],course:tx[1]||'',due:tx[2]||''});"
        "}"
        "});"
        "var payload=encodeURIComponent(JSON.stringify({v:1,items:items}));"
        f"var dest='{target}';"
        "if(dest){window.open(dest+'/?gc_sync='+payload,'_blank');}"
        "else{navigator.clipboard.writeText(JSON.stringify({v:1,items:items}));alert('Copied '+items.length+' Classroom items!');}"
        "})();"
    )
    return js


# -----------------------
# Smart Study Schedule Engine
# -----------------------
def _parse_time_to_mins(t_str: str) -> int:
    s = str(t_str or "").strip().upper()
    m = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)?$", s)
    if not m:
        return 15 * 60
    hh = int(m.group(1))
    mm = int(m.group(2))
    ampm = m.group(3)
    if ampm == "PM" and hh != 12:
        hh += 12
    elif ampm == "AM" and hh == 12:
        hh = 0
    return hh * 60 + mm


def _mins_to_time_str(total_mins: int) -> str:
    total_mins = max(0, min(23 * 60 + 59, int(total_mins)))
    hh = total_mins // 60
    mm = total_mins % 60
    ampm = "AM" if hh < 12 else "PM"
    disp_h = hh % 12
    if disp_h == 0:
        disp_h = 12
    return f"{disp_h}:{mm:02d} {ampm}"


def generate_smart_study_plan(
    df: pd.DataFrame,
    schedule: List[Dict[str, Any]],
    max_work_map: Dict[str, int],
    start_date: date,
    days_ahead: int = 7,
) -> Dict[str, Any]:
    active = df[df["status"] != "Done"].copy() if not df.empty else pd.DataFrame()
    plan_days: List[Dict[str, Any]] = []

    if active.empty:
        for offset in range(days_ahead):
            d_obj = start_date + timedelta(days=offset)
            d_name = DAYS_OF_WEEK[d_obj.weekday()]
            plan_days.append({
                "date_iso": d_obj.isoformat(),
                "day_name": d_name,
                "label": d_obj.strftime("%A, %b %d"),
                "used_mins": 0,
                "max_mins": int(max_work_map.get(d_name, 60)),
                "slots": [],
            })
        return {"days": plan_days, "unscheduled": []}

    work_items: List[Dict[str, Any]] = []
    for _, r in active.iterrows():
        aid = str(r["id"])
        title = str(r.get("title", "Untitled"))
        course = str(r.get("course", "GENERAL"))
        due_str = str(r.get("due_date") or "").strip()
        atype = str(r.get("atype", "Homework"))
        notes = str(r.get("notes", ""))
        eta_raw = str(r.get("eta", ""))
        prio = priority_to_int(r.get("priority"))
        eta_mins = parse_eta_to_mins(eta_raw)

        due_dt: Optional[date] = None
        if due_str:
            try:
                due_dt = date.fromisoformat(due_str)
            except Exception:
                due_dt = None

        study_flag = is_study_task(atype, title, notes)
        recurring_flag = is_daily_recurring_task(eta_raw, title, notes)

        if recurring_flag:
            end_d = due_dt if (due_dt and due_dt >= start_date) else (start_date + timedelta(days=days_ahead - 1))
            span = min(days_ahead, max(1, (end_d - start_date).days + 1))
            for off in range(span):
                target_d = start_date + timedelta(days=off)
                work_items.append({
                    "aid": aid,
                    "title": format_study_display_title(title) if study_flag else title,
                    "course": course,
                    "mins": min(eta_mins, 90),
                    "priority": prio,
                    "due_dt": target_d,
                    "preferred_dt": target_d,
                    "is_study": study_flag,
                })
        elif study_flag and due_dt and (due_dt - start_date).days >= 2:
            study_days = min(4, max(2, (due_dt - start_date).days))
            per_session = max(20, min(60, eta_mins // study_days))
            for s_idx in range(study_days):
                pref_d = start_date + timedelta(days=s_idx)
                if pref_d > due_dt:
                    break
                work_items.append({
                    "aid": aid,
                    "title": f"{format_study_display_title(title)} (Session {s_idx + 1}/{study_days})",
                    "course": course,
                    "mins": per_session,
                    "priority": prio,
                    "due_dt": due_dt,
                    "preferred_dt": pref_d,
                    "is_study": True,
                })
        else:
            work_items.append({
                "aid": aid,
                "title": format_study_display_title(title) if study_flag else title,
                "course": course,
                "mins": eta_mins,
                "priority": prio,
                "due_dt": due_dt,
                "preferred_dt": None,
                "is_study": study_flag,
            })

    work_items.sort(key=lambda x: (
        x["due_dt"].isoformat() if x["due_dt"] else "9999-12-31",
        -x["priority"],
        x["mins"],
    ))

    day_buckets: List[Dict[str, Any]] = []
    for offset in range(days_ahead):
        d_obj = start_date + timedelta(days=offset)
        d_name = DAYS_OF_WEEK[d_obj.weekday()]
        cap = int(max_work_map.get(d_name, 60))

        busy_intervals: List[Tuple[int, int]] = []
        if d_obj.weekday() < 5:
            busy_intervals.append((7 * 60 + 20, 14 * 60 + 25))
        for ev in schedule:
            if str(ev.get("day", "")).strip() == d_name:
                st_m = _parse_time_to_mins(ev.get("start", "3:00 PM"))
                en_m = _parse_time_to_mins(ev.get("end", "4:00 PM"))
                if en_m > st_m:
                    busy_intervals.append((st_m, en_m))
        busy_intervals.sort()

        day_buckets.append({
            "date_obj": d_obj,
            "date_iso": d_obj.isoformat(),
            "day_name": d_name,
            "label": d_obj.strftime("%A, %b %d"),
            "used_mins": 0,
            "max_mins": cap,
            "busy": busy_intervals,
            "cursor": 15 * 60 if d_obj.weekday() < 5 else 10 * 60,
            "slots": [],
        })

    def _find_next_free_window(bucket: Dict[str, Any], duration: int) -> Tuple[str, str]:
        cur = bucket["cursor"]
        for b_start, b_end in bucket["busy"]:
            if cur + duration <= b_start:
                break
            if cur < b_end:
                cur = b_end + 10
        end_t = cur + duration
        bucket["cursor"] = end_t + 10
        return (_mins_to_time_str(cur), _mins_to_time_str(end_t))

    unscheduled: List[Dict[str, Any]] = []
    for item in work_items:
        placed = False
        candidate_indices = list(range(days_ahead))
        if item["preferred_dt"]:
            pref_iso = item["preferred_dt"].isoformat()
            candidate_indices.sort(key=lambda idx: 0 if day_buckets[idx]["date_iso"] == pref_iso else 1)

        for idx in candidate_indices:
            b = day_buckets[idx]
            if item["due_dt"] and b["date_obj"] > item["due_dt"]:
                continue
            if b["used_mins"] + item["mins"] <= b["max_mins"]:
                s_str, e_str = _find_next_free_window(b, item["mins"])
                slot_id = hashlib.md5(f"{b['date_iso']}_{item['aid']}_{item['title']}_{len(b['slots'])}".encode()).hexdigest()[:12]
                b["slots"].append({
                    "slot_id": slot_id,
                    "aid": item["aid"],
                    "title": item["title"],
                    "course": item["course"],
                    "mins": item["mins"],
                    "start_time": s_str,
                    "end_time": e_str,
                    "priority": item["priority"],
                })
                b["used_mins"] += item["mins"]
                placed = True
                break

        if not placed:
            # Overflow onto earliest valid day before due date (or today)
            for idx in range(days_ahead):
                b = day_buckets[idx]
                if item["due_dt"] and b["date_obj"] > item["due_dt"] and idx > 0:
                    continue
                s_str, e_str = _find_next_free_window(b, item["mins"])
                slot_id = hashlib.md5(f"{b['date_iso']}_{item['aid']}_{item['title']}_{len(b['slots'])}".encode()).hexdigest()[:12]
                b["slots"].append({
                    "slot_id": slot_id,
                    "aid": item["aid"],
                    "title": item["title"],
                    "course": item["course"],
                    "mins": item["mins"],
                    "start_time": s_str,
                    "end_time": e_str,
                    "priority": item["priority"],
                })
                b["used_mins"] += item["mins"]
                placed = True
                break

        if not placed:
            unscheduled.append(item)

    for b in day_buckets:
        plan_days.append({
            "date_iso": b["date_iso"],
            "day_name": b["day_name"],
            "label": b["label"],
            "used_mins": b["used_mins"],
            "max_mins": b["max_mins"],
            "slots": b["slots"],
        })

    return {"days": plan_days, "unscheduled": unscheduled}# -----------------------
# Modal Dialogs (Admin Panel, Onboarding, Task CRUD, Classroom Sync)
# -----------------------
@dialog_decorator("🛠️ Creator Admin Panel — Feature Control Center")
def show_admin_panel_dialog(user_id: str, email: str):
    if not is_admin_user(email):
        st.error("Admin access only.")
        return

    st.caption("Control every feature live across the entire app: set to Public Released, put in Beta Testing, or Remove/Hide from users.")
    catalog = get_all_feature_catalog(force_refresh=True)
    statuses = get_global_feature_statuses(force_refresh=True)

    for fk, meta in catalog.items():
        cur_st = statuses.get(fk, "released")
        badge_html = {
            "released": "<span class='update-ver-badge'>PUBLIC RELEASED</span>",
            "beta": "<span class='update-beta-badge'>BETA TESTING</span>",
            "disabled": "<span style='background:#f43f5e; color:#fff; padding:2px 8px; border-radius:5px; font-size:0.72rem; font-weight:800; margin-right:6px;'>REMOVED / HIDDEN</span>",
        }.get(cur_st, "")

        st.markdown(
            f"<div class='update-card'>"
            f"<div style='margin-bottom:4px;'>{badge_html} <b>{meta.get('name', fk)}</b> <span class='slot-meta-text'>({fk})</span></div>"
            f"<div style='font-size:0.79rem;' class='slot-meta-text'>Location: {meta.get('location_hint', 'App')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        cols = st.columns([1.2, 1.1, 1.2, 0.8] if meta.get("is_custom") else [1.3, 1.2, 1.3])
        with cols[0]:
            if st.button("✅ Public Release", key=f"adm_rel_{fk}", use_container_width=True, disabled=(cur_st == "released")):
                set_feature_status(fk, "released", announce_public=(cur_st == "beta"))
                safe_rerun("app")
        with cols[1]:
            if st.button("🧪 Set Beta", key=f"adm_beta_{fk}", use_container_width=True, disabled=(cur_st == "beta")):
                set_feature_status(fk, "beta")
                safe_rerun("app")
        with cols[2]:
            if st.button("🚫 Remove", key=f"adm_rem_{fk}", use_container_width=True, disabled=(cur_st == "disabled")):
                set_feature_status(fk, "disabled")
                safe_rerun("app")
        if meta.get("is_custom"):
            with cols[3]:
                if st.button("🗑️", key=f"adm_del_{fk}", use_container_width=True, help="Delete custom feature entry"):
                    delete_custom_feature(fk)
                    safe_rerun("app")

    st.markdown("---")
    with st.expander("➕ Register New Feature Flag", expanded=False):
        with st.form("register_new_feature_form", clear_on_submit=True):
            nf_name = st.text_input("Feature Name", placeholder="e.g. Grade Calculator")
            nf_key = st.text_input("Feature Key (unique ID)", placeholder="e.g. grade_calc")
            nf_loc = st.text_input("Where is it located?", placeholder="e.g. Top toolbar")
            nf_status = st.selectbox(
                "Initial Status",
                ["beta", "released", "disabled"],
                format_func=lambda s: {"beta": "🧪 Beta Testing", "released": "✅ Public Released", "disabled": "🚫 Removed / Hidden"}[s],
            )
            nf_sum = st.text_input("Short Description", placeholder="What does this feature do?")
            if st.form_submit_button("Save Feature to Admin Panel", use_container_width=True):
                if nf_name.strip() and nf_key.strip():
                    register_custom_feature(nf_key, nf_name, nf_status, nf_loc, nf_sum)
                    safe_rerun("app")
                else:
                    st.error("Enter both a Feature Name and Feature Key.")


@dialog_decorator("Welcome! Setup Your Classes")
def show_welcome_courses_dialog(user_id: str):
    st.caption("Add your current classes so you can tag assignments and match Google Classroom automatically.")
    cur = get_courses_cached(user_id)
    with st.form("welcome_courses_form"):
        raw = st.text_area(
            "Enter one class per line",
            value="\n".join(cur) if cur else "AP Calculus\nAP US History\nHonors Chemistry\nEnglish 11\nSpanish 4",
            height=140,
        )
        if st.form_submit_button("Save Classes & Continue", use_container_width=True):
            lines = [x.strip().upper() for x in raw.splitlines() if x.strip()]
            save_courses_cached(user_id, lines if lines else ["GENERAL"])
            safe_rerun("app")


@dialog_decorator("➕ Add New Assignment")
def show_add_assignment_dialog(user_id: str, user_prio_mode: str):
    courses = get_courses_cached(user_id)
    course_opts = sorted(list(set(courses + ["OTHER", "GENERAL"])))
    with st.form("add_task_form", clear_on_submit=True):
        title = st.text_input("Assignment Title *", placeholder="e.g. Chapter 5 Problem Set")
        c1, c2 = st.columns(2)
        with c1:
            course = st.selectbox("Course", course_opts)
            atype = st.selectbox("Type", TYPE_OPTIONS)
        with c2:
            has_due = st.checkbox("Has Due Date", value=True)
            due_val = st.date_input("Due Date", value=get_local_now().date() + timedelta(days=1))

        c3, c4 = st.columns(2)
        with c3:
            if user_prio_mode == "1 to 10 Scale (Slider)":
                prio_int = st.slider("Priority (1-10)", 1, 10, 5)
            else:
                prio_lbl = st.selectbox("Priority", PRIORITY_OPTIONS, index=1)
                prio_int = priority_to_int(prio_lbl)
        with c4:
            eta = st.text_input("Estimated Time", value="30 mins", placeholder="e.g. 45 mins or 1 hr")

        notes = st.text_area("Notes / Instructions (optional)", height=80)
        if st.form_submit_button("Save Assignment", use_container_width=True):
            if not title.strip():
                st.error("Please enter an assignment title.")
            else:
                df = get_df_cached(user_id)
                new_row = pd.DataFrame([{
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "title": title.strip(),
                    "course": course.strip().upper(),
                    "due_date": due_val.isoformat() if has_due else "",
                    "status": "Not Started",
                    "priority": prio_int,
                    "atype": atype,
                    "eta": eta.strip() or "30 mins",
                    "created_at": get_local_now().isoformat(),
                    "notes": notes.strip(),
                    "prev_status": "Not Started",
                }])
                save_df_and_db(user_id, pd.concat([df, new_row], ignore_index=True))
                safe_rerun("app")


@dialog_decorator("✏️ Edit Assignment")
def show_edit_assignment_dialog(user_id: str, assignment_id: str, user_prio_mode: str):
    df = get_df_cached(user_id)
    match = df[df["id"] == assignment_id]
    if match.empty:
        st.session_state.pop("_pending_edit_aid", None)
        st.warning("Assignment not found.")
        return

    row = match.iloc[0]
    courses = get_courses_cached(user_id)
    cur_course = str(row.get("course", "GENERAL")).strip().upper()
    course_opts = sorted(list(set(courses + [cur_course, "OTHER", "GENERAL"])))

    cur_due_str = str(row.get("due_date") or "").strip()
    has_due_init = bool(cur_due_str)
    try:
        due_init = date.fromisoformat(cur_due_str) if has_due_init else get_local_now().date()
    except Exception:
        due_init = get_local_now().date()

    with st.form("edit_task_form"):
        title = st.text_input("Assignment Title", value=str(row.get("title", "")))
        c1, c2 = st.columns(2)
        with c1:
            course = st.selectbox("Course", course_opts, index=course_opts.index(cur_course))
            cur_type = str(row.get("atype", "Homework"))
            atype = st.selectbox("Type", TYPE_OPTIONS, index=TYPE_OPTIONS.index(cur_type) if cur_type in TYPE_OPTIONS else 0)
        with c2:
            has_due = st.checkbox("Has Due Date", value=has_due_init)
            due_val = st.date_input("Due Date", value=due_init)

        c3, c4 = st.columns(2)
        with c3:
            cur_p = priority_to_int(row.get("priority"))
            if user_prio_mode == "1 to 10 Scale (Slider)":
                prio_int = st.slider("Priority (1-10)", 1, 10, cur_p)
            else:
                cur_lbl = priority_to_label(cur_p)
                prio_lbl = st.selectbox("Priority", PRIORITY_OPTIONS, index=PRIORITY_OPTIONS.index(cur_lbl))
                prio_int = priority_to_int(prio_lbl)
        with c4:
            eta = st.text_input("Estimated Time", value=str(row.get("eta", "30 mins")))

        notes = st.text_area("Notes / Instructions", value=str(row.get("notes", "")), height=90)
        b1, b2 = st.columns(2)
        with b1:
            save_btn = st.form_submit_button("💾 Save Changes", use_container_width=True)
        with b2:
            cancel_btn = st.form_submit_button("Cancel", use_container_width=True)

        if save_btn and title.strip():
            df_upd = df.copy()
            idx = df_upd.index[df_upd["id"] == assignment_id]
            df_upd.loc[idx, "title"] = title.strip()
            df_upd.loc[idx, "course"] = course.strip().upper()
            df_upd.loc[idx, "atype"] = atype
            df_upd.loc[idx, "due_date"] = due_val.isoformat() if has_due else ""
            df_upd.loc[idx, "priority"] = prio_int
            df_upd.loc[idx, "eta"] = eta.strip() or "30 mins"
            df_upd.loc[idx, "notes"] = notes.strip()
            save_df_and_db(user_id, df_upd)
            st.session_state.pop("_pending_edit_aid", None)
            safe_rerun("app")
        elif cancel_btn:
            st.session_state.pop("_pending_edit_aid", None)
            safe_rerun("app")


@dialog_decorator("🔄 Google Classroom Sync")
def show_classroom_sync_dialog(user_id: str, email: str, user_prio_mode: str):
    render_feature_stage_header("classroom_sync_v2", user_id, email)
    courses = get_courses_cached(user_id)
    existing_df = get_df_cached(user_id)
    ignored = get_ignored_sync_cached(user_id)
    shs_cfg = get_shs_cached(user_id)

    # Check if bookmarklet sent data via URL query param
    auto_payload = st.session_state.pop("_classroom_auto_sync", "")
    if auto_payload:
        parsed_items, dups = parse_classroom_sync_input(auto_payload, courses, existing_df, ignored)
        st.session_state["_classroom_sync_preview"] = parsed_items
        if dups:
            st.info(f"Skipped {dups} already-imported or ignored items.")

    tab_paste, tab_bm = st.tabs(["📋 Chromebook Ctrl+A Paste Sync", "🔖 Bookmarklet (Personal Device)"])

    with tab_paste:
        st.caption("On your school Chromebook: open Google Classroom → **To-do**, expand **No due date** & **Later**, press **Ctrl+A** then **Ctrl+C**, paste below, and click **Scan & Import**.")
        raw_paste = st.text_area("Paste Classroom To-do text here", height=130, key="gc_paste_area")
        c_scan, c_imp = st.columns(2)
        with c_scan:
            if st.button("🔍 Preview Items", use_container_width=True):
                items, dups = parse_classroom_sync_input(raw_paste, courses, existing_df, ignored)
                st.session_state["_classroom_sync_preview"] = items
                if not items:
                    st.warning(f"No new items found ({dups} duplicates/ignored skipped).")
        with c_imp:
            if st.button("⚡ Scan & Import All Now", use_container_width=True):
                items, dups = parse_classroom_sync_input(raw_paste, courses, existing_df, ignored)
                if items:
                    now_iso = get_local_now().isoformat()
                    new_rows = pd.DataFrame([
                        {
                            "id": str(uuid.uuid4()),
                            "user_id": user_id,
                            "title": it["title"],
                            "course": it["course"],
                            "due_date": it["due_date"],
                            "status": "Not Started",
                            "priority": it["priority"],
                            "atype": it["atype"],
                            "eta": it["eta"],
                            "created_at": now_iso,
                            "notes": it["notes"],
                            "prev_status": "Not Started",
                        }
                        for it in items
                    ])
                    save_df_and_db(user_id, pd.concat([existing_df, new_rows], ignore_index=True))
                    st.session_state.pop("_classroom_sync_preview", None)
                    st.session_state["_sync_banner_msg"] = f"✅ Imported {len(items)} Classroom items!"
                    safe_rerun("app")
                else:
                    st.warning(f"No new items found ({dups} already in your tracker).")

    with tab_bm:
        st.caption("Note: School-managed Chromebooks block `javascript:` bookmarks. Use this on your personal computer or phone.")
        app_url = st.text_input("Your Tracker URL", value=shs_cfg.get("app_url", ""), placeholder="https://your-app.streamlit.app")
        if app_url.strip() != shs_cfg.get("app_url", ""):
            shs_cfg["app_url"] = app_url.strip()
            save_shs_cached(user_id, shs_cfg)
        bm_code = build_classroom_bookmarklet(app_url)
        st.code(bm_code, language="text")

    preview = st.session_state.get("_classroom_sync_preview")
    if preview:
        st.markdown("---")
        st.markdown(f"**Preview ({len(preview)} new items found):**")
        selected_indices = []
        for idx, it in enumerate(preview):
            due_disp = it["due_date"] if it["due_date"] else "No due date"
            chk = st.checkbox(
                f"[{it['course']}] {it['title']} ({it['atype']} • Due: {due_disp})",
                value=True,
                key=f"gc_prev_chk_{idx}",
            )
            if chk:
                selected_indices.append(idx)

        b_add, b_ign = st.columns(2)
        with b_add:
            if st.button(f"✅ Import Selected ({len(selected_indices)})", use_container_width=True):
                chosen = [preview[i] for i in selected_indices]
                if chosen:
                    now_iso = get_local_now().isoformat()
                    new_rows = pd.DataFrame([
                        {
                            "id": str(uuid.uuid4()),
                            "user_id": user_id,
                            "title": it["title"],
                            "course": it["course"],
                            "due_date": it["due_date"],
                            "status": "Not Started",
                            "priority": it["priority"],
                            "atype": it["atype"],
                            "eta": it["eta"],
                            "created_at": now_iso,
                            "notes": it["notes"],
                            "prev_status": "Not Started",
                        }
                        for it in chosen
                    ])
                    save_df_and_db(user_id, pd.concat([existing_df, new_rows], ignore_index=True))
                st.session_state.pop("_classroom_sync_preview", None)
                safe_rerun("app")
        with b_ign:
            if st.button("🚫 Ignore Unchecked Forever", use_container_width=True):
                unchecked = [preview[i]["title"] for i in range(len(preview)) if i not in selected_indices]
                if unchecked:
                    save_ignored_sync_cached(user_id, ignored + unchecked)
                st.session_state.pop("_classroom_sync_preview", None)
                safe_rerun("app")@dialog_decorator("📚 Manage Courses & Ignored Sync Items")
def show_manage_courses_dialog(user_id: str):
    courses = get_courses_cached(user_id)
    with st.form("manage_courses_form"):
        raw = st.text_area("Your Classes (one per line)", value="\n".join(courses), height=140)
        if st.form_submit_button("Save Classes", use_container_width=True):
            lines = [x.strip().upper() for x in raw.splitlines() if x.strip()]
            save_courses_cached(user_id, lines)
            safe_rerun("app")

    ignored = get_ignored_sync_cached(user_id)
    if ignored:
        with st.expander(f"🚫 Ignored Classroom Sync Items ({len(ignored)})", expanded=False):
            st.caption("Items here are skipped automatically when syncing Classroom.")
            if st.button("Clear Ignored List", use_container_width=True):
                save_ignored_sync_cached(user_id, [])
                safe_rerun("app")


@dialog_decorator("⚡ Priority System Settings")
def show_prio_config_dialog(user_id: str):
    cur = get_prio_mode_cached(user_id) or PRIORITY_SYSTEM_MODES[0]
    with st.form("prio_mode_form"):
        chosen = st.radio(
            "Choose how you want to rate assignment priority:",
            PRIORITY_SYSTEM_MODES,
            index=PRIORITY_SYSTEM_MODES.index(cur) if cur in PRIORITY_SYSTEM_MODES else 0,
        )
        if st.form_submit_button("Save Priority Style", use_container_width=True):
            save_prio_mode_cached(user_id, chosen)
            safe_rerun("app")


@dialog_decorator("🎨 Theme & Appearance Studio")
def show_theme_dialog(user_id: str, email: str):
    render_feature_stage_header("theme_studio", user_id, email)
    cur = {**DEFAULT_THEME_CONFIG, **get_theme_cached(user_id)}
    preset_names = list(THEME_PRESETS.keys())
    cur_preset = cur.get("preset") if cur.get("preset") in preset_names else preset_names[0]

    chosen_preset = st.selectbox("Quick Theme Preset", preset_names, index=preset_names.index(cur_preset))
    p_meta = THEME_PRESETS[chosen_preset]

    c1, c2 = st.columns(2)
    with c1:
        mode = st.selectbox("Text Contrast Mode", ["Dark", "Light"], index=0 if (cur.get("mode", p_meta["mode"]) == "Dark") else 1)
        bg_type = st.selectbox("Background Style", ["preset", "solid", "gradient", "photo"], index=["preset", "solid", "gradient", "photo"].index(cur.get("bg_type", "preset")))
    with c2:
        accent = st.color_picker("Accent Color", value=cur.get("accent") or p_meta["accent"])
        card_opacity = st.slider("Card Opacity (%)", 60, 98, int(cur.get("card_opacity", 88)))

    solid_bg = cur.get("solid_bg", p_meta["solid_bg"])
    grad_1 = cur.get("grad_1", p_meta["grad_1"])
    grad_2 = cur.get("grad_2", p_meta["grad_2"])
    grad_3 = cur.get("grad_3", p_meta["grad_3"])
    use_grad_3 = bool(cur.get("use_grad_3", False))
    grad_angle = cur.get("grad_angle", "135deg")
    photo_source = cur.get("photo_source", "")
    overlay_opacity = int(cur.get("overlay_opacity", 45))

    if bg_type == "solid":
        solid_bg = st.color_picker("Solid Background Color", value=solid_bg)
    elif bg_type == "gradient":
        gc1, gc2, gc3 = st.columns(3)
        with gc1:
            grad_1 = st.color_picker("Color 1", value=grad_1)
        with gc2:
            grad_2 = st.color_picker("Color 2", value=grad_2)
        with gc3:
            use_grad_3 = st.checkbox("3rd Color", value=use_grad_3)
            if use_grad_3:
                grad_3 = st.color_picker("Color 3", value=grad_3)
        grad_angle = st.selectbox("Direction", ["135deg", "90deg", "180deg", "radial"], index=["135deg", "90deg", "180deg", "radial"].index(grad_angle) if grad_angle in ["135deg", "90deg", "180deg", "radial"] else 0)
    elif bg_type == "photo":
        up = st.file_uploader("Upload Background Image", type=["png", "jpg", "jpeg", "webp"])
        if up is not None:
            photo_source = encode_uploaded_photo_to_data_uri(up)
        url_in = st.text_input("Or Image URL", value="" if str(photo_source).startswith("data:") else str(photo_source))
        if url_in.strip():
            photo_source = url_in.strip()
        overlay_opacity = st.slider("Readability Tint Overlay (%)", 10, 85, overlay_opacity)

    b1, b2 = st.columns(2)
    with b1:
        if st.button("💾 Apply & Save Theme", use_container_width=True):
            new_cfg = {
                "preset": chosen_preset,
                "mode": p_meta["mode"] if chosen_preset != cur_preset and bg_type == "preset" else mode,
                "accent": p_meta["accent"] if chosen_preset != cur_preset and accent == cur.get("accent") else accent,
                "bg_type": bg_type,
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
            save_theme_cached(user_id, new_cfg)
            safe_rerun("app")
    with b2:
        if st.button("↩️ Reset Default", use_container_width=True):
            save_theme_cached(user_id, dict(DEFAULT_THEME_CONFIG))
            safe_rerun("app")


@dialog_decorator("🎉 New Feature Now in Public Release!")
def show_public_release_dialog(user_id: str, newly_released_keys: List[str]):
    st.caption("A feature you may have seen in Beta testing has officially graduated to full Public Release!")
    catalog = get_all_feature_catalog()
    for fk in newly_released_keys:
        meta = catalog.get(fk, {})
        st.markdown(
            f"<div class='update-card'>"
            f"<div style='margin-bottom:5px;'><span class='update-ver-badge'>PUBLIC RELEASE</span> <b>{meta.get('name', fk)}</b></div>"
            f"<div style='font-size:0.84rem; line-height:1.45;'>{meta.get('release_summary', 'This feature is now officially live and ready for everyday use!')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    if st.button("Awesome, Got It!", use_container_width=True):
        cur_seen = get_seen_releases_cached(user_id)
        save_seen_releases_cached(user_id, cur_seen + newly_released_keys)
        safe_rerun("app")


@dialog_decorator(f"🚀 What's New — v{CURRENT_APP_VERSION}")
def show_updates_dialog(user_id: str, email: str):
    catalog = get_all_feature_catalog()
    statuses = get_global_feature_statuses()

    st.markdown(
        f"<div class='update-card'>"
        f"<div style='margin-bottom:4px;'><span class='update-ver-badge'>v{CURRENT_APP_VERSION}</span> <b>Creator Admin Panel & Chromebook Sync</b></div>"
        f"<div style='font-size:0.83rem;'>Added the Creator Feature Control Center, one-click Chromebook Ctrl+A Classroom Paste Sync, and live SHS Bell Schedule updates.</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    beta_items = [(k, v) for k, v in catalog.items() if statuses.get(k) == "beta"]
    if beta_items:
        st.markdown("**🧪 Currently in Beta Testing:**")
        for fk, meta in beta_items:
            st.markdown(
                f"<div class='update-card'>"
                f"<div style='margin-bottom:4px;'><span class='update-beta-badge'>BETA</span> <b>{meta.get('name', fk)}</b></div>"
                f"<div style='font-size:0.82rem;'>{meta.get('beta_summary', '')}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    if st.button("Close", use_container_width=True):
        save_seen_updates_cached(user_id, CURRENT_APP_VERSION)
        safe_rerun("app")


@dialog_decorator("💬 Feedback & Developer Inbox")
def show_feedback_dialog(user_id: str, email: str):
    admin_mode = is_admin_user(email)
    prefill_cat = st.session_state.pop("_open_feedback_prefill", "")

    if not admin_mode:
        with st.form("send_feedback_form", clear_on_submit=True):
            cats = ["Bug Report", "Feature Request", "Beta Feedback", "General Feedback"]
            def_idx = 2 if prefill_cat else 0
            cat = st.selectbox("Category", cats, index=def_idx)
            rating = st.slider("App Rating", 1, 5, 5)
            msg = st.text_area("Your Message", value=f"{prefill_cat} — " if prefill_cat else "", placeholder="Tell me what's broken or what feature you want next...", height=90)
            if st.form_submit_button("Send Message", use_container_width=True):
                if msg.strip():
                    submit_feedback_msg(user_id, email, cat, rating, msg)
                    st.success("Sent! You'll see replies right below.")
                    safe_rerun("app")
                else:
                    st.error("Please type a message first.")

    threads = get_feedback_threads(user_id, email)
    if not threads:
        st.caption("No messages yet.")
        return

    st.markdown("---")
    for th in threads:
        fid = str(th["id"])
        unread = (int(th.get("is_read_admin") or 0) == 0) if admin_mode else (int(th.get("is_read_user") or 1) == 0)
        tag = "🆕 " if unread else ""
        header = f"{tag}[{th.get('category', 'Feedback')}] {th.get('email', '')} ({th.get('rating', 5)}★)"
        with st.expander(header, expanded=unread):
            if unread:
                mark_feedback_thread_read(fid, admin_mode)
            st.markdown(f"<div class='msg-bubble-user'><b>{th.get('email', 'User')}:</b><br>{th.get('message', '')}</div>", unsafe_allow_html=True)
            for rep in th.get("replies", []):
                cls_b = "msg-bubble-admin" if int(rep.get("is_admin") or 0) == 1 else "msg-bubble-user"
                who = "🛠️ Developer" if int(rep.get("is_admin") or 0) == 1 else rep.get("sender_email", "User")
                st.markdown(f"<div class='{cls_b}'><b>{who}:</b><br>{rep.get('message', '')}</div>", unsafe_allow_html=True)

            rep_txt = st.text_input("Write a reply...", key=f"rep_in_{fid}")
            rc1, rc2 = st.columns([3, 1])
            with rc1:
                if st.button("Send Reply", key=f"rep_btn_{fid}", use_container_width=True):
                    if rep_txt.strip():
                        reply_to_feedback_msg(fid, email, admin_mode, rep_txt)
                        safe_rerun("app")
            with rc2:
                if admin_mode and st.button("🗑️ Delete", key=f"del_fb_{fid}", use_container_width=True):
                    delete_feedback_thread(fid)
                    safe_rerun("app")# -----------------------
# Zero-Latency Workspace Fragments
# -----------------------
@fragment_decorator
def render_assignment_grid_fragment(user_id: str, view_kind: str, user_prio_mode: str, is_light: bool, key_prefix: str):
    df = get_df_cached(user_id)
    today = get_local_now().date()

    if df.empty:
        st.info("No assignments yet! Click **+ Task** or **Sync** in the top bar to get started.")
        return

    active_df = df[df["status"] != "Done"].copy()
    if view_kind == "tests":
        sub = active_df[active_df["atype"] == "Test & Quizzes"].copy()
        empty_msg = "No upcoming Tests or Quizzes!"
    elif view_kind == "other":
        sub = active_df[active_df["atype"] == "Other"].copy()
        empty_msg = "No 'Other' tasks or club items right now."
    else:
        sub = active_df[~active_df["atype"].isin(["Test & Quizzes", "Other"])].copy()
        empty_msg = "All caught up on Homework, Essays, and Presentations!"

    if sub.empty:
        st.success(empty_msg)
        return

    fc1, fc2, fc3 = st.columns([1.4, 1.2, 1.4])
    with fc1:
        courses_avail = ["All Courses"] + sorted(list(sub["course"].dropna().unique()))
        sel_course = st.selectbox("Filter by Class", courses_avail, key=f"{key_prefix}flt_course")
    with fc2:
        sel_status = st.selectbox("Filter by Status", ["All", "Not Started", "In Progress"], key=f"{key_prefix}flt_status")
    with fc3:
        sort_by = st.selectbox("Sort By", ["Due Date (Soonest)", "Priority (Highest)", "Course"], key=f"{key_prefix}sort_by")

    if sel_course != "All Courses":
        sub = sub[sub["course"] == sel_course]
    if sel_status != "All":
        sub = sub[sub["status"] == sel_status]

    if sub.empty:
        st.info("No matching assignments for those filters.")
        return

    sub["_due_sort"] = sub["due_date"].apply(lambda x: str(x).strip() if str(x).strip() else "9999-12-31")
    sub["_prio_sort"] = sub["priority"].apply(priority_to_int)
    if sort_by == "Priority (Highest)":
        sub = sub.sort_values(by=["_prio_sort", "_due_sort"], ascending=[False, True])
    elif sort_by == "Course":
        sub = sub.sort_values(by=["course", "_due_sort"], ascending=[True, True])
    else:
        sub = sub.sort_values(by=["_due_sort", "_prio_sort"], ascending=[True, False])

    cols = st.columns(3)
    for idx, (_, row) in enumerate(sub.iterrows()):
        aid = str(row["id"])
        title = str(row.get("title", "Untitled"))
        course = str(row.get("course", "GENERAL"))
        atype = str(row.get("atype", "Homework"))
        status = str(row.get("status", "Not Started"))
        eta = str(row.get("eta", "30 mins"))
        notes = str(row.get("notes", "")).strip()
        due_str = str(row.get("due_date") or "").strip()
        p_int = priority_to_int(row.get("priority"))
        p_lbl = priority_to_label(p_int)
        p_disp = format_priority_display(p_int, user_prio_mode)
        prio_cls = {"High": "prio-high", "Medium": "prio-medium", "Low": "prio-low"}.get(p_lbl, "prio-medium")

        due_badge = "No due date"
        if due_str:
            try:
                d_obj = date.fromisoformat(due_str)
                diff = (d_obj - today).days
                if diff < 0:
                    due_badge = f"🔴 Overdue ({d_obj.strftime('%b %d')})"
                elif diff == 0:
                    due_badge = "🟠 Due Today"
                elif diff == 1:
                    due_badge = "🟡 Due Tomorrow"
                else:
                    due_badge = f"📅 {d_obj.strftime('%a, %b %d')}"
            except Exception:
                due_badge = f"📅 {due_str}"

        with cols[idx % 3]:
            with st.container(border=True):
                st.markdown(
                    f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                    f"{get_course_badge_html(course, is_light)}"
                    f"<span class='{prio_cls}'>{p_disp}</span>"
                    f"</div>"
                    f"<div class='card-task-title'>{title}</div>"
                    f"<div class='card-task-meta'>{atype} • ⏱️ {eta} • {status}</div>",
                    unsafe_allow_html=True,
                )
                if notes:
                    short_n = notes[:140] + ("..." if len(notes) > 140 else "")
                    st.markdown(f"<div class='card-note-text'>📝 {short_n}</div>", unsafe_allow_html=True)

                st.markdown(f"<div class='card-footer-row'><span class='card-due-text'>{due_badge}</span></div>", unsafe_allow_html=True)

                b1, b2, b3, b4 = st.columns(4)
                with b1:
                    if st.button("✅", key=f"{key_prefix}done_{aid}", help="Mark Done", use_container_width=True):
                        df_upd = get_df_cached(user_id).copy()
                        r_idx = df_upd.index[df_upd["id"] == aid]
                        df_upd.loc[r_idx, "prev_status"] = status
                        df_upd.loc[r_idx, "status"] = "Done"
                        save_df_and_db(user_id, df_upd)
                        safe_rerun("app")
                with b2:
                    next_st = "In Progress" if status == "Not Started" else "Not Started"
                    st_icon = "▶️" if status == "Not Started" else "⏸️"
                    if st.button(st_icon, key=f"{key_prefix}prog_{aid}", help=f"Set {next_st}", use_container_width=True):
                        df_upd = get_df_cached(user_id).copy()
                        df_upd.loc[df_upd["id"] == aid, "status"] = next_st
                        save_df_and_db(user_id, df_upd)
                        safe_rerun("app")
                with b3:
                    if st.button("✏️", key=f"{key_prefix}edit_{aid}", help="Edit", use_container_width=True):
                        st.session_state["_pending_edit_aid"] = aid
                        safe_rerun("app")
                with b4:
                    if st.button("🗑️", key=f"{key_prefix}del_{aid}", help="Delete", use_container_width=True):
                        delete_assignment_instant(user_id, aid)
                        safe_rerun("app")


@fragment_decorator
def render_schedule_and_ai_fragment(user_id: str, email: str, user_prio_mode: str, is_light: bool):
    render_feature_stage_header("ai_study_planner", user_id, email)
    col_sched_side, col_ai_main = st.columns([1.15, 1.85])

    schedule = get_schedule_cached(user_id)
    max_work = get_max_work_cached(user_id)

    with col_sched_side:
        st.markdown("<div class='section-heading'>🗓️ Weekly Commitments & Limits</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        with st.expander("⏱️ Daily Max Study Time Caps", expanded=False):
            new_caps = {}
            for d in DAYS_OF_WEEK:
                new_caps[d] = st.slider(f"{d} (mins)", 15, 300, int(max_work.get(d, 60)), step=15, key=f"cap_{d}")
            if st.button("Save Time Caps", use_container_width=True):
                save_max_work_cached(user_id, new_caps)
                st.success("Saved!")

        with st.expander("➕ Add Practice / Club / Activity", expanded=False):
            with st.form("add_sched_event_form", clear_on_submit=True):
                ev_title = st.text_input("Event Name", placeholder="e.g. Track Practice")
                ev_day = st.selectbox("Day", DAYS_OF_WEEK)
                ec1, ec2 = st.columns(2)
                with ec1:
                    ev_start = st.text_input("Start", value="3:00 PM")
                with ec2:
                    ev_end = st.text_input("End", value="5:00 PM")
                if st.form_submit_button("Add to Weekly Schedule", use_container_width=True):
                    if ev_title.strip():
                        schedule.append({
                            "id": str(uuid.uuid4()),
                            "title": ev_title.strip(),
                            "day": ev_day,
                            "start": ev_start.strip(),
                            "end": ev_end.strip(),
                        })
                        save_schedule_cached(user_id, schedule)
                        safe_rerun("app")

        if schedule:
            for ev in schedule:
                with st.container(border=True):
                    sc1, sc2 = st.columns([4, 1])
                    with sc1:
                        st.markdown(
                            f"<div class='sched-item-text'><b>{ev.get('title')}</b></div>"
                            f"<div class='slot-meta-text'>{ev.get('day')} • {ev.get('start')} – {ev.get('end')}</div>",
                            unsafe_allow_html=True,
                        )
                    with sc2:
                        if st.button("🗑️", key=f"del_ev_{ev.get('id')}", use_container_width=True):
                            upd = [x for x in schedule if x.get("id") != ev.get("id")]
                            save_schedule_cached(user_id, upd)
                            safe_rerun("app")
        else:
            st.caption("No recurring practices or clubs added yet.")

    with col_ai_main:
        st.markdown("<div class='section-heading'>🤖 7-Day Smart Study Plan</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        df = get_df_cached(user_id)
        today = get_local_now().date()
        plan = generate_smart_study_plan(df, schedule, max_work, today, days_ahead=7)
        completed_slots = get_completed_slots_cached(user_id)

        for day_info in plan["days"]:
            used_txt = format_mins_to_hrs_mins(day_info["used_mins"])
            cap_txt = format_mins_to_hrs_mins(day_info["max_mins"])
            st.markdown(
                f"<div class='ai-day-card'>"
                f"<div class='ai-day-header'>"
                f"<span class='ai-day-title'>{day_info['label']}</span>"
                f"<span class='day-time-badge'>{used_txt} <span class='time-max-cap'>/ {cap_txt}</span></span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if not day_info["slots"]:
                st.caption("Free evening — no study blocks needed!")
            else:
                for sl in day_info["slots"]:
                    sid = sl["slot_id"]
                    is_done_slot = sid in completed_slots
                    c_chk, c_body = st.columns([0.5, 5.5])
                    with c_chk:
                        checked = st.checkbox("", value=is_done_slot, key=f"slot_chk_{sid}", label_visibility="collapsed")
                        if checked != is_done_slot:
                            if checked:
                                completed_slots[sid] = {"aid": sl["aid"], "ts": get_local_now().isoformat()}
                            else:
                                completed_slots.pop(sid, None)
                            save_completed_slots_cached(user_id, completed_slots)
                            safe_rerun("fragment")
                    with c_body:
                        strike = "text-decoration: line-through; opacity: 0.6;" if checked else ""
                        st.markdown(
                            f"<div style='{strike}'>"
                            f"<span class='slot-badge'>{sl['start_time']} – {sl['end_time']}</span> "
                            f"{get_course_badge_html(sl['course'], is_light)} "
                            f"<span class='slot-title-text'>{sl['title']}</span> "
                            f"<span class='slot-meta-text'>({sl['mins']}m)</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
            st.markdown("</div>", unsafe_allow_html=True)


@fragment_decorator
def render_shs_bell_schedule_fragment(user_id: str, email: str, is_light: bool):
    render_feature_stage_header("shs_bell_schedule", user_id, email)
    shs_cfg = get_shs_cached(user_id)
    now_dt = get_local_now()

    c_date, c_ov_day, c_ov_sched = st.columns([1.3, 1.1, 1.4])
    with c_date:
        sel_date = st.date_input("Date", value=now_dt.date(), key="shs_date_pick")

    auto_info = get_shs_day_info(sel_date, shs_cfg.get("sheet_url", ""))
    auto_letter = auto_info.get("letter", "A")
    auto_sched = auto_info.get("schedule", "Daily")

    with c_ov_day:
        day_opts = ["Auto", "A", "B", "C", "D", "X", "NO SCHOOL"]
        ov_day = st.selectbox("Rotation Day", day_opts, index=0, key="shs_ov_day")
    with c_ov_sched:
        sched_opts = ["Auto"] + SHS_SCHEDULE_TYPES
        ov_sched = st.selectbox("Bell Schedule Type", sched_opts, index=0, key="shs_ov_sched")

    eff_letter = auto_letter if ov_day == "Auto" else ov_day
    eff_sched = auto_sched if ov_sched == "Auto" else ov_sched

    with st.expander("⚙️ Configure Your Periods (1–8), Lunch Waves & Study Hall Rooms", expanded=False):
        with st.form("shs_periods_form"):
            p_cols = st.columns(4)
            new_periods = dict(shs_cfg.get("periods", {}))
            for p_num in range(1, 9):
                with p_cols[(p_num - 1) % 4]:
                    new_periods[str(p_num)] = st.text_input(f"Period {p_num}", value=new_periods.get(str(p_num), ""))

            l_cols = st.columns(5)
            new_lunches = dict(shs_cfg.get("lunches", {}))
            for idx, d_let in enumerate(["A", "B", "C", "D", "X"]):
                with l_cols[idx]:
                    cur_l = new_lunches.get(d_let, "L2")
                    new_lunches[d_let] = st.selectbox(f"{d_let} Day Lunch", ["L1", "L2", "L3"], index=["L1", "L2", "L3"].index(cur_l) if cur_l in ["L1", "L2", "L3"] else 1)

            r_cols = st.columns(5)
            new_rooms = dict(shs_cfg.get("study_rooms", {}))
            for idx, d_let in enumerate(["A", "B", "C", "D", "X"]):
                with r_cols[idx]:
                    new_rooms[d_let] = st.text_input(f"{d_let} Study Rm", value=new_rooms.get(d_let, ""), placeholder="e.g. 214")

            sheet_in = st.text_input("Optional Live Google Sheet CSV/Link", value=shs_cfg.get("sheet_url", ""))
            if st.form_submit_button("Save SHS Bell Settings", use_container_width=True):
                shs_cfg["periods"] = new_periods
                shs_cfg["lunches"] = new_lunches
                shs_cfg["study_rooms"] = new_rooms
                shs_cfg["sheet_url"] = sheet_in.strip()
                save_shs_cached(user_id, shs_cfg)
                safe_rerun("fragment")

    if eff_letter in ("WEEKEND", "NO SCHOOL"):
        note_str = auto_info.get("note") or ("Weekend" if eff_letter == "WEEKEND" else "No School")
        st.info(f"🎉 **{note_str}** — No classes scheduled for {sel_date.strftime('%A, %B %d')}.")
        return

    drop_txt = SHS_DROPPED_PERIODS.get(eff_letter, "")
    extra_note = f" • {auto_info.get('note')}" if auto_info.get("note") else ""
    st.markdown(
        f"<div class='date-banner'>"
        f"{sel_date.strftime('%A, %B %d, %Y')} "
        f"<span class='shs-day-pill'>{eff_letter} DAY</span> "
        f"<span class='shs-day-pill'>{eff_sched}</span>"
        f"<div style='font-size:0.76rem; margin-top:4px;' class='slot-meta-text'>{drop_txt}{extra_note}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    lunch_wave = shs_cfg.get("lunches", {}).get(eff_letter, "L2")
    blocks = build_shs_bell_blocks(
        eff_letter,
        eff_sched,
        lunch_wave,
        shs_cfg.get("periods", {}),
        shs_cfg.get("study_rooms", {}),
    )

    cur_mins = now_dt.hour * 60 + now_dt.minute
    is_today = (sel_date == now_dt.date())

    for blk in blocks:
        st_m = _parse_time_to_mins(blk["start"])
        en_m = _parse_time_to_mins(blk["end"])
        is_live = is_today and (st_m <= cur_mins <= en_m)
        row_cls = "bell-row bell-row-active" if is_live else "bell-row"
        live_tag = f"<span class='bell-live-tag'>NOW • {en_m - cur_mins}m LEFT</span>" if is_live else ""
        rm_tag = f" <span class='slot-meta-text'>({blk['room']})</span>" if blk.get("room") else ""
        ann_tag = " 📢" if blk.get("ann") == "1" else ""

        st.markdown(
            f"<div class='{row_cls}'>"
            f"<div>"
            f"<span class='bell-period-badge'>{blk['label']}</span> "
            f"{get_course_badge_html(blk['class_name'], is_light)}{rm_tag}{ann_tag}{live_tag}"
            f"</div>"
            f"<div style='font-weight:800; font-size:0.86rem;'>{blk['start']} – {blk['end']} <span class='slot-meta-text'>({blk['mins']})</span></div>"
            f"</div>",
            unsafe_allow_html=True,
        )@fragment_decorator
def render_completed_recovery_fragment(user_id: str, is_light: bool):
    df = get_df_cached(user_id)
    done_df = df[df["status"] == "Done"].copy() if not df.empty else pd.DataFrame()

    st.markdown("<div class='section-heading'>✅ Completed Today & Task Recovery</div>", unsafe_allow_html=True)
    st.caption("Completed tasks stay here until midnight so you can undo any accidental check-offs.")

    if done_df.empty:
        st.info("No completed tasks waiting in recovery.")
        return

    for _, row in done_df.iterrows():
        aid = str(row["id"])
        title = str(row.get("title", "Untitled"))
        course = str(row.get("course", "GENERAL"))
        prev_st = str(row.get("prev_status") or "Not Started")

        with st.container(border=True):
            c1, c2, c3 = st.columns([4.2, 1.1, 0.8])
            with c1:
                st.markdown(
                    f"{get_course_badge_html(course, is_light)} "
                    f"<span style='font-weight:800; margin-left:6px;'>{title}</span>",
                    unsafe_allow_html=True,
                )
            with c2:
                if st.button("↩️ Restore", key=f"rest_{aid}", use_container_width=True):
                    df_upd = get_df_cached(user_id).copy()
                    df_upd.loc[df_upd["id"] == aid, "status"] = prev_st if prev_st != "Done" else "Not Started"
                    save_df_and_db(user_id, df_upd)
                    safe_rerun("app")
            with c3:
                if st.button("🗑️", key=f"perm_del_{aid}", use_container_width=True, help="Delete permanently"):
                    delete_assignment_instant(user_id, aid)
                    safe_rerun("app")


# -----------------------
# Authentication View
# -----------------------
def render_auth_screen():
    st.markdown(
        "<div style='max-width:440px; margin: 2.5rem auto 1rem auto; text-align:center;'>"
        "<div class='app-title'>📑 Assignment Tracker</div>"
        "<div class='app-subtitle'>Simsbury High School Student Planner & Classroom Sync</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    _, col_mid, _ = st.columns([1, 1.35, 1])
    with col_mid:
        tab_in, tab_up = st.tabs(["🔑 Sign In", "✨ Create Account"])
        with tab_in:
            with st.form("login_form"):
                em = st.text_input("School Email or Username", placeholder="30lastf@simsburyschools.net")
                pw = st.text_input("Password", type="password")
                if st.form_submit_button("Sign In", use_container_width=True):
                    ok, msg, uid, clean_em = authenticate_user(em, pw)
                    if ok and uid:
                        clear_all_session_caches()
                        st.session_state["user_id"] = uid
                        st.session_state["user_email"] = clean_em
                        safe_rerun("app")
                    else:
                        st.error(msg)

        with tab_up:
            with st.form("register_form"):
                em_new = st.text_input("School Email", placeholder="30lastf@simsburyschools.net")
                pw_new = st.text_input("Create Password (min 4 chars)", type="password")
                if st.form_submit_button("Create Account", use_container_width=True):
                    ok, msg, uid = register_user(em_new, pw_new)
                    if ok and uid:
                        clean_em = em_new.strip().lower()
                        if "@" not in clean_em:
                            clean_em = f"{clean_em}{DEFAULT_DOMAIN}"
                        clear_all_session_caches()
                        st.session_state["user_id"] = uid
                        st.session_state["user_email"] = clean_em
                        safe_rerun("app")
                    else:
                        st.error(msg)# -----------------------
# Main Application Controller
# -----------------------
def main():
    user_id = st.session_state.get("user_id")
    email = st.session_state.get("user_email", "")

    if not user_id:
        st.markdown(build_theme_css(DEFAULT_THEME_CONFIG), unsafe_allow_html=True)
        render_auth_screen()
        return

    hydrate_user_session(user_id)
    theme_cfg = get_theme_cached(user_id)
    st.markdown(build_theme_css(theme_cfg), unsafe_allow_html=True)
    is_light = (theme_cfg.get("mode", "Dark") == "Light")

    # Capture bookmarklet URL payload if opened from a personal device
    try:
        gc_param = st.query_params.get("gc_sync", "")
        if gc_param:
            st.session_state["_classroom_auto_sync"] = urllib.parse.unquote(str(gc_param))
            st.query_params.clear()
    except Exception:
        pass

    user_prio_mode = get_prio_mode_cached(user_id) or PRIORITY_SYSTEM_MODES[0]
    pending_edit_aid = st.session_state.get("_pending_edit_aid")

    if "_sync_banner_msg" in st.session_state:
        st.success(st.session_state.pop("_sync_banner_msg"))

    # Admin Health / Crash Fallback Alerts
    if is_admin_user(email):
        unresolved = get_unresolved_feature_errors()
        if unresolved:
            for err in unresolved[:3]:
                st.markdown(
                    f"<div class='crash-alert-box'>"
                    f"<b>🚨 Feature Fallback Triggered: {err.get('feature_name')}</b><br>"
                    f"<span style='font-size:0.80rem;'>{err.get('error_msg')} (User: {err.get('user_email')})</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if st.button("Mark Resolved", key=f"res_err_{err['id']}"):
                    resolve_feature_error(str(err["id"]))
                    safe_rerun("app")

    # Top Header & Action Toolbar
    col_brand, col_actions = st.columns([1.45, 2.55])
    with col_brand:
        st.markdown(
            f"<div class='header-brand-box'>"
            f"<div class='app-title'>📑 Assignment Tracker</div>"
            f"<div class='app-subtitle'>Signed in as <span class='accent-text'>{email}</span> • v{CURRENT_APP_VERSION}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    unread_fb_count = get_unread_feedback_count(user_id, email)
    inbox_btn_label = (
        f"Inbox ({unread_fb_count})"
        if (is_admin_user(email) and unread_fb_count > 0)
        else ("Inbox" if is_admin_user(email) else (f"Feedback ({unread_fb_count})" if unread_fb_count > 0 else "Feedback"))
    )

    sync_enabled = is_feature_enabled("classroom_sync_v2")
    theme_enabled = is_feature_enabled("theme_studio")
    sync_btn_label = (
        "Sync 🚫"
        if (not sync_enabled and is_admin_user(email))
        else ("Sync 🧪" if (is_feature_in_beta("classroom_sync_v2") and not is_admin_user(email)) else "Sync")
    )
    theme_btn_label = (
        "Theme 🚫"
        if (not theme_enabled and is_admin_user(email))
        else ("Theme 🧪" if (is_feature_in_beta("theme_studio") and not is_admin_user(email)) else "Theme")
    )

    admin_btn = False
    sync_btn = False
    theme_btn = False

    with col_actions:
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        if is_admin_user(email):
            b1, b2, b3, b4, b5, b6, b7, b8, b9 = st.columns(9)
            with b1:
                add_btn = st.button("+ Task", key="top_add_btn", use_container_width=True)
            with b2:
                sync_btn = st.button(sync_btn_label, key="top_sync_btn", use_container_width=True)
            with b3:
                courses_btn = st.button("Courses", key="top_courses_btn", use_container_width=True)
            with b4:
                prio_btn = st.button("Priority", key="top_prio_btn", use_container_width=True)
            with b5:
                theme_btn = st.button(theme_btn_label, key="top_theme_btn", use_container_width=True)
            with b6:
                updates_btn = st.button("Updates", key="top_updates_btn", use_container_width=True)
            with b7:
                feedback_btn = st.button(inbox_btn_label, key="top_feedback_btn", use_container_width=True)
            with b8:
                admin_btn = st.button("Admin", key="top_admin_btn", use_container_width=True)
            with b9:
                signout_btn = st.button("Sign Out", key="top_signout_btn", use_container_width=True)
        else:
            b1, b2, b3, b4, b5, b6, b7, b8 = st.columns(8)
            with b1:
                add_btn = st.button("+ Task", key="top_add_btn", use_container_width=True)
            with b2:
                if sync_enabled:
                    sync_btn = st.button(sync_btn_label, key="top_sync_btn", use_container_width=True)
            with b3:
                courses_btn = st.button("Courses", key="top_courses_btn", use_container_width=True)
            with b4:
                prio_btn = st.button("Priority", key="top_prio_btn", use_container_width=True)
            with b5:
                if theme_enabled:
                    theme_btn = st.button(theme_btn_label, key="top_theme_btn", use_container_width=True)
            with b6:
                updates_btn = st.button("Updates", key="top_updates_btn", use_container_width=True)
            with b7:
                feedback_btn = st.button(inbox_btn_label, key="top_feedback_btn", use_container_width=True)
            with b8:
                signout_btn = st.button("Sign Out", key="top_signout_btn", use_container_width=True)

    if signout_btn:
        clear_all_session_caches()
        st.session_state.pop("user_id", None)
        st.session_state.pop("user_email", None)
        safe_rerun("app")

    global_statuses = get_global_feature_statuses()
    full_catalog = get_all_feature_catalog()
    seen_releases = get_seen_releases_cached(user_id)
    newly_released_for_user = [
        fk
        for fk, st_val in global_statuses.items()
        if st_val == "released" and int(full_catalog.get(fk, {}).get("announce_release") or 0) == 1 and fk not in seen_releases
    ]

    if admin_btn:
        show_admin_panel_dialog(user_id, email)
    elif add_btn:
        show_add_assignment_dialog(user_id, user_prio_mode)
    elif sync_btn or "_classroom_sync_preview" in st.session_state or "_classroom_auto_sync" in st.session_state:
        show_classroom_sync_dialog(user_id, email, user_prio_mode)
    elif pending_edit_aid:
        show_edit_assignment_dialog(user_id, pending_edit_aid, user_prio_mode)
    elif courses_btn:
        show_manage_courses_dialog(user_id)
    elif prio_btn:
        show_prio_config_dialog(user_id)
    elif theme_btn:
        show_theme_dialog(user_id, email)
    elif updates_btn:
        show_updates_dialog(user_id, email)
    elif feedback_btn or "_open_feedback_prefill" in st.session_state:
        show_feedback_dialog(user_id, email)
    elif newly_released_for_user and not is_admin_user(email):
        show_public_release_dialog(user_id, newly_released_for_user)
    elif not get_courses_cached(user_id):
        show_welcome_courses_dialog(user_id)

    # Top Navigation Pill Bar (respects Admin feature toggles)
    ai_enabled = is_feature_enabled("ai_study_planner")
    shs_enabled = is_feature_enabled("shs_bell_schedule")
    ai_tab_label = "Schedule & AI Planner 🚫" if (not ai_enabled and is_admin_user(email)) else "Schedule & AI Planner"
    shs_tab_label = "SHS Bell Schedule 🚫" if (not shs_enabled and is_admin_user(email)) else "SHS Bell Schedule"

    nav_options = ["Assignments", "Tests & Quizzes", "Other"]
    if ai_enabled or is_admin_user(email):
        nav_options.append(ai_tab_label)
    if shs_enabled or is_admin_user(email):
        nav_options.append(shs_tab_label)
    nav_options.append("Completed & Recovery")

    active_view = st.radio(
        "Workspace Navigation",
        nav_options,
        horizontal=True,
        label_visibility="collapsed",
        key="main_workspace_nav",
    )

    if active_view == "Assignments":
        render_assignment_grid_fragment(user_id, "regular", user_prio_mode, is_light, "reg_")
    elif active_view == "Tests & Quizzes":
        render_assignment_grid_fragment(user_id, "tests", user_prio_mode, is_light, "tst_")
    elif active_view == "Other":
        render_assignment_grid_fragment(user_id, "other", user_prio_mode, is_light, "oth_")
    elif active_view == ai_tab_label:
        render_schedule_and_ai_fragment(user_id, email, user_prio_mode, is_light)
    elif active_view == shs_tab_label:
        render_shs_bell_schedule_fragment(user_id, email, is_light)
    elif active_view == "Completed & Recovery":
        render_completed_recovery_fragment(user_id, is_light)


if __name__ == "__main__":
    main()
