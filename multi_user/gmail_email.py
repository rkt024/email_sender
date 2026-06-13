import os
import re
import sqlite3
import smtplib
from email.message import EmailMessage
from datetime import datetime
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import time

# ==========================================
# CONFIGURATION & SETUP
# ==========================================
load_dotenv()

DB_NAME = "app.db"
ALLOWED_EXTENSIONS = [".pdf", ".docx"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB per file
MAX_TOTAL_SIZE = 25 * 1024 * 1024  # 25MB total

GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# ==========================================
# GLOBAL STYLES
# ==========================================
st.markdown("""
    <style>
        div[data-testid="stMetricValue"] div { font-size: 1.25rem !important; white-space: normal !important; }
        div[data-testid="stMetricLabel"] { font-size: 1rem !important; }
        .status-running { background-color: #f0f4f8; border-radius: 0.5rem; padding: 1rem; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# DATABASE LAYER
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, auth_code TEXT NOT NULL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS institutions (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, email TEXT NOT NULL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS email_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_name TEXT NOT NULL, institution_name TEXT NOT NULL, recipients TEXT NOT NULL, ref_no TEXT NOT NULL, pam_ref TEXT, sent_from TEXT, sent_at TEXT NOT NULL)")
    try: cursor.execute("ALTER TABLE email_logs ADD COLUMN pam_ref TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE email_logs ADD COLUMN sent_from TEXT")
    except sqlite3.OperationalError: pass
    conn.commit()
    return conn

def get_users(conn):
    return [row[0] for row in conn.execute("SELECT name FROM users ORDER BY name").fetchall()]

def get_institutions(conn):
    return conn.execute("SELECT name, email FROM institutions ORDER BY name").fetchall()

def verify_auth_code(conn, user_name, auth_code):
    result = conn.execute("SELECT auth_code FROM users WHERE name = ?", (user_name,)).fetchone()
    return result is not None and auth_code == result[0]

def log_email(conn, user_name, institution_name, recipients, ref_no, pam_ref, sent_from=None):
    conn.execute(
        "INSERT INTO email_logs (user_name, institution_name, recipients, ref_no, pam_ref, sent_from, sent_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_name, institution_name, recipients, ref_no, pam_ref, sent_from, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()

def get_email_logs(conn):
    df = pd.read_sql_query("SELECT id, user_name, institution_name, recipients, ref_no, pam_ref, sent_from, sent_at FROM email_logs ORDER BY datetime(sent_at) DESC", conn)
    if df.empty: return df
    if "pam_ref" in df.columns: df["pam_ref"] = df["pam_ref"].fillna("")
    if "sent_from" in df.columns: df["sent_from"] = df["sent_from"].fillna("N/A")
    mask = df["ref_no"].astype(str).str.strip() != ""
    return pd.concat([df[mask].drop_duplicates(subset=["ref_no"], keep="first"), df[~mask]]).sort_values(by="sent_at", ascending=False)

# ==========================================
# GMAIL SMTP BACKEND
# ==========================================
def send_email_via_gmail(to, cc, files, subject="रोक्का जानकारी"):
    """Generator yielding progress updates for st.status."""
    if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD: 
        raise ValueError("GMAIL credentials missing.")
        
    signature = "भूमि प्रशासन कार्यालय\nचावहिल, काठमाण्डौं\n\nLand Administration Office\nChabahil, Kathmandu\n\n📞 01-4822617\n✉️ chabahil@dolma.gov.np, bpkchabahil@dolma.gov.np\n🌐 https://chabahil.dolma.gov.np/office/chabahil"
    
    yield "🔐 Connecting to Gmail SMTP server...", 10
    time.sleep(0.4)
    
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = GMAIL_EMAIL
        msg['To'] = to
        if cc:
            msg['Cc'] = ", ".join(cc)
        msg.set_content(signature)
        
        yield "✅ Message prepared", 20
        time.sleep(0.3)
        
        yield f"📤 Attaching {len(files)} file(s)...", 40
        time.sleep(0.3)
        for f in files:
            f.seek(0)
            file_data = f.read()
            msg.add_attachment(file_data, maintype='application', subtype='octet-stream', filename=f.name)
            
        yield "✅ Attachments ready", 70
        time.sleep(0.3)
        
        yield "📨 Sending email...", 85
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)
            
        yield "✅ Email sent successfully!", 100
        time.sleep(0.5)
    except Exception as e:
        raise RuntimeError(f"SMTP Error: {str(e)}")

# ==========================================
# VALIDATION & UI HELPERS
# ==========================================
def validate_ref_no(r): return bool(re.match(r'^RK\d{7}$', r.strip().upper()))
def validate_email(e): return bool(re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", e.strip()))
def validate_cc(t):
    if not t.strip(): return True, []
    emails = [e.strip() for e in t.split(",") if e.strip()]
    for e in emails:
        if not validate_email(e): return False, []
    return True, emails
def validate_files(files):
    total = 0
    for f in files:
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS: return False, f"Invalid type: {f.name}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        if f.size > MAX_FILE_SIZE: return False, f"{f.name} exceeds 10MB limit"
        total += f.size
    if total > MAX_TOTAL_SIZE: return False, "Total attachment size exceeds 25MB limit"
    return True, ""

def init_session_state():
    defaults = {"show_auth_popup": False, "form_data": {}, "sending_email": False, "send_status": None, "form_version": 0, "last_sent_to": None, "last_sent_cc": None, "selected_user": None, "institution_map": {}}
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

def render_auth_section():
    """Inline authorization card — replaces the @st.dialog approach so there
    is no modal to dismiss. Flipping session state + st.rerun() is enough to
    make it vanish and show the progress status instantly."""
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.8rem 2rem;
        max-width: 480px;
        margin: 2rem auto;
        box-shadow: 0 8px 32px rgba(0,0,0,0.35);
    ">
        <h3 style="color:#f8fafc;margin:0 0 0.3rem 0;">🔐 Authorization Required</h3>
        <p style="color:#94a3b8;margin:0 0 1.2rem 0;font-size:0.9rem;">
            Enter your authorization code to confirm and send the email.
        </p>
    </div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        code = st.text_input(
            "Authorization Code",
            type="password",
            key="auth_code_inline",
            placeholder="Enter your code...",
        )
        c1, c2 = st.columns(2)
        if c1.button("✅ Confirm & Send", type="primary", use_container_width=True, key="btn_confirm_send"):
            if not code.strip():
                st.error("❌ Please enter your authorization code.")
            else:
                selected_user = st.session_state.form_data.get("selected_user")
                with sqlite3.connect(DB_NAME) as temp_conn:
                    if not verify_auth_code(temp_conn, selected_user, code):
                        st.error("❌ Invalid authorization code. Please try again.")
                    else:
                        # Auth passed — hide auth card and start sending
                        st.session_state.show_auth_popup = False
                        st.session_state.sending_email = True
                        st.rerun()
        if c2.button("❌ Cancel", use_container_width=True, key="btn_cancel_send"):
            st.session_state.show_auth_popup = False
            st.session_state.form_data = {}
            st.rerun()

# ==========================================
# UI PAGES
# ==========================================
def render_send_email_page(institution_names):
    st.title("📧 Daily Email Sender")
    
    # 1. Show success/error from previous run
    if st.session_state.send_status:
        if st.session_state.send_status == "success":
            cc = st.session_state.last_sent_cc or []
            cc_str = f", cc: {', '.join(cc)}" if cc else ""
            st.success(f"✅ Email sent successfully to: {st.session_state.last_sent_to}{cc_str}")
            st.toast("🎉 Delivered successfully!", icon="✅")
            st.balloons()
        else:
            st.error(st.session_state.send_status)
        st.session_state.send_status = None
        st.divider()

    # 2. Handle Sending State & Real-time Progress
    if st.session_state.sending_email:
        with st.status("📤 Sending Email...", expanded=True) as status:
            try:
                data = st.session_state.form_data
                to = st.session_state.institution_map[data["selected_institution"]]
                cc = data["cc_list"]
                
                # Iterate through generator to update UI in real-time
                for msg, val in send_email_via_gmail(to, cc, data["uploaded_files"], "रोक्का जानकारी"):
                    status.update(label=msg, state="running")
                    st.progress(val)
                
                # Log on success
                with sqlite3.connect(DB_NAME) as db:
                    log_email(db, data["selected_user"], data["selected_institution"], ", ".join([to]+cc), data["ref_no"], data.get("pam_ref",""), GMAIL_EMAIL)
                
                st.session_state.last_sent_to = to
                st.session_state.last_sent_cc = cc
                st.session_state.send_status = "success"
                
            except Exception as e:
                st.session_state.send_status = f"❌ Error: {type(e).__name__}: {e}"
                status.update(label=f"❌ {e}", state="error")
            finally:
                st.session_state.sending_email = False
                st.session_state.form_data = {}
                st.session_state.form_version += 1 # Forces complete form reset
                st.rerun() # Triggers UI update to show success message

    # 3. Show inline auth section (replaces @st.dialog — dismisses instantly on confirm)
    if st.session_state.show_auth_popup:
        render_auth_section()

    # 4. Show Form ONLY when not sending and dialog is closed
    if not st.session_state.sending_email and not st.session_state.show_auth_popup:
        fv = st.session_state.form_version
        
        files = st.file_uploader("📎 Upload Documents (.pdf, .docx)", type=ALLOWED_EXTENSIONS, accept_multiple_files=True, help="Max 10MB/file, 25MB total", key=f"files_{fv}")
        inst = st.selectbox("🏛️ Select Institution", institution_names, index=None, placeholder="Choose an institution...", key=f"inst_{fv}")
        
        if inst:
            email_addr = st.session_state.institution_map.get(inst)
            st.markdown(f"<div style='margin-top: -10px; margin-bottom: 10px; color: #10b981; font-size: 0.9rem;'>✅ <b>{email_addr}</b></div>", unsafe_allow_html=True)
            
        cc = st.text_input("📧 CC Emails (optional)", placeholder="branch@bank.com, manager@bank.com", key=f"cc_{fv}")
        
        ref_raw = st.text_input("🔖 Reference Number", placeholder="RK1234567", key=f"ref_{fv}")
        ref = ref_raw.upper().strip() if ref_raw else ""
        
        pam_raw = st.text_input("📋 PAM Reference Number (optional)", placeholder="Ref. number provided by bank", key=f"pam_{fv}")
        pam = pam_raw.upper().strip() if pam_raw else ""
        
        submitted = st.button("🚀 Send Email", type="primary", use_container_width=True)
        
        if submitted:
            if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
                st.error("🔑 Gmail credentials missing. Check `.env` file.")
                st.stop()
            if not inst:
                st.error("🏛️ Please select an institution.")
                st.stop()
            if not validate_ref_no(ref):
                st.error("🔖 Reference Number must start with 'RK' followed by 7 digits (e.g., RK1234567)")
                st.stop()
            if not files:
                st.error("📎 Please upload at least one file.")
                st.stop()
            v, e = validate_files(files)
            if not v: st.error(e); st.stop()
            vc, cc_list = validate_cc(cc)
            if not vc: st.error("📧 Invalid CC email format. Use comma-separated valid emails."); st.stop()
            
            st.session_state.form_data = {
                "selected_user": st.session_state.selected_user,
                "uploaded_files": files,
                "selected_institution": inst,
                "cc_list": cc_list,
                "ref_no": ref,
                "pam_ref": pam
            }
            st.session_state.show_auth_popup = True
            st.rerun()

def render_dashboard(conn):
    st.title("📊 Email Logs Dashboard")
    df = get_email_logs(conn)
    if df.empty: st.info("📭 No email logs found."); return
    df["sent_at"] = pd.to_datetime(df["sent_at"])
    
    st.sidebar.subheader("🔍 Filters")
    bank_list = ["All"] + sorted(df["institution_name"].dropna().unique().tolist())
    user_list = ["All"] + sorted(df["user_name"].dropna().unique().tolist())
    b = st.sidebar.selectbox("🏛️ Bank Name", bank_list)
    u = st.sidebar.selectbox("👤 User", user_list)
    r = st.sidebar.text_input("🔖 Reference", placeholder="RK1234567")
    p = st.sidebar.text_input("📋 PAM Ref", placeholder="PAM1234567")
    d = st.sidebar.date_input("📅 Range", [])
    
    f = df.copy()
    if b != "All": f = f[f.institution_name == b]
    if u != "All": f = f[f.user_name == u]
    if r.strip(): f = f[f.ref_no.str.contains(r.strip(), case=False, na=False)]
    if p.strip() and "pam_ref" in f.columns: f = f[f.pam_ref.str.contains(p.strip(), case=False, na=False)]
    if len(d) == 2: f = f[(f.sent_at >= pd.Timestamp(d[0])) & (f.sent_at <= pd.Timestamp(d[1]))]
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📧 Total Emails", len(f)); c2.metric("🏛️ Institutions", f.institution_name.nunique())
    c3.metric("👤 Users", f.user_name.nunique()); c4.metric("🕐 Latest", f.sent_at.max().strftime("%Y-%m-%d %H:%M") if not f.empty else "N/A")
    st.divider()
    
    co1, co2 = st.columns(2)
    # DESCENDING ORDER FIX
    inst_counts = f.institution_name.value_counts().sort_values(ascending=False)
    user_counts = f.user_name.value_counts().sort_values(ascending=False)
    with co1: st.subheader("📈 Emails by Bank"); st.bar_chart(inst_counts)
    with co2: st.subheader("📈 Emails by User"); st.bar_chart(user_counts)
        
    st.subheader("📈 Volume Over Time"); st.line_chart(f.groupby(f.sent_at.dt.date).size())
    st.divider()
    
    st.subheader("📋 Logs")
    disp = f.copy(); disp["sent_at"] = disp.sent_at.dt.strftime("%Y-%m-%d %H:%M:%S"); disp.insert(0, "S.No.", range(len(disp), 0, -1))
    st.dataframe(disp.drop(columns=["id"], errors="ignore"), use_container_width=True, hide_index=True)
    st.download_button("⬇️ CSV", disp.drop(columns=["id"], errors="ignore").to_csv(index=False), f"logs_{datetime.now().strftime('%Y%m%d')}.csv", use_container_width=True)

def main():
    st.set_page_config(page_title="Financial Email Sender", page_icon="📧", layout="wide", initial_sidebar_state="expanded")
    init_session_state()
    conn = init_db()
    
    # Persist maps
    inst_list = get_institutions(conn)
    st.session_state.institution_map = {n: e for n, e in inst_list}
    inst_names = list(st.session_state.institution_map.keys())
    
    with st.sidebar:
        st.title("📂 Navigation")
        st.info("📧 **Office Email**: bpkchabahil@gmail.com")
        menu = st.radio("Go To", ["📤 Send Email", "📊 Logs"], index=0, horizontal=False)
        st.divider()
        st.title("👤 User")
        users = get_users(conn)
        if users: st.session_state.selected_user = st.selectbox("Select User", users, index=2)
        st.divider()
        st.caption(f"🔄 App v1.3.0 (Gmail) | Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
    if menu == "📤 Send Email": render_send_email_page(inst_names)
    elif menu == "📊 Logs": render_dashboard(conn)
    conn.close()

if __name__ == "__main__": main()
