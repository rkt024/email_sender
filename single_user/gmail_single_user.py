import os
import re
import sqlite3
import time
from datetime import datetime
import smtplib
from email.message import EmailMessage

import pandas as pd
import streamlit as st
import urllib3
from dotenv import load_dotenv

# ==========================================
# CONFIGURATION & SETUP
# ==========================================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

DB_NAME = "email_app.db"
ALLOWED_EXTENSIONS = [".pdf", ".docx", ".xlsx", ".csv", ".jpg", ".png"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB per file
MAX_TOTAL_SIZE = 25 * 1024 * 1024  # 25MB total

GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Global Styles & Typography Injection
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        /* Base typography reset */
        html, body, [class*="css"], .stMarkdown, p, div, label, input, button, select, textarea {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        }
        
        /* Modern Glassmorphic Cards & Blocks */
        div[data-testid="stMetric"] {
            background: rgba(148, 163, 184, 0.05) !important;
            backdrop-filter: blur(10px) !important;
            -webkit-backdrop-filter: blur(10px) !important;
            border: 1px solid rgba(148, 163, 184, 0.12) !important;
            border-radius: 16px !important;
            padding: 1.2rem !important;
            box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05) !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease !important;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08) !important;
            border: 1px solid rgba(99, 102, 241, 0.3) !important;
        }
        div[data-testid="stMetricValue"] div {
            font-size: 1.2rem !important;
            white-space: normal !important;
            word-break: break-word !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.9rem !important;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            opacity: 0.8;
        }

        /* Clean Accent-styled Container & Expander */
        .office-card {
            background: rgba(148, 163, 184, 0.06);
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 0.85rem;
            border-left: 4px solid #6366f1;
        }

        /* Premium Adaptive Chips */
        .email-chip {
            background: rgba(99, 102, 241, 0.12) !important;
            color: #6366f1 !important;
            border: 1px solid rgba(99, 102, 241, 0.2) !important;
            padding: 4px 10px !important;
            border-radius: 100px !important;
            font-size: 0.85rem !important;
            font-weight: 500 !important;
            display: inline-flex !important;
            align-items: center !important;
            margin: 3px !important;
            transition: all 0.15s ease !important;
        }
        .email-chip:hover {
            background: rgba(99, 102, 241, 0.2) !important;
            transform: scale(1.02) !important;
        }

        /* Form improvements */
        div[data-testid="stForm"] {
            border: 1px solid rgba(148, 163, 184, 0.15) !important;
            border-radius: 18px !important;
            padding: 1.8rem !important;
            background: rgba(148, 163, 184, 0.02) !important;
            box-shadow: 0 10px 30px -10px rgba(0,0,0,0.05) !important;
        }

        /* Navigation styling styling */
        section[data-testid="stSidebar"] {
            background-color: rgba(15, 23, 42, 0.03) !important;
            border-right: 1px solid rgba(148, 163, 184, 0.1) !important;
        }
        
        /* Modern Title Accents */
        .premium-title {
            background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800 !important;
            letter-spacing: -0.5px;
        }

        /* Active Sender Card in Sidebar */
        .sender-card {
            background: rgba(99, 102, 241, 0.06) !important;
            border: 1px solid rgba(99, 102, 241, 0.15) !important;
            border-left: 4px solid #6366f1 !important;
            border-radius: 10px !important;
            padding: 10px 12px !important;
            margin-top: 15px !important;
            margin-bottom: 10px !important;
        }
        .sender-label {
            font-size: 0.75rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
            opacity: 0.7 !important;
            margin-bottom: 2px !important;
            font-weight: 600 !important;
        }
        .sender-value {
            font-size: 0.85rem !important;
            font-weight: 600 !important;
            color: #6366f1 !important;
            word-break: break-all !important;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# DATABASE LAYER
# ==========================================
def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Offices
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS offices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)
    # Office Emails
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS office_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            office_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            FOREIGN KEY (office_id) REFERENCES offices (id),
            UNIQUE(office_id, email)
        )
    """)
    # Email Logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            office_id INTEGER,
            sender TEXT,
            receivers TEXT NOT NULL,
            cc TEXT,
            subject TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (office_id) REFERENCES offices (id)
        )
    """)
    conn.commit()
    try:
        cursor.execute("ALTER TABLE email_logs ADD COLUMN sender TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    conn.close()

def add_office(name):
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO offices (name) VALUES (?)", (name.strip(),))
        conn.commit()
        return True, "Office added successfully."
    except sqlite3.IntegrityError:
        return False, "Office already exists."
    finally:
        conn.close()

def get_offices():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM offices ORDER BY name", conn)
    conn.close()
    return df

def add_office_email(office_id, email):
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO office_emails (office_id, email) VALUES (?, ?)", (office_id, email.strip().lower()))
        conn.commit()
        return True, "Email added successfully."
    except sqlite3.IntegrityError:
        return False, "Email already exists for this office."
    finally:
        conn.close()

def get_office_emails(office_id=None):
    conn = get_db_connection()
    query = """
        SELECT oe.id, oe.office_id, oe.email, o.name as office_name
        FROM office_emails oe
        JOIN offices o ON oe.office_id = o.id
    """
    params = ()
    if office_id is not None:
        query += " WHERE oe.office_id = ?"
        params = (office_id,)
    query += " ORDER BY o.name, oe.email"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def delete_office_email(email_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM office_emails WHERE id = ?", (email_id,))
    conn.commit()
    conn.close()

def log_email(office_id, sender, receivers, cc, subject):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO email_logs (office_id, sender, receivers, cc, subject, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (office_id, sender, receivers, cc, subject, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def get_email_logs():
    conn = get_db_connection()
    query = """
        SELECT el.id, o.name as office_name, el.sender, el.receivers, el.cc, el.subject, el.created_at
        FROM email_logs el
        LEFT JOIN offices o ON el.office_id = o.id
        ORDER BY el.created_at DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# ==========================================
# EMAIL BACKEND (Gmail SMTP)
# ==========================================
def send_email_via_gmail(to_list, cc_list, files, subject, body):
    """Generator yielding progress updates for st.status."""
    if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD: 
        raise ValueError("GMAIL credentials missing. Please check your .env file.")
        
    yield "🔐 Connecting to Gmail SMTP server...", 10
    time.sleep(0.4)
    
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = GMAIL_EMAIL
        msg['To'] = ", ".join(to_list)
        if cc_list:
            msg['Cc'] = ", ".join(cc_list)
        msg.set_content(body)
        
        yield "✅ Message prepared", 20
        time.sleep(0.3)
        
        if files:
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
# UTILS
# ==========================================
def validate_email(email):
    return bool(re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email.strip()))

# ==========================================
# UI PAGES
# ==========================================
def page_office_management():
    st.markdown("<h1 class='premium-title'>🏢 Office Management</h1>", unsafe_allow_html=True)
    st.markdown("Manage offices and their associated email addresses here.")
    
    offices_df = get_offices()
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Add New Office")
        with st.form("add_office_form", clear_on_submit=True):
            new_office_name = st.text_input("Office Name", placeholder="e.g. Kathmandu Branch")
            submitted = st.form_submit_button("➕ Add Office", use_container_width=True)
            if submitted:
                if not new_office_name.strip():
                    st.error("Office name cannot be empty.")
                else:
                    success, msg = add_office(new_office_name)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.warning(msg)
    
    with col2:
        st.subheader("Add Email to Office")
        if offices_df.empty:
            st.info("Please add an office first.")
        else:
            with st.form("add_email_form", clear_on_submit=True):
                office_dict = dict(zip(offices_df.name, offices_df.id))
                selected_office_name = st.selectbox("Select Office", placeholder= "Select Office" ,index=None,options=list(office_dict.keys()))
                new_email = st.text_input("Email Address", placeholder="contact@branch.com")
                submitted = st.form_submit_button("➕ Add Email", use_container_width=True)
                
                if submitted:
                    if not new_email.strip():
                        st.error("Email cannot be empty.")
                    elif not validate_email(new_email):
                        st.error("Invalid email format.")
                    else:
                        office_id = office_dict[selected_office_name]
                        success, msg = add_office_email(office_id, new_email)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.warning(msg)

    st.divider()
    st.subheader("Manage Existing Offices & Emails")
    
    if offices_df.empty:
        st.write("No offices available.")
        return

    all_emails_df = get_office_emails()
    
    for _, office_row in offices_df.iterrows():
        office_id = office_row['id']
        office_name = office_row['name']
        
        # Filter emails for this office
        emails = all_emails_df[all_emails_df['office_id'] == office_id] if not all_emails_df.empty else pd.DataFrame()
        
        with st.expander(f"📁 {office_name} ({len(emails)} emails)"):
            if emails.empty:
                st.caption("No emails added yet.")
            else:
                for _, email_row in emails.iterrows():
                    c1, c2 = st.columns([4, 1])
                    c1.markdown(f"<span class='email-chip'>{email_row['email']}</span>", unsafe_allow_html=True)
                    if c2.button("❌ Remove", key=f"del_{email_row['id']}", help="Delete this email"):
                        delete_office_email(email_row['id'])
                        st.toast("Email removed")
                        st.rerun()

def page_send_email():
    st.markdown("<h1 class='premium-title'>📤 Send Email</h1>", unsafe_allow_html=True)
    st.markdown("Compose and send an email.")
    
    offices_df = get_offices()
    if offices_df.empty:
        st.warning("No offices available. Please add an office first in the Office Management page.")
        return

    office_dict = dict(zip(offices_df.name, offices_df.id))
    
    # Form fields
    selected_office_name = st.selectbox("🏛️ Select Office", placeholder = "Select Office", index=None, options=list(office_dict.keys()))
    
    # Dynamic email selection
    selected_emails = []
    if selected_office_name:
        office_id = office_dict[selected_office_name]
        emails_df = get_office_emails(office_id)
        if emails_df.empty:
            st.info("⚠️ This office has no saved email addresses. You can still manually type one below, or add it in Office Management.")
        else:
            available_emails = emails_df['email'].tolist()
            selected_emails = st.multiselect("Receivers (Auto-populated from Office)", options=available_emails, default=available_emails)
            if selected_emails:
                 st.markdown(f"<div style='margin-top:-15px; margin-bottom:10px;'><span style='color:#10b981; font-size:0.9rem;'>✅ Will send to {len(selected_emails)} selected email(s)</span></div>", unsafe_allow_html=True)
    
    manual_to = st.text_input("➕ Additional Receivers (Optional, comma-separated)", placeholder="other@domain.com")
    
    cc_input = st.text_input("📧 CC (Optional, comma-separated)", placeholder="manager@domain.com, hr@domain.com")
    subject = st.text_input("🔖 Subject", placeholder="Email Subject")
    body = st.text_area("📝 Body", height=150, placeholder="Type your message here...")
    
    files = st.file_uploader("📎 Upload Attachments", type=ALLOWED_EXTENSIONS, accept_multiple_files=True, help="Max 10MB/file, 25MB total")
    
    if st.button("🚀 Send Email", type="primary", use_container_width=True):
        # Gather all TO emails
        final_to_list = list(selected_emails)
        if manual_to.strip():
            manual_list = [e.strip() for e in manual_to.split(",") if e.strip()]
            for e in manual_list:
                if validate_email(e):
                    final_to_list.append(e)
                else:
                    st.error(f"Invalid email in Additional Receivers: {e}")
                    return
        
        # Gather CC emails
        final_cc_list = []
        if cc_input.strip():
            cc_raw_list = [e.strip() for e in cc_input.split(",") if e.strip()]
            for e in cc_raw_list:
                if validate_email(e):
                    final_cc_list.append(e)
                else:
                    st.error(f"Invalid email in CC: {e}")
                    return

        # Validation
        if not final_to_list:
            st.error("Please provide at least one receiver.")
            return
        if not subject.strip():
            st.error("Subject is required.")
            return
            
        # File Validation
        total_size = 0
        if files:
            for f in files:
                if f.size > MAX_FILE_SIZE:
                    st.error(f"File {f.name} exceeds 10MB limit.")
                    return
                total_size += f.size
            if total_size > MAX_TOTAL_SIZE:
                st.error("Total attachment size exceeds 25MB limit.")
                return

        # Send Email Process
        with st.status("📤 Sending Email...", expanded=True) as status:
            try:
                for msg, val in send_email_via_gmail(final_to_list, final_cc_list, files, subject, body):
                    status.update(label=msg, state="running")
                    st.progress(val)
                
                # Log success
                office_id = office_dict[selected_office_name] if selected_office_name else None
                log_email(
                    office_id=office_id,
                    sender=GMAIL_EMAIL,
                    receivers=", ".join(final_to_list),
                    cc=", ".join(final_cc_list) if final_cc_list else "",
                    subject=subject
                )
                
                st.success("✅ Email sent successfully!")
                st.balloons()
            except Exception as e:
                status.update(label=f"❌ Error: {e}", state="error")
                st.error(f"Failed to send email: {e}")

def page_logs_analytics():
    st.markdown("<h1 class='premium-title'>📊 Logs & Analytics</h1>", unsafe_allow_html=True)
    
    logs_df = get_email_logs()
    if logs_df.empty:
        st.info("No emails have been sent yet.")
        return
        
    logs_df['created_at'] = pd.to_datetime(logs_df['created_at'])
    
    # Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Emails Sent", len(logs_df))
    unique_offices = logs_df['office_name'].nunique(dropna=True)
    c2.metric("Offices Mailed", unique_offices)
    c3.metric("Last Sent", logs_df['created_at'].max().strftime("%Y-%m-%d %H:%M"))
    
    st.divider()
    
    # Filters
    st.subheader("🔍 Filter Logs")
    f_col1, f_col2, f_col3 = st.columns(3)
    
    offices = ["All"] + sorted(logs_df['office_name'].dropna().unique().tolist())
    selected_office = f_col1.selectbox("Filter by Office", offices)
    
    search_subj = f_col2.text_input("Search Subject")
    date_range = f_col3.date_input("Date Range", [])

    filtered_df = logs_df.copy()
    if selected_office != "All":
        filtered_df = filtered_df[filtered_df['office_name'] == selected_office]
    if search_subj.strip():
        filtered_df = filtered_df[filtered_df['subject'].str.contains(search_subj, case=False, na=False)]
    if len(date_range) == 2:
        start_date = pd.Timestamp(date_range[0])
        end_date = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        filtered_df = filtered_df[(filtered_df['created_at'] >= start_date) & (filtered_df['created_at'] <= end_date)]

    # Display Logs
    st.subheader("📋 Sent Emails")
    display_df = filtered_df.copy()
    display_df['created_at'] = display_df['created_at'].dt.strftime("%Y-%m-%d %H:%M:%S")
    st.dataframe(display_df.drop(columns=['id']), use_container_width=True, hide_index=True)
    
    # Download
    csv = display_df.to_csv(index=False)
    st.download_button(
        label="⬇️ Download Logs as CSV",
        data=csv,
        file_name=f"email_logs_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

# ==========================================
# MAIN APP ENTRY POINT
# ==========================================
def main():
    st.set_page_config(page_title="Email Sender App", page_icon="📧", layout="wide", initial_sidebar_state="expanded")
    init_db()
    
    with st.sidebar:
        st.markdown("<h2 class='premium-title' style='font-size: 1.5rem; margin-bottom: 0.5rem;'>📧 Navigation</h2>", unsafe_allow_html=True)
        st.markdown("Select a page below:")
        page = st.radio("Go to", ["Office Management", "Send Email", "Logs & Analytics"])
        
        # Display currently used sender email
        st.markdown(f"""
        <div class="sender-card">
            <div class="sender-label">Active Sender</div>
            <div class="sender-value">{GMAIL_EMAIL if GMAIL_EMAIL else "Not Configured"}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        st.caption(f"App initialized. Local DB: `{DB_NAME}`")
        
    if page == "Office Management":
        page_office_management()
    elif page == "Send Email":
        page_send_email()
    elif page == "Logs & Analytics":
        page_logs_analytics()

if __name__ == "__main__":
    main()
