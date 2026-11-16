"""Assignment Tracker: lightweight Streamlit + PostgreSQL application."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Assignment Tracker", page_icon="📑", layout="wide", initial_sidebar_state="collapsed")
ADMIN_EMAIL = "30guptaa@simsburyschools.net"
DOMAIN = "@simsburyschools.net"
STATUSES = ["Not Started", "In Progress", "Done"]
TYPES = ["Homework", "Essay", "Presentation", "Test & Quizzes", "Other"]
PRIORITIES = ["Low", "Medium", "High"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SYSTEM_TITLES = {"__SYSTEM_COURSES__", "__SYSTEM_SCHEDULE__", "__SYSTEM_PRIO_CONFIG__", "__SYSTEM_MAX_WORK_CONFIG__", "__SYSTEM_COMPLETED_SLOTS__", "__SYSTEM_SEEN_UPDATES__", "__SYSTEM_THEME_CONFIG__", "__SYSTEM_SHS_CONFIG__", "__SYSTEM_IGNORED_SYNC__"}

# Compatibility helpers: these return decorators and never decorate Streamlit directly.
def dialog_decorator(title: str):
    native = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)
    if native:
        return native(title)
    def decorate(fn):
        def wrapped(*args, **kwargs):
            st.subheader(title)
            return fn(*args, **kwargs)
        return wrapped
    return decorate

def fragment_decorator(run_every=None):
    native = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None)
    if native:
        return native(run_every=run_every) if run_every is not None else native()
    return lambda fn: fn

def rerun():
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn:
        try: fn()
        except Exception: pass

def now_local():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.utcnow() - timedelta(hours=4)

def db_url():
    sec = st.secrets
    url = (sec.get("postgres", {}).get("url") or sec.get("connections", {}).get("neon", {}).get("url") or sec.get("DATABASE_URL"))
    if not url: raise RuntimeError("PostgreSQL URL is missing from Streamlit secrets")
    return url.replace("postgres://", "postgresql+psycopg2://", 1).replace("postgresql://", "postgresql+psycopg2://", 1)

@st.cache_resource
def engine():
    return create_engine(db_url(), pool_pre_ping=True, pool_size=4, max_overflow=4)

@st.cache_resource
def write_lock():
    return threading.Lock()

def init_db():
    # Existing tables/columns remain unchanged; new capabilities use separate tables.
    ddl = [
        "CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS assignments (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT, course TEXT, due_date TEXT, status TEXT, priority INTEGER, atype TEXT, eta TEXT, notes TEXT, created_at TEXT)",
        "CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, email TEXT NOT NULL, category TEXT NOT NULL, rating INTEGER, message TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS feature_errors (id TEXT PRIMARY KEY, feature TEXT, message TEXT, created_at TEXT, resolved INTEGER DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS feature_flags (feature TEXT PRIMARY KEY, status TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS feature_catalog (feature TEXT PRIMARY KEY, description TEXT)",
        "CREATE TABLE IF NOT EXISTS feedback_replies (id TEXT PRIMARY KEY, feedback_id TEXT NOT NULL, sender_email TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL, is_read INTEGER DEFAULT 0)",
    ]
    with engine().begin() as conn:
        for statement in ddl: conn.execute(text(statement))

try:
    init_db()
except Exception as exc:
    st.error(f"Database connection error: {exc}")
    st.stop()

def bg_write(sql: str, params: dict[str, Any]):
    def run():
        try:
            with write_lock(), engine().begin() as conn: conn.execute(text(sql), params)
        except Exception as exc:
            print(f"Background database write failed: {exc}")
    threading.Thread(target=run, daemon=True).start()

def password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def cfg_id(uid: str, title: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"assignment-tracker:{uid}:{title}"))

def unpack_notes(raw: Any):
    try:
        obj = json.loads(raw or "")
        if isinstance(obj, dict): return str(obj.get("text", "")), str(obj.get("prev_status", "Not Started"))
    except Exception: pass
    return str(raw or ""), "Not Started"

def hydrate_user_session(uid: str, force: bool = False):
    if not force and st.session_state.get("_hydrated_uid") == uid: return
    with engine().connect() as conn:
        records = conn.execute(text("SELECT * FROM assignments WHERE user_id=:uid"), {"uid": uid}).mappings().all()
    configs: dict[str, Any] = {}
    tasks = []
    today = now_local().date().isoformat()
    for r in records:
        title = str(r.get("title") or "")
        if title in SYSTEM_TITLES:
            configs[title] = r.get("notes") or ""
            continue
        due = str(r.get("due_date") or "")
        if r.get("status") == "Done" and due and due < today:
            bg_write("DELETE FROM assignments WHERE user_id=:uid AND id=:id", {"uid": uid, "id": r["id"]})
            continue
        notes, prev = unpack_notes(r.get("notes"))
        tasks.append({"id": str(r["id"]), "user_id": uid, "title": title, "course": str(r.get("course") or "GENERAL").upper(), "due_date": due, "status": r.get("status") or "Not Started", "priority": int(r.get("priority") or 5), "atype": r.get("atype") or "Homework", "eta": r.get("eta") or "", "notes": notes, "prev_status": prev, "created_at": r.get("created_at") or ""})
    def parse_cfg(key, default):
        try: return json.loads(configs.get(key, ""))
        except Exception: return default
    st.session_state.df_cached = pd.DataFrame(tasks, columns=["id", "user_id", "title", "course", "due_date", "status", "priority", "atype", "eta", "notes", "prev_status", "created_at"])
    st.session_state.cfg_courses = parse_cfg("__SYSTEM_COURSES__", [])
    st.session_state.cfg_schedule = parse_cfg("__SYSTEM_SCHEDULE__", [])
    st.session_state.cfg_prio = configs.get("__SYSTEM_PRIO_CONFIG__", "")
    st.session_state.cfg_max_work = parse_cfg("__SYSTEM_MAX_WORK_CONFIG__", {d: 60 for d in DAYS})
    st.session_state.cfg_theme = parse_cfg("__SYSTEM_THEME_CONFIG__", {"mode": "Dark", "accent": "#6366f1", "opacity": 90})
    st.session_state.cfg_shs = parse_cfg("__SYSTEM_SHS_CONFIG__", {"lunches": {d: "L2" for d in "ABCDX"}, "periods": {}, "study_rooms": {}, "sheet_url": ""})
    st.session_state.cfg_ignored = parse_cfg("__SYSTEM_IGNORED_SYNC__", [])
    st.session_state._hydrated_uid = uid

def save_config(uid: str, title: str, value: Any):
    payload = value if isinstance(value, str) else json.dumps(value)
    st.session_state["cfg_" + {"__SYSTEM_COURSES__":"courses", "__SYSTEM_SCHEDULE__":"schedule", "__SYSTEM_PRIO_CONFIG__":"prio", "__SYSTEM_MAX_WORK_CONFIG__":"max_work", "__SYSTEM_THEME_CONFIG__":"theme", "__SYSTEM_SHS_CONFIG__":"shs", "__SYSTEM_IGNORED_SYNC__":"ignored"}.get(title, "other")] = value
    sql = "INSERT INTO assignments (id,user_id,title,course,due_date,status,priority,atype,eta,notes,created_at) VALUES (:id,:uid,:title,'CONFIG','','Not Started',0,'Other','',:notes,:created) ON CONFLICT (id) DO UPDATE SET notes=EXCLUDED.notes,user_id=EXCLUDED.user_id"
    bg_write(sql, {"id": cfg_id(uid, title), "uid": uid, "title": title, "notes": payload, "created": now_local().isoformat()})

def task_db_row(row):
    notes = json.dumps({"text": str(row.get("notes", "")), "prev_status": str(row.get("prev_status", "Not Started"))})
    return {"id": str(row["id"]), "user_id": str(row["user_id"]), "title": str(row.get("title") or "Untitled Assignment"), "course": str(row.get("course") or "GENERAL").upper(), "due_date": str(row.get("due_date") or ""), "status": str(row.get("status") or "Not Started"), "priority": int(row.get("priority") or 5), "atype": str(row.get("atype") or "Homework"), "eta": str(row.get("eta") or ""), "notes": notes, "created_at": str(row.get("created_at") or now_local().isoformat())}

def upsert_task(row: dict[str, Any]):
    row = dict(row)
    row.setdefault("id", str(uuid.uuid4()))
    df = st.session_state.df_cached.copy()
    clean = {**row, "user_id": row.get("user_id", st.session_state.user["id"]), "course": str(row.get("course") or "GENERAL").upper(), "priority": int(row.get("priority") or 5), "status": row.get("status") or "Not Started", "notes": row.get("notes") or "", "prev_status": row.get("prev_status") or "Not Started"}
    if not df.empty and (df.id == clean["id"]).any(): df.loc[df.id == clean["id"], list(clean)] = pd.DataFrame([clean])[list(clean)].values[0]
    else: df = pd.concat([df, pd.DataFrame([clean])], ignore_index=True)
    st.session_state.df_cached = df
    st.session_state.pop("_ai_plan_result", None)
    sql = "INSERT INTO assignments (id,user_id,title,course,due_date,status,priority,atype,eta,notes,created_at) VALUES (:id,:user_id,:title,:course,:due_date,:status,:priority,:atype,:eta,:notes,:created_at) ON CONFLICT (id) DO UPDATE SET user_id=EXCLUDED.user_id,title=EXCLUDED.title,course=EXCLUDED.course,due_date=EXCLUDED.due_date,status=EXCLUDED.status,priority=EXCLUDED.priority,atype=EXCLUDED.atype,eta=EXCLUDED.eta,notes=EXCLUDED.notes,created_at=EXCLUDED.created_at"
    bg_write(sql, task_db_row(clean))

def delete_task(aid: str):
    st.session_state.df_cached = st.session_state.df_cached[st.session_state.df_cached.id != aid].reset_index(drop=True)
    st.session_state.pop("_ai_plan_result", None)
    bg_write("DELETE FROM assignments WHERE id=:id AND user_id=:uid", {"id": aid, "uid": st.session_state.user["id"]})

def run_with_fallback(feature: str, fn: Callable, fallback: Callable):
    try: return fn()
    except Exception as exc:
        try: bg_write("INSERT INTO feature_errors (id,feature,message,created_at,resolved) VALUES (:id,:feature,:message,:created,0)", {"id": str(uuid.uuid4()), "feature": feature, "message": str(exc)[:2000], "created": now_local().isoformat()})
        except Exception: pass
        st.warning(f"{feature} is temporarily unavailable. Showing a basic view instead.")
        return fallback()

def escape(value: Any) -> str:
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")

def css():
    cfg = st.session_state.get("cfg_theme", {})
    bg = "#f1f5f9" if cfg.get("mode") == "Light" else "#0b1020"
    fg = "#111827" if cfg.get("mode") == "Light" else "#f8fafc"
    accent = cfg.get("accent", "#6366f1")
    st.markdown(f"<style>.stApp{{background:{bg};color:{fg}}}.stApp p,.stApp label,.stApp h1,.stApp h2,.stApp h3{{color:{fg}}}.stButton>button{{border:1px solid {accent};border-radius:8px}}[data-testid=stVerticalBlockBorderWrapper]{{background:rgba(100,116,139,.10);border:1px solid rgba(148,163,184,.35);border-radius:12px;padding:12px}}</style>", unsafe_allow_html=True)

def sign_in(email, password):
    with engine().connect() as conn:
        row = conn.execute(text("SELECT id,email,password_hash FROM users WHERE email=:email"), {"email": email.lower().strip()}).fetchone()
    if not row or row.password_hash != password_hash(password): return None
    return {"id": row.id, "email": row.email}

def auth_page():
    st.title("📑 Assignment Tracker")
    mode = st.radio("Account", ["Sign In", "Sign Up"], horizontal=True)
    email = st.text_input("School email or username")
    password = st.text_input("Password", type="password")
    if st.button("Continue", type="primary"):
        email = email.strip().lower()
        if "@" not in email: email += DOMAIN
        if not email or not password: st.error("Enter both email and password."); return
        if mode == "Sign Up":
            uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, email))
            try:
                with engine().begin() as conn: conn.execute(text("INSERT INTO users (id,email,password_hash,created_at) VALUES (:id,:email,:pw,:created)"), {"id":uid,"email":email,"pw":password_hash(password),"created":now_local().isoformat()})
                st.success("Account created. Sign in to continue.")
            except Exception: st.error("Unable to create account; that email may already be registered.")
        else:
            user = sign_in(email, password)
            if user: st.session_state.user = user; hydrate_user_session(user["id"], True); rerun()
            else: st.error("Invalid email or password.")

@dialog_decorator("Edit assignment")
def edit_dialog(uid: str, aid: str):
    matches = st.session_state.df_cached[st.session_state.df_cached.id == aid]
    if matches.empty: st.info("Assignment no longer exists."); return
    r = matches.iloc[0].to_dict()
    with st.form("edit_" + aid):
        title = st.text_input("Title", r["title"])
        course = st.text_input("Course", r["course"])
        due = st.date_input("Due date", value=date.fromisoformat(r["due_date"]) if r["due_date"] else now_local().date())
        status = st.selectbox("Status", STATUSES, index=STATUSES.index(r["status"]) if r["status"] in STATUSES else 0)
        priority = st.selectbox("Priority", PRIORITIES, index=max(0, min(2, (int(r["priority"])-1)//4)))
        atype = st.selectbox("Type", TYPES, index=TYPES.index(r["atype"]) if r["atype"] in TYPES else 0)
        eta = st.text_input("Estimated time", r["eta"])
        notes = st.text_area("Notes", r["notes"])
        save = st.form_submit_button("Save changes")
    if save:
        prev = status if status != "Done" else r["prev_status"]
        upsert_task({**r, "title": title, "course": course, "due_date": due.isoformat(), "status": status, "priority": {"Low":2,"Medium":5,"High":9}[priority], "atype": atype, "eta": eta, "notes": notes, "prev_status": prev})
        st.success("Saved.")


def parse_classroom(text_blob: str):
    lines = [x.strip() for x in text_blob.splitlines() if x.strip()]
    ignored = {"to-do", "to do", "assigned", "missing", "done", "all classes", "no due date", "this week", "next week"}
    lines = [x for x in lines if x.lower() not in ignored and not x.isdigit()]
    date_re = re.compile(r"^(due\s+|today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}/\d{1,2})", re.I)
    out=[]; i=0
    while i < len(lines)-1:
        if date_re.match(lines[i]): i+=1; continue
        due = lines[i+2] if i+2 < len(lines) and date_re.match(lines[i+2]) else ""
        out.append({"title":lines[i],"raw_course":lines[i+1],"raw_due":due}); i += 3 if due else 2
    return out

def parse_due(raw):
    s=(raw or "").strip(); today=now_local().date()
    if not s: return ""
    if re.search("today",s,re.I): return today.isoformat()
    if re.search("tomorrow",s,re.I): return (today+timedelta(days=1)).isoformat()
    for fmt in ("%b %d, %Y","%B %d, %Y","%m/%d/%Y","%Y-%m-%d","%b %d","%B %d"):
        try:
            d=datetime.strptime(re.sub(r"^due\s+","",s,flags=re.I),fmt).date()
            if "%Y" not in fmt: d=d.replace(year=today.year + (d.month < today.month))
            return d.isoformat()
        except ValueError: pass
    for i,name in enumerate(DAYS):
        if name.lower() in s.lower(): return (today+timedelta(days=(i-today.weekday())%7)).isoformat()
    return ""

def match_course(raw, courses):
    s=(raw or "").upper()
    if any(w in s for w in ["CLUB","SPORT","ROBOT","MUSIC","ACTIVITY"]): return "OTHER"
    for c in courses:
        if c and c != "OTHER" and (c.upper() in s or s in c.upper()): return c
    return (re.split(r"[-–—|•(]", s)[0].strip()[:30] or "GENERAL")

def study_plan(df, schedule, caps):
    today=now_local().date(); plan={}
    tasks=df[df.status != "Done"].copy()
    tasks["_due"]=tasks.due_date.map(lambda x: date.fromisoformat(x) if x else today+timedelta(days=7))
    tasks=tasks.sort_values(["_due","priority"], ascending=[True,False])
    remaining=[]
    for _,r in tasks.iterrows(): remaining.append(r.to_dict())
    for offset in range(7):
        day=today+timedelta(days=offset); name=DAYS[day.weekday()]; cap=int(caps.get(name,60)); mins=0; slots=[]
        busy=[]
        for ev in schedule:
            if ev.get("day") == name:
                try: busy.append((datetime.strptime(ev["start"],"%I:%M %p").time(), datetime.strptime(ev["end"],"%I:%M %p").time()))
                except Exception: pass
        for r in list(remaining):
            due=r.get("_due",today+timedelta(days=7)); lead=(due-day).days
            if lead < 0: continue
            is_study=any(k in (str(r.get("title"))+" "+str(r.get("atype"))).lower() for k in ("study","review","test","quiz","exam"))
            repeat=is_study and lead>=2 or any(k in str(r.get("eta","")).lower() for k in ("/day","daily","per day"))
            if offset > lead or (lead>=2 and not repeat and offset < lead-1): continue
            try: needed=max(20,min(60,int(re.search(r"\d+",str(r.get("eta") or "30")).group()) if re.search(r"\d+",str(r.get("eta") or "30")) else 30))
            except Exception: needed=30
            if mins+needed>cap: continue
            slots.append({"title":r["title"],"course":r["course"],"mins":needed,"key":f"{r['id']}_{day.isoformat()}"}); mins+=needed
            if not repeat: remaining.remove(r)
        plan[name]={"date":day.isoformat(),"slots":slots,"mins":mins,"busy":len(busy)}
    return plan

def bell_blocks(letter, schedule, classes, lunch, rooms):
    rotations={"A":[1,2,3,5,6,7],"B":[4,1,2,8,5,6],"C":[3,4,1,7,8,5],"D":[2,3,4,6,7,8]}
    rot=rotations.get(letter, list(range(1,9)) if letter=="X" else rotations["A"])
    if schedule in ("X Day","X Day 2 Hour Delay","X Day Early Dismissal"): rot=list(range(1,9))
    times={"Daily":[("7:32 AM","8:29 AM"),("8:33 AM","9:31 AM"),("9:35 AM","10:32 AM"),("10:36 AM","12:08 PM"),("12:12 PM","1:09 PM"),("1:13 PM","2:10 PM")],"Connect":[("7:32 AM","8:23 AM"),("8:27 AM","9:18 AM"),("9:22 AM","9:53 AM"),("9:57 AM","12:20 PM"),("12:24 PM","1:15 PM"),("1:19 PM","2:10 PM")],"2 Hour Delay":[("9:32 AM","10:06 AM"),("10:10 AM","10:44 AM"),("10:48 AM","11:24 AM"),("11:28 AM","12:54 PM"),("12:58 PM","1:32 PM"),("1:36 PM","2:10 PM")],"Early Dismissal":[("7:32 AM","8:05 AM"),("8:09 AM","8:42 AM"),("8:46 AM","9:24 AM"),("9:28 AM","10:01 AM"),("10:05 AM","10:38 AM"),("10:42 AM","11:15 AM")],"Emergency Early Dismissal":[("7:32 AM","8:25 AM"),("8:29 AM","8:57 AM"),("9:01 AM","9:29 AM"),("9:33 AM","10:01 AM"),("10:05 AM","10:33 AM"),("10:37 AM","11:05 AM")],"X Day":[("7:32 AM","8:12 AM"),("8:16 AM","8:56 AM"),("9:00 AM","9:42 AM"),("9:46 AM","10:26 AM"),("10:30 AM","11:10 AM"),("11:14 AM","12:42 PM"),("12:46 PM","1:26 PM"),("1:30 PM","2:10 PM")],"X Day 2 Hour Delay":[("9:32 AM","9:55 AM"),("9:59 AM","10:22 AM"),("10:26 AM","10:50 AM"),("10:54 AM","11:17 AM"),("11:21 AM","11:44 AM"),("11:48 AM","1:16 PM"),("1:20 PM","1:43 PM"),("1:47 PM","2:10 PM")],"X Day Early Dismissal":[("7:32 AM","7:56 AM"),("8:00 AM","8:24 AM"),("8:28 AM","8:55 AM"),("8:59 AM","9:23 AM"),("9:27 AM","9:51 AM"),("9:55 AM","10:19 AM"),("10:23 AM","10:47 AM"),("10:51 AM","11:15 AM")]}
    chosen=times.get(schedule,times["Daily"]); rows=[]
    for i,(start,end) in enumerate(chosen):
        p=rot[min(i,len(rot)-1)] if len(rot)==6 else i+1
        label=f"Period {p}"; room=str(rooms.get(letter,"")); course=classes.get(str(p),"Unassigned")
        rows.append({"label":label,"course":course,"start":start,"end":end,"room":f"Rm {room}" if room and course.lower()=="study hall" else ""})
    return rows

def safe_text_time(raw):
    for fmt in ("%I:%M %p","%I:%M%p","%H:%M"):
        try: return datetime.strptime(raw.strip().upper(),fmt).time()
        except Exception: pass
    return None

@fragment_decorator(run_every="60s")
def render_bell(uid):
    cfg=st.session_state.cfg_shs
    day=st.date_input("Date",value=now_local().date(),key="bell_date")
    letter=st.selectbox("Letter day",["Auto","A","B","C","D","X"],key="bell_letter")
    schedule=st.selectbox("Schedule",["Auto","Daily","Connect","2 Hour Delay","Early Dismissal","Emergency Early Dismissal","X Day","X Day 2 Hour Delay","X Day Early Dismissal"],key="bell_sched")
    inferred="X" if letter=="Auto" and day.weekday()==4 else ("ABCD"[(day.toordinal()//1)%4] if letter=="Auto" else letter)
    active_sched=("X Day" if inferred=="X" else ("Connect" if day.weekday()==2 else "Daily")) if schedule=="Auto" else schedule
    with st.expander("Personalize classes, lunch, rooms and calendar override"):
        periods=cfg.setdefault("periods",{})
        for p in range(1,9): periods[str(p)]=st.text_input(f"Period {p}",value=periods.get(str(p),""),key=f"bell_p{p}")
        lunches=cfg.setdefault("lunches",{d:"L2" for d in "ABCDX"})
        cols=st.columns(5)
        for i,d in enumerate("ABCDX"):
            with cols[i]: lunches[d]=st.selectbox(f"{d} lunch",["L1","L2","L3"],index=["L1","L2","L3"].index(lunches.get(d,"L2")),key=f"lunch_{d}")
        url=st.text_input("Optional public Google Sheet CSV URL",value=cfg.get("sheet_url",""))
        cfg["sheet_url"]=url
        if st.button("Save bell settings"): save_config(uid,"__SYSTEM_SHS_CONFIG__",cfg)
    rows=bell_blocks(inferred,active_sched,cfg.get("periods",{}),cfg.get("lunches",{}).get(inferred,"L2"),cfg.get("study_rooms",{}))
    st.subheader(f"{inferred} Day — {active_sched} · Lunch {cfg.get('lunches',{}).get(inferred,'L2')}")
    current=now_local().time() if day==now_local().date() else None
    for r in rows:
        st.markdown(f"**{r['label']} · {escape(r['course'])}**  — {r['start']}–{r['end']} {('· '+escape(r['room'])) if r['room'] else ''}" + ("  🟢 LIVE" if current and safe_text_time(r['start']) <= current < safe_text_time(r['end']) else ""))

def render_admin():
    st.header("🛠️ Feature Control Center & Feedback Inbox")
    with engine().connect() as conn:
        errors=conn.execute(text("SELECT id,feature,message,created_at FROM feature_errors WHERE resolved=0 ORDER BY created_at DESC LIMIT 50")).mappings().all()
        feedback=conn.execute(text("SELECT id,email,category,message,created_at FROM feedback ORDER BY created_at DESC LIMIT 50")).mappings().all()
        flags=conn.execute(text("SELECT feature,status FROM feature_flags ORDER BY feature")).mappings().all()
    st.subheader("Feature flags")
    known={r["feature"]:r["status"] for r in flags}
    feature=st.text_input("Feature name",key="admin_feature")
    status=st.selectbox("Release state",["Public Released","Beta Testing","Removed/Hidden"])
    if st.button("Save feature flag") and feature.strip():
        bg_write("INSERT INTO feature_flags(feature,status) VALUES(:f,:s) ON CONFLICT(feature) DO UPDATE SET status=EXCLUDED.status",{"f":feature.strip(),"s":status})
    for k,v in known.items(): st.write(f"**{k}** — {v}")
    st.subheader("Unresolved feature errors")
    for e in errors:
        st.error(f"{e['feature']}: {e['message']}")
        if st.button("Dismiss",key="dismiss_"+e["id"]): bg_write("UPDATE feature_errors SET resolved=1 WHERE id=:id",{"id":e["id"]}); rerun()
    st.subheader("Feedback")
    for f in feedback:
        st.markdown(f"**{escape(f['email'])} · {escape(f['category'])}** — {escape(f['message'])}")
        reply=st.text_input("Reply",key="reply_"+f["id"])
        if st.button("Send reply",key="send_"+f["id"]) and reply.strip():
            bg_write("INSERT INTO feedback_replies(id,feedback_id,sender_email,message,created_at,is_read) VALUES(:id,:fid,:email,:message,:created,0)",{"id":str(uuid.uuid4()),"fid":f["id"],"email":ADMIN_EMAIL,"message":reply.strip(),"created":now_local().isoformat()})
            st.success("Reply queued")


def main():
    user=st.session_state.get("user")
    if not user: auth_page(); return
    uid=str(user["id"]); email=str(user["email"])
    hydrate_user_session(uid); css()
    st.title("📑 Assignment Tracker")
    left,right=st.columns([3,1])
    with left: st.caption(email)
    with right:
        if email.lower()==ADMIN_EMAIL and st.button("🛠️ Admin"): st.session_state.admin_open=not st.session_state.get("admin_open",False)
        if st.button("Sign out"): st.session_state.clear(); rerun()
    if email.lower()==ADMIN_EMAIL and st.session_state.get("admin_open"): render_admin(); st.divider()
    with st.expander("Appearance & settings"):
        mode=st.radio("Contrast",["Dark","Light"],index=0 if st.session_state.cfg_theme.get("mode")!="Light" else 1,horizontal=True)
        accent=st.color_picker("Accent",st.session_state.cfg_theme.get("accent","#6366f1"))
        opacity=st.slider("Card opacity",55,98,int(st.session_state.cfg_theme.get("opacity",90)))
        if st.button("Save appearance"):
            save_config(uid,"__SYSTEM_THEME_CONFIG__",{"mode":mode,"accent":accent,"opacity":opacity}); rerun()
    if not st.session_state.cfg_courses:
        course_text=st.text_input("Set up courses (comma separated)","MATH, SCIENCE, ENGLISH, HISTORY, OTHER")
        if st.button("Save courses"): save_config(uid,"__SYSTEM_COURSES__",[x.strip().upper() for x in course_text.split(",") if x.strip()]); rerun()
    with st.expander("＋ Add assignment"):
        with st.form("new_task"):
            title=st.text_input("Title"); course=st.selectbox("Course",st.session_state.cfg_courses+(["OTHER"] if "OTHER" not in st.session_state.cfg_courses else []))
            due=st.date_input("Due date",now_local().date()); status=st.selectbox("Status",STATUSES); priority=st.select_slider("Priority",PRIORITIES,value="Medium"); atype=st.selectbox("Type",TYPES); eta=st.text_input("Estimated time", "30 min"); notes=st.text_area("Notes")
            submit=st.form_submit_button("Add task")
        if submit:
            upsert_task({"id":str(uuid.uuid4()),"user_id":uid,"title":title,"course":course,"due_date":due.isoformat(),"status":status,"priority":{"Low":2,"Medium":5,"High":9}[priority],"atype":atype,"eta":eta,"notes":notes,"prev_status":status if status!="Done" else "Not Started"}); st.success("Added")
    tabs=st.tabs(["Assignments","Classroom Sync","Study Planner","SHS Bell Schedule","Feedback"])
    with tabs[0]:
        df=st.session_state.df_cached.copy()
        search=st.text_input("Search title, course or notes")
        courses=["All courses"]+sorted(set(df.course.tolist())) if not df.empty else ["All courses"]
        c1,c2,c3=st.columns(3)
        course_filter=c1.selectbox("Course",courses)
        status_filter=c2.selectbox("Status",["Active Only","All Tasks"]+STATUSES)
        sort=c3.selectbox("Sort",["Due Date","Priority","Course"])
        if search: df=df[df.apply(lambda r: search.lower() in (str(r.title)+" "+str(r.course)+" "+str(r.notes)).lower(),axis=1)]
        if course_filter!="All courses": df=df[df.course==course_filter]
        if status_filter=="Active Only": df=df[df.status!="Done"]
        elif status_filter in STATUSES: df=df[df.status==status_filter]
        if sort=="Priority": df=df.sort_values("priority",ascending=False)
        elif sort=="Course": df=df.sort_values("course")
        else: df=df.sort_values("due_date",na_position="last")
        for _,r in df.iterrows():
            with st.container(border=True):
                st.markdown(f"### {escape(r.title)} · {escape(r.course)}")
                st.caption(f"{r.atype} · Due {r.due_date or 'unscheduled'} · Priority {r.priority} · {r.eta}")
                if r.notes: st.write(r.notes)
                b1,b2,b3,b4,b5=st.columns(5)
                if b1.button("Undo" if r.status=="Done" else "Done",key="done_"+r.id):
                    new="In Progress" if r.status=="Done" else "Done"
                    upsert_task({**r.to_dict(),"status":new,"prev_status":r.status if new=="Done" else r.prev_status}); rerun()
                if b2.button("Pause" if r.status=="In Progress" else "Start",key="start_"+r.id):
                    upsert_task({**r.to_dict(),"status":"Not Started" if r.status=="In Progress" else "In Progress"}); rerun()
                if b3.button("Edit",key="edit_"+r.id): edit_dialog(uid,r.id)
                if b4.button("Delete",key="delete_"+r.id): delete_task(r.id); rerun()
                if b5.button("Ignore sync",key="ignore_"+r.id):
                    ignored=list(st.session_state.cfg_ignored); ignored.append(str(r.title).lower()); save_config(uid,"__SYSTEM_IGNORED_SYNC__",sorted(set(ignored))); st.info("Added to sync ignore list")
    with tabs[1]:
        st.markdown("For school-managed Chromebooks, open Classroom To-do, press **Ctrl+A**, **Ctrl+C**, then paste here.")
        with st.expander("Chromebook Ctrl+A Paste Sync",expanded=True):
            pasted=st.text_area("Pasted Classroom text",height=160)
            if st.button("Parse pasted tasks"):
                st.session_state.sync_preview=parse_classroom(pasted)
            for i,item in enumerate(st.session_state.get("sync_preview",[])):
                item["checked"]=st.checkbox(f"{item['title']} · {match_course(item['raw_course'],st.session_state.cfg_courses)} · {parse_due(item['raw_due']) or 'No due date'}",True,key=f"sync_{i}")
            if st.button("Import checked tasks"):
                current=st.session_state.df_cached
                for item in st.session_state.get("sync_preview",[]):
                    title=item["title"].strip(); course=match_course(item["raw_course"],st.session_state.cfg_courses)
                    ignored=st.session_state.cfg_ignored
                    if not title or title.lower() in ignored or (not current.empty and ((current.title.str.lower()==title.lower()).any())): continue
                    low=title.lower(); typ="Test & Quizzes" if any(w in low for w in ["test","quiz","exam"]) else "Essay" if "essay" in low else "Presentation" if "presentation" in low else "Homework"
                    upsert_task({"id":str(uuid.uuid4()),"user_id":uid,"title":title,"course":course,"due_date":parse_due(item["raw_due"]),"status":"Not Started","priority":5,"atype":typ,"eta":"30 min","notes":"Synced from Google Classroom","prev_status":"Not Started"})
                st.session_state.pop("sync_preview",None); st.success("Sync complete")
        with st.expander("Bookmarklet for personal devices"):
            st.code("javascript:(function(){alert('Use Chromebook Ctrl+A Paste Sync when bookmarklets are blocked.');})()",language="text")
    with tabs[2]:
        st.subheader("Multi-session study planner")
        caps=st.session_state.cfg_max_work
        with st.expander("Daily homework caps"):
            cc=st.columns(7)
            for i,d in enumerate(DAYS):
                with cc[i]: caps[d]=st.number_input(d[:3],0,300,int(caps.get(d,60)),step=15,key="cap_"+d)
            if st.button("Save caps"): save_config(uid,"__SYSTEM_MAX_WORK_CONFIG__",caps)
        schedule=st.session_state.cfg_schedule
        with st.expander("Weekly recurring commitments"):
            day=st.selectbox("Day",DAYS); event=st.text_input("Commitment"); start=st.text_input("Start (3:30 PM)"); end=st.text_input("End (5:00 PM)")
            if st.button("Add commitment") and event and safe_text_time(start) and safe_text_time(end):
                schedule.append({"id":str(uuid.uuid4()),"day":day,"title":event,"start":start,"end":end}); save_config(uid,"__SYSTEM_SCHEDULE__",schedule); rerun()
            for ev in schedule: st.write(f"{ev.get('day')}: {ev.get('title')} {ev.get('start')}–{ev.get('end')}")
        plan=run_with_fallback("AI Study Planner",lambda:study_plan(st.session_state.df_cached,schedule,caps),lambda:{})
        for day_name,info in plan.items():
            st.markdown(f"**{day_name} · {info['mins']} min / cap {caps.get(day_name,60)} min**")
            for slot in info["slots"]: st.write(f"☐ {slot['title']} — {slot['course']} ({slot['mins']} min)")
    with tabs[3]:
        run_with_fallback("SHS Bell Schedule",lambda:render_bell(uid),lambda:st.info("Schedule view unavailable; check the date and try again."))
    with tabs[4]:
        with st.form("feedback_form"):
            category=st.selectbox("Category",["Feature Request","Bug Report","SHS Bell Schedule Issue","General Feedback"]); rating=st.slider("Rating",1,5,5); msg=st.text_area("Message")
            if st.form_submit_button("Send feedback") and msg.strip():
                bg_write("INSERT INTO feedback(id,user_id,email,category,rating,message,created_at) VALUES(:id,:uid,:email,:category,:rating,:message,:created)",{"id":str(uuid.uuid4()),"uid":uid,"email":email,"category":category,"rating":rating,"message":msg.strip(),"created":now_local().isoformat()}); st.success("Feedback sent")
        with engine().connect() as conn: replies=conn.execute(text("SELECT message,created_at FROM feedback_replies WHERE sender_email=:admin AND feedback_id IN (SELECT id FROM feedback WHERE user_id=:uid) ORDER BY created_at DESC"),{"admin":ADMIN_EMAIL,"uid":uid}).mappings().all()
        if replies:
            st.subheader("Replies")
            for reply in replies: st.info(reply["message"])

if __name__ == "__main__":
    main()
