"""Assignment Tracker — Simsbury High School Edition."""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import threading
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(
    page_title="Assignment Tracker • SHS",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ADMIN_EMAIL = "30guptaa@simsburyschools.net"
DOMAIN = "@simsburyschools.net"
APP_VERSION = "4.2"

STATUSES = ["Not Started", "In Progress", "Done"]
TYPES = ["Homework", "Essay", "Presentation", "Test & Quizzes", "Other"]
PRIORITIES = ["Low", "Medium", "High"]
PRIO_MODES = ["Low / Medium / High", "1 to 10 Scale"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
LETTERS = ["A", "B", "C", "D", "X"]

SYSTEM_TITLES = {
    "__SYSTEM_COURSES__",
    "__SYSTEM_SCHEDULE__",
    "__SYSTEM_PRIO_CONFIG__",
    "__SYSTEM_MAX_WORK_CONFIG__",
    "__SYSTEM_COMPLETED_SLOTS__",
    "__SYSTEM_SEEN_UPDATES__",
    "__SYSTEM_THEME_CONFIG__",
    "__SYSTEM_SHS_CONFIG__",
    "__SYSTEM_IGNORED_SYNC__",
}

CONFIG_PREFIX = {
    "__SYSTEM_COURSES__": "user_courses_config",
    "__SYSTEM_SCHEDULE__": "user_schedule_config",
    "__SYSTEM_PRIO_CONFIG__": "user_prio_config",
    "__SYSTEM_MAX_WORK_CONFIG__": "user_max_work_config",
    "__SYSTEM_COMPLETED_SLOTS__": "user_completed_slots_config",
    "__SYSTEM_SEEN_UPDATES__": "user_seen_updates_config",
    "__SYSTEM_THEME_CONFIG__": "user_theme_config",
    "__SYSTEM_SHS_CONFIG__": "user_shs_config",
    "__SYSTEM_IGNORED_SYNC__": "user_ignored_sync_config",
}

DEFAULT_FEATURE_CATALOG: Dict[str, Tuple[str, str]] = {
    "ai_study_planner": (
        "AI Study Planner",
        "7-day multi-session smart study planner with daily caps & commitment blocking",
    ),
    "shs_bell_schedule": (
        "SHS Bell Schedule",
        "Live Simsbury High School bell schedule with A/B/C/D/X rotations & L1/L2/L3 lunches",
    ),
    "classroom_sync_v2": (
        "Google Classroom Sync",
        "Chromebook Ctrl+A Paste Sync & personal device Google Classroom bookmarklet",
    ),
    "theme_studio": (
        "Theme & Appearance Studio",
        "Dark/Light contrast modes, presets, gradients & compressed photo backgrounds",
    ),
}

THEME_PRESETS: Dict[str, Dict[str, Any]] = {
    "Midnight Indigo": {
        "mode": "Dark",
        "accent": "#6366f1",
        "bg_type": "Gradient",
        "grad_1": "#090d1a",
        "grad_2": "#141d38",
        "solid": "#0b1020",
    },
    "SHS Trojan Navy & Gold": {
        "mode": "Dark",
        "accent": "#eab308",
        "bg_type": "Gradient",
        "grad_1": "#071124",
        "grad_2": "#10254a",
        "solid": "#0a1730",
    },
    "Daylight Clean": {
        "mode": "Light",
        "accent": "#4f46e5",
        "bg_type": "Solid",
        "grad_1": "#f1f5f9",
        "grad_2": "#e2e8f0",
        "solid": "#f4f6fb",
    },
    "Emerald Forest": {
        "mode": "Dark",
        "accent": "#10b981",
        "bg_type": "Gradient",
        "grad_1": "#061512",
        "grad_2": "#0d2b24",
        "solid": "#081c18",
    },
    "Royal Amethyst": {
        "mode": "Dark",
        "accent": "#a855f7",
        "bg_type": "Gradient",
        "grad_1": "#120a21",
        "grad_2": "#241342",
        "solid": "#150c26",
    },
    "Warm Stone": {
        "mode": "Light",
        "accent": "#d97706",
        "bg_type": "Solid",
        "grad_1": "#faf7f2",
        "grad_2": "#f3ece0",
        "solid": "#f7f3eb",
    },
}

DEFAULT_THEME: Dict[str, Any] = {
    "preset": "Midnight Indigo",
    "mode": "Dark",
    "accent": "#6366f1",
    "opacity": 92,
    "bg_type": "Gradient",
    "solid": "#0b1020",
    "grad_1": "#090d1a",
    "grad_2": "#141d38",
    "background": "linear-gradient(135deg, #090d1a 0%, #141d38 100%)",
}

COURSE_PALETTE: List[Tuple[str, str, str]] = [
    ("#3b82f6", "#dbeafe", "#1e3a8a"),
    ("#8b5cf6", "#ede9fe", "#4c1d95"),
    ("#ec4899", "#fce7f3", "#831843"),
    ("#10b981", "#d1fae5", "#064e3b"),
    ("#f59e0b", "#fef3c7", "#78350f"),
    ("#06b6d4", "#cffafe", "#164e63"),
    ("#f43f5e", "#ffe4e6", "#881337"),
    ("#6366f1", "#e0e7ff", "#312e81"),
    ("#14b8a6", "#ccfbf1", "#134e4a"),
    ("#eab308", "#fef9c3", "#713f12"),
]

CLUB_KEYWORDS = (
    "CLUB", "COUNCIL", "SOCIETY", "NHS", "FBLA", "DECA", "MODEL UN", "MUN",
    "ROBOTICS", "KEY CLUB", "LEO CLUB", "INTERACT", "YEARBOOK", "NEWSPAPER",
    "BAND", "CHOIR", "ORCHESTRA", "THEATER", "DRAMA", "SPORTS", "ATHLETICS",
    "TEAM", "ADVISORY", "CLASS OF 20", "STUDENT GOV", "AMBASSADOR", "PEER",
    "MATH LEAGUE", "SCIENCE OLYMPIAD",
)


# ---------------------------------------------------------------------------
# Safe Streamlit Decorator & Navigation Helpers
# ---------------------------------------------------------------------------
def dialog_decorator(title: str):
    native = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)
    if native:
        try:
            return native(title)
        except TypeError:
            pass

    def decorate(fn: Callable):
        def wrapper(*args, **kwargs):
            with st.container(border=True):
                st.subheader(title)
                return fn(*args, **kwargs)

        return wrapper

    return decorate


def fragment_decorator(run_every=None):
    native = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None)
    if native:
        try:
            return native(run_every=run_every) if run_every is not None else native()
        except TypeError:
            try:
                return native()
            except Exception:
                pass
    return lambda fn: fn


def rerun() -> None:
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn:
        try:
            fn()
        except Exception:
            pass


def now_local() -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.utcnow() - timedelta(hours=4)


def fmt_time_12h(dt_or_t: Any) -> str:
    return dt_or_t.strftime("%I:%M %p").lstrip("0")


def esc(val: Any) -> str:
    return (
        str(val or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def is_admin(email: str) -> bool:
    return str(email or "").strip().lower() == ADMIN_EMAIL


# ---------------------------------------------------------------------------
# Database Engine, Auto-Schema Migration & Async Background Writer
# ---------------------------------------------------------------------------
def _db_url() -> str:
    sec = st.secrets
    url = (
        sec.get("postgres", {}).get("url")
        or sec.get("connections", {}).get("neon", {}).get("url")
        or sec.get("DATABASE_URL")
    )
    if not url:
        raise RuntimeError("PostgreSQL URL missing from Streamlit secrets.")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


@st.cache_resource
def db_engine():
    return create_engine(_db_url(), pool_pre_ping=True, pool_size=4, max_overflow=4)


@st.cache_resource
def db_lock() -> threading.Lock:
    return threading.Lock()


def _table_cols(conn, table_name: str) -> set[str]:
    rows = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t"
        ),
        {"t": table_name},
    ).fetchall()
    return {str(r[0]) for r in rows}


@st.cache_resource
def init_db() -> Dict[str, Any]:
    ddl = [
        "CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS assignments (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT, course TEXT, due_date TEXT, status TEXT, priority INTEGER, atype TEXT, eta TEXT, notes TEXT, created_at TEXT)",
        "CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, email TEXT NOT NULL, category TEXT NOT NULL, rating INTEGER, message TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS feedback_replies (id TEXT PRIMARY KEY, feedback_id TEXT NOT NULL, sender_email TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL, is_read INTEGER DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS feature_errors (id TEXT PRIMARY KEY, feature TEXT, message TEXT, created_at TEXT, resolved INTEGER DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS feature_flags (feature TEXT PRIMARY KEY, status TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS feature_catalog (feature TEXT PRIMARY KEY, description TEXT)",
    ]
    with db_engine().begin() as conn:
        for q in ddl:
            conn.execute(text(q))

        fc_cols = _table_cols(conn, "feature_catalog")
        ff_cols = _table_cols(conn, "feature_flags")
        fe_cols = _table_cols(conn, "feature_errors")
        fr_cols = _table_cols(conn, "feedback_replies")

        fc_pk = "feature_key" if "feature_key" in fc_cols else ("key" if "key" in fc_cols else "feature")
        ff_pk = "feature_key" if "feature_key" in ff_cols else ("key" if "key" in ff_cols else "feature")

        conn.execute(text("ALTER TABLE feature_catalog ADD COLUMN IF NOT EXISTS description TEXT"))
        conn.execute(text("ALTER TABLE feature_flags ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Public Released'"))
        conn.execute(text("ALTER TABLE feature_errors ADD COLUMN IF NOT EXISTS feature TEXT"))
        conn.execute(text("ALTER TABLE feature_errors ADD COLUMN IF NOT EXISTS message TEXT"))
        conn.execute(text("ALTER TABLE feature_errors ADD COLUMN IF NOT EXISTS created_at TEXT"))
        conn.execute(text("ALTER TABLE feature_errors ADD COLUMN IF NOT EXISTS resolved INTEGER DEFAULT 0"))
        conn.execute(text("ALTER TABLE feedback_replies ADD COLUMN IF NOT EXISTS is_read INTEGER DEFAULT 0"))

        fc_cols = _table_cols(conn, "feature_catalog")
        fe_cols = _table_cols(conn, "feature_errors")
        fr_cols = _table_cols(conn, "feedback_replies")

        for fk, (fname, desc) in DEFAULT_FEATURE_CATALOG.items():
            if "name" in fc_cols:
                conn.execute(
                    text(
                        f"INSERT INTO feature_catalog ({fc_pk}, name, description) "
                        f"VALUES (:f, :n, :d) ON CONFLICT ({fc_pk}) DO NOTHING"
                    ),
                    {"f": fk, "n": fname, "d": desc},
                )
            else:
                conn.execute(
                    text(
                        f"INSERT INTO feature_catalog ({fc_pk}, description) "
                        f"VALUES (:f, :d) ON CONFLICT ({fc_pk}) DO NOTHING"
                    ),
                    {"f": fk, "d": desc},
                )

            conn.execute(
                text(
                    f"INSERT INTO feature_flags ({ff_pk}, status) "
                    f"VALUES (:f, 'Public Released') ON CONFLICT ({ff_pk}) DO NOTHING"
                ),
                {"f": fk},
            )

    return {
        "fc_pk": fc_pk,
        "ff_pk": ff_pk,
        "fc_has_name": "name" in fc_cols,
        "fe_has_legacy": ("feature_name" in fe_cols and "error_msg" in fe_cols),
        "fr_has_is_admin": "is_admin" in fr_cols,
    }


try:
    SCHEMA_INFO = init_db()
except Exception as exc:
    st.error(f"Database connection error: {exc}")
    st.stop()


def bg_sql(sql: str, params: Dict[str, Any]) -> None:
    def worker():
        try:
            with db_lock(), db_engine().begin() as conn:
                conn.execute(text(sql), params)
        except Exception as exc:
            print(f"Background DB write failed: {exc}")

    threading.Thread(target=worker, daemon=True).start()


def _cfg_id(uid: str, title: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{CONFIG_PREFIX.get(title, 'user_config')}_{uid}"))


def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def _unpack_notes(raw: Any) -> Tuple[str, str]:
    try:
        d = json.loads(raw or "")
        if isinstance(d, dict):
            return str(d.get("text", "")), str(d.get("prev_status", "Not Started"))
    except Exception:
        pass
    return str(raw or ""), "Not Started"


def _unpack_config(raw: Any, default: Any) -> Any:
    try:
        return json.loads(raw) if raw not in (None, "") else default
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Session Hydration & Instant State Mutations
# ---------------------------------------------------------------------------
def hydrate_user_session(user_id: str, force: bool = False) -> None:
    if not force and st.session_state.get("_hydrated_uid") == user_id:
        return

    ff_pk = SCHEMA_INFO["ff_pk"]
    with db_engine().connect() as conn:
        rows = (
            conn.execute(text("SELECT * FROM assignments WHERE user_id = :uid"), {"uid": user_id})
            .mappings()
            .all()
        )
        flag_rows = conn.execute(text(f"SELECT {ff_pk} AS fk, status FROM feature_flags")).mappings().all()

    st.session_state.feature_flags_map = {str(r["fk"]): str(r["status"]) for r in flag_rows}

    today = now_local().date().isoformat()
    cfg: Dict[str, str] = {}
    tasks: List[Dict[str, Any]] = []
    expired: List[str] = []

    for r in rows:
        title = str(r.get("title") or "")
        if title in SYSTEM_TITLES:
            cfg[title] = str(r.get("notes") or "")
            continue
        due = str(r.get("due_date") or "")
        if r.get("status") == "Done" and due and due < today:
            expired.append(str(r["id"]))
            continue
        notes, prev = _unpack_notes(r.get("notes"))
        tasks.append(
            {
                "id": str(r["id"]),
                "user_id": user_id,
                "title": title,
                "course": str(r.get("course") or "GENERAL").upper(),
                "due_date": due,
                "status": str(r.get("status") or "Not Started"),
                "priority": int(r.get("priority") or 5),
                "atype": str(r.get("atype") or "Homework"),
                "eta": str(r.get("eta") or ""),
                "notes": notes,
                "prev_status": prev,
                "created_at": str(r.get("created_at") or ""),
            }
        )

    if expired:
        bg_sql(
            "DELETE FROM assignments WHERE user_id = :uid AND id = ANY(:ids)",
            {"uid": user_id, "ids": expired},
        )

    cols = [
        "id",
        "user_id",
        "title",
        "course",
        "due_date",
        "status",
        "priority",
        "atype",
        "eta",
        "notes",
        "prev_status",
        "created_at",
    ]
    st.session_state.df_cached = pd.DataFrame(tasks, columns=cols)
    st.session_state.cfg_courses = _unpack_config(cfg.get("__SYSTEM_COURSES__"), [])
    st.session_state.cfg_schedule = _unpack_config(cfg.get("__SYSTEM_SCHEDULE__"), [])
    st.session_state.cfg_prio = cfg.get("__SYSTEM_PRIO_CONFIG__") or PRIO_MODES[0]
    st.session_state.cfg_max_work = _unpack_config(
        cfg.get("__SYSTEM_MAX_WORK_CONFIG__"), {d: 60 for d in DAYS}
    )
    st.session_state.cfg_completed = _unpack_config(cfg.get("__SYSTEM_COMPLETED_SLOTS__"), {})
    st.session_state.cfg_seen = cfg.get("__SYSTEM_SEEN_UPDATES__", "")
    saved_theme = _unpack_config(cfg.get("__SYSTEM_THEME_CONFIG__"), {})
    st.session_state.cfg_theme = {**DEFAULT_THEME, **(saved_theme if isinstance(saved_theme, dict) else {})}
    st.session_state.cfg_shs = _unpack_config(
        cfg.get("__SYSTEM_SHS_CONFIG__"),
        {
            "lunches": {d: "L2" for d in LETTERS},
            "periods": {},
            "study_rooms": {d: "" for d in LETTERS},
            "sheet_url": "",
        },
    )
    st.session_state.cfg_ignored = _unpack_config(cfg.get("__SYSTEM_IGNORED_SYNC__"), [])
    st.session_state._hydrated_uid = user_id


def save_config(uid: str, title: str, value: Any) -> None:
    state_keys = {
        "__SYSTEM_COURSES__": "cfg_courses",
        "__SYSTEM_SCHEDULE__": "cfg_schedule",
        "__SYSTEM_PRIO_CONFIG__": "cfg_prio",
        "__SYSTEM_MAX_WORK_CONFIG__": "cfg_max_work",
        "__SYSTEM_COMPLETED_SLOTS__": "cfg_completed",
        "__SYSTEM_SEEN_UPDATES__": "cfg_seen",
        "__SYSTEM_THEME_CONFIG__": "cfg_theme",
        "__SYSTEM_SHS_CONFIG__": "cfg_shs",
        "__SYSTEM_IGNORED_SYNC__": "cfg_ignored",
    }
    st.session_state[state_keys[title]] = value
    payload = value if isinstance(value, str) else json.dumps(value)
    q = (
        "INSERT INTO assignments (id, user_id, title, course, due_date, status, priority, atype, eta, notes, created_at) "
        "VALUES (:id, :uid, :title, 'CONFIG', '', 'Not Started', 0, 'Other', '', :notes, :created) "
        "ON CONFLICT (id) DO UPDATE SET notes = EXCLUDED.notes, user_id = EXCLUDED.user_id"
    )
    bg_sql(
        q,
        {
            "id": _cfg_id(uid, title),
            "uid": uid,
            "title": title,
            "notes": payload,
            "created": now_local().isoformat(),
        },
    )


def _db_task(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "title": str(row.get("title") or "Untitled Assignment"),
        "course": str(row.get("course") or "GENERAL").upper(),
        "due_date": str(row.get("due_date") or ""),
        "status": str(row.get("status") or "Not Started"),
        "priority": int(row.get("priority") or 5),
        "atype": str(row.get("atype") or "Homework"),
        "eta": str(row.get("eta") or ""),
        "notes": json.dumps(
            {
                "text": str(row.get("notes") or ""),
                "prev_status": str(row.get("prev_status") or "Not Started"),
            }
        ),
        "created_at": str(row.get("created_at") or now_local().isoformat()),
    }


def upsert_task(row: Dict[str, Any]) -> None:
    row = dict(row)
    row.setdefault("id", str(uuid.uuid4()))
    row.setdefault("user_id", st.session_state.user["id"])
    row.setdefault("created_at", now_local().isoformat())
    row.setdefault("status", "Not Started")
    row.setdefault("priority", 5)
    row.setdefault("atype", "Homework")
    row.setdefault("eta", "30 mins")
    row.setdefault("notes", "")
    row.setdefault("prev_status", "Not Started")
    row["course"] = str(row.get("course") or "GENERAL").upper()
    row["title"] = str(row.get("title") or "Untitled Assignment")

    df = st.session_state.df_cached.copy()
    new_row = pd.DataFrame([{k: row.get(k) for k in df.columns}])
    if not df.empty and (df["id"] == row["id"]).any():
        idx = df.index[df["id"] == row["id"]][0]
        for k in df.columns:
            df.at[idx, k] = new_row.iloc[0][k]
    else:
        df = pd.concat([df, new_row], ignore_index=True)

    st.session_state.df_cached = df
    q = (
        "INSERT INTO assignments (id, user_id, title, course, due_date, status, priority, atype, eta, notes, created_at) "
        "VALUES (:id, :user_id, :title, :course, :due_date, :status, :priority, :atype, :eta, :notes, :created_at) "
        "ON CONFLICT (id) DO UPDATE SET "
        "user_id=EXCLUDED.user_id, title=EXCLUDED.title, course=EXCLUDED.course, due_date=EXCLUDED.due_date, "
        "status=EXCLUDED.status, priority=EXCLUDED.priority, atype=EXCLUDED.atype, eta=EXCLUDED.eta, "
        "notes=EXCLUDED.notes, created_at=EXCLUDED.created_at"
    )
    bg_sql(q, _db_task(row))


def delete_task(aid: str) -> None:
    df = st.session_state.df_cached
    st.session_state.df_cached = df[df["id"] != aid].reset_index(drop=True)
    bg_sql(
        "DELETE FROM assignments WHERE id = :id AND user_id = :uid",
        {"id": aid, "uid": st.session_state.user["id"]},
    )


def get_feature_state(feature_key: str) -> str:
    return st.session_state.get("feature_flags_map", {}).get(feature_key, "Public Released")


def is_feature_visible(feature_key: str, email: str) -> bool:
    if is_admin(email):
        return True
    st_val = get_feature_state(feature_key)
    return st_val not in ("Removed/Hidden", "disabled")


def run_with_fallback(feature: str, fn: Callable, fallback: Callable):
    try:
        return fn()
    except Exception as exc:
        try:
            eid = str(uuid.uuid4())
            msg_str = str(exc)[:2000]
            ts = now_local().isoformat()
            if SCHEMA_INFO.get("fe_has_legacy"):
                bg_sql(
                    "INSERT INTO feature_errors (id, feature, message, feature_name, error_msg, created_at, resolved) "
                    "VALUES (:id, :f, :m, :f, :m, :c, 0)",
                    {"id": eid, "f": feature, "m": msg_str, "c": ts},
                )
            else:
                bg_sql(
                    "INSERT INTO feature_errors (id, feature, message, created_at, resolved) VALUES (:id, :f, :m, :c, 0)",
                    {"id": eid, "f": feature, "m": msg_str, "c": ts},
                )
        except Exception:
            pass
        st.warning(f"{feature} encountered an issue. Running in backup mode.")
        return fallback()


# ---------------------------------------------------------------------------
# GPU-Friendly Styling & Visual Badges
# ---------------------------------------------------------------------------
def build_theme_css(cfg: Dict[str, Any]) -> str:
    light = cfg.get("mode") == "Light"
    accent = cfg.get("accent", "#6366f1")
    opacity = max(55, min(98, int(cfg.get("opacity", 92)))) / 100.0
    bg_type = cfg.get("bg_type", "Gradient")

    if bg_type == "Solid":
        bg_css = cfg.get("solid", "#f4f6fb" if light else "#0b1020")
    elif bg_type == "Photo" and str(cfg.get("background", "")).startswith("url("):
        bg_css = cfg["background"]
    else:
        g1 = cfg.get("grad_1", "#f1f5f9" if light else "#090d1a")
        g2 = cfg.get("grad_2", "#e2e8f0" if light else "#141d38")
        bg_css = f"linear-gradient(135deg, {g1} 0%, {g2} 100%)"

    fg = "#0f172a" if light else "#f1f5f9"
    muted = "#475569" if light else "#94a3b8"
    card_bg = f"rgba(255, 255, 255, {opacity})" if light else f"rgba(15, 23, 42, {opacity})"
    subcard_bg = "rgba(241, 245, 249, 0.94)" if light else "rgba(30, 41, 59, 0.82)"
    border_col = "rgba(15, 23, 42, 0.14)" if light else "rgba(148, 163, 184, 0.24)"

    return f"""
    <style>
        #MainMenu, footer, [data-testid="stToolbar"] {{ visibility: hidden; height: 0; }}
        header[data-testid="stHeader"] {{ background: transparent; height: 0.4rem; }}

        .stApp {{
            background: {bg_css};
            background-attachment: fixed;
            color: {fg};
        }}
        .block-container {{
            max-width: 1240px;
            padding-top: 1.1rem !important;
            padding-bottom: 3rem !important;
        }}
        .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp h4 {{
            color: {fg};
        }}

        /* Top Header Card */
        .shs-topbar {{
            background: {card_bg};
            border: 1px solid {border_col};
            border-left: 5px solid {accent};
            border-radius: 14px;
            padding: 12px 18px;
            margin-bottom: 10px;
        }}
        .shs-brand {{
            font-size: 1.48rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            line-height: 1.2;
        }}
        .shs-accent {{ color: {accent}; }}
        .shs-sub {{
            font-size: 0.82rem;
            color: {muted};
            margin-top: 3px;
        }}
        .shs-pill {{
            display: inline-block;
            background: {accent}24;
            color: {accent};
            border: 1px solid {accent}66;
            border-radius: 999px;
            padding: 2px 10px;
            font-size: 0.74rem;
            font-weight: 700;
            margin-left: 6px;
        }}

        /* Auth Card */
        .auth-hero {{
            background: {card_bg};
            border: 1px solid {border_col};
            border-top: 4px solid {accent};
            border-radius: 16px;
            padding: 22px 24px 14px 24px;
            text-align: center;
            margin-top: 28px;
            margin-bottom: 12px;
        }}

        /* Container Cards */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: {card_bg} !important;
            border: 1px solid {border_col} !important;
            border-radius: 14px !important;
            padding: 12px 14px !important;
            margin-bottom: 8px !important;
        }}

        /* Buttons */
        .stButton > button {{
            border-radius: 9px !important;
            border: 1px solid {border_col} !important;
            font-weight: 600 !important;
        }}
        .stButton > button:hover {{
            border-color: {accent} !important;
            color: {accent} !important;
        }}

        /* Task Card Typography */
        .task-title {{
            font-size: 1.03rem;
            font-weight: 700;
            margin: 6px 0 3px 0;
            line-height: 1.32;
        }}
        .task-title-done {{
            text-decoration: line-through;
            opacity: 0.65;
        }}
        .task-meta {{
            font-size: 0.79rem;
            color: {muted};
            margin-bottom: 6px;
        }}
        .task-note {{
            font-size: 0.81rem;
            color: {muted};
            background: {subcard_bg};
            border-radius: 8px;
            padding: 6px 10px;
            margin: 6px 0 8px 0;
        }}

        /* Pills & Urgency */
        .course-pill {{
            display: inline-block;
            padding: 2px 9px;
            border-radius: 999px;
            font-size: 0.71rem;
            font-weight: 800;
            letter-spacing: 0.03em;
        }}
        .prio-pill {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 0.71rem;
            font-weight: 700;
        }}
        .prio-high {{ background: #f43f5e24; color: #f43f5e; border: 1px solid #f43f5e66; }}
        .prio-med {{ background: #f59e0b24; color: #f59e0b; border: 1px solid #f59e0b66; }}
        .prio-low {{ background: #10b98124; color: #10b981; border: 1px solid #10b98166; }}

        .due-overdue {{ color: #f43f5e; font-weight: 700; }}
        .due-today {{ color: #f59e0b; font-weight: 700; }}
        .due-soon {{ color: {accent}; font-weight: 600; }}

        /* Metric Chips */
        .stat-chip {{
            background: {card_bg};
            border: 1px solid {border_col};
            border-radius: 12px;
            padding: 8px 12px;
            text-align: center;
            margin-bottom: 10px;
        }}
        .stat-num {{ font-size: 1.25rem; font-weight: 800; color: {accent}; line-height: 1.2; }}
        .stat-lbl {{ font-size: 0.70rem; color: {muted}; text-transform: uppercase; letter-spacing: 0.04em; }}

        /* Study Planner & Bell Schedule Cards */
        .plan-day-card {{
            background: {card_bg};
            border: 1px solid {border_col};
            border-left: 4px solid {accent};
            border-radius: 12px;
            padding: 12px 16px;
            margin-bottom: 10px;
        }}
        .slot-time-pill {{
            display: inline-block;
            background: {accent}22;
            color: {accent};
            border: 1px solid {accent}55;
            border-radius: 6px;
            padding: 2px 8px;
            font-size: 0.76rem;
            font-weight: 700;
        }}
        .bell-row {{
            background: {card_bg};
            border: 1px solid {border_col};
            border-radius: 11px;
            padding: 10px 14px;
            margin-bottom: 7px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .bell-row-live {{
            border: 2px solid {accent};
            background: {accent}18;
        }}
        .bell-live-badge {{
            background: {accent};
            color: #ffffff !important;
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 0.70rem;
            font-weight: 800;
            margin-left: 8px;
        }}
        .lunch-sub-box {{
            background: {subcard_bg};
            border-radius: 8px;
            padding: 5px 10px;
            margin-top: 6px;
            font-size: 0.79rem;
            width: 100%;
        }}
        .beta-banner {{
            background: #f59e0b1f;
            border: 1px solid #f59e0b66;
            border-radius: 10px;
            padding: 7px 12px;
            font-size: 0.80rem;
            margin-bottom: 10px;
        }}
    </style>
    """


def course_badge_html(course: str, light: bool) -> str:
    c_up = str(course or "GENERAL").strip().upper()
    idx = sum(ord(ch) for ch in c_up) % len(COURSE_PALETTE)
    dark_bg, light_bg, light_fg = COURSE_PALETTE[idx]
    if light:
        return f"<span class='course-pill' style='background:{light_bg}; color:{light_fg}; border:1px solid {light_fg}33;'>{esc(c_up)}</span>"
    return f"<span class='course-pill' style='background:{dark_bg}2b; color:{dark_bg}; border:1px solid {dark_bg}66;'>{esc(c_up)}</span>"


def priority_badge_html(prio_int: int, prio_mode: str) -> str:
    p = max(1, min(10, int(prio_int or 5)))
    if p >= 8:
        cls, lbl = "prio-high", "High"
    elif p >= 4:
        cls, lbl = "prio-med", "Medium"
    else:
        cls, lbl = "prio-low", "Low"
    text_lbl = f"P{p}/10 ({lbl})" if prio_mode == PRIO_MODES[1] else lbl
    return f"<span class='prio-pill {cls}'>{text_lbl}</span>"


def due_badge_html(due_str: str, today_dt: date, status: str) -> str:
    if not due_str:
        return "<span>📅 No due date</span>"
    try:
        d_obj = date.fromisoformat(due_str)
    except Exception:
        return f"<span>📅 {esc(due_str)}</span>"

    diff = (d_obj - today_dt).days
    nice = d_obj.strftime("%a, %b %d")
    if status == "Done":
        return f"<span>✅ {nice}</span>"
    if diff < 0:
        return f"<span class='due-overdue'>🚨 Overdue ({nice})</span>"
    if diff == 0:
        return f"<span class='due-today'>🔥 Due Today ({nice})</span>"
    if diff == 1:
        return f"<span class='due-soon'>⏰ Due Tomorrow ({nice})</span>"
    return f"<span>📅 {nice} (in {diff}d)</span>"


# ---------------------------------------------------------------------------
# Google Classroom Parser & Bookmarklet Generator
# ---------------------------------------------------------------------------
def parse_date(raw: str) -> str:
    s = str(raw or "").strip()
    today = now_local().date()
    if not s or "no due date" in s.lower():
        return ""
    s_clean = re.sub(r"^(due\s*:?\s*)", "", s, flags=re.I).strip()
    s_clean = re.sub(r",?\s*\d{1,2}:\d{2}\s*(AM|PM)?$", "", s_clean, flags=re.I).strip()

    low = s_clean.lower()
    if "today" in low:
        return today.isoformat()
    if "tomorrow" in low:
        return (today + timedelta(days=1)).isoformat()
    if "yesterday" in low:
        return (today - timedelta(days=1)).isoformat()

    for i, d_name in enumerate(DAYS):
        if re.search(rf"\b({d_name}|{d_name[:3]})\b", s_clean, re.I):
            return (today + timedelta(days=(i - today.weekday()) % 7)).isoformat()

    s_no_wd = re.sub(
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s*",
        "",
        s_clean,
        flags=re.I,
    ).strip()

    for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s_no_wd, fmt).date().isoformat()
        except ValueError:
            pass

    for fmt in ("%b %d", "%B %d", "%m/%d"):
        try:
            dt_obj = datetime.strptime(s_no_wd, fmt)
            cand = date(today.year, dt_obj.month, dt_obj.day)
            if (today - cand).days > 180:
                cand = date(today.year + 1, dt_obj.month, dt_obj.day)
            return cand.isoformat()
        except ValueError:
            pass
    return ""


def map_course(raw_course: str, title: str, user_courses: List[str]) -> str:
    blob = f"{raw_course} {title}".upper()
    if any(kw in blob for kw in CLUB_KEYWORDS):
        return "OTHER"

    rc = re.sub(r"\s+", " ", str(raw_course or "")).strip().upper()
    if not rc:
        return "GENERAL"

    for uc in user_courses:
        c_up = str(uc).strip().upper()
        if c_up and c_up != "OTHER" and (c_up in rc or rc in c_up):
            return c_up

    tokens = [
        t
        for t in re.split(r"[^A-Z0-9]+", rc)
        if len(t) >= 3
        and t not in ("PERIOD", "PER", "BLOCK", "CLASS", "HONORS", "AP", "CP", "2026", "2027")
    ]
    best_c, best_score = "", 0
    for uc in user_courses:
        c_up = str(uc).strip().upper()
        score = sum(1 for tok in tokens if tok in c_up)
        if score > best_score:
            best_score, best_c = score, c_up
    if best_score >= 1 and best_c:
        return best_c

    cleaned = re.sub(r"\b(PERIOD|PER|BLOCK)\s*\d+\b", "", rc)
    return re.split(r"[-–—|•(:]", cleaned)[0].strip()[:28] or "GENERAL"


def guess_type(title: str, course: str) -> str:
    if course == "OTHER":
        return "Other"
    s = title.lower()
    if any(x in s for x in ("test", "quiz", "exam", "midterm", "final", "frq", "dbq", "assessment")):
        return "Test & Quizzes"
    if any(x in s for x in ("essay", "paper", "thesis", "draft", "composition")):
        return "Essay"
    if any(x in s for x in ("presentation", "slides", "slideshow", "poster", "speech", "pitch")):
        return "Presentation"
    if any(x in s for x in ("form", "survey", "sign up", "permission", "bake sale", "meeting")):
        return "Other"
    return "Homework"


def is_duplicate_task(title: str, course: str, due: str, df: pd.DataFrame) -> bool:
    if df.empty:
        return False
    t_low = title.strip().lower()
    if (df["title"].fillna("").str.strip().str.lower() == t_low).any():
        return True
    same = (df["course"].fillna("").str.upper() == course.upper()) & (
        (df["due_date"].fillna("") == due) | (df["due_date"].fillna("") == "") | (due == "")
    )
    words = set(re.findall(r"[a-z0-9]{4,}", t_low))
    if len(words) < 2:
        return False
    return any(
        len(words & set(re.findall(r"[a-z0-9]{4,}", str(t).lower()))) >= 2
        for t in df.loc[same, "title"]
    )


def parse_classroom_blob(blob: str) -> List[Dict[str, str]]:
    txt = str(blob or "").strip()
    if not txt:
        return []

    if txt.startswith("{") or txt.startswith("["):
        try:
            data = json.loads(txt)
            arr = data.get("items", []) if isinstance(data, dict) else data
            if isinstance(arr, list):
                out = []
                for it in arr:
                    if isinstance(it, dict) and str(it.get("title", "")).strip():
                        out.append(
                            {
                                "title": str(it["title"]).strip(),
                                "raw_course": str(it.get("course") or it.get("class") or "").strip(),
                                "raw_due": str(it.get("due") or it.get("dueDate") or "").strip(),
                            }
                        )
                return out
        except Exception:
            pass

    skip = {
        "to-do", "to do", "assigned", "missing", "done", "all classes",
        "no due date", "this week", "next week", "later", "earlier",
        "last week", "this month", "assignment", "description", "view all",
    }
    date_re = re.compile(
        r"^(due\s+|today|tomorrow|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}/\d{1,2})",
        re.I,
    )
    lines = [
        x.strip()
        for x in txt.splitlines()
        if x.strip() and x.strip().lower() not in skip and not x.strip().isdigit() and len(x.strip()) > 1
    ]
    out: List[Dict[str, str]] = []
    i = 0
    while i < len(lines) - 1:
        if date_re.match(lines[i]):
            i += 1
            continue
        if date_re.match(lines[i + 1]):
            out.append({"title": lines[i], "raw_course": "GENERAL", "raw_due": lines[i + 1]})
            i += 2
        else:
            due = lines[i + 2] if (i + 2 < len(lines) and date_re.match(lines[i + 2])) else ""
            out.append({"title": lines[i], "raw_course": lines[i + 1], "raw_due": due})
            i += 3 if due else 2
    return out


def build_bookmarklet_code(app_base_url: str) -> str:
    target = str(app_base_url or "").strip().rstrip("/")
    js = (
        "javascript:(function(){"
        "var items=[],seen={};"
        "document.querySelectorAll('li,div[role=\"listitem\"],a[href*=\"/c/\"]').forEach(function(r){"
        "var tx=(r.innerText||'').split('\\n').map(function(s){return s.trim();}).filter(Boolean);"
        "if(tx.length>=2&&tx.length<=5&&tx[0].length>2&&!seen[tx[0]]){"
        "seen[tx[0]]=1;items.push({title:tx[0],course:tx[1]||'',due:tx[2]||''});"
        "}"
        "});"
        "var payload=encodeURIComponent(JSON.stringify({v:1,items:items}));"
        f"var dest='{target}';"
        "if(dest){window.open(dest+'/?gc_sync='+payload,'_blank');}"
        "else{navigator.clipboard.writeText(JSON.stringify({v:1,items:items}));alert('Copied '+items.length+' Classroom items! Paste into Sync tab.');}"
        "})();"
    )
    return js


# ---------------------------------------------------------------------------
# Multi-Session 7-Day Study Planner Engine
# ---------------------------------------------------------------------------
def parse_time_obj(s: Any) -> Optional[time]:
    raw = str(s or "").strip().upper()
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            pass
    return None


def parse_eta_mins(eta_str: Any) -> int:
    s = str(eta_str or "").strip().lower()
    if not s:
        return 30
    total = 0
    hr_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:hr|hour)", s)
    min_m = re.search(r"(\d+)\s*(?:min|m\b)", s)
    if hr_m:
        total += int(float(hr_m.group(1)) * 60)
    if min_m:
        total += int(min_m.group(1))
    if total == 0:
        num_m = re.search(r"\d+", s)
        total = int(num_m.group()) if num_m else 30
    return max(15, min(240, total))


def build_study_plan(
    df: pd.DataFrame, schedule: List[Dict[str, Any]], caps: Dict[str, int]
) -> Dict[str, Dict[str, Any]]:
    today = now_local().date()
    incomplete = df[df["status"] != "Done"].copy() if not df.empty else pd.DataFrame()
    work_queue: List[Dict[str, Any]] = []

    for _, r in incomplete.iterrows():
        try:
            due = date.fromisoformat(str(r["due_date"])) if str(r.get("due_date") or "").strip() else today + timedelta(days=6)
        except Exception:
            due = today + timedelta(days=6)

        txt = f"{r.get('title', '')} {r.get('atype', '')} {r.get('notes', '')}".lower()
        eta_raw = str(r.get("eta") or "").lower()
        recurring = any(k in (eta_raw + " " + txt) for k in ("/day", "per day", "daily", "every day", "each day"))
        is_study = any(k in txt for k in ("study", "review", "test", "quiz", "exam", "midterm", "final", "prep"))
        total_mins = parse_eta_mins(eta_raw)
        lead_days = max(1, (due - today).days)

        if recurring:
            work_queue.append(
                {
                    "id": str(r["id"]),
                    "task_id": str(r["id"]),
                    "title": str(r["title"]),
                    "course": str(r["course"]),
                    "due": due,
                    "priority": int(r.get("priority") or 5),
                    "mins": max(15, min(60, total_mins)),
                    "repeat": True,
                }
            )
        elif is_study and lead_days >= 2:
            sessions = min(4, lead_days)
            per_session = max(20, min(60, total_mins // sessions))
            for s_idx in range(sessions):
                work_queue.append(
                    {
                        "id": f"{r['id']}_s{s_idx+1}",
                        "task_id": str(r["id"]),
                        "title": f"{r['title']} (Session {s_idx+1}/{sessions})",
                        "course": str(r["course"]),
                        "due": due,
                        "preferred_date": today + timedelta(days=s_idx),
                        "priority": int(r.get("priority") or 5),
                        "mins": per_session,
                        "repeat": False,
                    }
                )
        else:
            work_queue.append(
                {
                    "id": str(r["id"]),
                    "task_id": str(r["id"]),
                    "title": str(r["title"]),
                    "course": str(r["course"]),
                    "due": due,
                    "preferred_date": None,
                    "priority": int(r.get("priority") or 5),
                    "mins": max(15, min(120, total_mins)),
                    "repeat": False,
                }
            )

    work_queue.sort(key=lambda t: (t["due"], -t["priority"]))
    scheduled_one_offs = set()
    result: Dict[str, Dict[str, Any]] = {}

    for offset in range(7):
        d = today + timedelta(days=offset)
        day_name = DAYS[d.weekday()]
        cap = max(0, int(caps.get(day_name, 60)))
        busy: List[Tuple[time, time]] = []

        for ev in schedule:
            if ev.get("day") == day_name:
                a, b = parse_time_obj(ev.get("start")), parse_time_obj(ev.get("end"))
                if a and b and b > a:
                    busy.append((a, b))

        cursor = datetime.combine(d, time(15, 30) if d.weekday() < 5 else time(10, 0))
        end_day = datetime.combine(d, time(21, 30) if d.weekday() < 5 else time(20, 30))
        if offset == 0:
            now_naive = now_local().replace(tzinfo=None)
            if now_naive > cursor:
                cursor = now_naive

        slots: List[Dict[str, Any]] = []
        used_mins = 0

        for t in work_queue:
            if not t["repeat"] and t["id"] in scheduled_one_offs:
                continue
            if d > t["due"]:
                continue
            if t.get("preferred_date") and d < t["preferred_date"]:
                continue

            needed = t["mins"]
            if used_mins + needed > cap:
                continue

            start_dt = cursor
            while True:
                stop_dt = start_dt + timedelta(minutes=needed)
                conflict = next(
                    (
                        (datetime.combine(d, a), datetime.combine(d, b))
                        for a, b in busy
                        if start_dt < datetime.combine(d, b) and stop_dt > datetime.combine(d, a)
                    ),
                    None,
                )
                if not conflict:
                    break
                start_dt = conflict[1] + timedelta(minutes=5)

            if start_dt + timedelta(minutes=needed) > end_day:
                continue

            slot_key = hashlib.md5(f"{d.isoformat()}_{t['id']}".encode()).hexdigest()[:10]
            slots.append(
                {
                    "slot_key": slot_key,
                    "task_id": t.get("task_id", t["id"]),
                    "title": t["title"],
                    "course": t["course"],
                    "mins": needed,
                    "time": fmt_time_12h(start_dt),
                    "end_time": fmt_time_12h(start_dt + timedelta(minutes=needed)),
                }
            )
            cursor = start_dt + timedelta(minutes=needed + 5)
            used_mins += needed
            if not t["repeat"]:
                scheduled_one_offs.add(t["id"])

        result[day_name] = {
            "date_label": d.strftime("%A, %b %d"),
            "mins": used_mins,
            "cap": cap,
            "slots": slots,
        }

    return result


# ---------------------------------------------------------------------------
# Simsbury High School (SHS) Bell Schedule & Lunch Wave Engine
# ---------------------------------------------------------------------------
ROTATIONS: Dict[str, List[int]] = {
    "A": [1, 2, 3, 5, 6, 7],
    "B": [4, 1, 2, 8, 5, 6],
    "C": [3, 4, 1, 7, 8, 5],
    "D": [2, 3, 4, 6, 7, 8],
    "X": [1, 2, 3, 4, 5, 6, 7, 8],
}

DROPPED_INFO: Dict[str, str] = {
    "A": "Drops Periods 4 & 8",
    "B": "Drops Periods 3 & 7",
    "C": "Drops Periods 2 & 6",
    "D": "Drops Periods 1 & 5",
    "X": "All 8 Periods Meet",
}

SCHEDULES = [
    "Daily",
    "Connect",
    "2 Hour Delay",
    "Early Dismissal",
    "Emergency Early Dismissal",
    "X Day",
    "X Day 2 Hour Delay",
    "X Day Early Dismissal",
]

BELL_BLOCKS: Dict[str, List[Tuple[str, str, str]]] = {
    "Daily": [
        ("Block 1", "7:32 AM", "8:29 AM"),
        ("Block 2", "8:33 AM", "9:31 AM"),
        ("Block 3", "9:35 AM", "10:32 AM"),
        ("Block 4 (Lunch)", "10:36 AM", "12:08 PM"),
        ("Block 5", "12:12 PM", "1:09 PM"),
        ("Block 6", "1:13 PM", "2:10 PM"),
    ],
    "Connect": [
        ("Block 1", "7:32 AM", "8:23 AM"),
        ("Block 2", "8:27 AM", "9:18 AM"),
        ("Connect", "9:22 AM", "9:53 AM"),
        ("Block 3", "9:57 AM", "10:48 AM"),
        ("Block 4 (Lunch)", "10:52 AM", "12:20 PM"),
        ("Block 5", "12:24 PM", "1:15 PM"),
        ("Block 6", "1:19 PM", "2:10 PM"),
    ],
    "2 Hour Delay": [
        ("Block 1", "9:32 AM", "10:06 AM"),
        ("Block 2", "10:10 AM", "10:44 AM"),
        ("Block 3", "10:48 AM", "11:24 AM"),
        ("Block 4 (Lunch)", "11:28 AM", "12:54 PM"),
        ("Block 5", "12:58 PM", "1:32 PM"),
        ("Block 6", "1:36 PM", "2:10 PM"),
    ],
    "Early Dismissal": [
        ("Block 1", "7:32 AM", "8:05 AM"),
        ("Block 2", "8:09 AM", "8:42 AM"),
        ("Block 3", "8:46 AM", "9:24 AM"),
        ("Block 4", "9:28 AM", "10:01 AM"),
        ("Block 5", "10:05 AM", "10:38 AM"),
        ("Block 6", "10:42 AM", "11:15 AM"),
    ],
    "Emergency Early Dismissal": [
        ("Block 1", "7:32 AM", "8:25 AM"),
        ("Block 2", "8:29 AM", "8:57 AM"),
        ("Block 3", "9:01 AM", "9:29 AM"),
        ("Block 4", "9:33 AM", "10:01 AM"),
        ("Block 5", "10:05 AM", "10:33 AM"),
        ("Block 6", "10:37 AM", "11:05 AM"),
    ],
    "X Day": [
        ("Period 1", "7:32 AM", "8:12 AM"),
        ("Period 2", "8:16 AM", "8:56 AM"),
        ("Period 3", "9:00 AM", "9:42 AM"),
        ("Period 4", "9:46 AM", "10:26 AM"),
        ("Period 5", "10:30 AM", "11:10 AM"),
        ("Period 6 (Lunch)", "11:14 AM", "12:42 PM"),
        ("Period 7", "12:46 PM", "1:26 PM"),
        ("Period 8", "1:30 PM", "2:10 PM"),
    ],
    "X Day 2 Hour Delay": [
        ("Period 1", "9:32 AM", "9:55 AM"),
        ("Period 2", "9:59 AM", "10:22 AM"),
        ("Period 3", "10:26 AM", "10:50 AM"),
        ("Period 4", "10:54 AM", "11:17 AM"),
        ("Period 5", "11:21 AM", "11:44 AM"),
        ("Period 6 (Lunch)", "11:48 AM", "1:16 PM"),
        ("Period 7", "1:20 PM", "1:43 PM"),
        ("Period 8", "1:47 PM", "2:10 PM"),
    ],
    "X Day Early Dismissal": [
        ("Period 1", "7:32 AM", "7:56 AM"),
        ("Period 2", "8:00 AM", "8:24 AM"),
        ("Period 3", "8:28 AM", "8:55 AM"),
        ("Period 4", "8:59 AM", "9:23 AM"),
        ("Period 5", "9:27 AM", "9:51 AM"),
        ("Period 6", "9:55 AM", "10:19 AM"),
        ("Period 7", "10:23 AM", "10:47 AM"),
        ("Period 8", "10:51 AM", "11:15 AM"),
    ],
}

LUNCH_SPLITS: Dict[str, Dict[str, str]] = {
    "Daily": {
        "L1": "🍽️ Lunch 1: 10:36 – 11:04 AM  •  📚 Class: 11:08 AM – 12:08 PM",
        "L2": "📚 Class: 10:36 – 11:06 AM  •  🍽️ Lunch 2: 11:08 – 11:36 AM  •  📚 Class: 11:40 AM – 12:08 PM",
        "L3": "📚 Class: 10:36 – 11:36 AM  •  🍽️ Lunch 3: 11:40 AM – 12:08 PM",
    },
    "Connect": {
        "L1": "🍽️ Lunch 1: 10:52 – 11:19 AM  •  📚 Class: 11:23 AM – 12:20 PM",
        "L2": "📚 Class: 10:52 – 11:21 AM  •  🍽️ Lunch 2: 11:23 – 11:50 AM  •  📚 Class: 11:53 AM – 12:20 PM",
        "L3": "📚 Class: 10:52 – 11:50 AM  •  🍽️ Lunch 3: 11:53 AM – 12:20 PM",
    },
    "2 Hour Delay": {
        "L1": "🍽️ Lunch 1: 11:28 – 11:54 AM  •  📚 Class: 11:58 AM – 12:54 PM",
        "L2": "📚 Class: 11:28 – 11:56 AM  •  🍽️ Lunch 2: 11:58 AM – 12:24 PM  •  📚 Class: 12:28 – 12:54 PM",
        "L3": "📚 Class: 11:28 – 12:24 PM  •  🍽️ Lunch 3: 12:28 – 12:54 PM",
    },
    "X Day": {
        "L1": "🍽️ Lunch 1: 11:14 – 11:41 AM  •  📚 Class: 11:45 AM – 12:42 PM",
        "L2": "📚 Class: 11:14 – 11:42 AM  •  🍽️ Lunch 2: 11:45 AM – 12:12 PM  •  📚 Class: 12:15 – 12:42 PM",
        "L3": "📚 Class: 11:14 – 12:12 PM  •  🍽️ Lunch 3: 12:15 – 12:42 PM",
    },
    "X Day 2 Hour Delay": {
        "L1": "🍽️ Lunch 1: 11:48 AM – 12:15 PM  •  📚 Class: 12:19 – 1:16 PM",
        "L2": "📚 Class: 11:48 AM – 12:16 PM  •  🍽️ Lunch 2: 12:19 – 12:46 PM  •  📚 Class: 12:49 – 1:16 PM",
        "L3": "📚 Class: 11:48 AM – 12:46 PM  •  🍽️ Lunch 3: 12:49 – 1:16 PM",
    },
}


def build_bell_rows(letter: str, schedule: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    periods = cfg.get("periods", {})
    lunches = cfg.get("lunches", {})
    wave = lunches.get(letter, "L2")
    rotation = (
        ROTATIONS["X"]
        if (letter == "X" or schedule.startswith("X Day"))
        else ROTATIONS.get(letter, ROTATIONS["A"])
    )
    blocks = BELL_BLOCKS.get(schedule, BELL_BLOCKS["Daily"])

    rows: List[Dict[str, Any]] = []
    rot_idx = 0
    for blk_label, start_s, end_s in blocks:
        if blk_label == "Connect":
            rows.append(
                {
                    "tag": "Connect",
                    "class_name": "Connect / Advisory",
                    "start": start_s,
                    "end": end_s,
                    "room": "",
                    "lunch_detail": "",
                }
            )
            continue

        p_num = rotation[rot_idx % len(rotation)]
        rot_idx += 1
        cls_name = str(periods.get(str(p_num), "")).strip() or f"Period {p_num}"
        room = (
            str(cfg.get("study_rooms", {}).get(letter, "")).strip()
            if "study" in cls_name.lower()
            else ""
        )
        lunch_detail = ""
        if "(Lunch)" in blk_label and schedule in LUNCH_SPLITS:
            lunch_detail = LUNCH_SPLITS[schedule].get(wave, "")

        rows.append(
            {
                "tag": f"Period {p_num}",
                "class_name": cls_name,
                "start": start_s,
                "end": end_s,
                "room": room,
                "lunch_detail": lunch_detail,
            }
        )
    return rows


def _sheet_override(url: str, target: date) -> Optional[str]:
    if not url:
        return None
    try:
        if "docs.google.com/spreadsheets" in url and "/export?" not in url:
            m = re.search(r"/spreadsheets/d/([^/]+)", url)
            if m:
                url = f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            content = resp.read(500000).decode("utf-8", "replace")
        for row in csv.reader(io.StringIO(content)):
            joined = " ".join(row)
            if target.isoformat() in joined:
                m = re.search(r"\b([ABCDX])(?:\s*Day)?\b", joined, re.I)
                if m:
                    return m.group(1).upper()
    except Exception:
        return None
    return None


def detect_shs_day(target: date, sheet_url: str) -> Tuple[str, str]:
    detected = _sheet_override(sheet_url, target)
    if detected:
        return detected, ("X Day" if detected == "X" else ("Connect" if target.weekday() == 2 else "Daily"))
    if target.weekday() >= 5:
        return "WEEKEND", "Weekend"
    letter = "ABCD"[(target.toordinal() - date(2026, 9, 1).toordinal()) % 4]
    sched = "Connect" if target.weekday() == 2 else "Daily"
    return letter, sched


# ---------------------------------------------------------------------------
# Modal Dialogs
# ---------------------------------------------------------------------------
@dialog_decorator("➕ Add New Assignment")
def show_add_dialog(uid: str, prio_mode: str) -> None:
    courses = sorted(list(set((st.session_state.cfg_courses or []) + ["OTHER", "GENERAL"])))
    with st.form("add_task_modal_form", clear_on_submit=True):
        title = st.text_input("Assignment Title *", placeholder="e.g. Chapter 6 Review Packet")
        c1, c2 = st.columns(2)
        with c1:
            course = st.selectbox("Course", courses)
            atype = st.selectbox("Type", TYPES)
        with c2:
            has_due = st.checkbox("Has Due Date", value=True)
            due_val = st.date_input("Due Date", value=now_local().date() + timedelta(days=1))

        c3, c4 = st.columns(2)
        with c3:
            if prio_mode == PRIO_MODES[1]:
                prio_int = st.slider("Priority (1–10)", 1, 10, 5)
            else:
                pr_lbl = st.selectbox("Priority", PRIORITIES, index=1)
                prio_int = {"Low": 2, "Medium": 5, "High": 9}[pr_lbl]
        with c4:
            eta = st.text_input("Estimated Time", value="30 mins", placeholder="e.g. 45 mins or 1 hr")

        notes = st.text_area("Notes / Instructions (optional)", height=80)
        if st.form_submit_button("💾 Save Assignment", use_container_width=True):
            if not title.strip():
                st.error("Please enter an assignment title.")
            else:
                upsert_task(
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": uid,
                        "title": title.strip(),
                        "course": course,
                        "due_date": due_val.isoformat() if has_due else "",
                        "status": "Not Started",
                        "priority": prio_int,
                        "atype": atype,
                        "eta": eta.strip() or "30 mins",
                        "notes": notes.strip(),
                        "prev_status": "Not Started",
                    }
                )
                st.session_state.pop("_open_modal", None)
                rerun()


@dialog_decorator("✏️ Edit Assignment")
def show_edit_dialog(uid: str, aid: str, prio_mode: str) -> None:
    df = st.session_state.df_cached
    match = df[df["id"] == aid]
    if match.empty:
        st.session_state.pop("_pending_edit_aid", None)
        st.warning("Assignment not found.")
        return

    r = match.iloc[0].to_dict()
    cur_c = str(r.get("course") or "GENERAL").upper()
    courses = sorted(list(set((st.session_state.cfg_courses or []) + [cur_c, "OTHER", "GENERAL"])))
    has_due_init = bool(str(r.get("due_date") or "").strip())
    try:
        due_init = date.fromisoformat(r["due_date"]) if has_due_init else now_local().date()
    except Exception:
        due_init = now_local().date()

    with st.form(f"edit_modal_form_{aid}"):
        title = st.text_input("Assignment Title", value=r["title"])
        c1, c2 = st.columns(2)
        with c1:
            course = st.selectbox("Course", courses, index=courses.index(cur_c))
            cur_t = r.get("atype", "Homework")
            atype = st.selectbox("Type", TYPES, index=TYPES.index(cur_t) if cur_t in TYPES else 0)
        with c2:
            has_due = st.checkbox("Has Due Date", value=has_due_init)
            due_val = st.date_input("Due Date", value=due_init)

        c3, c4 = st.columns(2)
        with c3:
            cur_p = int(r.get("priority") or 5)
            if prio_mode == PRIO_MODES[1]:
                prio_int = st.slider("Priority (1–10)", 1, 10, max(1, min(10, cur_p)))
            else:
                idx_p = 2 if cur_p >= 8 else (1 if cur_p >= 4 else 0)
                pr_lbl = st.selectbox("Priority", PRIORITIES, index=idx_p)
                prio_int = {"Low": 2, "Medium": 5, "High": 9}[pr_lbl]
        with c4:
            eta = st.text_input("Estimated Time", value=str(r.get("eta") or "30 mins"))

        notes = st.text_area("Notes / Instructions", value=str(r.get("notes") or ""), height=85)
        b1, b2 = st.columns(2)
        save_btn = b1.form_submit_button("💾 Save Changes", use_container_width=True)
        cancel_btn = b2.form_submit_button("Cancel", use_container_width=True)

        if save_btn and title.strip():
            upsert_task(
                {
                    **r,
                    "title": title.strip(),
                    "course": course,
                    "due_date": due_val.isoformat() if has_due else "",
                    "priority": prio_int,
                    "atype": atype,
                    "eta": eta.strip() or "30 mins",
                    "notes": notes.strip(),
                }
            )
            st.session_state.pop("_pending_edit_aid", None)
            rerun()
        elif cancel_btn:
            st.session_state.pop("_pending_edit_aid", None)
            rerun()


@dialog_decorator("📚 Manage Courses & Sync Ignore List")
def show_courses_dialog(uid: str) -> None:
    cur = st.session_state.cfg_courses or []
    with st.form("manage_courses_modal"):
        raw = st.text_area(
            "Enter your classes (one per line)",
            value="\n".join(cur) if cur else "GEOMETRY\nSPANISH\nENGLISH\nHISTORY\nCHEMISTRY",
            height=150,
        )
        if st.form_submit_button("Save Classes", use_container_width=True):
            lines = [x.strip().upper() for x in raw.splitlines() if x.strip()]
            save_config(uid, "__SYSTEM_COURSES__", lines)
            st.session_state.pop("_open_modal", None)
            rerun()

    ignored = st.session_state.cfg_ignored or []
    if ignored:
        st.markdown("---")
        st.caption(f"🚫 {len(ignored)} Classroom items permanently ignored during sync.")
        if st.button("Clear Ignored Sync List", use_container_width=True):
            save_config(uid, "__SYSTEM_IGNORED_SYNC__", [])
            rerun()


@dialog_decorator("⚡ Priority Display Style")
def show_prio_dialog(uid: str) -> None:
    cur = st.session_state.cfg_prio or PRIO_MODES[0]
    with st.form("prio_style_modal"):
        chosen = st.radio(
            "Choose how priority is displayed and edited:",
            PRIO_MODES,
            index=PRIO_MODES.index(cur) if cur in PRIO_MODES else 0,
        )
        if st.form_submit_button("Save Priority Style", use_container_width=True):
            save_config(uid, "__SYSTEM_PRIO_CONFIG__", chosen)
            st.session_state.pop("_open_modal", None)
            rerun()


@dialog_decorator("🎨 Theme & Appearance Studio")
def show_theme_dialog(uid: str) -> None:
    cfg = dict(st.session_state.cfg_theme)
    preset_names = list(THEME_PRESETS.keys())
    cur_preset = cfg.get("preset") if cfg.get("preset") in preset_names else preset_names[0]

    chosen_preset = st.selectbox("Quick Preset", preset_names, index=preset_names.index(cur_preset))
    p_meta = THEME_PRESETS[chosen_preset]

    c1, c2 = st.columns(2)
    with c1:
        default_mode = p_meta["mode"] if chosen_preset != cur_preset else cfg.get("mode", "Dark")
        mode = st.selectbox("Contrast Mode", ["Dark", "Light"], index=0 if default_mode == "Dark" else 1)
        bg_opts = ["Gradient", "Solid", "Photo"]
        cur_bg_t = cfg.get("bg_type", "Gradient")
        bg_type = st.selectbox(
            "Background Style", bg_opts, index=bg_opts.index(cur_bg_t) if cur_bg_t in bg_opts else 0
        )
    with c2:
        default_acc = p_meta["accent"] if chosen_preset != cur_preset else cfg.get("accent", "#6366f1")
        accent = st.color_picker("Accent Color", value=default_acc)
        opacity = st.slider("Card Opacity (%)", 60, 98, int(cfg.get("opacity", 92)))

    solid = cfg.get("solid", p_meta["solid"])
    grad_1 = p_meta["grad_1"] if chosen_preset != cur_preset else cfg.get("grad_1", "#090d1a")
    grad_2 = p_meta["grad_2"] if chosen_preset != cur_preset else cfg.get("grad_2", "#141d38")
    background = cfg.get("background", "")

    if bg_type == "Solid":
        solid = st.color_picker("Solid Background Color", value=solid if solid.startswith("#") else p_meta["solid"])
        background = solid
    elif bg_type == "Gradient":
        gc1, gc2 = st.columns(2)
        grad_1 = gc1.color_picker("Gradient Start", value=grad_1)
        grad_2 = gc2.color_picker("Gradient End", value=grad_2)
        background = f"linear-gradient(135deg, {grad_1} 0%, {grad_2} 100%)"
    else:
        up = st.file_uploader("Upload Background Image (auto-compressed)", type=["jpg", "jpeg", "png", "webp"])
        if up is not None:
            try:
                from PIL import Image

                img = Image.open(up)
                img.thumbnail((1200, 1200))
                buf = io.BytesIO()
                img.convert("RGB").save(buf, format="JPEG", quality=70, optimize=True)
                background = f"url(data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}) center/cover"
            except Exception:
                st.warning("Could not compress image; please choose Solid or Gradient.")

    b1, b2 = st.columns(2)
    if b1.button("💾 Apply & Save Theme", use_container_width=True):
        save_config(
            uid,
            "__SYSTEM_THEME_CONFIG__",
            {
                "preset": chosen_preset,
                "mode": mode,
                "accent": accent,
                "opacity": opacity,
                "bg_type": bg_type,
                "solid": solid,
                "grad_1": grad_1,
                "grad_2": grad_2,
                "background": background,
            },
        )
        st.session_state.pop("_open_modal", None)
        rerun()
    if b2.button("↩️ Reset Default", use_container_width=True):
        save_config(uid, "__SYSTEM_THEME_CONFIG__", dict(DEFAULT_THEME))
        st.session_state.pop("_open_modal", None)
        rerun()


@dialog_decorator("💬 Feedback & Developer Replies")
def show_feedback_dialog(uid: str, email: str) -> None:
    with st.form("student_feedback_modal", clear_on_submit=True):
        category = st.selectbox(
            "Category", ["Feature Request", "Bug Report", "SHS Bell Schedule Issue", "General Feedback"]
        )
        rating = st.slider("App Rating", 1, 5, 5)
        msg = st.text_area("Message", placeholder="Describe a bug or suggest a feature...", height=90)
        if st.form_submit_button("Send Feedback", use_container_width=True):
            if msg.strip():
                bg_sql(
                    "INSERT INTO feedback (id, user_id, email, category, rating, message, created_at) VALUES (:id, :uid, :em, :cat, :rat, :msg, :ca)",
                    {
                        "id": str(uuid.uuid4()),
                        "uid": uid,
                        "em": email,
                        "cat": category,
                        "rat": rating,
                        "msg": msg.strip(),
                        "ca": now_local().isoformat(),
                    },
                )
                st.success("Sent! Developer replies will appear below.")
            else:
                st.error("Please enter a message first.")

    with db_engine().connect() as conn:
        threads = (
            conn.execute(
                text("SELECT id, category, message, created_at FROM feedback WHERE user_id = :uid ORDER BY created_at DESC LIMIT 20"),
                {"uid": uid},
            )
            .mappings()
            .all()
        )
        replies = (
            conn.execute(
                text(
                    "SELECT id, feedback_id, sender_email, message, created_at, COALESCE(is_read, 0) AS is_read FROM feedback_replies "
                    "WHERE feedback_id IN (SELECT id FROM feedback WHERE user_id = :uid) ORDER BY created_at ASC"
                ),
                {"uid": uid},
            )
            .mappings()
            .all()
        )

    rep_by_fid: Dict[str, List[Dict[str, Any]]] = {}
    unread_ids: List[str] = []
    for rep in replies:
        rep_by_fid.setdefault(str(rep["feedback_id"]), []).append(dict(rep))
        if int(rep.get("is_read") or 0) == 0 and str(rep.get("sender_email", "")).lower() == ADMIN_EMAIL:
            unread_ids.append(str(rep["id"]))

    if unread_ids:
        bg_sql("UPDATE feedback_replies SET is_read = 1 WHERE id = ANY(:ids)", {"ids": unread_ids})

    if threads:
        st.markdown("---")
        for th in threads:
            fid = str(th["id"])
            with st.expander(f"[{th['category']}] {th['message'][:45]}...", expanded=bool(rep_by_fid.get(fid))):
                st.write(f"**You:** {th['message']}")
                for rep in rep_by_fid.get(fid, []):
                    who = "🛠️ Developer" if str(rep["sender_email"]).lower() == ADMIN_EMAIL else "You"
                    st.info(f"**{who}:** {rep['message']}")


@dialog_decorator("🛠️ Creator Admin Panel — Feature Control Center")
def show_admin_dialog() -> None:
    fc_pk = SCHEMA_INFO["fc_pk"]
    ff_pk = SCHEMA_INFO["ff_pk"]

    with db_engine().connect() as conn:
        if SCHEMA_INFO.get("fe_has_legacy"):
            err_sql = (
                "SELECT id, COALESCE(feature, feature_name, 'Feature') AS feature, "
                "COALESCE(message, error_msg, '') AS message, created_at "
                "FROM feature_errors WHERE COALESCE(resolved, 0) = 0 ORDER BY created_at DESC LIMIT 30"
            )
        else:
            err_sql = (
                "SELECT id, feature, message, created_at FROM feature_errors "
                "WHERE COALESCE(resolved, 0) = 0 ORDER BY created_at DESC LIMIT 30"
            )
        errors = conn.execute(text(err_sql)).mappings().all()
        flags = conn.execute(text(f"SELECT {ff_pk} AS fk, status FROM feature_flags")).mappings().all()
        catalog = conn.execute(
            text(f"SELECT {fc_pk} AS fk, COALESCE(description, '') AS description FROM feature_catalog ORDER BY {fc_pk}")
        ).mappings().all()
        fb_items = (
            conn.execute(
                text("SELECT id, email, category, rating, message, created_at FROM feedback ORDER BY created_at DESC LIMIT 40")
            )
            .mappings()
            .all()
        )

    flag_map = {str(r["fk"]): str(r["status"]) for r in flags}

    if errors:
        st.subheader(f"🚨 Unresolved Fallback Alerts ({len(errors)})")
        for err in errors:
            c1, c2 = st.columns([4, 1])
            c1.error(f"**{err['feature']}**: {err['message']}")
            if c2.button("Dismiss", key=f"adm_err_{err['id']}", use_container_width=True):
                bg_sql("UPDATE feature_errors SET resolved = 1 WHERE id = :id", {"id": err["id"]})
                rerun()

    st.subheader("🎛️ Feature Release Toggles")
    state_opts = ["Public Released", "Beta Testing", "Removed/Hidden"]
    for item in catalog:
        fk = str(item["fk"])
        cur_st = flag_map.get(fk, "Public Released")
        if cur_st == "released":
            cur_st = "Public Released"
        elif cur_st == "beta":
            cur_st = "Beta Testing"
        elif cur_st == "disabled":
            cur_st = "Removed/Hidden"

        c1, c2, c3 = st.columns([2.5, 1.6, 0.9])
        c1.markdown(
            f"**{fk}**  \n<span style='font-size:0.78rem; opacity:0.75;'>{esc(item['description'])}</span>",
            unsafe_allow_html=True,
        )
        new_st = c2.selectbox(
            fk,
            state_opts,
            index=state_opts.index(cur_st) if cur_st in state_opts else 0,
            label_visibility="collapsed",
            key=f"adm_sel_{fk}",
        )
        if c3.button("Save", key=f"adm_sav_{fk}", use_container_width=True):
            bg_sql(
                f"INSERT INTO feature_flags ({ff_pk}, status) VALUES (:f, :s) "
                f"ON CONFLICT ({ff_pk}) DO UPDATE SET status = EXCLUDED.status",
                {"f": fk, "s": new_st},
            )
            st.session_state.feature_flags_map[fk] = new_st
            rerun()

    st.subheader("📬 User Feedback Inbox")
    if not fb_items:
        st.caption("No user feedback messages yet.")
    for fb in fb_items:
        fid = str(fb["id"])
        with st.expander(f"[{fb['category']}] {fb['email']} ({fb.get('rating', 5)}★)"):
            st.write(fb["message"])
            rep_txt = st.text_input("Reply to student", key=f"adm_rep_in_{fid}")
            if st.button("Send Reply", key=f"adm_rep_btn_{fid}") and rep_txt.strip():
                if SCHEMA_INFO.get("fr_has_is_admin"):
                    bg_sql(
                        "INSERT INTO feedback_replies (id, feedback_id, sender_email, message, created_at, is_read, is_admin) "
                        "VALUES (:id, :fid, :em, :msg, :ca, 0, 1)",
                        {
                            "id": str(uuid.uuid4()),
                            "fid": fid,
                            "em": ADMIN_EMAIL,
                            "msg": rep_txt.strip(),
                            "ca": now_local().isoformat(),
                        },
                    )
                else:
                    bg_sql(
                        "INSERT INTO feedback_replies (id, feedback_id, sender_email, message, created_at, is_read) "
                        "VALUES (:id, :fid, :em, :msg, :ca, 0)",
                        {
                            "id": str(uuid.uuid4()),
                            "fid": fid,
                            "em": ADMIN_EMAIL,
                            "msg": rep_txt.strip(),
                            "ca": now_local().isoformat(),
                        },
                    )
                st.success("Reply sent!")


# ---------------------------------------------------------------------------
# Tab Renderers
# ---------------------------------------------------------------------------
def render_assignments_tab(uid: str, email: str, prio_mode: str, light: bool) -> None:
    df = st.session_state.df_cached
    today_dt = now_local().date()

    total_active = int((df["status"] != "Done").sum()) if not df.empty else 0
    due_today_cnt = (
        int(((df["status"] != "Done") & (df["due_date"] == today_dt.isoformat())).sum()) if not df.empty else 0
    )
    overdue_cnt = (
        int(((df["status"] != "Done") & (df["due_date"] != "") & (df["due_date"] < today_dt.isoformat())).sum())
        if not df.empty
        else 0
    )
    done_cnt = int((df["status"] == "Done").sum()) if not df.empty else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(
        f"<div class='stat-chip'><div class='stat-num'>{total_active}</div><div class='stat-lbl'>Active Tasks</div></div>",
        unsafe_allow_html=True,
    )
    m2.markdown(
        f"<div class='stat-chip'><div class='stat-num'>{due_today_cnt}</div><div class='stat-lbl'>Due Today</div></div>",
        unsafe_allow_html=True,
    )
    m3.markdown(
        f"<div class='stat-chip'><div class='stat-num'>{overdue_cnt}</div><div class='stat-lbl'>Overdue</div></div>",
        unsafe_allow_html=True,
    )
    m4.markdown(
        f"<div class='stat-chip'><div class='stat-num'>{done_cnt}</div><div class='stat-lbl'>Completed</div></div>",
        unsafe_allow_html=True,
    )

    c_add, c_search, c_course, c_status, c_sort = st.columns([1.05, 1.85, 1.15, 1.15, 1.05])
    if c_add.button("➕ Add Task", use_container_width=True, key="board_add_btn"):
        st.session_state["_open_modal"] = "add"
        rerun()

    search = c_search.text_input(
        "Search", placeholder="🔍 Search title, class, or notes...", label_visibility="collapsed", key="board_search"
    )
    course_opts = ["All Classes"] + (sorted(list({str(c).upper() for c in df["course"].dropna()})) if not df.empty else [])
    cf = c_course.selectbox("Course", course_opts, label_visibility="collapsed", key="board_course")
    sf = c_status.selectbox(
        "Status", ["Active Only", "All Tasks"] + STATUSES, label_visibility="collapsed", key="board_status"
    )
    sort_by = c_sort.selectbox(
        "Sort", ["Due Date", "Priority", "Course"], label_visibility="collapsed", key="board_sort"
    )

    if df.empty:
        st.info("No assignments yet! Click **➕ Add Task** above or open **Classroom Sync** to import your work.")
        return

    view = df.copy()
    if sf == "Active Only":
        view = view[view["status"] != "Done"]
    elif sf in STATUSES:
        view = view[view["status"] == sf]

    if cf != "All Classes":
        view = view[view["course"].str.upper() == cf]

    if search.strip():
        q = search.strip().lower()
        view = view[
            view.apply(lambda r: q in f"{r['title']} {r['course']} {r['notes']}".lower(), axis=1)
        ]

    if view.empty:
        st.info("No assignments match your current filters.")
        return

    view["_s_done"] = view["status"].apply(lambda s: 1 if s == "Done" else 0)
    view["_s_due"] = view["due_date"].apply(lambda x: str(x).strip() if str(x).strip() else "9999-12-31")
    view["_s_prio"] = view["priority"].apply(lambda p: -int(p or 5))

    if sort_by == "Priority":
        view = view.sort_values(["_s_done", "_s_prio", "_s_due"])
    elif sort_by == "Course":
        view = view.sort_values(["_s_done", "course", "_s_due"])
    else:
        view = view.sort_values(["_s_done", "_s_due", "_s_prio"])

    col_l, col_r = st.columns(2)
    rows_list = [r for _, r in view.iterrows()]
    for idx, r in enumerate(rows_list):
        target_col = col_l if idx % 2 == 0 else col_r
        with target_col:
            with st.container(border=True):
                aid = str(r["id"])
                status = str(r["status"])
                c_pill = course_badge_html(r["course"], light)
                p_pill = priority_badge_html(r["priority"], prio_mode)
                d_pill = due_badge_html(r["due_date"], today_dt, status)
                title_cls = "task-title task-title-done" if status == "Done" else "task-title"

                st.markdown(
                    f"<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;'>"
                    f"<div>{c_pill} <span style='font-size:0.76rem; opacity:0.75; margin-left:6px;'>• {esc(r['atype'])}</span></div>"
                    f"{p_pill}"
                    f"</div>"
                    f"<div class='{title_cls}'>{esc(r['title'])}</div>"
                    f"<div class='task-meta'>{d_pill} &nbsp;•&nbsp; ⏱️ {esc(r['eta'] or '30 mins')} &nbsp;•&nbsp; <b>{esc(status)}</b></div>",
                    unsafe_allow_html=True,
                )
                if str(r.get("notes") or "").strip():
                    note_txt = str(r["notes"]).strip()
                    if len(note_txt) > 150:
                        note_txt = note_txt[:147] + "..."
                    st.markdown(f"<div class='task-note'>{esc(note_txt)}</div>", unsafe_allow_html=True)

                b1, b2, b3, b4 = st.columns([1.3, 1.3, 0.85, 0.85])
                if b1.button("↩️ Undo" if status == "Done" else "✅ Done", key=f"done_{aid}", use_container_width=True):
                    prev_s = str(r.get("prev_status") or "Not Started")
                    new_s = (prev_s if prev_s != "Done" else "Not Started") if status == "Done" else "Done"
                    upsert_task(
                        {
                            **r.to_dict(),
                            "status": new_s,
                            "prev_status": status if new_s == "Done" else prev_s,
                        }
                    )
                    rerun()

                if b2.button(
                    "⏸️ Pause" if status == "In Progress" else "▶️ Start",
                    key=f"start_{aid}",
                    use_container_width=True,
                    disabled=(status == "Done"),
                ):
                    upsert_task(
                        {
                            **r.to_dict(),
                            "status": "Not Started" if status == "In Progress" else "In Progress",
                        }
                    )
                    rerun()

                if b3.button("✏️", key=f"edit_{aid}", use_container_width=True, help="Edit task"):
                    st.session_state["_pending_edit_aid"] = aid
                    rerun()

                if b4.button("🗑️", key=f"del_{aid}", use_container_width=True, help="Delete task"):
                    delete_task(aid)
                    rerun()


def render_classroom_sync_tab(uid: str, email: str) -> None:
    if get_feature_state("classroom_sync_v2") in ("Beta Testing", "beta"):
        st.markdown(
            "<div class='beta-banner'>🧪 <b>Beta Feature:</b> Chromebook Ctrl+A Paste Sync is active.</div>",
            unsafe_allow_html=True,
        )

    tab_paste, tab_bm = st.tabs(["📋 Chromebook Ctrl+A Paste Sync", "🔖 Bookmarklet (Personal Device)"])
    auto_payload = st.session_state.pop("_gc_auto_payload", "")
    if auto_payload:
        st.session_state.sync_preview = parse_classroom_blob(auto_payload)

    with tab_paste:
        st.caption(
            "On a school Chromebook: open Google Classroom → **To-do**, expand **No due date** & **Later**, "
            "press **Ctrl+A** then **Ctrl+C**, paste below, and click **Scan Classroom Tasks**."
        )
        pasted = st.text_area("Paste Classroom To-do text here", height=150, key="gc_paste_box")
        c1, c2 = st.columns(2)
        if c1.button("🔍 Scan Classroom Tasks", use_container_width=True):
            st.session_state.sync_preview = parse_classroom_blob(pasted)

        if c2.button("⚡ Scan & Import All New", use_container_width=True):
            items = parse_classroom_blob(pasted)
            df_cur = st.session_state.df_cached
            ignored_set = {x.lower() for x in (st.session_state.cfg_ignored or [])}
            added = 0
            for it in items:
                title = it["title"].strip()
                course = map_course(it["raw_course"], title, st.session_state.cfg_courses or [])
                due = parse_date(it["raw_due"])
                if not title or title.lower() in ignored_set or is_duplicate_task(title, course, due, df_cur):
                    continue
                upsert_task(
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": uid,
                        "title": title,
                        "course": course,
                        "due_date": due,
                        "status": "Not Started",
                        "priority": 5,
                        "atype": guess_type(title, course),
                        "eta": "30 mins",
                        "notes": f"Synced from Google Classroom ({it['raw_course']})" if it["raw_course"] else "Synced from Google Classroom",
                        "prev_status": "Not Started",
                    }
                )
                df_cur = st.session_state.df_cached
                added += 1
            st.session_state.pop("sync_preview", None)
            if added:
                st.success(f"Imported {added} new assignments!")
                rerun()
            else:
                st.info("No new assignments found (duplicates and ignored items were skipped).")

        preview = st.session_state.get("sync_preview", [])
        if preview:
            st.markdown("---")
            df_cur = st.session_state.df_cached
            ignored_set = {x.lower() for x in (st.session_state.cfg_ignored or [])}
            checked_items = []
            unchecked_titles = []
            for idx, it in enumerate(preview):
                course = map_course(it["raw_course"], it["title"], st.session_state.cfg_courses or [])
                due = parse_date(it["raw_due"])
                dup = is_duplicate_task(it["title"], course, due, df_cur) or (it["title"].lower() in ignored_set)
                lbl = f"[{course}] {it['title']} • Due: {due or 'No due date'}" + (" (already added/ignored)" if dup else "")
                is_chk = st.checkbox(lbl, value=not dup, key=f"sync_chk_{idx}")
                if is_chk:
                    checked_items.append((it, course, due))
                else:
                    unchecked_titles.append(it["title"].strip())

            b_imp, b_ign = st.columns(2)
            if b_imp.button(f"✅ Import Selected ({len(checked_items)})", use_container_width=True):
                for it, course, due in checked_items:
                    title = it["title"].strip()
                    if not title or is_duplicate_task(title, course, due, st.session_state.df_cached):
                        continue
                    upsert_task(
                        {
                            "id": str(uuid.uuid4()),
                            "user_id": uid,
                            "title": title,
                            "course": course,
                            "due_date": due,
                            "status": "Not Started",
                            "priority": 5,
                            "atype": guess_type(title, course),
                            "eta": "30 mins",
                            "notes": f"Synced from Google Classroom ({it['raw_course']})" if it["raw_course"] else "Synced from Google Classroom",
                            "prev_status": "Not Started",
                        }
                    )
                st.session_state.pop("sync_preview", None)
                rerun()

            if b_ign.button("🚫 Ignore Unchecked Forever", use_container_width=True):
                if unchecked_titles:
                    cur_ign = list(st.session_state.cfg_ignored or [])
                    save_config(uid, "__SYSTEM_IGNORED_SYNC__", list(set(cur_ign + unchecked_titles)))
                st.session_state.pop("sync_preview", None)
                rerun()

    with tab_bm:
        st.caption("School-managed Chromebooks block `javascript:` bookmarks. Use this bookmarklet on your personal laptop or phone.")
        shs_cfg = st.session_state.cfg_shs
        app_url = st.text_input(
            "Your Tracker URL",
            value=shs_cfg.get("app_url", ""),
            placeholder="https://your-app.streamlit.app",
            key="bm_app_url",
        )
        if app_url.strip() != shs_cfg.get("app_url", ""):
            shs_cfg["app_url"] = app_url.strip()
            save_config(uid, "__SYSTEM_SHS_CONFIG__", shs_cfg)
        st.code(build_bookmarklet_code(app_url), language="text")


def render_planner_tab(uid: str, light: bool) -> None:
    if get_feature_state("ai_study_planner") in ("Beta Testing", "beta"):
        st.markdown(
            "<div class='beta-banner'>🧪 <b>Beta Feature:</b> Multi-Session 7-Day Study Planner.</div>",
            unsafe_allow_html=True,
        )

    caps = dict(st.session_state.cfg_max_work or {d: 60 for d in DAYS})
    schedule = list(st.session_state.cfg_schedule or [])
    completed_slots = dict(st.session_state.cfg_completed or {})

    with st.expander("⚙️ Daily Homework Time Caps & Weekly Commitments (Sports / Clubs / Work)", expanded=False):
        st.markdown("**1. Max Homework Minutes Per Day**")
        cols = st.columns(7)
        for i, d_name in enumerate(DAYS):
            caps[d_name] = cols[i].number_input(
                d_name[:3], min_value=0, max_value=360, step=15, value=int(caps.get(d_name, 60)), key=f"cap_{d_name}"
            )
        if st.button("💾 Save Daily Caps", key="save_caps_btn"):
            save_config(uid, "__SYSTEM_MAX_WORK_CONFIG__", caps)
            st.success("Daily limits saved!")
            rerun()

        st.markdown("---")
        st.markdown("**2. Weekly Recurring Commitments (Blocked Automatically)**")
        sc1, sc2, sc3, sc4, sc5 = st.columns([1.2, 2.0, 1.1, 1.1, 0.9])
        ev_day = sc1.selectbox("Day", DAYS, key="sched_day")
        ev_name = sc2.text_input("Activity", placeholder="e.g. Track Practice", key="sched_name")
        ev_start = sc3.text_input("Start", value="3:30 PM", key="sched_start")
        ev_end = sc4.text_input("End", value="5:30 PM", key="sched_end")
        sc5.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if sc5.button("➕ Add", key="sched_add_btn", use_container_width=True):
            if ev_name.strip() and parse_time_obj(ev_start) and parse_time_obj(ev_end):
                schedule.append(
                    {
                        "id": str(uuid.uuid4())[:8],
                        "day": ev_day,
                        "title": ev_name.strip(),
                        "start": ev_start.strip(),
                        "end": ev_end.strip(),
                    }
                )
                save_config(uid, "__SYSTEM_SCHEDULE__", schedule)
                rerun()
            else:
                st.error("Enter a valid activity name and start/end times (e.g. 3:30 PM).")

        for idx, ev in enumerate(schedule):
            ec1, ec2 = st.columns([5, 1])
            ec1.write(f"• **{ev.get('day')}**: {ev.get('title')} ({ev.get('start')} – {ev.get('end')})")
            if ec2.button("✕", key=f"del_sched_{idx}"):
                trimmed = [x for j, x in enumerate(schedule) if j != idx]
                save_config(uid, "__SYSTEM_SCHEDULE__", trimmed)
                rerun()

    plan = run_with_fallback(
        "AI Study Planner",
        lambda: build_study_plan(st.session_state.df_cached, schedule, caps),
        lambda: build_study_plan(st.session_state.df_cached, [], {d: 90 for d in DAYS}),
    )

    if not any(info["slots"] for info in plan.values()):
        st.info("🎉 All caught up! No active assignments need scheduling right now.")
        return

    for day_name, info in plan.items():
        if not info["slots"]:
            continue
        st.markdown(
            f"<div class='plan-day-card'>"
            f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
            f"<b>📅 {esc(info['date_label'])}</b>"
            f"<span class='slot-time-pill'>Planned: {info['mins']}m / {info['cap']}m cap</span>"
            f"</div></div>",
            unsafe_allow_html=True,
        )
        for sl in info["slots"]:
            sk = sl["slot_key"]
            is_done_slot = sk in completed_slots
            c_pill = course_badge_html(sl["course"], light)
            c1, c2, c3 = st.columns([0.4, 4.5, 1.1])
            chk = c1.checkbox("Done", value=is_done_slot, key=f"slot_chk_{sk}", label_visibility="collapsed")
            if chk != is_done_slot:
                if chk:
                    completed_slots[sk] = sl["title"]
                else:
                    completed_slots.pop(sk, None)
                save_config(uid, "__SYSTEM_COMPLETED_SLOTS__", completed_slots)
                rerun()

            strike = "text-decoration:line-through; opacity:0.6;" if chk else ""
            c2.markdown(
                f"<div style='{strike} padding-top:4px;'>"
                f"<span class='slot-time-pill'>{sl['time']} – {sl['end_time']}</span> &nbsp;"
                f"{c_pill} &nbsp;"
                f"<b>{esc(sl['title'])}</b> <span style='opacity:0.75; font-size:0.82rem;'>({sl['mins']} min)</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if c3.button("✅ Finish Task", key=f"fin_task_{sk}", use_container_width=True):
                df_cur = st.session_state.df_cached
                match = df_cur[df_cur["id"] == sl["task_id"]]
                if not match.empty:
                    row_d = match.iloc[0].to_dict()
                    upsert_task({**row_d, "status": "Done", "prev_status": row_d["status"]})
                    rerun()


@fragment_decorator(run_every=30)
def render_bell_schedule_tab(uid: str, light: bool) -> None:
    if get_feature_state("shs_bell_schedule") in ("Beta Testing", "beta"):
        st.markdown(
            "<div class='beta-banner'>🧪 <b>Beta Feature:</b> Live Simsbury High School Bell Schedule.</div>",
            unsafe_allow_html=True,
        )

    cfg = dict(st.session_state.cfg_shs)
    now_dt = now_local()
    today_dt = now_dt.date()

    c1, c2, c3 = st.columns([1.2, 1.1, 1.4])
    view_date = c1.date_input("Date", value=today_dt, key="shs_date_in")
    auto_letter, auto_sched = detect_shs_day(view_date, cfg.get("sheet_url", ""))

    day_opts = [f"Auto ({auto_letter})"] + LETTERS
    sel_day = c2.selectbox("Letter Day", day_opts, key="shs_letter_sel")
    letter = auto_letter if sel_day.startswith("Auto") else sel_day

    sched_opts = [f"Auto ({auto_sched})"] + SCHEDULES
    sel_sched = c3.selectbox("Schedule Type", sched_opts, key="shs_sched_sel")
    sched = auto_sched if sel_sched.startswith("Auto") else sel_sched

    if letter == "WEEKEND" and sel_day.startswith("Auto"):
        st.info(f"📅 **{view_date.strftime('%A, %b %d')}** — Weekend (no classes scheduled). Switch **Letter Day** above to preview any rotation.")
    else:
        l_key = letter if letter in LETTERS else "A"
        wave = cfg.get("lunches", {}).get(l_key, "L2")
        dropped_txt = DROPPED_INFO.get(l_key, "")
        st.markdown(
            f"<div class='shs-topbar'>"
            f"🔔 <b>{view_date.strftime('%A, %b %d')}</b> &nbsp;•&nbsp; <b>{l_key} Day</b> ({esc(sched)}) "
            f"<span class='shs-pill'>{esc(dropped_txt)}</span>"
            f"<span class='shs-pill'>Lunch Wave {esc(wave)}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        rows = build_bell_rows(l_key, sched, cfg)
        cur_time = now_dt.time() if view_date == today_dt else None

        for r in rows:
            t_start = parse_time_obj(r["start"])
            t_end = parse_time_obj(r["end"])
            is_live = bool(cur_time and t_start and t_end and t_start <= cur_time < t_end)
            row_cls = "bell-row bell-row-live" if is_live else "bell-row"

            mins_left = ""
            if is_live and t_end is not None:
                rem = (t_end.hour * 60 + t_end.minute) - (cur_time.hour * 60 + cur_time.minute)
                mins_left = f"<span class='bell-live-badge'>NOW • {rem}m LEFT</span>"

            c_pill = course_badge_html(r["class_name"], light)
            rm_html = f"<span style='font-size:0.80rem; opacity:0.8; margin-left:6px;'>Room {esc(r['room'])}</span>" if r["room"] else ""
            lunch_html = f"<div class='lunch-sub-box'>{esc(r['lunch_detail'])}</div>" if r["lunch_detail"] else ""

            st.markdown(
                f"<div class='{row_cls}'>"
                f"<div><span class='slot-time-pill'>{esc(r['tag'])}</span> &nbsp; {c_pill}{rm_html}{mins_left}</div>"
                f"<div><b>{esc(r['start'])} – {esc(r['end'])}</b></div>"
                f"{lunch_html}"
                f"</div>",
                unsafe_allow_html=True,
            )

    with st.expander("⚙️ Customize Period 1–8 Classes, Lunch Waves & Study Hall Rooms", expanded=False):
        st.markdown("**1. Period 1–8 Classes** *(Include `Study Hall` in a period name to show your Study Hall room)*")
        periods = dict(cfg.get("periods", {}))
        p_cols = st.columns(4)
        for p_num in range(1, 9):
            with p_cols[(p_num - 1) % 4]:
                periods[str(p_num)] = st.text_input(
                    f"Period {p_num}", value=periods.get(str(p_num), ""), key=f"shs_p_{p_num}"
                )

        st.markdown("**2. Lunch Wave & Study Hall Room by Letter Day**")
        lunches = dict(cfg.get("lunches", {d: "L2" for d in LETTERS}))
        rooms = dict(cfg.get("study_rooms", {d: "" for d in LETTERS}))
        d_cols = st.columns(5)
        for idx, let in enumerate(LETTERS):
            with d_cols[idx]:
                cur_w = lunches.get(let, "L2")
                lunches[let] = st.selectbox(
                    f"{let} Lunch",
                    ["L1", "L2", "L3"],
                    index=["L1", "L2", "L3"].index(cur_w) if cur_w in ("L1", "L2", "L3") else 1,
                    key=f"shs_lw_{let}",
                )
                rooms[let] = st.text_input(
                    f"{let} Study Room", value=rooms.get(let, ""), placeholder="e.g. 214", key=f"shs_rm_{let}"
                )

        sheet_url = st.text_input(
            "Optional Public Google Sheet Calendar URL",
            value=cfg.get("sheet_url", ""),
            placeholder="https://docs.google.com/spreadsheets/d/...",
            key="shs_sheet_url",
        )
        if st.button("💾 Save SHS Schedule Settings", key="save_shs_settings_btn", use_container_width=True):
            cfg.update({"periods": periods, "lunches": lunches, "study_rooms": rooms, "sheet_url": sheet_url.strip()})
            save_config(uid, "__SYSTEM_SHS_CONFIG__", cfg)
            st.success("SHS schedule settings saved!")
            rerun()


# ---------------------------------------------------------------------------
# Authentication & Main App Entry
# ---------------------------------------------------------------------------
def auth_page() -> None:
    st.markdown(build_theme_css(DEFAULT_THEME), unsafe_allow_html=True)
    _, col_mid, _ = st.columns([1, 1.35, 1])
    with col_mid:
        st.markdown(
            "<div class='auth-hero'>"
            "<div class='shs-brand'>📚 Assignment <span class='shs-accent'>Tracker</span></div>"
            "<div class='shs-sub'>Simsbury High School • Student Planner & Bell Schedule</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        mode = st.radio("Account", ["Sign In", "Create Account"], horizontal=True, label_visibility="collapsed")
        with st.form("auth_login_form"):
            email_in = st.text_input("School Email or Username", placeholder="30lastnamef@simsburyschools.net")
            pw_in = st.text_input("Password", type="password", placeholder="Enter your password")
            btn_lbl = "Sign In" if mode == "Sign In" else "Create Account"
            if st.form_submit_button(btn_lbl, use_container_width=True):
                clean_em = email_in.strip().lower()
                if "@" not in clean_em and clean_em:
                    clean_em += DOMAIN
                if not clean_em or not pw_in:
                    st.error("Please enter both your email and password.")
                elif mode == "Create Account":
                    if not clean_em.endswith(DOMAIN) and not is_admin(clean_em):
                        st.error(f"Please use your {DOMAIN} email.")
                    elif len(pw_in) < 4:
                        st.error("Password must be at least 4 characters.")
                    else:
                        try:
                            new_uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, clean_em))
                            with db_engine().begin() as conn:
                                conn.execute(
                                    text(
                                        "INSERT INTO users (id, email, password_hash, created_at) VALUES (:id, :em, :pw, :ca)"
                                    ),
                                    {
                                        "id": new_uid,
                                        "em": clean_em,
                                        "pw": _hash_pw(pw_in),
                                        "ca": now_local().isoformat(),
                                    },
                                )
                            st.session_state.user = {"id": new_uid, "email": clean_em}
                            hydrate_user_session(new_uid, True)
                            rerun()
                        except Exception:
                            st.error("An account with that email already exists. Switch to Sign In.")
                else:
                    with db_engine().connect() as conn:
                        row = conn.execute(
                            text("SELECT id, email, password_hash FROM users WHERE email = :em"),
                            {"em": clean_em},
                        ).fetchone()
                    if row and row.password_hash == _hash_pw(pw_in):
                        st.session_state.user = {"id": str(row.id), "email": str(row.email)}
                        hydrate_user_session(str(row.id), True)
                        rerun()
                    else:
                        st.error("Invalid email or password.")


def main() -> None:
    try:
        qp = st.query_params.get("gc_sync", "")
        if qp:
            st.session_state["_gc_auto_payload"] = urllib.parse.unquote(qp)
            try:
                del st.query_params["gc_sync"]
            except Exception:
                pass
    except Exception:
        pass

    user = st.session_state.get("user")
    if not user:
        auth_page()
        return

    uid = str(user["id"])
    email = str(user["email"])
    hydrate_user_session(uid)

    theme_cfg = st.session_state.cfg_theme
    light = theme_cfg.get("mode") == "Light"
    st.markdown(build_theme_css(theme_cfg), unsafe_allow_html=True)

    now_dt = now_local()
    shs_letter, shs_sched = detect_shs_day(now_dt.date(), st.session_state.cfg_shs.get("sheet_url", ""))
    shs_badge = "Weekend" if shs_letter == "WEEKEND" else f"{shs_letter} Day • {shs_sched}"

    admin_user = is_admin(email)
    if admin_user:
        h_info, b_adm, b_thm, b_cls, b_pri, b_fb, b_out = st.columns([3.8, 0.85, 0.65, 0.65, 0.65, 0.65, 0.75])
    else:
        h_info, b_thm, b_cls, b_pri, b_fb, b_out = st.columns([4.4, 0.7, 0.7, 0.7, 0.7, 0.8])
        b_adm = None

    with h_info:
        st.markdown(
            f"<div class='shs-topbar'>"
            f"<div class='shs-brand'>📚 Assignment <span class='shs-accent'>Tracker</span></div>"
            f"<div class='shs-sub'>{now_dt.strftime('%a, %b %d')} <span class='shs-pill'>{esc(shs_badge)}</span> &nbsp;•&nbsp; {esc(email)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    if admin_user and b_adm is not None:
        if b_adm.button("🛠️ Admin", key="top_adm_btn", use_container_width=True, help="Creator Admin Panel"):
            st.session_state["_open_modal"] = "admin"
            rerun()

    if is_feature_visible("theme_studio", email):
        if b_thm.button("🎨", key="top_thm_btn", use_container_width=True, help="Theme & Appearance Studio"):
            st.session_state["_open_modal"] = "theme"
            rerun()

    if b_cls.button("📚", key="top_cls_btn", use_container_width=True, help="Manage Courses"):
        st.session_state["_open_modal"] = "courses"
        rerun()

    if b_pri.button("⚡", key="top_pri_btn", use_container_width=True, help="Priority Style"):
        st.session_state["_open_modal"] = "prio"
        rerun()

    if b_fb.button("💬", key="top_fb_btn", use_container_width=True, help="Feedback & Replies"):
        st.session_state["_open_modal"] = "feedback"
        rerun()

    if b_out.button("🚪", key="top_out_btn", use_container_width=True, help="Sign Out"):
        st.session_state.clear()
        rerun()

    # Modal Router
    prio_mode = st.session_state.cfg_prio or PRIO_MODES[0]
    pending_edit = st.session_state.get("_pending_edit_aid")
    open_modal = st.session_state.get("_open_modal")

    if pending_edit:
        show_edit_dialog(uid, pending_edit, prio_mode)
    elif open_modal == "add":
        show_add_dialog(uid, prio_mode)
    elif open_modal == "courses":
        show_courses_dialog(uid)
    elif open_modal == "prio":
        show_prio_dialog(uid)
    elif open_modal == "theme":
        show_theme_dialog(uid)
    elif open_modal == "feedback":
        show_feedback_dialog(uid, email)
    elif open_modal == "admin" and admin_user:
        show_admin_dialog()
    elif not st.session_state.cfg_courses and st.session_state.df_cached.empty:
        show_courses_dialog(uid)

    # Navigation Tabs
    nav_labels = ["📋 Assignments"]
    if is_feature_visible("classroom_sync_v2", email):
        nav_labels.append("🔄 Classroom Sync")
    if is_feature_visible("ai_study_planner", email):
        nav_labels.append("🧠 Study Planner")
    if is_feature_visible("shs_bell_schedule", email):
        nav_labels.append("🔔 SHS Bell Schedule")

    active_view = st.radio(
        "Navigation", nav_labels, horizontal=True, label_visibility="collapsed", key="main_view_selector"
    )

    if active_view == "📋 Assignments":
        render_assignments_tab(uid, email, prio_mode, light)
    elif active_view == "🔄 Classroom Sync":
        render_classroom_sync_tab(uid, email)
    elif active_view == "🧠 Study Planner":
        render_planner_tab(uid, light)
    elif active_view == "🔔 SHS Bell Schedule":
        run_with_fallback(
            "SHS Bell Schedule",
            lambda: render_bell_schedule_tab(uid, light),
            lambda: st.info("SHS Bell Schedule is temporarily running in simplified mode."),
        )


if __name__ == "__main__":
    main()
