"""Father Bot owner web panel. Disabled unless FATHER_WEB_PASSWORD is configured."""
import os, hmac, secrets, threading, time, datetime, html
from flask import Flask, request, session, redirect, url_for, render_template_string, flash
from waitress import serve
import config, database as db, provisioner

app = Flask(__name__)
app.secret_key = os.getenv("FATHER_WEB_SECRET", "")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=True,
               SESSION_COOKIE_SAMESITE="Lax", PERMANENT_SESSION_LIFETIME=datetime.timedelta(seconds=1800))

LOGIN_HTML = r'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>PX-9 Father Panel</title>
<style>body{margin:0;background:#0b1020;color:#e8edf8;font:16px system-ui;display:grid;min-height:100vh;place-items:center}.card{width:min(420px,92vw);box-sizing:border-box;background:#151d31;border:1px solid #293550;border-radius:18px;padding:28px}h1{margin:0 0 8px}p{color:#aab6d0}input,button{width:100%;box-sizing:border-box;padding:13px;margin-top:12px;border-radius:10px;border:1px solid #354361;background:#0e1628;color:white}button{background:#6757e8;border:0;font-weight:700;cursor:pointer}.err{color:#ff8c9b}</style></head><body><form class="card" method="post"><h1>PX-9 FATHER</h1><p>Owner control panel · secure login</p>{% if error %}<p class="err">{{error}}</p>{% endif %}<input type="hidden" name="csrf" value="{{csrf}}"><input type="password" name="password" placeholder="Web panel password" required autofocus><button>LOGIN</button></form></body></html>'''

DASH_HTML = r'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>PX-9 Father Control</title>
<style>
:root{--bg:#0b1020;--panel:#141d31;--panel2:#10182b;--line:#26344f;--text:#e8edf8;--muted:#9ba9c4;--accent:#7564ef;--green:#39c58b;--red:#ed6378}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px system-ui}header{padding:18px 24px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}header h1{margin:0;font-size:20px}header a{color:#c6c2ff;text-decoration:none}.layout{display:grid;grid-template-columns:220px 1fr;min-height:calc(100vh - 68px)}nav{padding:18px;border-right:1px solid var(--line);background:#0d1426}nav a{display:block;color:var(--muted);padding:10px 12px;text-decoration:none;border-radius:10px;margin-bottom:4px}nav a:hover{background:#1a2540;color:white}.main{padding:24px;max-width:1400px;width:100%}.cards{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:14px}.card,.section{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}.metric{font-size:28px;font-weight:750;margin-top:8px}.muted{color:var(--muted)}h2{margin:0 0 14px}h3{margin:0 0 10px;font-size:17px}.section{margin-top:18px}.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}.formgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.formgrid label{color:var(--muted);font-size:13px}.formgrid input,.formgrid select{display:block;width:100%;padding:11px;margin-top:5px;border-radius:9px;border:1px solid var(--line);background:var(--panel2);color:white}button{background:var(--accent);color:white;border:0;border-radius:9px;padding:10px 14px;font-weight:650;cursor:pointer}button.danger{background:#a73950}button.small{padding:7px 10px;font-size:12px}table{width:100%;border-collapse:collapse;min-width:650px}th,td{text-align:left;padding:10px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-size:12px;text-transform:uppercase}.tablewrap{overflow:auto}.pill{display:inline-block;border-radius:99px;padding:3px 8px;background:#20334e;color:#b9c9e8;font-size:12px}.pill.ok{background:#163e37;color:#8ae0ba}.pill.off{background:#482331;color:#f2a1b1}.flash{padding:12px;border:1px solid #39567c;background:#132a44;border-radius:10px;margin-bottom:12px}.inline{display:inline}.actions{white-space:nowrap}.bottom{margin-top:24px;color:var(--muted);font-size:12px}
@media(max-width:850px){.layout{grid-template-columns:1fr}nav{border-right:0;border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;gap:3px;padding:8px}nav a{padding:8px}.main{padding:14px}.cards{grid-template-columns:repeat(2,minmax(130px,1fr))}.two{grid-template-columns:1fr}.formgrid{grid-template-columns:1fr}header{padding:14px}}
</style></head><body>
<header><h1>⚡ PX-9 Father Control Center</h1><div><span class="muted">Owner panel</span> · <a href="{{url_for('logout')}}">Logout</a></div></header>
<div class="layout"><nav><a href="#overview">🏠 Overview</a><a href="#users">👥 Users</a><a href="#bots">🤖 Bots</a><a href="#builder-access">🛠 Son Bot Builder</a><a href="#keys">🎟 Premium Keys</a><a href="#subscriptions">💎 Premium Users</a><a href="#actions">🛠 Quick Actions</a></nav>
<main class="main">
{% for message in messages %}<div class="flash">{{message}}</div>{% endfor %}
<section id="overview"><h2>Overview</h2><div class="cards">
<div class="card"><div class="muted">Registered users</div><div class="metric">{{stats.users}}</div></div>
<div class="card"><div class="muted">Bots total</div><div class="metric">{{stats.bots}}</div></div>
<div class="card"><div class="muted">Running bots</div><div class="metric">{{stats.running}}</div></div>
<div class="card"><div class="muted">Premium users</div><div class="metric">{{stats.premium}}</div></div></div></section>
<section class="section" id="actions"><h2>Quick Actions</h2><div class="two">
<form method="post" action="{{url_for('create_premium_key')}}"><input type="hidden" name="csrf" value="{{csrf}}"><h3>🎟 Create Premium Key</h3><div class="formgrid">
<label>Plan name<input name="plan" value="ELITE" required maxlength="50"></label><label>Redeemable users<input type="number" name="users" value="1" min="1" max="10000" required></label><label>Bots per user<input type="number" name="bots" value="1" min="1" max="100" required></label><label>Duration (days)<input type="number" name="days" value="30" min="1" max="3650" required></label><label>Price (₹)<input type="number" name="price" value="0" min="0" max="10000000" required></label></div><p><button>Create key</button></p></form>
<form method="post" action="{{url_for('remove_premium')}}"><input type="hidden" name="csrf" value="{{csrf}}"><h3>➖ Remove Premium</h3><p class="muted">Disable an active subscription by Telegram user ID.</p><label>User ID<input type="number" name="user_id" min="1" required></label><p><button class="danger">Remove Premium</button></p></form></div></section>
<section class="section" id="users"><h2>👥 Users</h2><div class="tablewrap"><table><thead><tr><th>ID</th><th>Name</th><th>Username</th><th>Registered</th><th>Last seen</th></tr></thead><tbody>{% for u in users %}<tr><td>{{u.user_id}}</td><td>{{u.first_name}} {{u.last_name}}</td><td>{% if u.username %}@{{u.username}}{% else %}—{% endif %}</td><td>{{u.registered_at}}</td><td>{{u.last_seen}}</td></tr>{% endfor %}</tbody></table></div></section>
<section class="section" id="bots"><h2>🤖 Bot Instances</h2><div class="tablewrap"><table><thead><tr><th>Record</th><th>Bot</th><th>Owner</th><th>Admin</th><th>Status</th><th>Created</th><th>Builder access</th><th>Action</th></tr></thead><tbody>{% for b in bots %}<tr><td>#{{b.id}}</td><td>{% if b.bot_username %}@{{b.bot_username}}{% else %}—{% endif %}</td><td>{{b.owner_id}}</td><td>{{b.admin_id}}</td><td><span class="pill {% if b.status=='RUNNING' %}ok{% else %}off{% endif %}">{{b.status}}</span></td><td>{{b.created_at}}</td><td>{% if b.status!='REVOKED' %}<form class="inline" method="post" action="{{url_for('builder_password',bot_id=b.id)}}"><input type="hidden" name="csrf" value="{{csrf}}"><button class="small" type="submit">Generate 5-min Password</button></form>{% else %}—{% endif %}</td><td>{% if b.status!='REVOKED' %}<form class="inline" method="post" action="{{url_for('revoke_bot',bot_id=b.id)}}"><input type="hidden" name="csrf" value="{{csrf}}"><button class="small danger" onclick="return confirm('Revoke this bot?')">Revoke</button></form>{% else %}—{% endif %}</td></tr>{% endfor %}</tbody></table></div></section>
<section class="section" id="builder-access"><h2>🛠 Son Bot Builder</h2><p class="muted">Every active Son Bot has a separate setup webpage. Generate its temporary password in the Bot Instances table. Password expires after 5 minutes; username is ADMIN or the Telegram admin ID. After login, edit that bot’s supported configuration only.</p></section><section class="section" id="keys"><h2>🎟 Premium Keys</h2><div class="tablewrap"><table><thead><tr><th>Key ID</th><th>Hint</th><th>Plan</th><th>Users</th><th>Redeemed</th><th>Bot slots</th><th>Duration</th><th>Price</th><th>Status</th><th>Created</th></tr></thead><tbody>{% for k in keys %}<tr><td>#{{k.id}}</td><td>••••{{k.key_hint}}</td><td>{{k.plan_name}}</td><td>{{k.max_users}}</td><td>{{k.redeemed_count}}</td><td>{{k.bots_per_user}}</td><td>{{k.duration_days}} d</td><td>₹{{k.price}}</td><td>{{k.status}}</td><td>{{k.created_at}}</td></tr>{% endfor %}</tbody></table></div></section>
<section class="section" id="subscriptions"><h2>💎 Premium Users</h2><div class="tablewrap"><table><thead><tr><th>User</th><th>Plan</th><th>Bot limit</th><th>Expiry</th><th>Status</th><th>Action</th></tr></thead><tbody>{% for s in subs %}<tr><td>{{s.user_id}}</td><td>{{s.plan_name}}</td><td>{{s.bot_limit}}</td><td>{{s.expires_at}}</td><td>{{s.status}}</td><td><form class="inline" method="post" action="{{url_for('remove_premium')}}"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="user_id" value="{{s.user_id}}"><button class="small danger">Remove</button></form></td></tr>{% endfor %}</tbody></table></div></section>
<div class="bottom">Credentials and bot tokens are never displayed here. All changes are recorded by the Father Bot database.</div></main></div></body></html>'''



def _csrf():
    if "csrf" not in session: session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]

def _check_csrf():
    return hmac.compare_digest(str(request.form.get("csrf", "")), str(session.get("csrf", "")))

def _auth(): return bool(session.get("father_admin_authenticated"))

def _password(): return os.getenv("FATHER_WEB_PASSWORD", "")

def _login_limiter_ok():
    now=time.time(); ip=request.remote_addr or "unknown"; bucket=login_attempts.setdefault(ip,[])
    bucket[:]=[t for t in bucket if now-t<600]
    return len(bucket)<8

login_attempts={}

@app.route("/", methods=["GET","POST"])
def index():
    if not _password(): return "Father web panel is disabled. Configure FATHER_WEB_PASSWORD in Railway variables.",503
    if _auth(): return redirect(url_for("dashboard"))
    error=""
    if request.method=="POST":
        if not _login_limiter_ok(): return render_template_string(LOGIN_HTML,error="Too many attempts. Wait 10 minutes.",csrf=_csrf()),429
        if not _check_csrf(): error="Session expired. Reload and try again."
        elif hmac.compare_digest(request.form.get("password", ""),_password()):
            session.clear(); session["father_admin_authenticated"]=True; session.permanent=True; session["csrf"]=secrets.token_urlsafe(32)
            return redirect(url_for("dashboard"))
        else:
            login_attempts.setdefault(request.remote_addr or "unknown",[]).append(time.time()); error="Incorrect password."
    return render_template_string(LOGIN_HTML,error=error,csrf=_csrf())

@app.route("/health")
def health():
    return "ok", 200

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if not _auth(): return redirect(url_for("index"))
    users=db.list_users(); bots=db.list_bots(); subs=db.premium_users()
    c=db.conn(); keys=c.execute("SELECT * FROM father_premium_keys ORDER BY id DESC LIMIT 100").fetchall(); c.close()
    stats={"users":len(users),"bots":len(bots),"running":sum(1 for b in bots if b["status"]=="RUNNING"),"premium":len(subs)}
    return render_template_string(DASH_HTML,users=users[:500],bots=bots[:500],subs=subs[:500],keys=keys,stats=stats,csrf=_csrf(),messages=list(session.pop("flash_messages",[])))

def _flash(msg): session.setdefault("flash_messages",[]).append(msg)

def _valid_post():
    if not _auth(): return False
    if not _check_csrf(): return False
    return True


@app.post("/keys/create")
def create_premium_key():
    if not _valid_post(): return "Unauthorized or invalid CSRF token",403
    try:
        plan=(request.form.get("plan", "ELITE").strip() or "ELITE")[:50]
        users=int(request.form.get("users",1)); bots=int(request.form.get("bots",1)); days=int(request.form.get("days",30)); price=int(request.form.get("price",0))
        if not (1<=users<=10000 and 1<=bots<=100 and 1<=days<=3650 and 0<=price<=10000000): raise ValueError("out of range")
        raw=db.create_premium_key(config.ADMIN_ID,plan,users,bots,days,price)
        session["flash_messages"]=["Premium key created: "+raw+" (copy it now; it is not stored in plaintext)."]
    except Exception: session["flash_messages"]=["Invalid key settings. Check values and try again."]
    return redirect(url_for("dashboard")+"#actions")

@app.post("/premium/remove")
def remove_premium():
    if not _valid_post(): return "Unauthorized or invalid CSRF token",403
    try: uid=int(request.form.get("user_id",0)); ok=db.remove_premium(uid)
    except Exception: ok=False
    session["flash_messages"]=[f"Premium removed for user {uid}." if ok else "No active premium found for that ID."]
    return redirect(url_for("dashboard")+"#subscriptions")

@app.post("/bots/<int:bot_id>/revoke")
def revoke_bot(bot_id):
    if not _valid_post(): return "Unauthorized or invalid CSRF token",403
    row=db.get_bot_by_id(bot_id)
    if not row or row["status"]=="REVOKED": session["flash_messages"]=["Bot not found or already revoked."]
    else:
        try:
            provisioner.stop_bot(row); session["flash_messages"]=[f"Bot #{bot_id} revoked and slot released."]
        except Exception: session["flash_messages"]=[f"Bot #{bot_id} could not be revoked. Check server logs."]
    return redirect(url_for("dashboard")+"#bots")


# ---------------- Per-Son-Bot Builder ----------------
BUILDER_LOGIN = r'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Son Bot Builder Login</title><style>body{margin:0;background:#0a1020;color:#e9eefb;font:15px system-ui;display:grid;place-items:center;min-height:100vh}.card{width:min(430px,92vw);padding:26px;background:#141e32;border:1px solid #2a3956;border-radius:18px}input,button{width:100%;padding:12px;margin-top:12px;border-radius:10px;background:#0d172a;color:white;border:1px solid #354563}button{background:#705cf0;border:0;font-weight:700}.muted{color:#9eacc8}.error{color:#ff9aa9}</style></head><body><form class="card" method="post"><h1>🛠 Son Bot Builder</h1><p class="muted">Bot: @{{ bot_username or 'Unknown' }} · Admin ID: {{admin_id}}</p>{% if error %}<p class="error">{{error}}</p>{% endif %}<input type="hidden" name="csrf" value="{{csrf}}"><input name="username" placeholder="Username (ADMIN or Telegram admin ID)" required><input type="password" name="password" placeholder="5-minute access password" required><button>OPEN BUILDER</button><p class="muted">Temporary password expires 5 minutes after it is generated.</p></form></body></html>'''

BUILDER_HTML = r'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Son Bot Setup Builder</title><style>
:root{--bg:#0a1020;--panel:#141e32;--line:#293956;--text:#eaf0fc;--muted:#9cabc8;--accent:#725ff0}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px system-ui}header{padding:20px 24px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px}header h1{margin:0;font-size:21px}.wrap{max-width:1100px;margin:auto;padding:22px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:16px}.panel h2{margin:0 0 14px;font-size:18px}.fields{display:grid;grid-template-columns:1fr 1fr;gap:12px}label{color:var(--muted);font-size:13px}input,select,textarea{display:block;width:100%;margin-top:5px;padding:11px;border-radius:9px;border:1px solid var(--line);background:#0d172a;color:var(--text)}textarea{min-height:85px;resize:vertical}button{background:var(--accent);border:0;color:white;border-radius:9px;padding:11px 15px;font-weight:700;cursor:pointer}.save{margin-top:14px}.muted{color:var(--muted)}.menurow{display:grid;grid-template-columns:70px 1fr 2fr;gap:9px;margin:10px 0}.flash{padding:12px;background:#162d48;border:1px solid #35577d;border-radius:10px;margin-bottom:12px}a{color:#c9c4ff;text-decoration:none}@media(max-width:720px){.wrap{padding:12px}.grid,.fields{grid-template-columns:1fr}.menurow{grid-template-columns:55px 1fr}.menurow input:last-child{grid-column:1/-1}header{padding:15px}}</style></head><body><header><h1>🛠 Son Bot Setup Builder</h1><div>@{{bot_username or 'Son Bot'}} · Admin {{admin_id}} · <a href="{{url_for('builder_logout',bot_id=bot_id)}}">Logout</a></div></header><main class="wrap">{% for message in messages %}<div class="flash">{{message}}</div>{% endfor %}<div class="panel"><h2>Bot overview</h2><p class="muted">Bot @{{bot_username or 'unknown'}} · instance #{{bot_id}} · settings apply to this bot only.</p></div><form method="post" action="{{url_for('builder_save',bot_id=bot_id)}}"><input type="hidden" name="csrf" value="{{csrf}}"><div class="grid"><section class="panel"><h2>🎨 Theme & User Experience</h2><div class="fields"><label>Theme<select name="theme"><option value="1" {% if theme=='1' %}selected{% endif %}>Theme 1</option><option value="2" {% if theme=='2' %}selected{% endif %}>Theme 2</option><option value="3" {% if theme=='3' %}selected{% endif %}>Theme 3</option></select></label><label>Restrict forwarded content<select name="restrict"><option value="0" {% if restrict!='1' %}selected{% endif %}>Off</option><option value="1" {% if restrict=='1' %}selected{% endif %}>On</option></select></label></div></section><section class="panel"><h2>💳 Payment & Links</h2><div class="fields"><label>UPI ID<input name="upi" value="{{upi}}" maxlength="160"></label><label>Permanent UPI ID<input name="permanent_upi" value="{{permanent_upi}}" maxlength="160"></label><label>Demo link<input name="demo" value="{{demo}}" maxlength="500"></label><label>Contact link<input name="contact" value="{{contact}}" maxlength="500"></label></div></section></div><section class="panel"><h2>🔘 Menu Buttons</h2><p class="muted">Edit up to 10 menu button labels and links. Empty labels remove that slot.</p>{% for row in menu %}<div class="menurow"><input value="{{row.id}}" disabled aria-label="Button ID"><input name="btn_text_{{row.id}}" value="{{row.text}}" placeholder="Button label"><input name="btn_link_{{row.id}}" value="{{row.link}}" placeholder="https:// or Telegram link"></div>{% endfor %}</section><section class="panel"><h2>💾 Save configuration</h2><p class="muted">This updates this Son Bot's database. Tokens and gateway secrets are not exposed. Existing bot settings are kept unless changed in these fields.</p><button class="save" type="submit">SAVE SETTINGS</button></section></form></main></body></html>'''


def _builder_key(bot_id, suffix):
    return f"builder_{int(bot_id)}_{suffix}"


def _active_bot(bot_id):
    row = db.get_bot_by_id(int(bot_id))
    return row if row and row["status"] == "RUNNING" else None



def _bot_db_path(row):
    from pathlib import Path
    return Path(row["instance_path"]) / "bot_database.db"


def _builder_read(row):
    import sqlite3
    path = _bot_db_path(row)
    if not path.exists(): raise RuntimeError("Bot database not found.")
    c = sqlite3.connect(path); c.row_factory = sqlite3.Row
    settings = {r["key"]: r["value"] for r in c.execute("SELECT key,value FROM settings").fetchall()}
    raw = c.execute("SELECT btn_id,text,link FROM menu_buttons ORDER BY btn_id").fetchall()
    c.close()
    found = {int(x["btn_id"]): {"id":int(x["btn_id"]),"text":x["text"] or "","link":x["link"] or ""} for x in raw}
    return settings, [found.get(i,{"id":i,"text":"","link":""}) for i in range(1,11)]


def _builder_write(row, form):
    import sqlite3
    path = _bot_db_path(row)
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS menu_buttons (btn_id INTEGER PRIMARY KEY,text TEXT,link TEXT)")
    theme = str(form.get("theme","1"))
    if theme not in {"1","2","3"}: raise ValueError("Invalid theme")
    updates = {"selected_theme":theme,"restrict_content":"1" if form.get("restrict")=="1" else "0","upi_id":form.get("upi","").strip()[:160],"permanent_upi_id":form.get("permanent_upi","").strip()[:160],"demo_link":form.get("demo","").strip()[:500],"contact_link":form.get("contact","").strip()[:500]}
    for k,v in updates.items(): c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(k,v))
    for i in range(1,11):
        label=form.get(f"btn_text_{i}","").strip()[:80]
        link=form.get(f"btn_link_{i}","").strip()[:500]
        if label: c.execute("INSERT OR REPLACE INTO menu_buttons(btn_id,text,link) VALUES(?,?,?)",(i,label.upper(),link))
        else: c.execute("DELETE FROM menu_buttons WHERE btn_id=?",(i,))
    c.commit(); c.close()


@app.post("/bots/<int:bot_id>/builder-password")
def builder_password(bot_id):
    if not _valid_post(): return "Unauthorized or invalid CSRF token",403
    row = _active_bot(bot_id)
    if not row: session["flash_messages"]=["Bot is not active."]; return redirect(url_for("dashboard")+"#bots")
    raw = secrets.token_urlsafe(12); expiry = time.time()+300
    import hashlib
    db.setting(_builder_key(bot_id,"password_hash"),hashlib.sha256(raw.encode()).hexdigest())
    db.setting(_builder_key(bot_id,"expires"),str(expiry))
    session["flash_messages"]=[f"Builder URL: {request.url_root.rstrip('/')}/builder/{bot_id} | Username: ADMIN or {row['admin_id']} | Temporary password (5 minutes): {raw}"]
    return redirect(url_for("dashboard")+"#bots")


@app.route("/builder/<int:bot_id>",methods=["GET","POST"])
def builder_login(bot_id):
    row = _active_bot(bot_id)
    if not row: return "Bot not active or not found",404
    if session.get("builder_auth_bot")==int(bot_id) and session.get("builder_session_exp",0)>time.time(): return redirect(url_for("builder_page",bot_id=bot_id))
    error = ""
    if request.method=="POST":
        if not _check_csrf(): return "Invalid CSRF",403
        import hashlib
        username=request.form.get("username","").strip(); password=request.form.get("password","")
        expires=float(db.setting(_builder_key(bot_id,"expires")) or 0); stored=db.setting(_builder_key(bot_id,"password_hash")) or ""
        username_ok=username.upper()=="ADMIN" or username==str(row["admin_id"])
        if username_ok and expires>time.time() and stored and hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(),stored):
            session["builder_auth_bot"]=int(bot_id); session["builder_session_exp"]=time.time()+1800; session["csrf"]=secrets.token_urlsafe(32)
            db.setting(_builder_key(bot_id,"password_hash"),""); db.setting(_builder_key(bot_id,"expires"),"0")
            return redirect(url_for("builder_page",bot_id=bot_id))
        error="Credentials invalid or password expired. Generate a fresh password from Father Panel."
    return render_template_string(BUILDER_LOGIN,error=error,csrf=_csrf(),bot_username=row["bot_username"],admin_id=row["admin_id"])


@app.route("/builder/<int:bot_id>/setup")
def builder_page(bot_id):
    if session.get("builder_auth_bot")!=int(bot_id) or session.get("builder_session_exp",0)<=time.time(): return redirect(url_for("builder_login",bot_id=bot_id))
    row=_active_bot(bot_id)
    if not row: return "Bot not active or not found",404
    try: settings,menu=_builder_read(row)
    except Exception as e: return "Could not read bot settings database: "+html.escape(str(e)),500
    return render_template_string(BUILDER_HTML,bot_id=bot_id,bot_username=row["bot_username"],admin_id=row["admin_id"],theme=settings.get("selected_theme","1"),restrict=settings.get("restrict_content","0"),upi=settings.get("upi_id",""),permanent_upi=settings.get("permanent_upi_id",""),demo=settings.get("demo_link",""),contact=settings.get("contact_link",""),menu=menu,csrf=_csrf(),messages=list(session.pop("builder_flash",[])))

@app.post("/builder/<int:bot_id>/save")
def builder_save(bot_id):
    if session.get("builder_auth_bot")!=int(bot_id) or session.get("builder_session_exp",0)<=time.time(): return redirect(url_for("builder_login",bot_id=bot_id))
    if not _check_csrf(): return "Invalid CSRF",403
    row=_active_bot(bot_id)
    if not row: return "Bot not active or not found",404
    try: _builder_write(row,request.form); session["builder_flash"]=["Settings saved for this Son Bot."]
    except Exception as e: session["builder_flash"]=["Save failed: "+str(e)[:180]]
    return redirect(url_for("builder_page",bot_id=bot_id))

@app.route("/builder/<int:bot_id>/logout")
def builder_logout(bot_id):
    if session.get("builder_auth_bot")==int(bot_id): session.pop("builder_auth_bot",None); session.pop("builder_session_exp",None)
    return redirect(url_for("builder_login",bot_id=bot_id))



def run_webpanel():
    password=_password()
    if not password:
        print("Father web panel disabled (FATHER_WEB_PASSWORD not set).")
        return
    if len(password)<12: print("WARNING: FATHER_WEB_PASSWORD should be at least 12 characters.")
    if not app.secret_key:
        # Derive a stable signing secret from the instance master key; still fail closed if unset.
        key=config.MASTER_INSTANCE_KEY
        if not key or key.startswith("CHANGE_THIS"): raise RuntimeError("Set FATHER_WEB_SECRET or a strong MASTER_INSTANCE_KEY before enabling web panel.")
        import hashlib
        app.secret_key=hashlib.sha256((key+"father-web-session").encode()).hexdigest()
    port=int(os.getenv("PORT","8080"))
    print(f"Father web panel listening on 0.0.0.0:{port}")
    serve(app,host="0.0.0.0",port=port,threads=8)

def start_webpanel_thread():
    if not _password(): return None
    t=threading.Thread(target=run_webpanel,daemon=True,name="father-webpanel")
    t.start(); return t
