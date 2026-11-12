"""
📚 Assignment Tracker — Zero-Latency @st.fragment & Onboarding Updates Edition
Features:
- First-Sign-In "What's New, Previous Updates & Quick Guide" Modal (version-tracked in DB)
- Single-query session hydration (1 DB read per login)
- Optimistic in-memory UI + background thread PostgreSQL sync (0ms click freeze)
- Isolated @st.fragment views for Assignments, Tests, Other, AI Planner & Recovery
- Mobile portrait layout optimization
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from datetime import datetime, date, timedelta, time
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# Bump this version string anytime you push new features to auto-show the modal once per user
CURRENT_APP_VERSION = "3.0"


# Timezone helper for Simsbury/Eastern Time
def get_local_now() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.utcnow() - timedelta(hours=4)


# -----------------------
# Streamlit Page Config & Custom Mobile-Optimized Styling
# -----------------------
st.set_page_config(
    page_title="Assignment Tracker",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, .stApp {
        background-color: #070a12 !important;
        background-image: 
            radial-gradient(at 15% 15%, rgba(99, 102, 241, 0.08) 0px, transparent 50%),
            radial-gradient(at 85% 85%, rgba(14, 165, 233, 0.06) 0px, transparent 50%);
        color: #f1f5f9 !important;
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

    /* Pill Navigation Bar */
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        display: flex;
        flex-wrap: nowrap;
        gap: 6px;
        background-color: rgba(15, 23, 42, 0.65);
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 5px;
        margin-bottom: 18px;
        backdrop-filter: blur(8px);
        overflow-x: auto;
        scrollbar-width: none;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"]::-webkit-scrollbar {
        display: none;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label {
        background-color: transparent !important;
        border-radius: 8px !important;
        padding: 7px 16px !important;
        margin: 0 !important;
        cursor: pointer;
        border: none !important;
        white-space: nowrap;
        transition: all 0.15s ease-in-out;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label p {
        color: #94a3b8 !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        margin: 0 !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label[data-checked="true"],
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
        background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%) !important;
        box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35) !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label[data-checked="true"] p,
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) p {
        color: #ffffff !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(15, 23, 42, 0.75) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 14px !important;
        padding: 16px 18px !important;
        margin-bottom: 16px !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        backdrop-filter: blur(12px);
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }

    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: rgba(99, 102, 241, 0.4) !important;
        box-shadow: 0 10px 30px rgba(99, 102, 241, 0.15);
    }

    .app-title {
        font-size: 1.7rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.03em;
        margin: 0;
    }

    .app-subtitle {
        font-size: 0.82rem;
        color: #64748b;
        font-weight: 500;
        margin-top: 2px;
    }

    .date-banner {
        background: linear-gradient(90deg, rgba(30, 27, 75, 0.5) 0%, rgba(15, 23, 42, 0.7) 100%);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 10px;
        padding: 9px 16px;
        font-size: 0.84rem;
        font-weight: 700;
        color: #818cf8;
        text-align: center;
        margin-bottom: 14px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
    }

    .prio-high {
        background: rgba(244, 63, 94, 0.15);
        color: #fb7185;
        border: 1px solid rgba(244, 63, 94, 0.35);
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
    }

    .prio-medium {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.35);
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
    }

    .prio-low {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.35);
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
    }

    .ai-day-card {
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 14px;
    }

    .ai-day-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 1px solid #1e293b;
        padding-bottom: 8px;
        margin-bottom: 10px;
        flex-wrap: wrap;
        gap: 6px;
    }

    .ai-day-title {
        color: #38bdf8;
        font-size: 0.95rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .day-time-badge {
        background: rgba(14, 165, 233, 0.12);
        border: 1px solid rgba(56, 189, 248, 0.3);
        border-radius: 6px;
        padding: 3px 10px;
        font-size: 0.78rem;
        font-weight: 700;
        color: #e0f2fe;
    }

    .time-max-cap {
        color: #94a3b8;
        font-weight: 500;
    }

    .slot-badge {
        background: #1e1b4b;
        color: #38bdf8;
        border: 1px solid #0284c7;
        padding: 3px 8px;
        border-radius: 6px;
        font-family: monospace;
        font-size: 0.78rem;
        font-weight: 700;
    }

    .undo-toast-box {
        position: relative;
        background-color: #0f172a;
        border: 1px solid #3b82f6;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .recovery-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    /* Update / Changelog Modal Styling */
    .update-card {
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 10px;
    }

    .update-ver-badge {
        background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
        color: #ffffff;
        padding: 2px 8px;
        border-radius: 5px;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.03em;
        margin-right: 6px;
    }

    .update-old-badge {
        background: rgba(148, 163, 184, 0.15);
        color: #cbd5e1;
        border: 1px solid rgba(148, 163, 184, 0.3);
        padding: 2px 8px;
        border-radius: 5px;
        font-size: 0.72rem;
        font-weight: 700;
        margin-right: 6px;
    }

    .tip-card {
        background: rgba(14, 165, 233, 0.08);
        border-left: 3px solid #38bdf8;
        border-radius: 6px;
        padding: 10px 12px;
        margin-bottom: 9px;
        font-size: 0.84rem;
        color: #e2e8f0;
    }

    /* -------------------------------------------
       MOBILE & VERTICAL PORTRAIT OPTIMIZATIONS
    ------------------------------------------- */
    @media (max-width: 768px) {
        .main .block-container {
            padding-top: 0.5rem !important;
            padding-left: 0.45rem !important;
            padding-right: 0.45rem !important;
        }

        .app-title {
            font-size: 1.28rem !important;
        }

        .app-subtitle {
            font-size: 0.74rem !important;
        }

        div[data-testid="stHorizontalBlock"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])) {
            flex-wrap: nowrap !important;
            gap: 5px !important;
        }
        div[data-testid="stHorizontalBlock"]:not(:has(div[data-testid="stVerticalBlockBorderWrapper"])) > div[data-testid="stColumn"] {
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

        div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 12px 13px !important;
            margin-bottom: 10px !important;
            border-radius: 12px !important;
        }

        .stButton button {
            padding: 4px 5px !important;
            font-size: 0.71rem !important;
            min-height: 32px !important;
        }

        .ai-day-card {
            padding: 12px !important;
            margin-bottom: 10px !important;
        }

        .ai-day-header {
            flex-direction: row;
            align-items: center;
            justify-content: space-between;
            gap: 4px;
        }

        .day-time-badge {
            font-size: 0.70rem;
            padding: 2px 7px;
        }

        .date-banner {
            padding: 7px 10px !important;
            font-size: 0.75rem !important;
            margin-bottom: 10px !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------
# Streamlit Decorators (@st.fragment, @st.dialog & Rerun Helpers)
# -----------------------
def safe_rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


if hasattr(st, "fragment"):
    fragment_decorator = st.fragment
elif hasattr(st, "experimental_fragment"):
    fragment_decorator = st.experimental_fragment
else:
    def fragment_decorator(func=None, **kwargs):
        if func is None:
            return lambda f: f
        return func


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
}


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
    db_url = get_connection_url()
    return create_engine(db_url, pool_pre_ping=True, pool_size=5, max_overflow=10)


@st.cache_resource
def get_db_write_lock() -> threading.Lock:
    return threading.Lock()


engine = get_db_engine()
db_write_lock = get_db_write_lock()


def _run_bg_sql(worker_fn: Callable[..., None], *args: Any, **kwargs: Any) -> None:
    """Executes database writes asynchronously on a daemon thread so UI never freezes."""
    def _target():
        with db_write_lock:
            try:
                worker_fn(*args, **kwargs)
            except Exception:
                pass

    t = threading.Thread(target=_target, daemon=True)
    t.start()


@st.cache_resource
def init_db_once():
    sql_users = text("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    sql_assignments = text("""
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
    """)
    with engine.begin() as conn:
        conn.execute(sql_users)
        conn.execute(sql_assignments)
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
    h = mins // 60
    m = mins % 60
    if h == 0:
        return f"{m} mins"
    if m == 0:
        return f"{h} hr" if h == 1 else f"{h} hrs"
    return f"{h} hr {m} mins" if h == 1 else f"{h} hrs {m} mins"


def get_course_badge_html(course_name: str) -> str:
    c = str(course_name or "GENERAL").strip().upper()
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

    return f"<span style='background-color:{bg}; color:{fg}; border:1px solid {border}; padding:3px 9px; border-radius:6px; font-weight:700; font-size:0.73rem; letter-spacing:0.03em; display:inline-block;'>{c}</span>"


def priority_to_label(val: Any) -> str:
    if pd.isna(val) or val is None:
        return "Medium"
    if isinstance(val, (int, float)):
        val_int = int(val)
        if val_int <= 3:
            return "Low"
        elif val_int <= 7:
            return "Medium"
        else:
            return "High"
    val_str = str(val).strip().title()
    if val_str in PRIORITY_OPTIONS:
        return val_str
    if val_str.isdigit():
        return priority_to_label(int(val_str))
    return "Medium"


def priority_to_int(label_or_val: Any) -> int:
    if isinstance(label_or_val, (int, float)):
        return max(1, min(10, int(label_or_val)))
    mapping = {"Low": 2, "Medium": 5, "High": 9}
    return mapping.get(str(label_or_val).strip().title(), 5)


def format_priority_display(val: Any, mode: str) -> str:
    p_num = priority_to_int(val)
    p_label = priority_to_label(p_num)

    if mode == "1 to 10 Scale (Slider)":
        return f"{p_num}/10"
    elif mode == "Both Systems":
        return f"{p_label} ({p_num}/10)"
    else:
        return p_label


def parse_eta_to_mins(eta_raw: Any) -> int:
    if not eta_raw or pd.isna(eta_raw):
        return 30
    s = str(eta_raw).lower().strip()
    if not s:
        return 30

    nums = [int(n) for n in re.findall(r"\d+", s)]
    if not nums:
        return 30

    is_hours = "hr" in s or "hour" in s
    avg_val = nums[0]

    if is_hours:
        return max(15, avg_val * 60)
    return max(10, avg_val)


def is_study_task(atype: str, title: str, notes: str) -> bool:
    content = f"{atype} {title} {notes}".lower()
    keywords = ["study", "studying", "review", "prep", "prepping", "practice", "flashcard", "quiz", "test", "exam"]
    return any(kw in content for kw in keywords)


def is_daily_recurring_task(eta_raw: Any, title: str, notes: str) -> bool:
    content = f"{str(eta_raw)} {title} {notes}".lower()
    daily_keywords = ["/day", "per day", "a day", "daily", "every day", "each day", "per-day", "/ d"]
    return any(kw in content for kw in daily_keywords)


def format_study_display_title(raw_title: str) -> str:
    t_lower = raw_title.lower()
    study_words = ["study", "review", "prep", "practice", "flashcard"]
    if any(w in t_lower for w in study_words):
        return raw_title
    return f"Study for {raw_title}"


def get_courses_config_id(user_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"user_courses_config_{user_id}"))


def get_schedule_config_id(user_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"user_schedule_config_{user_id}"))


def get_prio_config_id(user_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"user_prio_config_{user_id}"))


def get_max_work_config_id(user_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"user_max_work_config_{user_id}"))


def get_completed_slots_config_id(user_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"user_completed_slots_config_{user_id}"))


def get_seen_updates_config_id(user_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"user_seen_updates_config_{user_id}"))


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
        "cfg_seen_updates", "_ai_plan_result", "_undo_slot_state", "_hydrated_uid"
    ]:
        if k in st.session_state:
            del st.session_state[k]


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
        conn.execute(sql, {
            "id": cfg_id,
            "user_id": user_id,
            "title": sys_title,
            "notes": notes_payload,
            "created_at": created_at,
        })


def _db_upsert_assignments_worker(db_rows: List[Dict[str, Any]]) -> None:
    if not db_rows:
        return
    sql = text("""
        INSERT INTO assignments (id, user_id, title, course, due_date, status, priority, atype, eta, notes, created_at)
        VALUES (:id, :user_id, :title, :course, :due_date, :status, :priority, :atype, :eta, :notes, :created_at)
        ON CONFLICT (id) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            title = EXCLUDED.title,
            course = EXCLUDED.course,
            due_date = EXCLUDED.due_date,
            status = EXCLUDED.status,
            priority = EXCLUDED.priority,
            atype = EXCLUDED.atype,
            eta = EXCLUDED.eta,
            notes = EXCLUDED.notes,
            created_at = EXCLUDED.created_at;
    """)
    with engine.begin() as conn:
        for row in db_rows:
            conn.execute(sql, row)


def _db_delete_assignment_worker(assignment_id: str) -> None:
    sql = text("DELETE FROM assignments WHERE id = :id")
    with engine.begin() as conn:
        conn.execute(sql, {"id": assignment_id})


def hydrate_user_session(user_id: str, force: bool = False) -> None:
    """Loads ALL assignments + user settings in ONE single database query."""
    if not force and st.session_state.get("_hydrated_uid") == user_id:
        return

    today_iso = get_local_now().date().isoformat()
    sql_all = text("SELECT * FROM assignments WHERE user_id = :uid")

    with engine.connect() as conn:
        raw_rows = conn.execute(sql_all, {"uid": user_id}).mappings().all()

    courses: List[str] = []
    schedule: List[Dict[str, Any]] = []
    prio_mode: Optional[str] = None
    max_work: Dict[str, int] = {d: 60 for d in DAYS_OF_WEEK}
    completed_slots: Dict[str, Dict[str, Any]] = {}
    seen_updates_ver: str = ""

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
                elif isinstance(parsed, int) or str(r_notes or "").strip().isdigit():
                    val = int(str(r_notes).strip())
                    max_work = {d: val for d in DAYS_OF_WEEK}
            except Exception:
                pass
        elif r_title == "__SYSTEM_COMPLETED_SLOTS__":
            try:
                parsed = json.loads(str(r_notes or "{}"))
                if isinstance(parsed, dict):
                    today_data = parsed.get(today_iso, {})
                    if isinstance(today_data, dict):
                        completed_slots = today_data
            except Exception:
                pass
        elif r_title == "__SYSTEM_SEEN_UPDATES__":
            seen_updates_ver = str(r_notes or "").strip()
        elif r_title not in SYSTEM_TITLES:
            status_val = str(r.get("status") or "Not Started")
            due_val = str(r.get("due_date") or "")
            aid_val = str(r.get("id"))

            if status_val == "Done" and due_val and due_val < today_iso:
                expired_done_ids.append(aid_val)
                continue

            n_text, prev_st = _unpack_notes(r_notes)
            assignment_rows.append({
                "id": aid_val,
                "user_id": str(r.get("user_id")),
                "title": r_title,
                "course": str(r.get("course") or "GENERAL").strip().upper(),
                "due_date": due_val,
                "status": status_val,
                "priority": priority_to_int(r.get("priority")),
                "atype": str(r.get("atype") or "Homework"),
                "eta": str(r.get("eta") or ""),
                "created_at": str(r.get("created_at") or ""),
                "notes": n_text,
                "prev_status": prev_st,
            })

    if expired_done_ids:
        _run_bg_sql(_db_purge_ids_worker, user_id, expired_done_ids)

    if assignment_rows:
        df_res = pd.DataFrame(assignment_rows)
    else:
        df_res = pd.DataFrame(columns=[
            "id", "user_id", "title", "course", "due_date", "status", "priority",
            "atype", "eta", "created_at", "notes", "prev_status"
        ])

    st.session_state["df_cached"] = df_res
    st.session_state["cfg_courses"] = courses
    st.session_state["cfg_schedule"] = schedule
    st.session_state["cfg_prio_mode"] = prio_mode
    st.session_state["cfg_max_work"] = max_work
    st.session_state["cfg_completed_slots"] = completed_slots
    st.session_state["cfg_completed_slots_date"] = today_iso
    st.session_state["cfg_seen_updates"] = seen_updates_ver
    st.session_state["_hydrated_uid"] = user_id


# -----------------------
# Instant In-Memory Getters & Optimistic Writers
# -----------------------
def get_courses_cached(user_id: str) -> List[str]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_courses", [])


def _write_courses_file(user_id: str, courses: List[str]) -> None:
    if not user_id:
        return
    st.session_state["cfg_courses"] = courses
    _run_bg_sql(
        _db_upsert_config_worker,
        get_courses_config_id(user_id),
        user_id,
        "__SYSTEM_COURSES__",
        json.dumps(courses),
        get_local_now().isoformat(),
    )


def get_schedule_cached(user_id: str) -> List[Dict[str, Any]]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_schedule", [])


def _write_schedule_file(user_id: str, schedule: List[Dict[str, Any]]) -> None:
    if not user_id:
        return
    st.session_state["cfg_schedule"] = schedule
    if "_ai_plan_result" in st.session_state:
        del st.session_state["_ai_plan_result"]
    _run_bg_sql(
        _db_upsert_config_worker,
        get_schedule_config_id(user_id),
        user_id,
        "__SYSTEM_SCHEDULE__",
        json.dumps(schedule),
        get_local_now().isoformat(),
    )


def get_prio_cached(user_id: str) -> Optional[str]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_prio_mode")


def _write_prio_config(user_id: str, mode: str) -> None:
    if not user_id or mode not in PRIORITY_SYSTEM_MODES:
        return
    st.session_state["cfg_prio_mode"] = mode
    _run_bg_sql(
        _db_upsert_config_worker,
        get_prio_config_id(user_id),
        user_id,
        "__SYSTEM_PRIO_CONFIG__",
        mode,
        get_local_now().isoformat(),
    )


def get_seen_updates_cached(user_id: str) -> str:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_seen_updates", "")


def _write_seen_updates(user_id: str, version_str: str) -> None:
    if not user_id:
        return
    st.session_state["cfg_seen_updates"] = version_str
    _run_bg_sql(
        _db_upsert_config_worker,
        get_seen_updates_config_id(user_id),
        user_id,
        "__SYSTEM_SEEN_UPDATES__",
        version_str,
        get_local_now().isoformat(),
    )


def get_max_work_cached(user_id: str) -> Dict[str, int]:
    hydrate_user_session(user_id)
    return st.session_state.get("cfg_max_work", {d: 60 for d in DAYS_OF_WEEK})


def _write_max_work_config(user_id: str, max_mins_dict: Dict[str, int]) -> None:
    if not user_id:
        return
    st.session_state["cfg_max_work"] = max_mins_dict
    if "_ai_plan_result" in st.session_state:
        del st.session_state["_ai_plan_result"]
    _run_bg_sql(
        _db_upsert_config_worker,
        get_max_work_config_id(user_id),
        user_id,
        "__SYSTEM_MAX_WORK_CONFIG__",
        json.dumps(max_mins_dict),
        get_local_now().isoformat(),
    )


def get_completed_slots_cached(user_id: str) -> Dict[str, Dict[str, Any]]:
    hydrate_user_session(user_id)
    today_str = get_local_now().date().isoformat()
    if st.session_state.get("cfg_completed_slots_date") != today_str:
        st.session_state["cfg_completed_slots"] = {}
        st.session_state["cfg_completed_slots_date"] = today_str
    return st.session_state.get("cfg_completed_slots", {})


def _write_completed_slots(user_id: str, today_slots: Dict[str, Dict[str, Any]]) -> None:
    if not user_id:
        return
    today_str = get_local_now().date().isoformat()
    st.session_state["cfg_completed_slots"] = today_slots
    st.session_state["cfg_completed_slots_date"] = today_str
    _run_bg_sql(
        _db_upsert_config_worker,
        get_completed_slots_config_id(user_id),
        user_id,
        "__SYSTEM_COMPLETED_SLOTS__",
        json.dumps({today_str: today_slots}),
        get_local_now().isoformat(),
    )


def get_assignments_cached(user_id: str) -> pd.DataFrame:
    hydrate_user_session(user_id)
    return st.session_state["df_cached"]


def upsert_assignments(rows_to_upsert: List[Dict[str, Any]]) -> None:
    if not rows_to_upsert:
        return

    normalized_rows = []
    db_payloads = []

    for row in rows_to_upsert:
        n_text = str(row.get("notes", "")).strip()
        prev_st = str(row.get("prev_status", "Not Started"))
        packed = _pack_notes(n_text, prev_st)

        clean_row = {
            "id": str(row.get("id")),
            "user_id": str(row.get("user_id")),
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
        db_payloads.append({**clean_row, "notes": packed})

    if "df_cached" in st.session_state:
        df = st.session_state["df_cached"]
        for c_row in normalized_rows:
            if not df.empty and (df["id"] == c_row["id"]).any():
                idx = df.index[df["id"] == c_row["id"]][0]
                for col, val in c_row.items():
                    df.at[idx, col] = val
            else:
                df = pd.concat([df, pd.DataFrame([c_row])], ignore_index=True)
        st.session_state["df_cached"] = df

    if "_ai_plan_result" in st.session_state:
        del st.session_state["_ai_plan_result"]

    _run_bg_sql(_db_upsert_assignments_worker, db_payloads)


def delete_assignment(assignment_id: str) -> None:
    if "df_cached" in st.session_state and not st.session_state["df_cached"].empty:
        df = st.session_state["df_cached"]
        st.session_state["df_cached"] = df[df["id"] != assignment_id].reset_index(drop=True)

    if "_ai_plan_result" in st.session_state:
        del st.session_state["_ai_plan_result"]

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
# Authentication Handlers
# -----------------------
def sign_up_user(email: str, password: str) -> Dict[str, Any]:
    email_clean = email.lower().strip()
    user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, email_clean))
    pw_hash = _hash_pw(password.strip())
    now_iso = get_local_now().isoformat()

    sql_check = text("SELECT id FROM users WHERE email = :email")
    sql_insert = text("""
        INSERT INTO users (id, email, password_hash, created_at)
        VALUES (:id, :email, :password_hash, :created_at)
    """)

    with engine.begin() as conn:
        existing = conn.execute(sql_check, {"email": email_clean}).fetchone()
        if existing:
            return {"error": "User with this email already exists."}
        conn.execute(sql_insert, {
            "id": user_id,
            "email": email_clean,
            "password_hash": pw_hash,
            "created_at": now_iso
        })

    return {"data": {"id": user_id, "email": email_clean}}


def sign_in_user(email: str, password: str) -> Dict[str, Any]:
    email_clean = email.lower().strip()
    pw_hash = _hash_pw(password.strip())

    sql_find = text("SELECT id, email, password_hash FROM users WHERE email = :email")

    with engine.connect() as conn:
        row = conn.execute(sql_find, {"email": email_clean}).fetchone()
        if not row:
            return {"error": "Invalid email or password."}
        if row.password_hash != pw_hash:
            return {"error": "Invalid email or password."}
        return {"data": {"id": row.id, "email": row.email}}


def sign_out_user() -> None:
    clear_all_session_caches()
    if "user" in st.session_state:
        del st.session_state["user"]
    safe_rerun()


# -----------------------
# Instant Fragment Callbacks (0ms UI latency)
# -----------------------
def on_checkbox_toggle(aid: str, chk_key: str, sel_key: str):
    chk_val = st.session_state.get(chk_key, False)
    df = st.session_state.get("df_cached")
    if df is None or df.empty:
        return

    mask = df["id"] == aid
    if not mask.any():
        return

    row_dict = df.loc[mask].iloc[0].to_dict()
    current_st = row_dict.get("status", "Not Started")

    if chk_val:
        if current_st != "Done":
            row_dict["prev_status"] = current_st
            st.session_state[f"prev_st_{aid}"] = current_st
        new_status = "Done"
    else:
        prev_st = st.session_state.get(f"prev_st_{aid}") or row_dict.get("prev_status", "In Progress")
        if prev_st == "Done" or not prev_st:
            prev_st = "In Progress"
        new_status = prev_st

    row_dict["status"] = new_status
    st.session_state[sel_key] = new_status
    upsert_assignments([row_dict])


def on_status_change(aid: str, sel_key: str, chk_key: str):
    new_status = st.session_state.get(sel_key)
    df = st.session_state.get("df_cached")
    if not new_status or df is None or df.empty:
        return

    mask = df["id"] == aid
    if not mask.any():
        return

    row_dict = df.loc[mask].iloc[0].to_dict()
    if new_status != "Done":
        row_dict["prev_status"] = new_status
        st.session_state[f"prev_st_{aid}"] = new_status
    row_dict["status"] = new_status
    st.session_state[chk_key] = (new_status == "Done")
    upsert_assignments([row_dict])


def on_remove_schedule_block(user_id: str, block_id: str):
    sched = [item for item in get_schedule_cached(user_id) if item.get("id") != block_id]
    _write_schedule_file(user_id, sched)


def on_daily_slot_check(slot_key: str, task_title: str, slot_dict: Dict[str, Any], user_id: str):
    completed_today = get_completed_slots_cached(user_id).copy()
    completed_today[slot_key] = slot_dict
    _write_completed_slots(user_id, completed_today)

    st.session_state["_undo_slot_state"] = {
        "slot_key": slot_key,
        "title": task_title,
        "user_id": user_id,
        "time": get_local_now()
    }


def on_undo_daily_slot(user_id: str):
    undo_info = st.session_state.get("_undo_slot_state")
    if undo_info:
        s_key = undo_info["slot_key"]
        completed_today = get_completed_slots_cached(user_id).copy()
        completed_today.pop(s_key, None)
        _write_completed_slots(user_id, completed_today)

        for k in list(st.session_state.keys()):
            if s_key in k:
                st.session_state[k] = False
        del st.session_state["_undo_slot_state"]


def restore_single_daily_slot(slot_key: str, user_id: str):
    completed_today = get_completed_slots_cached(user_id).copy()
    completed_today.pop(slot_key, None)
    _write_completed_slots(user_id, completed_today)

    for k in list(st.session_state.keys()):
        if slot_key in k:
            st.session_state[k] = False


# -----------------------
# Date & Time Helpers
# -----------------------
def parse_date_iso_or_empty(s: Any) -> Optional[date]:
    if s is None or pd.isna(s):
        return None
    if isinstance(s, date):
        return s
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, str):
        s = s.strip()
        if not s:
            return None
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                pass
    return None


def parse_time_str(t_str: str) -> Optional[time]:
    if not t_str or pd.isna(t_str):
        return None
    t_str = str(t_str).strip().upper()
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(t_str, fmt).time()
        except ValueError:
            pass
    return None


def format_mdy(d: Optional[date]) -> str:
    if not d:
        return get_local_now().date().strftime("%m/%d/%Y")
    return d.strftime("%m/%d/%Y")


def days_left(d: Optional[date]) -> Tuple[str, int]:
    if not d:
        return ("0d", 0)
    today = get_local_now().date()
    delta = (d - today).days
    return (f"{delta}d left" if delta >= 0 else f"{delta}d overdue", delta)


# -----------------------
# AI Time-Slot Scheduler Engine
# -----------------------
def generate_ai_study_plan(
    df_tasks: pd.DataFrame,
    schedule: List[Dict[str, Any]],
    max_daily_mins_config: Dict[str, int] | int = 60
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
        days_until = (due_d - today).days
        if days_until < 0:
            days_until = 0

        prio_val = priority_to_int(row.get("priority"))
        prio_label = priority_to_label(prio_val)
        urgency_multiplier = 10.0 / max(1, days_until)
        ai_score = prio_val * urgency_multiplier

        eta_raw = str(row.get("eta") or "")
        eta_mins = parse_eta_to_mins(eta_raw)
        atype = str(row.get("atype") or "Homework")
        title = str(row.get("title") or "Untitled")
        notes = str(row.get("notes") or "")

        is_study = is_study_task(atype, title, notes)
        is_daily = is_daily_recurring_task(eta_raw, title, notes)
        repeat_daily = is_study or is_daily

        display_title = format_study_display_title(title) if is_study else title

        task_queue.append({
            "id": row.get("id"),
            "title": display_title,
            "course": row.get("course") or "GENERAL",
            "atype": atype,
            "due_date": due_d.strftime("%a %b %d"),
            "priority": prio_label,
            "score": ai_score,
            "eta_mins": eta_mins,
            "days_until": days_until,
            "repeat_daily": repeat_daily
        })

    task_queue.sort(key=lambda x: x["score"], reverse=True)

    plan = {DAYS_OF_WEEK[(today.weekday() + i) % 7]: {"busy": [], "slots": []} for i in range(7)}

    for i in range(7):
        day_date = today + timedelta(days=i)
        day_name = DAYS_OF_WEEK[day_date.weekday()]

        if isinstance(max_daily_mins_config, dict):
            max_daily_mins = max_daily_mins_config.get(day_name, 60)
        else:
            max_daily_mins = int(max_daily_mins_config)

        if day_date.weekday() in (5, 6):
            default_start_mins = 10 * 60
            DAY_END_MINS = 20 * 60
        else:
            default_start_mins = 15 * 60 + 30
            DAY_END_MINS = 21 * 60

        if i == 0:
            DAY_START_MINS = max(default_start_mins, now_mins)
        else:
            DAY_START_MINS = default_start_mins

        busy_intervals = []
        day_events = [s for s in schedule if s.get("day") == day_name]

        for ev in day_events:
            st_time = parse_time_str(ev.get("start"))
            end_time = parse_time_str(ev.get("end"))
            if st_time and end_time:
                st_m = st_time.hour * 60 + st_time.minute
                end_m = end_time.hour * 60 + end_time.minute
                busy_intervals.append((st_m, end_m))
                plan[day_name]["busy"].append(f"{ev.get('title')} ({ev.get('start')} - {ev.get('end')})")

        busy_intervals.sort(key=lambda x: x[0])

        free_slots = []
        curr = DAY_START_MINS
        for b_start, b_end in busy_intervals:
            if b_start > curr:
                slot_end = min(b_start, DAY_END_MINS)
                if slot_end > curr:
                    free_slots.append([curr, slot_end])
            curr = max(curr, b_end)
        if curr < DAY_END_MINS:
            free_slots.append([curr, DAY_END_MINS])

        day_scheduled_mins = 0
        remaining_tasks = []

        for t in task_queue:
            target_max_day = max(0, t["days_until"] - 1) if t["days_until"] > 0 else 0

            if i <= target_max_day and day_scheduled_mins < max_daily_mins:
                scheduled = False
                needed = t["eta_mins"]

                for slot in free_slots:
                    slot_len = slot[1] - slot[0]
                    if slot_len >= needed:
                        st_m = slot[0]
                        end_m = st_m + needed

                        start_str = time(st_m // 60, st_m % 60).strftime("%I:%M %p").lstrip("0")
                        end_str = time(end_m // 60, end_m % 60).strftime("%I:%M %p").lstrip("0")

                        plan[day_name]["slots"].append({
                            "slot_key": f"daily_{t['id']}_{day_date.isoformat()}",
                            "task_id": t["id"],
                            "day_name": day_name,
                            "day_date_str": day_date.isoformat(),
                            "time": f"{start_str} - {end_str}",
                            "title": t["title"],
                            "course": t["course"],
                            "priority": t["priority"],
                            "eta_mins": t["eta_mins"]
                        })

                        slot[0] = end_m
                        day_scheduled_mins += needed
                        scheduled = True
                        break

                if not scheduled:
                    remaining_tasks.append(t)
                elif t["repeat_daily"]:
                    remaining_tasks.append(t)
            else:
                remaining_tasks.append(t)

        task_queue = remaining_tasks

    return {"status": "success", "plan": plan}


# -----------------------
# Instant-Rerun Terminal Auth Interface
# -----------------------
def render_terminal_auth_page():
    auth_container = st.empty()
    with auth_container.container():
        c_left, c_center, c_right = st.columns([1, 1.6, 1])

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
                        <span style='font-size: 1.9rem; font-weight: 800; color: #ffffff; letter-spacing: -0.03em;'>Assignment Tracker</span>
                    </div>
                    <div style='font-size: 0.85rem; color: #64748b;'>Simsbury High School Portal</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown('<div style="background: rgba(15, 23, 42, 0.7); border: 1px solid #1e293b; border-radius: 14px; padding: 24px 28px;">', unsafe_allow_html=True)

            mode = st.radio("Action Mode", ["Sign In", "Sign Up"], horizontal=True, label_visibility="collapsed", key="terminal_mode")

            with st.form("auth_credentials_form", clear_on_submit=False):
                raw_user_input = st.text_input(
                    "Username or Email",
                    placeholder="e.g. 30guptaa or username@simsburyschools.net",
                    key="terminal_user"
                )

                password = st.text_input("Password", type="password", key="terminal_pw")
                typed_user = raw_user_input.strip()
                btn_label = "Sign In" if mode == "Sign In" else "Register Account"

                submitted = st.form_submit_button(btn_label, use_container_width=True)

                if submitted:
                    email_val = typed_user
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
                            u_id = res["data"]["id"]
                            hydrate_user_session(u_id, force=True)
                            auth_container.empty()
                            safe_rerun()

            st.markdown('</div>', unsafe_allow_html=True)


# -----------------------
# Modal Dialogs (What's New, Welcome Courses, Priority, Add/Edit Tasks)
# -----------------------
@dialog_decorator(f"Welcome to Assignment Tracker v{CURRENT_APP_VERSION}")
def show_updates_dialog(user_id: str, is_first_time: bool = False):
    if is_first_time:
        st.caption("Here is what's new, what changed recently, and a few tips to get started.")
    else:
        st.caption("Release notes, changelog history, and helpful tracker tips.")

    tab_latest, tab_prev, tab_tips = st.tabs([
        "✨ Latest Updates",
        "📜 Previous Updates",
        "💡 Things to Know",
    ])

    with tab_latest:
        st.markdown(
            """
            <div class='update-card'>
                <div style='margin-bottom:6px;'><span class='update-ver-badge'>v3.0 NEW</span> <b style='color:#f8fafc;'>Zero-Latency Speed Upgrade</b></div>
                <div style='font-size:0.83rem; color:#cbd5e1; line-height:1.45;'>
                    Checking off tasks, switching statuses, and updating your schedule now happen <b>instantaneously</b> with zero page freezes or reload lag.
                </div>
            </div>
            <div class='update-card'>
                <div style='margin-bottom:6px;'><span class='update-ver-badge'>MOBILE</span> <b style='color:#f8fafc;'>Vertical Phone Layout Overhaul</b></div>
                <div style='font-size:0.83rem; color:#cbd5e1; line-height:1.45;'>
                    Redesigned cards, inline toolbar buttons, and top-priority AI daily schedules so vertical phone screens stay clean and uncluttered.
                </div>
            </div>
            <div class='update-card'>
                <div style='margin-bottom:6px;'><span class='update-ver-badge'>UI</span> <b style='color:#f8fafc;'>New Stacked-Card Brand Identity</b></div>
                <div style='font-size:0.83rem; color:#cbd5e1; line-height:1.45;'>
                    Added the custom stacked-card icon header and streamlined pill navigation across all tabs.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with tab_prev:
        st.markdown(
            """
            <div class='update-card'>
                <div style='margin-bottom:4px;'><span class='update-old-badge'>v2.5</span> <b style='color:#f8fafc;'>Smart AI Time-Slot Planner & Daily Limits</b></div>
                <div style='font-size:0.81rem; color:#94a3b8; line-height:1.4;'>
                    Added automatic daily scheduling around your recurring weekly commitments, customizable per-day work caps, and 15-second Undo toasts.
                </div>
            </div>
            <div class='update-card'>
                <div style='margin-bottom:4px;'><span class='update-old-badge'>v2.0</span> <b style='color:#f8fafc;'>Completed & Recovery Center</b></div>
                <div style='font-size:0.81rem; color:#94a3b8; line-height:1.4;'>
                    Added a dedicated recovery tab to restore accidentally checked-off tasks or daily study slots, plus auto-cleanup of past-due finished items.
                </div>
            </div>
            <div class='update-card'>
                <div style='margin-bottom:4px;'><span class='update-old-badge'>v1.5</span> <b style='color:#f8fafc;'>Custom Priority Scales</b></div>
                <div style='font-size:0.81rem; color:#94a3b8; line-height:1.4;'>
                    Added support for Low / Medium / High badges, a 1–10 numeric slider, or both combined.
                </div>
            </div>
            <div class='update-card'>
                <div style='margin-bottom:4px;'><span class='update-old-badge'>v1.0</span> <b style='color:#f8fafc;'>Initial Release</b></div>
                <div style='font-size:0.81rem; color:#94a3b8; line-height:1.4;'>
                    Launched color-coded subject badges, due-date countdowns, and separate views for Assignments, Tests & Quizzes, and Other tasks.
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
                Any task set to <i>Test & Quizzes</i>, containing words like <i>"study"</i>, <i>"review"</i>, or <i>"prep"</i>, or using <b>/day</b> in its duration (e.g. <code>30 mins/day</code>) will automatically schedule a session every day leading up to its due date.
            </div>
            <div class='tip-card'>
                <b>2. Block Out Your Weekly Commitments First:</b><br/>
                Add sports, clubs, or practices in the <b>Weekly Schedule & AI Planner</b> tab so the AI automatically schedules homework around your busy hours.
            </div>
            <div class='tip-card'>
                <b>3. Automatic Cleanup & Recovery:</b><br/>
                Completed (<code>Done</code>) tasks move to <b>Completed & Recovery</b> where you can restore them anytime until their due date passes.
            </div>
            <div class='tip-card'>
                <b>4. Customize Anytime:</b><br/>
                Use the top toolbar to manage your courses, switch your priority scale, or reopen this guide via <b>Updates</b>.
            </div>
            """,
            unsafe_allow_html=True,
        )

    btn_text = "Got it, Let's Go!" if is_first_time else "Close"
    if st.button(btn_text, key="dismiss_updates_modal_btn", use_container_width=True):
        _write_seen_updates(user_id, CURRENT_APP_VERSION)
        safe_rerun()


@dialog_decorator("Welcome! Setup Your Classes")
def show_welcome_courses_dialog(user_id: str):
    st.markdown("### Setup Your Courses")
    courses_input = st.text_area(
        "Enter your subjects (comma separated):",
        value="MATH, SCIENCE, ENGLISH, HISTORY, OTHER",
    )

    if st.button("Save Schedule", key="save_initial_courses_btn", use_container_width=True):
        parsed_courses = [c.strip().upper() for c in courses_input.replace("\n", ",").split(",") if c.strip()]
        if parsed_courses:
            _write_courses_file(user_id, parsed_courses)
            safe_rerun()


@dialog_decorator("Choose Your Priority System")
def show_prio_config_dialog(user_id: str):
    st.markdown("### How would you like to view & set task priorities?")
    st.write("You can update this setting anytime from the toolbar.")

    current_mode = get_prio_cached(user_id) or "Low / Medium / High"
    prio_choice = st.radio(
        "Select System Preference:",
        PRIORITY_SYSTEM_MODES,
        index=PRIORITY_SYSTEM_MODES.index(current_mode) if current_mode in PRIORITY_SYSTEM_MODES else 0,
        key="prio_modal_radio"
    )

    if st.button("Save Preference", key="save_prio_choice_btn", use_container_width=True):
        _write_prio_config(user_id, prio_choice)
        safe_rerun()


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

        prio_val_to_save = 5
        if prio_mode == "1 to 10 Scale (Slider)":
            prio_val_to_save = st.slider("Priority Rating (1 - 10)", min_value=1, max_value=10, value=5, key="add_prio_slider")
        elif prio_mode == "Both Systems":
            c_p1, c_p2 = st.columns(2)
            with c_p1:
                p_lbl = st.selectbox("Priority Category", PRIORITY_OPTIONS, index=1, key="add_prio_select")
            with c_p2:
                p_num = st.slider("Priority Rating (1 - 10)", min_value=1, max_value=10, value=priority_to_int(p_lbl), key="add_prio_slider_both")
            prio_val_to_save = p_num
        else:
            importance_label = st.selectbox("Priority", PRIORITY_OPTIONS, index=1, key="add_prio_select")
            prio_val_to_save = priority_to_int(importance_label)

        atype = st.selectbox("Type", TYPE_OPTIONS, index=0, key="add_atype")
        eta = st.text_input("Estimated Duration (e.g. 30 mins/day)", key="add_eta")
        notes = st.text_area("Notes", value="", key="add_notes")
        submitted_add = st.form_submit_button("Add Assignment")

        if submitted_add:
            course_val = (course_free.strip() or course_choice or "GENERAL").upper()
            new_row = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "title": title.strip() or "Untitled Assignment",
                "course": course_val.strip(),
                "due_date": due.isoformat() if isinstance(due, date) else "",
                "status": status,
                "priority": prio_val_to_save,
                "atype": atype,
                "eta": eta.strip(),
                "created_at": get_local_now().isoformat(),
                "notes": notes.strip(),
                "prev_status": status if status != "Done" else "Not Started",
            }
            upsert_assignments([new_row])
            if course_free.strip():
                c_list = list(get_courses_cached(user_id))
                if course_free.strip().upper() not in c_list:
                    c_list.append(course_free.strip().upper())
                    _write_courses_file(user_id, c_list)
            safe_rerun()


@dialog_decorator("Edit Assignment Details")
def show_edit_assignment_dialog(user_id: str, aid: str, prio_mode: str):
    df_current = get_assignments_cached(user_id)
    assignment = df_current[df_current["id"] == aid].to_dict(orient="records") if not df_current.empty else []
    assignment_record = assignment[0] if assignment else None

    if not assignment_record:
        st.warning("Assignment no longer exists.")
        return

    courses = get_courses_cached(user_id) or ["MATH", "SCIENCE", "ENGLISH", "HISTORY", "OTHER"]
    if "OTHER" not in courses:
        courses = courses + ["OTHER"]

    with st.form("edit_assignment_form"):
        title = st.text_input("Assignment Title", value=assignment_record.get("title", ""), key=f"edit_title_{aid}")
        course_choice = st.selectbox(
            "Course",
            options=[""] + courses,
            index=(0 if assignment_record.get("course", "") not in courses else courses.index(assignment_record.get("course", "")) + 1),
            key=f"edit_course_choice_{aid}",
        )
        course_free = st.text_input("Or custom course name", value=assignment_record.get("course", ""), key=f"edit_course_free_{aid}")
        status = st.selectbox(
            "Status",
            STATUS_OPTIONS,
            index=(STATUS_OPTIONS.index(assignment_record.get("status")) if assignment_record.get("status") in STATUS_OPTIONS else 0),
            key=f"edit_status_{aid}",
        )
        due_parsed = parse_date_iso_or_empty(assignment_record.get("due_date")) or get_local_now().date()
        due = st.date_input("Due Date", value=due_parsed, key=f"edit_due_{aid}")

        curr_prio_num = priority_to_int(assignment_record.get("priority"))
        curr_prio_lbl = priority_to_label(curr_prio_num)

        if prio_mode == "1 to 10 Scale (Slider)":
            prio_val_to_save = st.slider("Priority Rating (1 - 10)", min_value=1, max_value=10, value=curr_prio_num, key=f"edit_prio_slider_{aid}")
        elif prio_mode == "Both Systems":
            c_p1, c_p2 = st.columns(2)
            with c_p1:
                p_lbl = st.selectbox("Priority Category", PRIORITY_OPTIONS, index=PRIORITY_OPTIONS.index(curr_prio_lbl), key=f"edit_prio_select_{aid}")
            with c_p2:
                p_num = st.slider("Priority Rating (1 - 10)", min_value=1, max_value=10, value=curr_prio_num, key=f"edit_prio_slider_both_{aid}")
            prio_val_to_save = p_num
        else:
            importance_label = st.selectbox("Priority", PRIORITY_OPTIONS, index=PRIORITY_OPTIONS.index(curr_prio_lbl), key=f"edit_prio_select_{aid}")
            prio_val_to_save = priority_to_int(importance_label)

        atype = st.selectbox(
            "Type",
            TYPE_OPTIONS,
            index=(TYPE_OPTIONS.index(assignment_record.get("atype")) if assignment_record.get("atype") in TYPE_OPTIONS else 0),
            key=f"edit_atype_{aid}",
        )
        eta = st.text_input("Estimated Duration", value=assignment_record.get("eta", ""), key=f"edit_eta_{aid}")
        notes = st.text_area("Notes", value=assignment_record.get("notes", ""), key=f"edit_notes_{aid}")

        c_save, c_del = st.columns([1, 1])
        with c_save:
            updated_click = st.form_submit_button("Save Changes")
        with c_del:
            delete_click = st.form_submit_button("Delete Assignment")

        if updated_click:
            course_val = (course_free.strip() or course_choice or "GENERAL").upper()
            updated = {
                "id": aid,
                "user_id": user_id,
                "title": title.strip(),
                "course": course_val.strip(),
                "due_date": due.isoformat() if isinstance(due, date) else "",
                "status": status,
                "priority": prio_val_to_save,
                "atype": atype,
                "eta": eta.strip(),
                "notes": notes.strip(),
                "created_at": assignment_record.get("created_at") or get_local_now().isoformat(),
                "prev_status": status if status != "Done" else assignment_record.get("prev_status", "Not Started"),
            }
            upsert_assignments([updated])
            safe_rerun()

        if delete_click:
            delete_assignment(aid)
            safe_rerun()


@dialog_decorator("Manage Courses")
def show_manage_courses_dialog(user_id: str):
    courses = list(get_courses_cached(user_id))
    to_remove = []

    if courses:
        for i, c in enumerate(courses):
            col_a, col_b = st.columns([6, 2])
            with col_a:
                st.write(f"• **{c}**")
            with col_b:
                if st.button("Remove", key=f"remove_course_{i}"):
                    to_remove.append(c)

    if to_remove:
        courses = [c for c in courses if c not in to_remove]
        _write_courses_file(user_id, courses)
        safe_rerun()

    st.markdown("---")
    new_course = st.text_input("Add a new course", key="new_course_field")
    if st.button("Add Course", key="add_course_button"):
        v = new_course.strip().upper()
        if v and v not in courses:
            courses.append(v)
            _write_courses_file(user_id, courses)
            safe_rerun()


# -----------------------
# Isolated @st.fragment Workspaces (Zero Full-Page Reloads)
# -----------------------
@fragment_decorator
def render_assignment_grid_fragment(user_id: str, view_filter: str, user_prio_mode: str, key_prefix: str):
    df_all = get_assignments_cached(user_id)

    if view_filter == "regular":
        df_grid = df_all[
            (df_all["status"] != "Done") &
            (df_all["atype"] != "Test & Quizzes") &
            (df_all["atype"] != "Other") &
            (df_all["course"] != "OTHER")
        ]
    elif view_filter == "tests":
        df_grid = df_all[
            (df_all["status"] != "Done") &
            (df_all["atype"] == "Test & Quizzes")
        ]
    else:
        df_grid = df_all[
            (df_all["status"] != "Done") &
            ((df_all["atype"] == "Other") | (df_all["course"] == "OTHER"))
        ]

    if df_grid.empty:
        st.markdown("<div style='padding:45px 0; text-align:center; color:#475569; font-size:0.9rem;'>No active assignments in this view.</div>", unsafe_allow_html=True)
        return

    df_sorted = df_grid.copy()
    df_sorted["due_parsed"] = df_sorted["due_date"].apply(parse_date_iso_or_empty)
    df_sorted = df_sorted.sort_values(by=["due_parsed", "priority"], ascending=[True, False]).drop(columns=["due_parsed"])

    cards_per_row = 3
    chunked_rows = [df_sorted.iloc[i:i + cards_per_row] for i in range(0, len(df_sorted), cards_per_row)]

    for row_df in chunked_rows:
        cols = st.columns(cards_per_row)
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
                    prio_cls = f"prio-{prio_label.lower()}"
                    prio_display_str = format_priority_display(prio_num, user_prio_mode)

                    c_top_a, c_top_b, c_top_c = st.columns([0.55, 3.45, 1.2])

                    with c_top_a:
                        st.checkbox(
                            "Done",
                            value=(status == "Done"),
                            key=chk_key,
                            label_visibility="collapsed",
                            on_change=on_checkbox_toggle,
                            args=(aid, chk_key, sel_key)
                        )

                    with c_top_b:
                        st.markdown(get_course_badge_html(course), unsafe_allow_html=True)

                    with c_top_c:
                        if st.button("Edit", key=f"{key_prefix}edit_btn_{aid}", use_container_width=True):
                            show_edit_assignment_dialog(user_id, aid, user_prio_mode)

                    st.selectbox(
                        "Status",
                        STATUS_OPTIONS,
                        index=STATUS_OPTIONS.index(status) if status in STATUS_OPTIONS else 0,
                        key=sel_key,
                        label_visibility="collapsed",
                        on_change=on_status_change,
                        args=(aid, sel_key, chk_key)
                    )

                    st.markdown(f"<div style='font-size:1.1rem; font-weight:700; color:#f8fafc; margin-top:6px;'>{title}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='color:#64748b; font-size:0.78rem; margin-top:1px; margin-bottom:10px;'>{atype}</div>", unsafe_allow_html=True)

                    eta = str(row.get("eta") or "").strip()
                    notes = str(row.get("notes") or "").strip()
                    eta_snippet = f" &bull; Est: {eta}" if eta else ""

                    st.markdown(
                        f"<div style='display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:6px; margin-top:8px; padding-top:8px; border-top:1px solid rgba(255, 255, 255, 0.08);'>"
                        f"<div style='font-size:0.76rem; color:#94a3b8;'>Due {due_text} <span style='color:#64748b;'>({days_text})</span>{eta_snippet}</div>"
                        f"<div class='{prio_cls}'>Priority: {prio_display_str}</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                    if notes:
                        note_preview = notes if len(notes) <= 90 else notes[:87] + "..."
                        st.markdown(f"<div style='font-size:0.74rem; color:#64748b; margin-top:6px;'>Note: {note_preview}</div>", unsafe_allow_html=True)


@fragment_decorator
def render_schedule_and_ai_fragment(user_id: str, user_prio_mode: str):
    col_ai_main, col_sched_side = st.columns([1.85, 1.15])

    user_schedule = list(get_schedule_cached(user_id))
    stored_max_daily_work_dict = get_max_work_cached(user_id)

    with col_ai_main:
        st.markdown("<div style='font-weight:700; font-size:1.05rem; color:#f8fafc;'>AI Daily Action Plan</div>", unsafe_allow_html=True)
        st.caption("Optimized timeline across available days based on due dates & priority.")

        undo_state = st.session_state.get("_undo_slot_state")
        if undo_state:
            elapsed = (get_local_now() - undo_state["time"]).total_seconds()
            if elapsed < 15:
                u_col1, u_col2 = st.columns([4.2, 1.2])
                with u_col1:
                    st.markdown(
                        f"<div class='undo-toast-box'>"
                        f"<span style='font-size: 0.84rem; color: #f8fafc;'>Finished <b>{undo_state['title']}</b> for today</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with u_col2:
                    st.button("Undo", key="btn_undo_slot", on_click=on_undo_daily_slot, args=(user_id,), use_container_width=True)
            else:
                del st.session_state["_undo_slot_state"]

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
                    cur_idx = opts.index(cur_val) if cur_val in opts else 4
                    val = st.selectbox(
                        d_name[:3],
                        options=opts,
                        index=cur_idx,
                        key=f"p_limit_{d_name}",
                        format_func=lambda x: f"{x}m"
                    )
                    new_limits_dict[d_name] = val

            if new_limits_dict != stored_max_daily_work_dict:
                _write_max_work_config(user_id, new_limits_dict)
                stored_max_daily_work_dict = new_limits_dict

        cached_assignments = get_assignments_cached(user_id)

        if gen_plan_click or "_ai_plan_result" not in st.session_state:
            st.session_state["_ai_plan_result"] = generate_ai_study_plan(
                cached_assignments, user_schedule, max_daily_mins_config=stored_max_daily_work_dict
            )

        plan_res = st.session_state["_ai_plan_result"]
        status = plan_res.get("status")
        plan = plan_res.get("plan", {})

        if status == "no_tasks":
            st.info("No active assignments. Add items in the 'Assignments', 'Tests & Quizzes', or 'Other' tab.")
        elif status == "all_done":
            st.success("All assignments marked completed!")
        elif status == "success" and plan:
            completed_slots_today = get_completed_slots_cached(user_id)
            completed_set = set(completed_slots_today.keys())

            for day_name, day_data in plan.items():
                if not isinstance(day_data, dict):
                    st.session_state["_ai_plan_result"] = generate_ai_study_plan(
                        cached_assignments, user_schedule, max_daily_mins_config=stored_max_daily_work_dict
                    )
                    break

                raw_slots = day_data.get("slots", [])
                visible_slots = [s for s in raw_slots if s.get("slot_key") not in completed_set]

                day_cap_mins = stored_max_daily_work_dict.get(day_name, 60)
                scheduled_mins = sum(s.get("eta_mins", 0) for s in visible_slots)

                sched_formatted = format_mins_to_hrs_mins(scheduled_mins)
                max_formatted = format_mins_to_hrs_mins(day_cap_mins)

                st.markdown(
                    f'<div class="ai-day-card">'
                    f'<div class="ai-day-header">'
                    f'<span class="ai-day-title">{day_name}</span>'
                    f'<div class="day-time-badge">{sched_formatted} scheduled <span class="time-max-cap">/ Max {max_formatted}</span></div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                busy_list = day_data.get("busy", [])
                if busy_list:
                    st.caption("Busy: " + ", ".join(busy_list))

                if visible_slots:
                    for idx_slot, s in enumerate(visible_slots):
                        s_key = s.get("slot_key")
                        slot_prio_str = format_priority_display(s.get("priority"), user_prio_mode)
                        slot_duration_str = format_mins_to_hrs_mins(s.get("eta_mins", 0))

                        c_chk, c_text = st.columns([0.45, 7.55])
                        with c_chk:
                            chk_widget_key = f"chk_{s_key}_{idx_slot}"
                            st.checkbox(
                                "Done Today",
                                value=False,
                                key=chk_widget_key,
                                label_visibility="collapsed",
                                on_change=on_daily_slot_check,
                                args=(s_key, s["title"], s, user_id)
                            )

                        with c_text:
                            if show_time_slots:
                                st.markdown(
                                    f"<span class='slot-badge'>{s['time']}</span> — <b style='color:#f8fafc;'>{s['title']}</b> {get_course_badge_html(s['course'])} <span style='color:#94a3b8; font-size:0.78rem;'>| Priority: {slot_prio_str} ({slot_duration_str})</span>",
                                    unsafe_allow_html=True
                                )
                            else:
                                st.markdown(
                                    f"<b style='color:#f8fafc;'>{s['title']}</b> {get_course_badge_html(s['course'])} <span style='color:#94a3b8; font-size:0.78rem;'>| Priority: {slot_prio_str} ({slot_duration_str})</span>",
                                    unsafe_allow_html=True
                                )
                else:
                    st.markdown("<span style='color:#64748b; font-size:0.82rem;'>No work scheduled for this day. Free time!</span>", unsafe_allow_html=True)

                st.markdown('</div>', unsafe_allow_html=True)

    with col_sched_side:
        st.markdown("<div style='font-weight:700; font-size:1.05rem; color:#f8fafc;'>Weekly Commitments</div>", unsafe_allow_html=True)
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
                st_time = parse_time_str(s_start_raw)
                end_time = parse_time_str(s_end_raw)
                if s_title.strip() and st_time and end_time:
                    formatted_start = st_time.strftime("%I:%M %p").lstrip("0")
                    formatted_end = end_time.strftime("%I:%M %p").lstrip("0")
                    user_schedule.append({
                        "id": str(uuid.uuid4()),
                        "day": s_day,
                        "title": s_title.strip(),
                        "start": formatted_start,
                        "end": formatted_end
                    })
                    _write_schedule_file(user_id, user_schedule)

        st.markdown("---")
        if user_schedule:
            for idx, item in enumerate(user_schedule):
                b_id = item.get("id", str(idx))
                col_item_a, col_item_b = st.columns([4, 1.3])
                with col_item_a:
                    st.markdown(f"<span style='color:#cbd5e1; font-size:0.82rem;'>**{item.get('day')}**: {item.get('title')} ({item.get('start')} - {item.get('end')})</span>", unsafe_allow_html=True)
                with col_item_b:
                    st.button(
                        "Remove",
                        key=f"del_sched_{b_id}",
                        on_click=on_remove_schedule_block,
                        args=(user_id, b_id),
                        use_container_width=True
                    )


@fragment_decorator
def render_completed_recovery_fragment(user_id: str):
    st.markdown("<div style='font-weight:800; font-size:1.15rem; color:#f8fafc; margin-bottom:4px;'>Completed Tasks & Recovery Center</div>", unsafe_allow_html=True)
    st.caption("Finished assignments stay here until their due date passes. Restoring an item returns it to your active tab with its previous status.")

    rec_col1, rec_col2 = st.columns(2)

    with rec_col1:
        st.markdown("<div style='font-weight:700; font-size:1.0rem; color:#38bdf8; margin-bottom:10px;'>1. Daily Planner Slots Checked Today</div>", unsafe_allow_html=True)
        completed_slots_dict = get_completed_slots_cached(user_id)

        if completed_slots_dict:
            for s_key, s_data in list(completed_slots_dict.items()):
                c_info, c_act = st.columns([3.8, 1.6])
                with c_info:
                    st.markdown(
                        f"<div class='recovery-card'>"
                        f"<div><b style='color:#f8fafc;'>{s_data.get('title')}</b> {get_course_badge_html(s_data.get('course'))}"
                        f"<div style='font-size:0.75rem; color:#94a3b8; margin-top:2px;'>{s_data.get('day_name')} &bull; {s_data.get('time')}</div></div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with c_act:
                    st.button(
                        "Restore",
                        key=f"rec_slot_{s_key}",
                        on_click=restore_single_daily_slot,
                        args=(s_key, user_id),
                        use_container_width=True
                    )
        else:
            st.info("No daily planner slots marked completed today.")

    with rec_col2:
        st.markdown("<div style='font-weight:700; font-size:1.0rem; color:#fbbf24; margin-bottom:10px;'>2. Finished Assignments (Database)</div>", unsafe_allow_html=True)
        df_all = get_assignments_cached(user_id)
        df_done_db = df_all[df_all["status"] == "Done"].copy()

        if not df_done_db.empty:
            for _, r_done in df_done_db.iterrows():
                r_aid = r_done.get("id")
                c_info_db, c_act_db = st.columns([3.8, 1.6])
                with c_info_db:
                    st.markdown(
                        f"<div class='recovery-card'>"
                        f"<div><b style='color:#f8fafc;'>{r_done.get('title')}</b> {get_course_badge_html(r_done.get('course'))}"
                        f"<div style='font-size:0.75rem; color:#94a3b8; margin-top:2px;'>Type: {r_done.get('atype')} &bull; Due: {r_done.get('due_date')}</div></div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with c_act_db:
                    st.button(
                        "Restore",
                        key=f"rec_db_{r_aid}",
                        on_click=restore_single_assignment,
                        args=(r_done.to_dict(),),
                        use_container_width=True
                    )
        else:
            st.info("No main database assignments currently marked as 'Done'.")


# -----------------------
# Auth Session Control & Sequential Onboarding Modals
# -----------------------
user = st.session_state.get("user")

if not user:
    render_terminal_auth_page()
    st.stop()

user_id = str(user.get("id"))
email = str(user.get("email", "User"))

# Single-query session hydration (instant on subsequent fragment reruns)
hydrate_user_session(user_id)

active_prio_mode = get_prio_cached(user_id)
seen_updates_ver = get_seen_updates_cached(user_id)
user_prio_mode = active_prio_mode or "Low / Medium / High"

# Sequential onboarding queue (ensures only 1 @st.dialog opens per script run)
if seen_updates_ver != CURRENT_APP_VERSION:
    show_updates_dialog(user_id, is_first_time=True)
elif not get_courses_cached(user_id):
    show_welcome_courses_dialog(user_id)
elif not active_prio_mode:
    show_prio_config_dialog(user_id)


# -----------------------
# Main App Header
# -----------------------
col_header_left, col_header_right = st.columns([2.0, 3.0])

with col_header_left:
    st.markdown(
        f"""
        <div style='margin-bottom:6px;'>
            <div style='display:flex; align-items:center; gap:10px;'>
                <svg width='28' height='28' viewBox='0 0 24 24' fill='none' xmlns='http://www.w3.org/2000/svg'>
                    <rect x='2' y='3' width='12' height='12' rx='2' fill='white' opacity='0.5'/>
                    <rect x='6' y='7' width='12' height='12' rx='2' fill='white' opacity='0.8'/>
                    <rect x='10' y='11' width='12' height='12' rx='2' fill='white'/>
                </svg>
                <span class='app-title' style='line-height:1;'>Assignment Tracker</span>
            </div>
            <div class='app-subtitle' style='margin-top:4px;'>{email} &bull; <span style='color:#818cf8;'>System: {user_prio_mode}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_header_right:
    btn_col1, btn_col2, btn_col3, btn_col4, btn_col5 = st.columns([1.05, 1.0, 1.0, 1.0, 1.0])
    with btn_col1:
        if st.button("+ Task", key="toolbar_add", use_container_width=True):
            show_add_assignment_dialog(user_id, user_prio_mode)
    with btn_col2:
        if st.button("Courses", key="toolbar_courses", use_container_width=True):
            show_manage_courses_dialog(user_id)
    with btn_col3:
        if st.button("Priority", key="toolbar_prio_sys", use_container_width=True):
            show_prio_config_dialog(user_id)
    with btn_col4:
        if st.button("Updates", key="toolbar_updates", use_container_width=True):
            show_updates_dialog(user_id, is_first_time=False)
    with btn_col5:
        if st.button("Sign Out", key="toolbar_signout", use_container_width=True):
            sign_out_user()

today_str = get_local_now().strftime("%A, %B %d, %Y")
st.markdown(
    f'<div class="date-banner">Today\'s Date: {today_str}</div>',
    unsafe_allow_html=True,
)


# -----------------------
# Fast Pill Navigation & Isolated Fragments
# -----------------------
NAV_OPTIONS = [
    "Assignments",
    "Tests & Quizzes",
    "Other",
    "Weekly Schedule & AI Planner",
    "Completed & Recovery",
]

active_tab = st.radio(
    "Navigation",
    NAV_OPTIONS,
    horizontal=True,
    label_visibility="collapsed",
    key="main_nav_pill"
)

if active_tab == "Assignments":
    render_assignment_grid_fragment(user_id, "regular", user_prio_mode, key_prefix="reg_")
elif active_tab == "Tests & Quizzes":
    render_assignment_grid_fragment(user_id, "tests", user_prio_mode, key_prefix="tests_")
elif active_tab == "Other":
    render_assignment_grid_fragment(user_id, "other", user_prio_mode, key_prefix="other_")
elif active_tab == "Weekly Schedule & AI Planner":
    render_schedule_and_ai_fragment(user_id, user_prio_mode)
elif active_tab == "Completed & Recovery":
    render_completed_recovery_fragment(user_id)
