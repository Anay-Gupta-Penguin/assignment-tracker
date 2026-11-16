"""Assignment Tracker — Streamlit and PostgreSQL app."""
from __future__ import annotations
import base64, csv, hashlib, io, json, re, threading, uuid
from datetime import date, datetime, timedelta
from typing import Any, Callable
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
LETTERS = "ABCDX"
SYSTEM_TITLES = {"__SYSTEM_COURSES__", "__SYSTEM_SCHEDULE__", "__SYSTEM_PRIO_CONFIG__", "__SYSTEM_MAX_WORK_CONFIG__", "__SYSTEM_COMPLETED_SLOTS__", "__SYSTEM_SEEN_UPDATES__", "__SYSTEM_THEME_CONFIG__", "__SYSTEM_SHS_CONFIG__", "__SYSTEM_IGNORED_SYNC__"}
CONFIG_PREFIX = {"__SYSTEM_COURSES__":"user_courses_config", "__SYSTEM_SCHEDULE__":"user_schedule_config", "__SYSTEM_PRIO_CONFIG__":"user_prio_config", "__SYSTEM_MAX_WORK_CONFIG__":"user_max_work_config", "__SYSTEM_COMPLETED_SLOTS__":"user_completed_slots_config", "__SYSTEM_SEEN_UPDATES__":"user_seen_updates_config", "__SYSTEM_THEME_CONFIG__":"user_theme_config", "__SYSTEM_SHS_CONFIG__":"user_shs_config", "__SYSTEM_IGNORED_SYNC__":"user_ignored_sync_config"}

# Always call these wrappers rather than decorating Streamlit functions directly.
def dialog_decorator(title: str):
    native = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)
    if native:
        try: return native(title)
        except TypeError: pass
    def decorate(fn):
        def wrapper(*args, **kwargs):
            st.subheader(title)
            return fn(*args, **kwargs)
        return wrapper
    return decorate

def fragment_decorator(run_every=None):
    native = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None)
    if native:
        try: return native(run_every=run_every) if run_every is not None else native()
        except TypeError:
            try: return native()
            except Exception: pass
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
    except Exception: return datetime.utcnow() - timedelta(hours=4)

def _db_url():
    sec = st.secrets
    url = sec.get("postgres", {}).get("url") or sec.get("connections", {}).get("neon", {}).get("url") or sec.get("DATABASE_URL")
    if not url: raise RuntimeError("PostgreSQL URL missing from Streamlit secrets")
    if url.startswith("postgres://"): url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"): url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url

@st.cache_resource
def db_engine(): return create_engine(_db_url(), pool_pre_ping=True, pool_size=4, max_overflow=4)
@st.cache_resource
def db_lock(): return threading.Lock()

def init_db():
    # Keep the existing users, assignments, and feedback schemas and all their data intact.
    ddl = [
        "CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS assignments (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT, course TEXT, due_date TEXT, status TEXT, priority INTEGER, atype TEXT, eta TEXT, notes TEXT, created_at TEXT)",
        "CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, email TEXT NOT NULL, category TEXT NOT NULL, rating INTEGER, message TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS feature_errors (id TEXT PRIMARY KEY, feature TEXT, message TEXT, created_at TEXT, resolved INTEGER DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS feature_flags (feature TEXT PRIMARY KEY, status TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS feature_catalog (feature TEXT PRIMARY KEY, description TEXT)",
        "CREATE TABLE IF NOT EXISTS feedback_replies (id TEXT PRIMARY KEY, feedback_id TEXT NOT NULL, sender_email TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL, is_read INTEGER DEFAULT 0)",
    ]
    with db_engine().begin() as conn:
        for q in ddl: conn.execute(text(q))
try: init_db()
except Exception as exc: st.error(f"Database connection error: {exc}"); st.stop()

def bg_sql(sql: str, params: dict[str, Any]):
    def worker():
        try:
            with db_lock(), db_engine().begin() as conn: conn.execute(text(sql), params)
        except Exception as exc: print(f"Background database write failed: {exc}")
    threading.Thread(target=worker, daemon=True).start()

def _cfg_id(uid: str, title: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{CONFIG_PREFIX.get(title, 'user_config')}_{uid}"))

def _hash_pw(pw: str) -> str: return hashlib.sha256(pw.encode("utf-8")).hexdigest()
def _unpack_notes(raw):
    try:
        d=json.loads(raw or "")
        if isinstance(d,dict): return str(d.get("text","")),str(d.get("prev_status","Not Started"))
    except Exception: pass
    return str(raw or ""),"Not Started"
def _unpack_config(raw, default):
    try: return json.loads(raw) if raw not in (None, "") else default
    except Exception: return default

def hydrate_user_session(user_id: str, force: bool = False):
    if not force and st.session_state.get("_hydrated_uid") == user_id: return
    with db_engine().connect() as conn:
        rows=conn.execute(text("SELECT * FROM assignments WHERE user_id=:uid"),{"uid":user_id}).mappings().all()
    today=now_local().date().isoformat(); cfg={}; tasks=[]; expired=[]
    for r in rows:
        title=str(r.get("title") or "")
        if title in SYSTEM_TITLES: cfg[title]=r.get("notes") or ""; continue
        due=str(r.get("due_date") or "")
        if r.get("status")=="Done" and due and due<today: expired.append(str(r["id"])); continue
        notes,prev=_unpack_notes(r.get("notes"))
        tasks.append({"id":str(r["id"]),"user_id":user_id,"title":title,"course":str(r.get("course") or "GENERAL").upper(),"due_date":due,"status":r.get("status") or "Not Started","priority":int(r.get("priority") or 5),"atype":r.get("atype") or "Homework","eta":r.get("eta") or "","notes":notes,"prev_status":prev,"created_at":r.get("created_at") or ""})
    if expired: bg_sql("DELETE FROM assignments WHERE user_id=:uid AND id=ANY(:ids)",{"uid":user_id,"ids":expired})
    st.session_state.df_cached=pd.DataFrame(tasks,columns=["id","user_id","title","course","due_date","status","priority","atype","eta","notes","prev_status","created_at"])
    st.session_state.cfg_courses=_unpack_config(cfg.get("__SYSTEM_COURSES__"),[])
    st.session_state.cfg_schedule=_unpack_config(cfg.get("__SYSTEM_SCHEDULE__"),[])
    st.session_state.cfg_prio=cfg.get("__SYSTEM_PRIO_CONFIG__","")
    st.session_state.cfg_max_work=_unpack_config(cfg.get("__SYSTEM_MAX_WORK_CONFIG__"),{d:60 for d in DAYS})
    st.session_state.cfg_completed=_unpack_config(cfg.get("__SYSTEM_COMPLETED_SLOTS__"),{})
    st.session_state.cfg_seen=cfg.get("__SYSTEM_SEEN_UPDATES__","")
    st.session_state.cfg_theme=_unpack_config(cfg.get("__SYSTEM_THEME_CONFIG__"),{"mode":"Dark","accent":"#6366f1","opacity":90,"bg_type":"solid","background":"#0b1020"})
    st.session_state.cfg_shs=_unpack_config(cfg.get("__SYSTEM_SHS_CONFIG__"),{"lunches":{d:"L2" for d in LETTERS},"periods":{},"study_rooms":{},"sheet_url":""})
    st.session_state.cfg_ignored=_unpack_config(cfg.get("__SYSTEM_IGNORED_SYNC__"),[])
    st.session_state._hydrated_uid=user_id

def save_config(uid: str, title: str, value: Any):
    names={"__SYSTEM_COURSES__":"cfg_courses","__SYSTEM_SCHEDULE__":"cfg_schedule","__SYSTEM_PRIO_CONFIG__":"cfg_prio","__SYSTEM_MAX_WORK_CONFIG__":"cfg_max_work","__SYSTEM_COMPLETED_SLOTS__":"cfg_completed","__SYSTEM_SEEN_UPDATES__":"cfg_seen","__SYSTEM_THEME_CONFIG__":"cfg_theme","__SYSTEM_SHS_CONFIG__":"cfg_shs","__SYSTEM_IGNORED_SYNC__":"cfg_ignored"}
    st.session_state[names[title]]=value
    if title in ("__SYSTEM_SCHEDULE__","__SYSTEM_MAX_WORK_CONFIG__"): st.session_state.pop("_ai_plan_result",None)
    payload=value if isinstance(value,str) else json.dumps(value)
    q="INSERT INTO assignments (id,user_id,title,course,due_date,status,priority,atype,eta,notes,created_at) VALUES (:id,:uid,:title,'CONFIG','','Not Started',0,'Other','',:notes,:created) ON CONFLICT (id) DO UPDATE SET notes=EXCLUDED.notes,user_id=EXCLUDED.user_id"
    bg_sql(q,{"id":_cfg_id(uid,title),"uid":uid,"title":title,"notes":payload,"created":now_local().isoformat()})

def _db_task(row):
    return {"id":str(row["id"]),"user_id":str(row["user_id"]),"title":str(row.get("title") or "Untitled Assignment"),"course":str(row.get("course") or "GENERAL").upper(),"due_date":str(row.get("due_date") or ""),"status":str(row.get("status") or "Not Started"),"priority":int(row.get("priority") or 5),"atype":str(row.get("atype") or "Homework"),"eta":str(row.get("eta") or ""),"notes":json.dumps({"text":str(row.get("notes") or ""),"prev_status":str(row.get("prev_status") or "Not Started")}),"created_at":str(row.get("created_at") or now_local().isoformat())}
def upsert_task(row: dict[str, Any]):
    row=dict(row); row.setdefault("id",str(uuid.uuid4())); row.setdefault("user_id",st.session_state.user["id"])
    row.setdefault("created_at",now_local().isoformat()); row.setdefault("status","Not Started"); row.setdefault("priority",5); row.setdefault("atype","Homework"); row.setdefault("eta",""); row.setdefault("notes",""); row.setdefault("prev_status","Not Started")
    row["course"]=str(row.get("course") or "GENERAL").upper(); row["title"]=str(row.get("title") or "Untitled Assignment")
    df=st.session_state.df_cached.copy(); new=pd.DataFrame([{k:row.get(k) for k in df.columns}])
    if not df.empty and (df.id==row["id"]).any():
        idx=df.index[df.id==row["id"]][0]
        for k in df.columns: df.at[idx,k]=new.iloc[0][k]
    else: df=pd.concat([df,new],ignore_index=True)
    st.session_state.df_cached=df; st.session_state.pop("_ai_plan_result",None)
    q="INSERT INTO assignments (id,user_id,title,course,due_date,status,priority,atype,eta,notes,created_at) VALUES (:id,:user_id,:title,:course,:due_date,:status,:priority,:atype,:eta,:notes,:created_at) ON CONFLICT(id) DO UPDATE SET user_id=EXCLUDED.user_id,title=EXCLUDED.title,course=EXCLUDED.course,due_date=EXCLUDED.due_date,status=EXCLUDED.status,priority=EXCLUDED.priority,atype=EXCLUDED.atype,eta=EXCLUDED.eta,notes=EXCLUDED.notes,created_at=EXCLUDED.created_at"
    bg_sql(q,_db_task(row))
def delete_task(aid):
    st.session_state.df_cached=st.session_state.df_cached[st.session_state.df_cached.id!=aid].reset_index(drop=True); st.session_state.pop("_ai_plan_result",None)
    bg_sql("DELETE FROM assignments WHERE id=:id AND user_id=:uid",{"id":aid,"uid":st.session_state.user["id"]})

def run_with_fallback(feature: str, fn: Callable, fallback: Callable):
    try: return fn()
    except Exception as exc:
        try: bg_sql("INSERT INTO feature_errors(id,feature,message,created_at,resolved) VALUES(:id,:feature,:message,:created,0)",{"id":str(uuid.uuid4()),"feature":feature,"message":str(exc)[:2000],"created":now_local().isoformat()})
        except Exception: pass
        st.warning(f"{feature} is unavailable right now. A safe backup view is shown.")
        return fallback()
def esc(x): return str(x or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")
def theme_css():
    cfg=st.session_state.cfg_theme; light=cfg.get("mode")=="Light"; bg=cfg.get("background","#f1f5f9" if light else "#0b1020"); fg="#111827" if light else "#f8fafc"; accent=cfg.get("accent","#6366f1")
    st.markdown(f"<style>.stApp{{background:{bg};color:{fg}}}.stApp p,.stApp label,.stApp h1,.stApp h2,.stApp h3{{color:{fg}}}.stButton>button{{border:1px solid {accent};border-radius:8px}}[data-testid=stVerticalBlockBorderWrapper]{{background:rgba(100,116,139,.10);border:1px solid rgba(148,163,184,.35);border-radius:12px;padding:12px}}</style>",unsafe_allow_html=True)

def parse_date(raw):
    s=str(raw or "").strip(); today=now_local().date()
    if not s: return ""
    if "today" in s.lower(): return today.isoformat()
    if "tomorrow" in s.lower(): return (today+timedelta(days=1)).isoformat()
    for i,d in enumerate(DAYS):
        if re.search(rf"\b{d}\b",s,re.I): return (today+timedelta(days=(i-today.weekday())%7)).isoformat()
    s=re.sub(r"^due\s+","",s,flags=re.I)
    for fmt in ("%b %d, %Y","%B %d, %Y","%m/%d/%Y","%m/%d/%y","%Y-%m-%d","%b %d","%B %d","%m/%d"):
        try:
            d=datetime.strptime(s,fmt).date()
            if "%Y" not in fmt: d=d.replace(year=today.year+(d.month<today.month))
            return d.isoformat()
        except ValueError: pass
    return ""
def parse_classroom(blob):
    skip={"to-do","to do","assigned","missing","done","all classes","no due date","this week","next week","later","earlier","assignment","description"}
    date_re=re.compile(r"^(due\s+|today|tomorrow|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}/\d{1,2})",re.I)
    lines=[x.strip() for x in str(blob).splitlines() if x.strip() and x.strip().lower() not in skip and not x.strip().isdigit()]
    out=[]; i=0
    while i<len(lines)-1:
        if date_re.match(lines[i]): i+=1; continue
        due=lines[i+2] if i+2<len(lines) and date_re.match(lines[i+2]) else ""
        out.append({"title":lines[i],"raw_course":lines[i+1],"raw_due":due}); i+=3 if due else 2
    return out
def map_course(raw,courses):
    s=str(raw or "").upper()
    if any(w in s for w in ("CLUB","SPORT","ROBOT","MUSIC","ACTIVITY","TEAM")): return "OTHER"
    for course in courses:
        c=str(course).upper()
        if c!="OTHER" and c and (c in s or s in c): return c
    return re.split(r"[-–—|•(]",s)[0].strip()[:28] or "GENERAL"
def guess_type(title):
    s=title.lower()
    if any(x in s for x in ("test","quiz","exam","midterm","final")): return "Test & Quizzes"
    if "essay" in s or "paper" in s: return "Essay"
    if any(x in s for x in ("presentation","slides","poster","speech")): return "Presentation"
    return "Homework"
def duplicate(title,course,due,df):
    if df.empty: return False
    exact=df.title.fillna("").str.strip().str.lower()==title.strip().lower()
    if exact.any(): return True
    same=(df.course.fillna("").str.upper()==course.upper()) & ((df.due_date.fillna("")==due)|(df.due_date.fillna("")=="")|(due==""))
    words=set(re.findall(r"[a-z0-9]{4,}",title.lower()))
    return any(len(words & set(re.findall(r"[a-z0-9]{4,}",str(t).lower())))>=2 for t in df.loc[same,"title"])

def parse_time(s):
    for fmt in ("%I:%M %p","%I:%M%p","%H:%M"):
        try: return datetime.strptime(str(s).strip().upper(),fmt).time()
        except Exception: pass
    return None

def study_plan(df,schedule,caps):
    today=now_local().date(); incomplete=df[df.status!="Done"].copy(); tasks=[]
    for _,r in incomplete.iterrows():
        try: due=date.fromisoformat(str(r.due_date)) if r.due_date else today+timedelta(days=7)
        except Exception: due=today+timedelta(days=7)
        txt=(str(r.title)+" "+str(r.atype)+" "+str(r.notes)).lower(); eta=str(r.eta).lower()
        recurring=any(k in (eta+" "+txt) for k in ("/day","per day","daily","every day","each day"))
        study=any(k in txt for k in ("study","review","test","quiz","exam","prep"))
        mins=int(re.search(r"\d+",eta).group()) if re.search(r"\d+",eta) else 30
        tasks.append({"id":r.id,"title":r.title,"course":r.course,"due":due,"priority":int(r.priority or 5),"mins":max(20,min(60,mins)),"repeat":recurring or (study and (due-today).days>=2)})
    tasks.sort(key=lambda t:(t["due"],-t["priority"]))
    result={}
    for offset in range(7):
        d=today+timedelta(days=offset); name=DAYS[d.weekday()]; cap=max(0,int(caps.get(name,60))); busy=[]; slots=[]; total=0
        for ev in schedule:
            if ev.get("day")==name:
                a,b=parse_time(ev.get("start")),parse_time(ev.get("end"))
                if a and b: busy.append((a,b))
        cursor=datetime.combine(d,datetime.strptime("3:30 PM","%I:%M %p").time())
        endday=datetime.combine(d,datetime.strptime("9:00 PM","%I:%M %p").time())
        if d.weekday()>=5: cursor=datetime.combine(d,datetime.strptime("10:00 AM","%I:%M %p").time()); endday=datetime.combine(d,datetime.strptime("8:00 PM","%I:%M %p").time())
        if offset==0 and now_local().replace(tzinfo=None)>cursor: cursor=now_local().replace(tzinfo=None)
        for t in tasks:
            lead=(t["due"]-d).days
            if lead<0 or (not t["repeat"] and lead>1): continue
            needed=t["mins"]
            if total+needed>cap: continue
            # Find an available interval around weekly commitments.
            start=cursor
            while True:
                stop=start+timedelta(minutes=needed)
                conflict=next(((datetime.combine(d,a),datetime.combine(d,b)) for a,b in busy if start<datetime.combine(d,b) and stop>datetime.combine(d,a)),None)
                if not conflict: break
                start=conflict[1]
            if start+timedelta(minutes=needed)>endday: continue
            slots.append({"title":t["title"],"course":t["course"],"mins":needed,"time":start.strftime("%-I:%M %p")})
            cursor=start+timedelta(minutes=needed); total+=needed
            if not t["repeat"]: tasks.remove(t)
        result[name]={"mins":total,"slots":slots}
    return result

ROTATIONS={"A":[1,2,3,5,6,7],"B":[4,1,2,8,5,6],"C":[3,4,1,7,8,5],"D":[2,3,4,6,7,8]}
SCHEDULES=["Daily","Connect","2 Hour Delay","Early Dismissal","Emergency Early Dismissal","X Day","X Day 2 Hour Delay","X Day Early Dismissal"]
BELL_TIMES={
"Daily":[("7:32 AM","8:29 AM"),("8:33 AM","9:31 AM"),("9:35 AM","10:32 AM"),("10:36 AM","12:08 PM"),("12:12 PM","1:09 PM"),("1:13 PM","2:10 PM")],
"Connect":[("7:32 AM","8:23 AM"),("8:27 AM","9:18 AM"),("9:22 AM","9:53 AM"),("9:57 AM","12:20 PM"),("12:24 PM","1:15 PM"),("1:19 PM","2:10 PM")],
"2 Hour Delay":[("9:32 AM","10:06 AM"),("10:10 AM","10:44 AM"),("10:48 AM","11:24 AM"),("11:28 AM","12:54 PM"),("12:58 PM","1:32 PM"),("1:36 PM","2:10 PM")],
"Early Dismissal":[("7:32 AM","8:05 AM"),("8:09 AM","8:42 AM"),("8:46 AM","9:24 AM"),("9:28 AM","10:01 AM"),("10:05 AM","10:38 AM"),("10:42 AM","11:15 AM")],
"Emergency Early Dismissal":[("7:32 AM","8:25 AM"),("8:29 AM","8:57 AM"),("9:01 AM","9:29 AM"),("9:33 AM","10:01 AM"),("10:05 AM","10:33 AM"),("10:37 AM","11:05 AM")],
"X Day":[("7:32 AM","8:12 AM"),("8:16 AM","8:56 AM"),("9:00 AM","9:42 AM"),("9:46 AM","10:26 AM"),("10:30 AM","11:10 AM"),("11:14 AM","12:42 PM"),("12:46 PM","1:26 PM"),("1:30 PM","2:10 PM")],
"X Day 2 Hour Delay":[("9:32 AM","9:55 AM"),("9:59 AM","10:22 AM"),("10:26 AM","10:50 AM"),("10:54 AM","11:17 AM"),("11:21 AM","11:44 AM"),("11:48 AM","1:16 PM"),("1:20 PM","1:43 PM"),("1:47 PM","2:10 PM")],
"X Day Early Dismissal":[("7:32 AM","7:56 AM"),("8:00 AM","8:24 AM"),("8:28 AM","8:55 AM"),("8:59 AM","9:23 AM"),("9:27 AM","9:51 AM"),("9:55 AM","10:19 AM"),("10:23 AM","10:47 AM"),("10:51 AM","11:15 AM")]}
def bell_rows(letter,schedule,cfg):
    periods=cfg.get("periods",{}); lunches=cfg.get("lunches",{}); wave=lunches.get(letter,"L2")
    rotation=list(range(1,9)) if letter=="X" or schedule.startswith("X Day") else ROTATIONS.get(letter,ROTATIONS["A"])
    times=BELL_TIMES.get(schedule,BELL_TIMES["Daily"]); rows=[]
    for i,(start,end) in enumerate(times):
        p=rotation[i] if len(rotation)==len(times) and i<len(rotation) else (i+1 if len(rotation)==8 else rotation[min(i,len(rotation)-1)])
        cls=periods.get(str(p),"") or f"Period {p}"
        room=cfg.get("study_rooms",{}).get(letter,"") if cls.lower()=="study hall" else ""
        rows.append({"period":p,"class":cls,"start":start,"end":end,"room":room,"wave":wave})
    return rows

def _sheet_override(url, target):
    if not url: return None
    try:
        if "docs.google.com/spreadsheets" in url and "/export?" not in url:
            m=re.search(r"/spreadsheets/d/([^/]+)",url)
            if m: url=f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv"
        import urllib.request
        with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=4) as resp: content=resp.read(500000).decode("utf-8","replace")
        for row in csv.reader(io.StringIO(content)):
            joined=" ".join(row)
            if target.isoformat() in joined:
                m=re.search(r"\b([ABCDX])(?:\s*Day)?\b",joined,re.I)
                if m: return m.group(1).upper()
    except Exception: return None
    return None

@fragment_decorator(run_every="60s")
def render_bell(uid):
    cfg=st.session_state.cfg_shs; day=st.date_input("Select date",now_local().date(),key="bell_date")
    override=st.selectbox("Letter day",["Auto","A","B","C","D","X"],key="bell_letter")
    sched_override=st.selectbox("Schedule",["Auto"]+SCHEDULES,key="bell_schedule")
    detected=_sheet_override(cfg.get("sheet_url",""),day)
    if override!="Auto": letter=override
    elif detected: letter=detected
    elif day.weekday()>=5: letter="WEEKEND"
    else: letter="ABCD"[(day.toordinal()-date(2026,9,1).toordinal())%4]
    sched=sched_override if sched_override!="Auto" else ("X Day" if letter=="X" else ("Connect" if day.weekday()==2 else "Daily"))
    with st.expander("Customize classes, lunch waves, study hall rooms, and calendar"):
        periods=dict(cfg.get("periods",{})); cols=st.columns(4)
        for p in range(1,9):
            with cols[(p-1)%4]: periods[str(p)]=st.text_input(f"Period {p}",periods.get(str(p),""),key=f"bell_period_{p}")
        lunches=dict(cfg.get("lunches",{d:"L2" for d in LETTERS})); rooms=dict(cfg.get("study_rooms",{})); col=st.columns(5)
        for i,d in enumerate(LETTERS):
            with col[i]:
                lunches[d]=st.selectbox(f"{d} lunch",["L1","L2","L3"],index=["L1","L2","L3"].index(lunches.get(d,"L2")),key=f"lunch_{d}")
                rooms[d]=st.text_input(f"{d} Study Hall room",rooms.get(d,""),key=f"room_{d}")
        sheet=st.text_input("Optional public calendar Google Sheet/CSV URL",cfg.get("sheet_url",""))
        if st.button("Save SHS settings"):
            cfg.update({"periods":periods,"lunches":lunches,"study_rooms":rooms,"sheet_url":sheet}); save_config(uid,"__SYSTEM_SHS_CONFIG__",cfg); st.success("Saved")
    if letter in ("WEEKEND",): st.info("Weekend — no classes scheduled."); return
    rows=bell_rows(letter,sched,cfg); st.subheader(f"{letter} Day · {sched} · Lunch {cfg.get('lunches',{}).get(letter,'L2')}")
    now=now_local(); current=now.time() if day==now.date() else None
    for r in rows:
        a=parse_time(r["start"]); b=parse_time(r["end"]); live=bool(current and a and b and a<=current<b)
        extra=f" · Room {esc(r['room'])}" if r["room"] else ""
        remain=f" · {((b.hour*60+b.minute)-(now.hour*60+now.minute))} min remaining" if live else ""
        st.markdown(f"{'🟢 **LIVE —** ' if live else ''}**Period {r['period']} · {esc(r['class'])}** — {r['start']}–{r['end']} · {r['wave']}{extra}{remain}")


def render_admin():
    st.header("🛠️ Feature Control Center & Feedback Inbox")
    with db_engine().connect() as conn:
        errors=conn.execute(text("SELECT id,feature,message FROM feature_errors WHERE resolved=0 ORDER BY created_at DESC LIMIT 50")).mappings().all()
        flags=conn.execute(text("SELECT feature,status FROM feature_flags ORDER BY feature")).mappings().all()
        catalog=conn.execute(text("SELECT feature,description FROM feature_catalog ORDER BY feature")).mappings().all()
        items=conn.execute(text("SELECT id,email,category,message,created_at FROM feedback ORDER BY created_at DESC LIMIT 100")).mappings().all()
        unread=conn.execute(text("SELECT COUNT(*) FROM feedback_replies WHERE is_read=0")).scalar_one()
    st.metric("Unread replies",unread); st.subheader("Feature catalog and release controls")
    if catalog:
        for item in catalog:
            old=next((x["status"] for x in flags if x["feature"]==item["feature"]),"Beta Testing")
            col1,col2=st.columns([3,2]); col1.write(f"**{item['feature']}** — {item['description']}")
            with col2:
                choice=st.selectbox(item["feature"],["Public Released","Beta Testing","Removed/Hidden"],index=["Public Released","Beta Testing","Removed/Hidden"].index(old),key="flag_"+item["feature"])
                if st.button("Save",key="saveflag_"+item["feature"]): bg_sql("INSERT INTO feature_flags(feature,status) VALUES(:f,:s) ON CONFLICT(feature) DO UPDATE SET status=EXCLUDED.status",{"f":item["feature"],"s":choice})
    else:
        st.caption("No catalog entries yet.")
        feature=st.text_input("Feature"); desc=st.text_input("Description"); state=st.selectbox("Release state",["Public Released","Beta Testing","Removed/Hidden"])
        if st.button("Add/update catalog entry") and feature.strip():
            bg_sql("INSERT INTO feature_catalog(feature,description) VALUES(:f,:d) ON CONFLICT(feature) DO UPDATE SET description=EXCLUDED.description",{"f":feature.strip(),"d":desc})
            bg_sql("INSERT INTO feature_flags(feature,status) VALUES(:f,:s) ON CONFLICT(feature) DO UPDATE SET status=EXCLUDED.status",{"f":feature.strip(),"s":state})
    st.subheader("Unresolved feature errors")
    for e in errors:
        st.error(f"{e['feature']}: {e['message']}")
        if st.button("Dismiss",key="dismiss_"+e["id"]): bg_sql("UPDATE feature_errors SET resolved=1 WHERE id=:id",{"id":e["id"]}); rerun()
    st.subheader("Feedback inbox")
    for f in items:
        st.markdown(f"**{esc(f['email'])} · {esc(f['category'])}** — {esc(f['message'])}")
        replies=st.text_input("Reply",key="reply_"+f["id"])
        if st.button("Send reply",key="send_"+f["id"]) and replies.strip():
            bg_sql("INSERT INTO feedback_replies(id,feedback_id,sender_email,message,created_at,is_read) VALUES(:id,:fid,:email,:message,:created,0)",{"id":str(uuid.uuid4()),"fid":f["id"],"email":ADMIN_EMAIL,"message":replies.strip(),"created":now_local().isoformat()}); st.success("Reply sent")

def auth_page():
    st.title("📑 Assignment Tracker")
    mode=st.radio("Account",["Sign In","Sign Up"],horizontal=True); email=st.text_input("School email or username"); password=st.text_input("Password",type="password")
    if st.button("Continue",type="primary"):
        email=email.strip().lower()
        if "@" not in email: email+=DOMAIN
        if not password: st.error("Enter a password."); return
        if mode=="Sign Up":
            try:
                uid=str(uuid.uuid5(uuid.NAMESPACE_DNS,email))
                with db_engine().begin() as conn: conn.execute(text("INSERT INTO users(id,email,password_hash,created_at) VALUES(:id,:email,:pw,:created)"),{"id":uid,"email":email,"pw":_hash_pw(password),"created":now_local().isoformat()})
                st.success("Account created; please sign in.")
            except Exception: st.error("Could not register this email; it may already exist.")
        else:
            with db_engine().connect() as conn: r=conn.execute(text("SELECT id,email,password_hash FROM users WHERE email=:email"),{"email":email}).fetchone()
            if r and r.password_hash==_hash_pw(password): st.session_state.user={"id":r.id,"email":r.email}; hydrate_user_session(r.id,True); rerun()
            else: st.error("Invalid email or password.")

@dialog_decorator("Edit assignment")
def edit_dialog(uid, aid):
    frame=st.session_state.df_cached; found=frame[frame.id==aid]
    if found.empty: st.info("Assignment no longer exists."); return
    r=found.iloc[0].to_dict()
    with st.form("edit_"+aid):
        title=st.text_input("Title",r["title"]); course=st.text_input("Course",r["course"])
        due=st.date_input("Due date",date.fromisoformat(r["due_date"]) if r["due_date"] else now_local().date())
        status=st.selectbox("Status",STATUSES,index=STATUSES.index(r["status"]) if r["status"] in STATUSES else 0)
        priority=st.selectbox("Priority",PRIORITIES,index=max(0,min(2,(int(r["priority"])-1)//4)))
        atype=st.selectbox("Type",TYPES,index=TYPES.index(r["atype"]) if r["atype"] in TYPES else 0); eta=st.text_input("Estimated time",r["eta"]); notes=st.text_area("Notes",r["notes"])
        save=st.form_submit_button("Save changes")
    if save:
        upsert_task({**r,"title":title,"course":course,"due_date":due.isoformat(),"status":status,"priority":{"Low":2,"Medium":5,"High":9}[priority],"atype":atype,"eta":eta,"notes":notes}); st.success("Saved")

def main():
    user=st.session_state.get("user")
    if not user: auth_page(); return
    uid=str(user["id"]); email=str(user["email"]); hydrate_user_session(uid); theme_css()
    header,actions=st.columns([3,2]); header.title("📑 Assignment Tracker"); header.caption(email)
    with actions:
        if email.lower()==ADMIN_EMAIL and st.button("🛠️ Admin"): st.session_state.admin_open=not st.session_state.get("admin_open",False)
        if st.button("Sign out"): st.session_state.clear(); rerun()
    if email.lower()==ADMIN_EMAIL and st.session_state.get("admin_open"): render_admin(); st.divider()
    with st.expander("Theme & Appearance Studio"):
        cfg=st.session_state.cfg_theme; mode=st.radio("Contrast",["Dark","Light"],index=0 if cfg.get("mode")!="Light" else 1,horizontal=True); preset=st.selectbox("Preset",["Midnight","Daylight","Warm Stone","Sage"]); accent=st.color_picker("Accent",cfg.get("accent","#6366f1")); opacity=st.slider("Card opacity",55,98,int(cfg.get("opacity",90))); bgtype=st.selectbox("Background",["Solid","Gradient","Photo"]); background=cfg.get("background","#0b1020")
        if bgtype=="Solid": background=st.color_picker("Solid background",background if background.startswith("#") else "#0b1020")
        elif bgtype=="Gradient":
            a=st.color_picker("Gradient start","#0b1020"); b=st.color_picker("Gradient end",accent); background=f"linear-gradient(135deg,{a},{b})"
        else:
            upload=st.file_uploader("Upload lightweight background photo",type=["jpg","jpeg","png","webp"])
            if upload:
                try:
                    from PIL import Image
                    image=Image.open(upload); image.thumbnail((1000,1000)); buf=io.BytesIO(); image.convert("RGB").save(buf,format="JPEG",quality=65,optimize=True); background="url(data:image/jpeg;base64,"+base64.b64encode(buf.getvalue()).decode()+") center/cover"
                except Exception: st.warning("Photo compression unavailable; choose a solid or gradient background.")
        if st.button("Save appearance"):
            if preset=="Daylight": mode="Light"
            save_config(uid,"__SYSTEM_THEME_CONFIG__",{"mode":mode,"accent":accent,"opacity":opacity,"bg_type":bgtype,"background":background}); rerun()
    if not st.session_state.cfg_courses:
        cs=st.text_input("Set up courses (comma separated)","MATH, SCIENCE, ENGLISH, HISTORY, OTHER")
        if st.button("Save courses"): save_config(uid,"__SYSTEM_COURSES__",[x.strip().upper() for x in cs.split(",") if x.strip()]); rerun()
    with st.expander("＋ Add assignment"):
        with st.form("add_task"):
            title=st.text_input("Title"); options=st.session_state.cfg_courses or ["MATH","SCIENCE","ENGLISH","HISTORY","OTHER"]; course=st.selectbox("Course",options); due=st.date_input("Due date",now_local().date()); status=st.selectbox("Status",STATUSES); pr=st.select_slider("Priority",PRIORITIES,value="Medium"); atype=st.selectbox("Type",TYPES); eta=st.text_input("Estimated time","30 min"); notes=st.text_area("Notes"); submit=st.form_submit_button("Add assignment")
        if submit:
            upsert_task({"id":str(uuid.uuid4()),"user_id":uid,"title":title,"course":course,"due_date":due.isoformat(),"status":status,"priority":{"Low":2,"Medium":5,"High":9}[pr],"atype":atype,"eta":eta,"notes":notes,"prev_status":status if status!="Done" else "Not Started"}); st.success("Added")
    tabs=st.tabs(["Assignments","Classroom Sync","Study Planner","SHS Bell Schedule","Feedback"])
    with tabs[0]:
        df=st.session_state.df_cached.copy(); search=st.text_input("Search title, course or notes")
        courses=["All courses"]+sorted(set(df.course.tolist())) if not df.empty else ["All courses"]
        c1,c2,c3=st.columns(3); cf=c1.selectbox("Course",courses); sf=c2.selectbox("Status",["Active Only","All Tasks"]+STATUSES); sort=c3.selectbox("Sort",["Due Date","Priority","Course"])
        if search: df=df[df.apply(lambda r:search.lower() in f"{r.title} {r.course} {r.notes}".lower(),axis=1)]
        if cf!="All courses": df=df[df.course==cf]
        if sf=="Active Only": df=df[df.status!="Done"]
        elif sf in STATUSES: df=df[df.status==sf]
        if sort=="Priority": df=df.sort_values("priority",ascending=False)
        elif sort=="Course": df=df.sort_values("course")
        else: df=df.sort_values("due_date",na_position="last")
        for _,r in df.iterrows():
            with st.container(border=True):
                st.markdown(f"### {esc(r.title)} · {esc(r.course)}"); st.caption(f"{r.atype} · Due {r.due_date or 'unscheduled'} · Priority {r.priority} · {r.eta}")
                if r.notes: st.write(r.notes)
                a,b,c,d=st.columns(4)
                if a.button("Undo" if r.status=="Done" else "Done",key="done_"+r.id):
                    new="In Progress" if r.status=="Done" else "Done"; upsert_task({**r.to_dict(),"status":new,"prev_status":r.status if new=="Done" else r.prev_status}); rerun()
                if b.button("Pause" if r.status=="In Progress" else "Start",key="start_"+r.id): upsert_task({**r.to_dict(),"status":"Not Started" if r.status=="In Progress" else "In Progress"}); rerun()
                if c.button("Edit",key="edit_"+r.id): edit_dialog(uid,r.id)
                if d.button("Delete",key="delete_"+r.id): delete_task(r.id); rerun()
    with tabs[1]:
        st.caption("Open Classroom To-do, press Ctrl+A then Ctrl+C, and paste below. Bookmarklets are provided separately for personal devices.")
        pasted=st.text_area("Chromebook Ctrl+A Paste Sync",height=150)
        if st.button("Parse pasted Classroom tasks"): st.session_state.sync_preview=parse_classroom(pasted)
        preview=st.session_state.get("sync_preview",[]); df=st.session_state.df_cached
        for i,item in enumerate(preview):
            course=map_course(item["raw_course"],st.session_state.cfg_courses); due=parse_date(item["raw_due"]); dup=duplicate(item["title"],course,due,df) or item["title"].lower() in st.session_state.cfg_ignored
            item["checked"]=st.checkbox(f"{item['title']} · {course} · {due or 'No due date'}"+(" (duplicate/ignored)" if dup else ""),value=not dup,key=f"sync_{i}")
        if st.button("Import selected tasks"):
            for item in preview:
                if not item.get("checked"): continue
                course=map_course(item["raw_course"],st.session_state.cfg_courses); due=parse_date(item["raw_due"]); title=item["title"].strip()
                if not title or title.lower() in st.session_state.cfg_ignored or duplicate(title,course,due,st.session_state.df_cached): continue
                upsert_task({"id":str(uuid.uuid4()),"user_id":uid,"title":title,"course":course,"due_date":due,"status":"Not Started","priority":5,"atype":guess_type(title),"eta":"30 min","notes":"Synced from Google Classroom","prev_status":"Not Started"})
            st.session_state.pop("sync_preview",None); st.success("Sync complete")
        with st.expander("Bookmarklet generator — personal devices"):
            app_url=st.text_input("App URL",placeholder="https://your-app.streamlit.app")
            code="javascript:(function(){location.href='"+app_url.rstrip("/")+"/?sync=PASTE_CLASSROOM_DATA';})()"
            st.code(code,language="text")
    with tabs[2]:
        st.subheader("Seven-day multi-session study planner"); caps=st.session_state.cfg_max_work
        with st.expander("Per-day work caps"):
            cc=st.columns(7)
            for i,d in enumerate(DAYS):
                with cc[i]: caps[d]=st.number_input(d[:3],0,300,int(caps.get(d,60)),step=15,key="cap_"+d)
            if st.button("Save caps"): save_config(uid,"__SYSTEM_MAX_WORK_CONFIG__",caps)
        schedule=st.session_state.cfg_schedule
        with st.expander("Weekly recurring commitments"):
            day=st.selectbox("Day",DAYS); event=st.text_input("Commitment name"); start=st.text_input("Start time","3:30 PM"); end=st.text_input("End time","5:00 PM")
            if st.button("Add commitment") and event.strip() and parse_time(start) and parse_time(end):
                schedule.append({"id":str(uuid.uuid4()),"day":day,"title":event.strip(),"start":start,"end":end}); save_config(uid,"__SYSTEM_SCHEDULE__",schedule); rerun()
            for ev in schedule: st.write(f"{ev.get('day')}: {ev.get('title')} {ev.get('start')}–{ev.get('end')}")
        plan=run_with_fallback("AI Study Planner",lambda:study_plan(st.session_state.df_cached,schedule,caps),lambda:{})
        for day_name,info in plan.items():
            st.markdown(f"**{day_name} · {info['mins']} min / cap {caps.get(day_name,60)} min**")
            for slot in info["slots"]: st.write(f"{slot['time']} — {slot['title']} · {slot['course']} ({slot['mins']} min)")
    with tabs[3]: run_with_fallback("SHS Bell Schedule",lambda:render_bell(uid),lambda:st.info("The bell schedule is unavailable. Try again later."))
    with tabs[4]:
        with st.form("feedback_form"):
            category=st.selectbox("Category",["Feature Request","Bug Report","SHS Bell Schedule Issue","General Feedback"]); rating=st.slider("Rating",1,5,5); msg=st.text_area("Message")
            submit=st.form_submit_button("Send feedback")
        if submit and msg.strip():
            bg_sql("INSERT INTO feedback(id,user_id,email,category,rating,message,created_at) VALUES(:id,:uid,:email,:category,:rating,:message,:created)",{"id":str(uuid.uuid4()),"uid":uid,"email":email,"category":category,"rating":rating,"message":msg.strip(),"created":now_local().isoformat()}); st.success("Feedback sent")
        with db_engine().connect() as conn: replies=conn.execute(text("SELECT id,message,created_at FROM feedback_replies WHERE feedback_id IN (SELECT id FROM feedback WHERE user_id=:uid) ORDER BY created_at DESC"),{"uid":uid}).mappings().all()
        if replies:
            st.subheader("Replies")
            for reply in replies:
                st.info(reply["message"])
                if not email.lower()==ADMIN_EMAIL: bg_sql("UPDATE feedback_replies SET is_read=1 WHERE id=:id",{"id":reply["id"]})

if __name__ == "__main__": main()
