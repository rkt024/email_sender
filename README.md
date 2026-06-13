# Email Automation Tools

> **Gmail & DOLMA email automation for Nepal land management system**

Streamlit-based email automation tools for sending bulk emails via Gmail and DOLMA (Department of Land Management and Archive) systems. Supports both single-user and multi-user modes with SQLite tracking.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Gmail account with **App Password** (for Gmail sending)
- DOLMA account (for DOLMA email sending)

### Installation

```bash
# Clone the repository
git clone https://github.com/rkt024/email_sender.git
cd email_sender

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials (see Configuration below)

# Run single-user mode
streamlit run single_user/gmail_single_user.py   # Gmail
streamlit run single_user/dolma_single_user.py   # DOLMA

# Run multi-user mode
streamlit run multi_user/gmail_email.py          # Gmail
streamlit run multi_user/dolma_email.py          # DOLMA
```

Default port: **8503** (configured in `.streamlit/config.toml`)

---

## ⚙️ Configuration

Create `.env` from `.env.example`:

```env
# Gmail OAuth / App Password
GMAIL_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password

# DOLMA API
DOLMA_BASE_URL=https://public.dolma.gov.np
DOLMA_USERNAME=your-dolma-username
DOLMA_PASSWORD=your-dolma-password

# Database
TRACKING_DB_PATH=email_tracking.db

# Streamlit (overrides .streamlit/config.toml if needed)
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_HEADLESS=true
```

| Variable | Required | Description |
|----------|----------|-------------|
| `GMAIL_EMAIL` | For Gmail | Your Gmail address |
| `GMAIL_APP_PASSWORD` | For Gmail | **App Password** (not regular password) — [Create one](https://support.google.com/accounts/answer/185833) |
| `DOLMA_BASE_URL` | For DOLMA | Default: `https://public.dolma.gov.np` |
| `DOLMA_USERNAME` | For DOLMA | DOLMA portal username |
| `DOLMA_PASSWORD` | For DOLMA | DOLMA portal password |
| `TRACKING_DB_PATH` | Optional | SQLite path for sent email tracking |

> ⚠️ **Security**: Never commit `.env` — it's in `.gitignore`. Use **App Passwords**, not your main Google password.

---

## 📁 Project Structure

```
email_sender/
├── .env.example              # Environment template
├── .gitignore                # Ignores .env, *.db, __pycache__, venv
├── requirements.txt          # Dependencies
├── .streamlit/
│   └── config.toml           # Server config (port 8503, headless)
├── single_user/
│   ├── gmail_single_user.py  # Gmail single-user sender
│   ├── dolma_single_user.py  # DOLMA single-user sender
│   └── run_*.bat             # Windows launchers (optional)
└── multi_user/
    ├── gmail_email.py        # Gmail multi-user sender
    ├── dolma_email.py        # DOLMA multi-user sender
    └── run_*.bat             # Windows launchers (optional)
```

---

## 🎯 Modes

### Single User
- One sender account per session
- Simple UI: compose, attach, send
- Tracks sent emails in local SQLite

### Multi User
- Multiple sender accounts (loaded from config/CSV)
- Rotation / distribution logic
- Per-account tracking
- Batch sending with progress

---

## 🔧 Gmail Setup (Important)

1. Enable **2-Step Verification** on Google Account
2. Generate **App Password**:  
   `Google Account → Security → 2-Step Verification → App passwords`
3. Use the **16-character App Password** in `GMAIL_APP_PASSWORD`
4. "Less secure apps" NOT needed — App Password bypasses this

---

## 📧 DOLMA Email

Uses DOLMA's internal email API (`public.dolma.gov.np`). Requires valid DOLMA credentials with email permissions.

---

## 🗄️ Tracking Database

Local SQLite (`email_tracking.db` or `app.db` / `email_app.db`) stores:

```sql
CREATE TABLE sent_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient TEXT,
    subject TEXT,
    sent_at TEXT,
    status TEXT,        -- 'sent', 'failed'
    error TEXT,
    sender_account TEXT
);
```

- Auto-created on first run
- Per-mode separate databases (multi_user/app.db, single_user/email_app.db)

---

## 🛠️ Development

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Tests
```bash
# Add tests to test_*.py and run
pytest -v
```

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| `streamlit` | Web UI |
| `requests` | HTTP for DOLMA API |
| `pandas` | CSV/Excel contact lists |
| `python-dotenv` | Environment config |

*(Full list in `requirements.txt`)*

---

## 🔒 Security Notes

- **Never commit `.env`** — contains passwords
- Use **Gmail App Passwords**, not account password
- DOLMA credentials entered at runtime or in `.env` (local only)
- SQLite databases contain sent email logs — treat as sensitive
- `.streamlit/secrets.toml` ignored — use for Streamlit Cloud deployment

---

## 🐛 Common Issues

| Issue | Solution |
|-------|----------|
| "Authentication failed" (Gmail) | Check App Password, 2FA enabled, no typos |
| "Connection refused" (DOLMA) | Verify `DOLMA_BASE_URL`, network access |
| Port 8503 in use | Change `STREAMLIT_SERVER_PORT` in `.env` |
| Emails not sending | Check spam folder, sender reputation, rate limits |

---

## 📜 License

Internal tool for Nepal land management workflows. Not for public distribution.

---

## 👤 Author

**Raju Tamang** — [@rkt024](https://github.com/rkt024)